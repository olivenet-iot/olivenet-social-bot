"""
Pipeline Manager - Agent iş akışını yönetir
Semi-autonomous mod: Her aşamada Telegram onayı bekler
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from enum import Enum

from app.database import save_prompt
from app.validators.text_validator import validate_html_content, fix_common_issues
from app.video_models import get_model_config, get_prompt_key, validate_duration, should_disable_audio, get_max_duration
from telegram.helpers import escape_markdown

# Conversational Reels Constants
BROLL_AUDIO_DELAY = 1.5  # Silence at start of B-roll audio (seconds)
CONV_FREEZE_BUFFER = 0.3  # Buffer after last word for freeze frame


def calculate_freeze_duration(video_duration: float, last_word_end: float) -> float:
    """
    Calculate freeze frame duration based on audio timing.
    Only returns > 0 if audio extends beyond video.

    Args:
        video_duration: Duration of video in seconds
        last_word_end: End time of last spoken word in seconds

    Returns:
        Freeze duration in seconds (0 if not needed)
    """
    audio_end_with_buffer = last_word_end + CONV_FREEZE_BUFFER
    if audio_end_with_buffer > video_duration:
        return audio_end_with_buffer - video_duration
    return 0


async def add_freeze_frame(video_path: str, duration: float) -> str:
    """
    Add freeze frame to end of video using FFmpeg tpad filter.

    Args:
        video_path: Path to input video
        duration: Duration of freeze in seconds

    Returns:
        Path to output video with freeze frame
    """
    import subprocess

    output_path = video_path.replace(".mp4", "_freeze.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"tpad=stop_mode=clone:stop_duration={duration}",
        "-c:a", "copy",
        output_path
    ]

    print(f"[FREEZE FRAME] Adding {duration:.1f}s freeze to video...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Freeze frame failed: {result.stderr}")

    print(f"[FREEZE FRAME] Output: {output_path}")
    return output_path


def _escape_md(value) -> str:
    """Telegram Markdown için güvenli escape - None ve boş değerleri de handle eder"""
    if value is None:
        return "N/A"
    return escape_markdown(str(value))


def extract_shot_structure(speech_script: str, target_duration: int) -> list:
    """
    Speech script'ten shot yapısı çıkar.
    Her 4 saniye = 1 shot, video prompt ile senkronize edilecek.

    Args:
        speech_script: Voiceover metni
        target_duration: Hedef süre (8 veya 12 saniye)

    Returns:
        [{"time": "0-4s", "concept": "...", "keywords": [...]}]
    """
    if not speech_script:
        return []

    words = speech_script.split()
    num_shots = max(1, int(target_duration // 4))  # Her 4s = 1 shot
    words_per_shot = max(1, len(words) // num_shots)

    shots = []
    for i in range(num_shots):
        start_time = i * 4
        end_time = min((i + 1) * 4, target_duration)

        start_idx = i * words_per_shot
        end_idx = min(start_idx + words_per_shot, len(words))
        shot_words = words[start_idx:end_idx]

        # Anahtar kelimeler: 4+ karakter, önemli kelimeler
        keywords = [w.strip('.,!?') for w in shot_words if len(w) > 4][:3]

        shots.append({
            "time": f"{start_time}-{end_time}s",
            "concept": " ".join(shot_words),
            "keywords": keywords
        })

    return shots


class PipelineState(Enum):
    """Pipeline durumları"""
    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_TOPIC_APPROVAL = "awaiting_topic_approval"
    CREATING_CONTENT = "creating_content"
    AWAITING_CONTENT_APPROVAL = "awaiting_content_approval"
    CREATING_VISUAL = "creating_visual"
    AWAITING_VISUAL_APPROVAL = "awaiting_visual_approval"
    REVIEWING = "reviewing"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    ERROR = "error"

class ContentPipeline:
    """İçerik üretim pipeline'ı"""

    def __init__(self, telegram_callback: Optional[Callable] = None):
        self.state = PipelineState.IDLE
        self.current_data = {}
        self.telegram_callback = telegram_callback
        self.approval_event = asyncio.Event()
        self.approval_response = None

        # Agent'ları import et
        from app.agents import (
            OrchestratorAgent,
            PlannerAgent,
            CreatorAgent,
            ReviewerAgent,
            PublisherAgent
        )

        self.orchestrator = OrchestratorAgent()
        self.planner = PlannerAgent()
        self.creator = CreatorAgent()
        self.reviewer = ReviewerAgent()
        self.publisher = PublisherAgent()

    def log(self, message: str):
        """Pipeline log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[PIPELINE {timestamp}] {message}")

    async def notify_telegram(self, message: str, data: Dict = None, buttons: list = None):
        """Telegram'a bildirim gönder"""
        if self.telegram_callback:
            await self.telegram_callback(message, data, buttons)

    async def wait_for_approval(self, timeout: int = 3600) -> Dict[str, Any]:
        """Kullanıcı onayı bekle (default 1 saat)"""
        self.approval_event.clear()
        self.approval_response = None

        try:
            await asyncio.wait_for(self.approval_event.wait(), timeout=timeout)
            return self.approval_response or {"action": "timeout"}
        except asyncio.TimeoutError:
            return {"action": "timeout"}

    def set_approval(self, response: Dict[str, Any]):
        """Onay yanıtını ayarla (Telegram'dan çağrılır)"""
        self.approval_response = response
        self.approval_event.set()

    def _create_avatar_prompt(self, original_prompt: str) -> str:
        """Video prompt'u lipsync için sessiz avatar prompt'una çevir."""
        avatar_prompt = original_prompt

        remove_phrases = [
            "speaking Turkish", "Speaking Turkish",
            "clear lip movements", "Clear lip movements",
            "synchronized with speech", "Turkish dialogue",
            "DIALOGUE FLOW:", "AUDIO:", "talking", "speaking"
        ]

        for phrase in remove_phrases:
            avatar_prompt = avatar_prompt.replace(phrase, "")

        avatar_prompt += """

IMPORTANT: Characters should be SILENT (lip-sync added later).
Show natural gestures and expressions, NO actual speech.
"""
        return avatar_prompt

    @property
    def current_state(self) -> Dict[str, Any]:
        """Audit logging için current_data'dan state çıkar"""
        content = self.current_data.get("content", {})
        topic = self.current_data.get("topic_suggestion", {})
        visual = self.current_data.get("visual_result", {})

        return {
            "post_id": content.get("post_id"),
            "topic": topic.get("topic"),
            "visual_type": visual.get("visual_type", "post")
        }

    async def run_daily_content(self, topic: str = None, manual_topic_mode: bool = False, visual_type: str = None) -> Dict[str, Any]:
        """Günlük içerik pipeline'ı çalıştır — v2 PostPipeline'a delege eder"""
        from app.production.post_pipeline import PostPipeline
        pp = PostPipeline(telegram_callback=self.telegram_callback)
        pp.approval_event = self.approval_event
        pp.approval_response = self.approval_response
        pp.set_approval = self.set_approval
        pp.wait_for_approval = self.wait_for_approval
        return await pp.run(topic=topic, manual_topic_mode=manual_topic_mode, visual_type=visual_type)

    async def _run_daily_content_original(self, topic: str = None, manual_topic_mode: bool = False, visual_type: str = None) -> Dict[str, Any]:
        """Orijinal run_daily_content — yedek olarak tutuluyor"""
        self.log("Günlük içerik pipeline'ı başlatılıyor...")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "final_state": None
        }

        try:
            # ========== AŞAMA 1: Konu Önerisi ==========
            self.log("Aşama 1: Konu önerisi alınıyor...")

            # Manuel konu modunda planner'ı atla
            if manual_topic_mode and topic:
                self.log(f"Manuel konu kullanılıyor: {topic}, görsel: {visual_type or 'nano_banana'}")
                topic_result = {
                    "topic": topic,
                    "category": "manuel",
                    "suggested_visual": visual_type or "nano_banana",
                    "best_time": "10:00",
                    "reasoning": "Manuel olarak belirlenen konu",
                    "suggested_hooks": [f"🔥 {topic}"],
                    "manual": True
                }
            else:
                topic_result = await self.planner.execute({"action": "suggest_topic"})

            if "error" in topic_result:
                raise Exception(f"Planner error: {topic_result['error']}")

            self.current_data["topic_suggestion"] = topic_result
            result["stages_completed"].append("planning")

            # Telegram'a konu önerisini gönder
            self.state = PipelineState.AWAITING_TOPIC_APPROVAL
            await self.notify_telegram(
                message=f"""
📋 *Bugünün Konu Önerisi*

🎯 *Konu:* {_escape_md(topic_result.get('topic', 'N/A'))}
📂 *Kategori:* {_escape_md(topic_result.get('category', 'N/A'))}
🎨 *Görsel:* {_escape_md(topic_result.get('suggested_visual', 'N/A'))}
⏰ *Önerilen Saat:* {_escape_md(topic_result.get('best_time', 'N/A'))}

💡 *Neden bu konu?*
{_escape_md(topic_result.get('reasoning', 'N/A'))}

🪝 *Hook Önerileri:*
{chr(10).join(['• ' + _escape_md(h) for h in topic_result.get('suggested_hooks', [])])}
""",
                data=topic_result,
                buttons=[
                    {"text": "✅ Onayla", "callback": "approve_topic"},
                    {"text": "🔄 Başka Öner", "callback": "new_topic"},
                    {"text": "✏️ Düzenle", "callback": "edit_topic"},
                    {"text": "❌ İptal", "callback": "cancel"}
                ]
            )

            # Onay bekle
            approval = await self.wait_for_approval()

            if approval.get("action") == "cancel":
                self.state = PipelineState.IDLE
                return {"success": False, "reason": "Kullanıcı iptal etti"}

            if approval.get("action") == "new_topic":
                # Yeni konu öner (recursive)
                return await self.run_daily_content()

            if approval.get("action") == "edit_topic":
                # Düzenlenmiş konuyu kullan
                topic_result["topic"] = approval.get("edited_topic", topic_result["topic"])

            # ========== AŞAMA 2: İçerik Üretimi ==========
            self.log("Aşama 2: İçerik üretiliyor...")
            self.state = PipelineState.CREATING_CONTENT

            content_result = await self.creator.execute({
                "action": "create_post",
                "topic": topic_result.get("topic"),
                "category": topic_result.get("category"),
                "suggested_hooks": topic_result.get("suggested_hooks", []),
                "visual_type": topic_result.get("suggested_visual", "flux")
            })

            if "error" in content_result:
                raise Exception(f"Creator error: {content_result['error']}")

            self.current_data["content"] = content_result
            result["stages_completed"].append("content_creation")

            # Telegram'a içeriği gönder
            self.state = PipelineState.AWAITING_CONTENT_APPROVAL
            await self.notify_telegram(
                message=f"""
📝 *Post Metni Hazır*

{_escape_md(content_result.get('post_text', 'N/A'))}

---
📊 *Detaylar:*
- Kelime sayısı: {_escape_md(content_result.get('word_count', 'N/A'))}
- Emoji sayısı: {_escape_md(content_result.get('emoji_count', 'N/A'))}
- Ton: {_escape_md(content_result.get('tone', 'N/A'))}
- Hook: {_escape_md(content_result.get('hook_used', 'N/A'))}
""",
                data=content_result,
                buttons=[
                    {"text": "✅ Onayla", "callback": "approve_content"},
                    {"text": "🔄 Yeniden Yaz", "callback": "regenerate_content"},
                    {"text": "✏️ Düzenle", "callback": "edit_content"},
                    {"text": "❌ İptal", "callback": "cancel"}
                ]
            )

            approval = await self.wait_for_approval()

            if approval.get("action") == "cancel":
                self.state = PipelineState.IDLE
                return {"success": False, "reason": "Kullanıcı iptal etti"}

            if approval.get("action") == "regenerate_content":
                # Revize et
                revision_result = await self.creator.execute({
                    "action": "revise_post",
                    "post_text": content_result.get("post_text"),
                    "feedback": approval.get("feedback", "Daha iyi yaz"),
                    "post_id": content_result.get("post_id")
                })
                content_result["post_text"] = revision_result.get("revised_post", content_result["post_text"])

            if approval.get("action") == "edit_content":
                content_result["post_text"] = approval.get("edited_content", content_result["post_text"])

            # ========== AŞAMA 3: Görsel Üretimi ==========
            self.log("Aşama 3: Görsel prompt oluşturuluyor...")
            self.state = PipelineState.CREATING_VISUAL

            visual_type = topic_result.get("suggested_visual", "flux")

            # nano_banana ve infographic kendi promptlarını oluşturur - visual_prompt agent atla
            if visual_type in ["nano_banana", "infographic"]:
                self.log(f"{visual_type} için visual_prompt agent atlanıyor (kendi promptunu oluşturur)...")
                visual_prompt_result = {
                    "visual_prompt": topic_result.get("topic", ""),
                    "style": visual_type
                }
            else:
                visual_prompt_result = await self.creator.execute({
                    "action": "create_visual_prompt",
                    "post_text": content_result.get("post_text"),
                    "topic": topic_result.get("topic"),
                    "visual_type": visual_type,
                    "post_id": content_result.get("post_id")
                })

                if "error" in visual_prompt_result:
                    raise Exception(f"Visual prompt error: {visual_prompt_result['error']}")

            self.current_data["visual_prompt"] = visual_prompt_result
            result["stages_completed"].append("visual_prompt")

            # Visual prompt'u kaydet
            visual_prompt = visual_prompt_result.get("visual_prompt", "")
            if visual_prompt and content_result.get("post_id"):
                prompt_style = visual_prompt_result.get("style") or visual_type
                save_prompt(
                    post_id=content_result.get("post_id"),
                    prompt_text=visual_prompt,
                    prompt_type='image',
                    style=prompt_style
                )
                self.log(f"Visual prompt kaydedildi (style: {prompt_style})")

            # ========== GÖRSEL + REVIEW ANA DÖNGÜSÜ ==========
            # Final onayda "görsel değiştir" talebi gelirse geri dönmek için
            while True:  # Ana döngü - görsel regenerate from review için

                # ========== GÖRSEL ÜRETİM DÖNGÜSÜ ==========
                while True:
                    self.log(f"Görsel üretiliyor ({visual_type})...")

                    image_path = None
                    video_path = None
                    visual_result = None

                    if visual_type in ["flux", "single"]:
                        from app.flux_helper import generate_image_flux
                        visual_result = await generate_image_flux(
                            prompt=visual_prompt_result.get("visual_prompt"),
                            width=1024,
                            height=1024
                        )
                        if visual_result.get("success"):
                            image_path = visual_result.get("image_path")

                    elif visual_type == "video":
                        from app.veo_helper import generate_video_with_retry
                        visual_result = await generate_video_with_retry(
                            prompt=visual_prompt_result.get("visual_prompt")
                        )
                        if visual_result.get("success"):
                            video_path = visual_result.get("video_path")

                    elif visual_type == "gemini":
                        # Gemini devre dışı - FLUX'a yönlendir
                        self.log("Gemini devre dışı, FLUX kullanılıyor...")
                        from app.flux_helper import generate_image_flux
                        visual_result = await generate_image_flux(
                            prompt=visual_prompt_result.get("visual_prompt"),
                            width=1024,
                            height=1024
                        )
                        if visual_result.get("success"):
                            image_path = visual_result.get("image_path")

                    elif visual_type == "infographic":
                        from app.claude_helper import generate_visual_html
                        from app.renderer import render_html_to_png
                        html = await generate_visual_html(
                            content_result.get("post_text"),
                            topic_result.get("topic")
                        )
                        image_path = await render_html_to_png(html)
                        visual_result = {"success": True, "image_path": image_path}

                    elif visual_type == "nano_banana":
                        # Nano Banana Pro AI Infographic
                        self.log("Nano Banana Pro ile AI infographic üretiliyor...")
                        from app.nano_banana_helper import generate_infographic
                        visual_result = await generate_infographic(
                            topic=topic_result.get("topic"),
                            content_text=content_result.get("post_text"),
                            style="modern",
                            use_search=True
                        )
                        if visual_result.get("success"):
                            image_path = visual_result.get("image_path")
                        else:
                            # Fallback to HTML infographic
                            self.log(f"Nano Banana hatası: {visual_result.get('error')}, HTML'e fallback...")
                            from app.claude_helper import generate_visual_html
                            from app.renderer import render_html_to_png
                            html = await generate_visual_html(
                                content_result.get("post_text"),
                                topic_result.get("topic")
                            )
                            image_path = await render_html_to_png(html)
                            visual_result = {"success": True, "image_path": image_path}

                    elif visual_type == "carousel":
                        # Carousel tipi seçildi - carousel pipeline'a yönlendir
                        self.log("Carousel tipi seçildi, carousel pipeline'a geçiliyor...")
                        await self.notify_telegram(message="📱 Carousel modu için /carousel komutu kullanın.")
                        visual_type = "flux"  # Varsayılana dön
                        continue

                    self.current_data["visual_result"] = {
                        "image_path": image_path,
                        "video_path": video_path,
                        "visual_type": visual_type
                    }

                    # Görsel üretimi başarısız olduysa
                    if not image_path and not video_path:
                        error_msg = visual_result.get("error", "Görsel üretilemedi") if visual_result else "Görsel üretilemedi"
                        self.log(f"Görsel üretim hatası: {error_msg}")
                        await self.notify_telegram(
                            message=f"❌ Görsel üretim hatası: {_escape_md(error_msg)}",
                            buttons=[
                                {"text": "🔄 Tekrar Dene", "callback": "retry_visual"},
                                {"text": "🎨 Tip Değiştir", "callback": "change_visual_type"},
                                {"text": "❌ İptal", "callback": "cancel"}
                            ]
                        )
                        self.state = PipelineState.AWAITING_VISUAL_APPROVAL
                        approval = await self.wait_for_approval()

                        if approval.get("action") == "cancel":
                            self.state = PipelineState.IDLE
                            return {"success": False, "reason": "Görsel üretilemedi"}

                        if approval.get("action") == "regenerate":
                            self.log("Görsel yeniden üretiliyor...")
                            continue

                        if approval.get("action") == "change_type":
                            visual_type = approval.get("new_type", "flux")
                            self.log(f"Görsel tipi değiştirildi: {visual_type}")
                            continue

                        continue  # Varsayılan: tekrar dene

                    if "visual_generation" not in result["stages_completed"]:
                        result["stages_completed"].append("visual_generation")

                    # Telegram'a görseli gönder
                    self.state = PipelineState.AWAITING_VISUAL_APPROVAL
                    await self.notify_telegram(
                        message=f"""
🎨 *Görsel Hazır*

Tip: {visual_type}
Prompt: _{visual_prompt_result.get('visual_prompt', 'N/A')[:200]}..._
""",
                        data={
                            "image_path": image_path,
                            "video_path": video_path,
                            "visual_type": visual_type
                        },
                        buttons=[
                            {"text": "✅ Onayla", "callback": "approve_visual"},
                            {"text": "🔄 Yeniden Üret", "callback": "regenerate_visual"},
                            {"text": "🎨 Tip Değiştir", "callback": "change_visual_type"},
                            {"text": "❌ İptal", "callback": "cancel"}
                        ]
                    )

                    approval = await self.wait_for_approval()

                    if approval.get("action") == "cancel":
                        self.state = PipelineState.IDLE
                        return {"success": False, "reason": "Kullanıcı iptal etti"}

                    if approval.get("action") == "regenerate":
                        await self.notify_telegram(message="🔄 Görsel yeniden üretiliyor...")
                        continue

                    if approval.get("action") == "change_type":
                        visual_type = approval.get("new_type", "flux")
                        await self.notify_telegram(message=f"🎨 Görsel tipi değiştirildi: {visual_type}")
                        continue

                    # approve_visual -> görsel döngüsünden çık
                    break

                # ========== AŞAMA 4-5: Review + Final Onay Döngüsü ==========
                regenerate_visual = False  # Flag for visual regeneration from review

                while True:
                    self.log("Aşama 4: Kalite kontrol...")
                    self.state = PipelineState.REVIEWING

                    review_result = await self.reviewer.execute({
                        "action": "review_post",
                        "post_text": content_result.get("post_text"),
                        "topic": topic_result.get("topic"),
                        "post_id": content_result.get("post_id")
                    })

                    self.current_data["review"] = review_result
                    if "review" not in result["stages_completed"]:
                        result["stages_completed"].append("review")

                    # ========== AŞAMA 5: Final Onay ==========
                    self.state = PipelineState.AWAITING_FINAL_APPROVAL

                    score = review_result.get("total_score", 0)
                    decision = review_result.get("decision") or "revise"  # None-safe

                    await self.notify_telegram(
                        message=f"""
✅ *Final Onay*

📊 *İçerik Review:*
- Karar: {decision.upper()}
- Puan: {score}/10
- Hook: {review_result.get('scores', {}).get('hook_score', 'N/A')}/10
- Değer: {review_result.get('scores', {}).get('value_score', 'N/A')}/10
- Marka: {review_result.get('scores', {}).get('brand_score', 'N/A')}/10

💪 *Güçlü Yönler:*
{chr(10).join(['• ' + s for s in review_result.get('strengths', [])])}

⚠️ *Geri Bildirim:*
{review_result.get('feedback', 'N/A')}

---
*Post şimdi yayınlansın mı?*
""",
                        data=review_result,
                        buttons=[
                            {"text": "🚀 YAYINLA", "callback": "publish_now"},
                            {"text": "⏰ Zamanla", "callback": "schedule"},
                            {"text": "✏️ Metni Revize Et", "callback": "revise"},
                            {"text": "🎨 Görseli Değiştir", "callback": "regenerate_visual"},
                            {"text": "❌ İptal", "callback": "cancel"}
                        ]
                    )

                    approval = await self.wait_for_approval()

                    if approval.get("action") == "cancel":
                        self.state = PipelineState.IDLE
                        return {"success": False, "reason": "Kullanıcı iptal etti"}

                    # Görsel regenerate talebi (revize feedback'ten)
                    if approval.get("action") == "regenerate":
                        await self.notify_telegram(message="🔄 Görsel yeniden üretiliyor...")
                        regenerate_visual = True
                        break  # Review loop'dan çık, dış loop devam edecek

                    # Revize talebi
                    if approval.get("action") == "revise_content":
                        await self.notify_telegram(message="✏️ İçerik revize ediliyor...")

                        revision_result = await self.creator.execute({
                            "action": "revise_post",
                            "post_text": content_result.get("post_text"),
                            "feedback": approval.get("feedback", "İyileştir"),
                            "post_id": content_result.get("post_id")
                        })
                        content_result["post_text"] = revision_result.get("revised_post", content_result["post_text"])
                        self.log("İçerik revize edildi, tekrar review yapılıyor...")
                        continue  # Tekrar review yap

                    # publish_now veya schedule → döngüden çık
                    break

                # Görsel regenerate talep edildiyse dış loop'a dön
                if regenerate_visual:
                    self.log("Görsel regenerate talebi, görsel döngüsüne dönülüyor...")
                    continue  # Dış while True loop'una dön
                else:
                    # publish_now veya schedule - dış loop'tan çık
                    break

            # ========== AŞAMA 6: Yayınla ==========
            if approval.get("action") in ["publish_now", "schedule"]:
                self.log("Aşama 6: Yayınlanıyor...")
                self.state = PipelineState.PUBLISHING

                publish_result = await self.publisher.execute({
                    "action": "publish",
                    "post_id": content_result.get("post_id"),
                    "post_text": content_result.get("post_text"),
                    "image_path": image_path,
                    "video_path": video_path,
                    "platform": "instagram"
                })

                if publish_result.get("success"):
                    result["stages_completed"].append("published")
                    result["success"] = True

                    await self.notify_telegram(
                        message=f"""
🎉 *YAYINLANDI!*

✅ Post başarıyla Instagram'a gönderildi.

📊 Post ID: {publish_result.get('instagram_post_id', 'N/A')}
""",
                        data=publish_result,
                        buttons=[]
                    )
                else:
                    raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *Pipeline Hatası*\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def run_autonomous_content(self, min_score: int = 7) -> Dict[str, Any]:
        """
        Tam otonom içerik pipeline'ı - Telegram onayı beklemez

        Args:
            min_score: Minimum kabul edilebilir review puanı (default: 7/10)
                       Bu puanın altındaki içerikler yayınlanmaz

        Returns:
            Pipeline sonucu
        """
        self.log("OTONOM MOD: İçerik pipeline'ı başlatılıyor...")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "final_state": None,
            "autonomous": True
        }

        try:
            # ========== AŞAMA 1: Konu Önerisi ==========
            self.log("[OTONOM] Aşama 1: Konu seçiliyor...")

            topic_result = await self.planner.execute({"action": "suggest_topic"})

            if "error" in topic_result:
                raise Exception(f"Planner error: {topic_result['error']}")

            self.current_data["topic_suggestion"] = topic_result
            result["stages_completed"].append("planning")
            result["topic"] = topic_result.get("topic")

            self.log(f"[OTONOM] Konu: {topic_result.get('topic')}")

            # Telegram'a bilgi gönder (sadece bilgi, onay beklenmez)
            await self.notify_telegram(
                message=f"🤖 *OTONOM MOD* - Konu Secildi\n\nKonu: {escape_markdown(topic_result.get('topic', 'N/A'))}\nKategori: {escape_markdown(topic_result.get('category', 'N/A'))}",
                data=topic_result,
                buttons=[]
            )

            # ========== AŞAMA 2: İçerik Üretimi ==========
            self.log("[OTONOM] Aşama 2: İçerik üretiliyor...")
            self.state = PipelineState.CREATING_CONTENT

            content_result = await self.creator.execute({
                "action": "create_post_multiplatform",
                "topic": topic_result.get("topic"),
                "category": topic_result.get("category"),
                "suggested_hooks": topic_result.get("suggested_hooks", []),
                "visual_type": topic_result.get("suggested_visual", "flux")
            })

            if "error" in content_result:
                raise Exception(f"Creator error: {content_result['error']}")

            self.current_data["content"] = content_result
            result["stages_completed"].append("content_creation")

            self.log(f"[OTONOM] İçerik üretildi ({content_result.get('ig_word_count', 0)} kelime)")

            # ========== AŞAMA 3: Görsel Üretimi ==========
            self.log("[OTONOM] Aşama 3: Görsel üretiliyor...")
            self.state = PipelineState.CREATING_VISUAL

            visual_type = topic_result.get("suggested_visual", "flux")

            visual_prompt_result = await self.creator.execute({
                "action": "create_visual_prompt",
                "post_text": content_result.get("post_text"),
                "topic": topic_result.get("topic"),
                "visual_type": visual_type,
                "post_id": content_result.get("post_id")
            })

            if "error" in visual_prompt_result:
                raise Exception(f"Visual prompt error: {visual_prompt_result['error']}")

            self.current_data["visual_prompt"] = visual_prompt_result
            result["stages_completed"].append("visual_prompt")

            # Visual prompt'u kaydet
            visual_prompt = visual_prompt_result.get("visual_prompt", "")
            if visual_prompt and content_result.get("post_id"):
                prompt_style = visual_prompt_result.get("style") or visual_type
                save_prompt(
                    post_id=content_result.get("post_id"),
                    prompt_text=visual_prompt,
                    prompt_type='image',
                    style=prompt_style
                )
                self.log(f"[OTONOM] Visual prompt kaydedildi (style: {prompt_style})")

            # Görsel üret
            self.log(f"[OTONOM] Görsel üretiliyor ({visual_type})...")

            image_path = None
            video_path = None

            if visual_type in ["flux", "single"]:
                from app.flux_helper import generate_image_flux
                visual_result = await generate_image_flux(
                    prompt=visual_prompt_result.get("visual_prompt"),
                    width=1024,
                    height=1024
                )
                if visual_result.get("success"):
                    image_path = visual_result.get("image_path")

            elif visual_type == "video":
                from app.veo_helper import generate_video_with_retry
                visual_result = await generate_video_with_retry(
                    prompt=visual_prompt_result.get("visual_prompt")
                )
                if visual_result.get("success"):
                    video_path = visual_result.get("video_path")

            elif visual_type == "gemini":
                # Gemini devre dışı - FLUX kullan
                self.log("[OTONOM] Gemini devre dışı, FLUX kullanılıyor...")
                from app.flux_helper import generate_image_flux
                visual_result = await generate_image_flux(
                    prompt=visual_prompt_result.get("visual_prompt"),
                    width=1024,
                    height=1024
                )
                if visual_result.get("success"):
                    image_path = visual_result.get("image_path")

            elif visual_type == "infographic":
                from app.claude_helper import generate_visual_html
                from app.renderer import render_html_to_png
                html = await generate_visual_html(
                    content_result.get("post_text"),
                    topic_result.get("topic")
                )
                image_path = await render_html_to_png(html)
                visual_result = {"success": True, "image_path": image_path}

            self.current_data["visual_result"] = {
                "image_path": image_path,
                "video_path": video_path,
                "visual_type": visual_type
            }

            # Görsel başarısız olduysa hata ver
            if not image_path and not video_path:
                error_msg = visual_result.get("error", "Görsel üretilemedi") if visual_result else "Görsel üretilemedi"
                raise Exception(f"Visual generation failed: {error_msg}")

            result["stages_completed"].append("visual_generation")
            self.log(f"[OTONOM] Görsel üretildi: {image_path or video_path}")

            # ========== AŞAMA 4: Kalite Kontrol (Retry ile) ==========
            self.log("[OTONOM] Aşama 4: Kalite kontrol...")
            self.state = PipelineState.REVIEWING

            MAX_REVIEW_RETRIES = 2
            current_post_text = content_result.get("post_text")

            for review_attempt in range(MAX_REVIEW_RETRIES):
                review_result = await self.reviewer.execute({
                    "action": "review_post",
                    "post_text": current_post_text,
                    "topic": topic_result.get("topic"),
                    "post_id": content_result.get("post_id")
                })

                self.current_data["review"] = review_result
                score = review_result.get("total_score", 0)
                decision = review_result.get("decision") or "revise"
                result["review_score"] = score

                self.log(f"[OTONOM] Review ({review_attempt + 1}/{MAX_REVIEW_RETRIES}): {score}/10 - {decision}")

                if score >= min_score:
                    break  # Başarılı, döngüden çık

                # Retry gerekli - feedback ile revize et
                if review_attempt < MAX_REVIEW_RETRIES - 1:
                    feedback = review_result.get("feedback", "İçeriği iyileştir")
                    self.log(f"[OTONOM] Düşük puan, feedback ile revize ediliyor...")

                    revision_result = await self.creator.execute({
                        "action": "revise_post",
                        "post_text": current_post_text,
                        "feedback": feedback,
                        "post_id": content_result.get("post_id")
                    })

                    if revision_result.get("revised_post"):
                        current_post_text = revision_result.get("revised_post")
                        content_result["post_text"] = current_post_text
                        self.log(f"[OTONOM] İçerik revize edildi, tekrar review yapılıyor...")
                    else:
                        self.log(f"[OTONOM] Revizyon başarısız, eski içerikle devam...")

            result["stages_completed"].append("review")

            # Tüm denemeler sonrası puan kontrolü
            if score < min_score:
                self.log(f"[OTONOM] {MAX_REVIEW_RETRIES} denemede de puan yetersiz ({score} < {min_score})")
                await self.notify_telegram(
                    message=f"⚠️ *OTONOM MOD* - Icerik Reddedildi\n\nPuan: {score}/10 (min: {min_score})\nKonu: {escape_markdown(topic_result.get('topic') or '')}\nDeneme: {MAX_REVIEW_RETRIES}\n\nIcerik kalite standardini karsilamiyor.",
                    data=review_result,
                    buttons=[]
                )
                self.state = PipelineState.IDLE
                result["reason"] = f"Review puanı yetersiz: {score}/{min_score} ({MAX_REVIEW_RETRIES} deneme)"
                return result

            # ========== AŞAMA 5: Yayınla ==========
            self.log("[OTONOM] Aşama 5: Yayınlanıyor...")
            self.state = PipelineState.PUBLISHING

            publish_result = await self.publisher.execute({
                "action": "publish",
                "post_id": content_result.get("post_id"),
                "post_text": content_result.get("post_text"),
                "post_text_ig": content_result.get("post_text_ig"),
                "image_path": image_path,
                "video_path": video_path,
                "platform": "instagram"
            })

            if publish_result.get("success"):
                result["stages_completed"].append("published")
                result["success"] = True
                result["instagram_post_id"] = publish_result.get("instagram_post_id")

                self.log(f"[OTONOM] Başarıyla yayınlandı! IG: {publish_result.get('instagram_post_id')}")

                await self.notify_telegram(
                    message=f"🎉 *OTONOM MOD* - Yayinlandi!\n\nKonu: {escape_markdown(topic_result.get('topic') or '')}\nPuan: {score}/10\nIG Post: {publish_result.get('instagram_post_id', 'N/A')}",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("[OTONOM] Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"[OTONOM] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *OTONOM MOD* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def run_autonomous_content_with_plan(self, plan: dict) -> Dict[str, Any]:
        """Plana göre otonom içerik üret ve paylaş - Engagement stratejileriyle"""
        topic = plan.get('topic_suggestion') or 'Genel IoT konusu'
        self.log(f"Planlı içerik üretiliyor: {topic[:50]}...")

        result = {
            "success": False,
            "stages_completed": [],
            "post_id": None
        }

        try:
            category = plan.get('topic_category') or 'egitici'
            visual_type = plan.get('visual_type_suggestion') or 'flux'

            # Engagement strategy fields from calendar
            viral_format = plan.get('viral_format')
            hook_type = plan.get('hook_type')
            comment_cta_type = plan.get('comment_cta_type')
            save_trigger_type = plan.get('save_trigger_type')
            visual_style = plan.get('visual_style', 'cinematic_4k')

            # ========== CONTENT TYPE ROUTING ==========
            # Reels/video içerik için özel pipeline kullan
            if visual_type in ["reels", "video"]:
                self.log(f"[ROUTING] Reels pipeline'a yönlendiriliyor: {topic[:50]}...")
                if viral_format or hook_type:
                    self.log(f"[ENGAGEMENT] Format: {viral_format}, Hook: {hook_type}")
                return await self.run_reels_content(
                    topic=topic,
                    visual_style=visual_style,
                    viral_format=viral_format,
                    hook_type=hook_type
                )

            # Carousel içerik için özel pipeline kullan
            if visual_type == "carousel":
                self.log(f"[ROUTING] Carousel pipeline'a yönlendiriliyor: {topic[:50]}...")
                return await self.run_carousel_pipeline(topic=topic)

            # ========== STANDART POST FLOW ==========
            # 1. İçerik üret (multiplatform)
            self.log("Aşama 1: İçerik üretiliyor...")
            content_result = await self.creator.execute({
                "action": "create_post_multiplatform",
                "topic": topic,
                "category": category,
                "suggested_hooks": [],
                "visual_type": visual_type
            })

            if "error" in content_result:
                raise Exception(f"Creator error: {content_result['error']}")

            result["stages_completed"].append("content")
            result["post_id"] = content_result.get("post_id")
            self.log(f"İçerik: {content_result.get('ig_word_count', 0)} kelime")

            # 2. Görsel prompt
            self.log("Aşama 2: Görsel prompt oluşturuluyor...")
            visual_prompt_result = await self.creator.execute({
                "action": "create_visual_prompt",
                "post_text": content_result.get("post_text"),
                "topic": topic,
                "visual_type": visual_type,
                "post_id": content_result.get("post_id")
            })

            if "error" in visual_prompt_result:
                raise Exception(f"Visual prompt error: {visual_prompt_result['error']}")

            result["stages_completed"].append("visual_prompt")

            # 3. Görsel üret
            self.log(f"Aşama 3: Görsel üretiliyor ({visual_type})...")
            image_path = None
            video_path = None

            if visual_type in ["flux", "single"]:
                from app.flux_helper import generate_image_flux
                visual_result = await generate_image_flux(
                    prompt=visual_prompt_result.get("visual_prompt"),
                    width=1024, height=1024
                )
                if visual_result.get("success"):
                    image_path = visual_result.get("image_path")

            elif visual_type == "infographic":
                from app.claude_helper import generate_visual_html
                from app.renderer import render_html_to_png
                html = await generate_visual_html(content_result.get("post_text"), topic)
                image_path = await render_html_to_png(html)

            elif visual_type == "video":
                from app.veo_helper import generate_video_with_retry
                visual_result = await generate_video_with_retry(
                    prompt=visual_prompt_result.get("visual_prompt")
                )
                if visual_result.get("success"):
                    video_path = visual_result.get("video_path")

            if not image_path and not video_path:
                raise Exception("Görsel üretilemedi")

            result["stages_completed"].append("visual")

            # 4. Review
            self.log("Aşama 4: Kalite kontrol...")
            review_result = await self.reviewer.execute({
                "action": "review_post",
                "post_text": content_result.get("post_text"),
                "topic": topic,
                "post_id": content_result.get("post_id")
            })

            score = review_result.get("total_score", 0)
            self.log(f"Review puanı: {score}/10")

            if score < 7:
                self.log(f"Puan düşük ({score}), revizyon yapılıyor...")
                revision_result = await self.creator.execute({
                    "action": "revise_post",
                    "post_text": content_result.get("post_text"),
                    "feedback": review_result.get("feedback", "Daha etkili yaz"),
                    "post_id": content_result.get("post_id")
                })
                content_result["post_text"] = revision_result.get("revised_post", content_result["post_text"])

            result["stages_completed"].append("review")

            # 5. Yayınla
            self.log("Aşama 5: Yayınlanıyor...")
            publish_result = await self.publisher.execute({
                "action": "publish",
                "post_id": content_result.get("post_id"),
                "post_text": content_result.get("post_text"),
                "post_text_ig": content_result.get("post_text_ig"),
                "image_path": image_path,
                "video_path": video_path,
                "platform": "instagram"
            })

            if publish_result.get("success"):
                result["stages_completed"].append("published")
                result["success"] = True

                await self.notify_telegram(
                    message=f"✅ Planlı İçerik Yayınlandı!\n\n"
                    f"📝 Konu: {_escape_md(topic[:50])}...\n"
                    f"🎨 Görsel: {_escape_md(visual_type)}\n"
                    f"📱 Platform: Instagram\n"
                    f"⭐ Puan: {score}/10",
                    data={},
                    buttons=[]
                )

                self.log("✅ Planlı içerik başarıyla paylaşıldı!")
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            return result

        except Exception as e:
            self.log(f"❌ Planlı içerik hatası: {str(e)}")
            result["error"] = str(e)
            return result

    async def run_reels_content(self, topic: str = None, force_model: str = None, manual_topic_mode: bool = False, visual_style: str = "cinematic_4k", viral_format: str = None, hook_type: str = None) -> Dict[str, Any]:
        """Instagram Reels — v2 ReelsPipeline'a delege eder"""
        from app.production.reels_pipeline import ReelsPipeline
        rp = ReelsPipeline(telegram_callback=self.telegram_callback)
        rp.approval_event = self.approval_event
        rp.approval_response = self.approval_response
        rp.set_approval = self.set_approval
        rp.wait_for_approval = self.wait_for_approval
        return await rp.run(topic=topic, force_model=force_model, manual_topic_mode=manual_topic_mode,
                            visual_style=visual_style, viral_format=viral_format, hook_type=hook_type)

    async def _run_reels_content_original(self, topic: str = None, force_model: str = None, manual_topic_mode: bool = False, visual_style: str = "cinematic_4k", viral_format: str = None, hook_type: str = None) -> Dict[str, Any]:
        """Orijinal run_reels_content — yedek"""
        mode_text = "Manuel Konu" if manual_topic_mode else "Otomatik"
        engagement_info = f" [Format: {viral_format}, Hook: {hook_type}]" if viral_format or hook_type else ""
        self.log(f"REELS MOD ({mode_text}): Pipeline başlatılıyor...{engagement_info}")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "final_state": None,
            "reels": True
        }

        try:
            # ========== AŞAMA 1: Konu Seçimi ==========
            if topic:
                topic_data = {
                    "topic": topic,
                    "category": "tanitim",
                    "suggested_visual": "video"
                }
                self.log(f"[REELS] Konu verildi: {topic[:50]}...")
            else:
                self.log("[REELS] Aşama 1: Konu seçiliyor...")
                topic_result = await self.planner.execute({"action": "suggest_topic"})

                if "error" in topic_result:
                    raise Exception(f"Planner error: {topic_result['error']}")

                topic_data = topic_result
                topic = topic_data.get("topic", "IoT ve akıllı tarım")
                self.log(f"[REELS] Konu: {topic}")

            self.current_data["topic"] = topic_data
            result["stages_completed"].append("topic_selection")
            result["topic"] = topic

            await self.notify_telegram(
                message=f"🎬 *REELS MOD* - Başlatıldı\n\nKonu: {escape_markdown(topic[:80])}...",
                data=topic_data,
                buttons=[]
            )

            # ========== AŞAMA 2: Caption Üretimi ==========
            self.log("[REELS] Aşama 2: Caption üretiliyor...")
            self.state = PipelineState.CREATING_CONTENT

            content_result = await self.creator.execute({
                "action": "create_post_multiplatform",
                "topic": topic,
                "category": topic_data.get("category", "tanitim"),
                "visual_type": "video"
            })

            if "error" in content_result:
                raise Exception(f"Creator error: {content_result['error']}")

            self.current_data["content"] = content_result
            result["stages_completed"].append("caption")
            result["post_id"] = content_result.get("post_id")

            self.log(f"[REELS] Caption: IG {content_result.get('ig_word_count', 0)} kelime")

            # ========== AŞAMA 3: Video Prompt Üretimi ==========
            self.log("[REELS] Aşama 3: Video prompt oluşturuluyor...")
            self.state = PipelineState.CREATING_VISUAL

            reels_prompt_result = await self.creator.execute({
                "action": "create_reels_prompt",
                "topic": topic,
                "category": topic_data.get("category", "tanitim"),
                "post_text": content_result.get("post_text_ig", ""),
                "post_id": content_result.get("post_id"),
                "visual_style": visual_style,
                "viral_format": viral_format,
                "hook_type": hook_type
            })

            if not reels_prompt_result.get("success"):
                raise Exception(f"Reels prompt error: {reels_prompt_result.get('error', 'Unknown')}")

            self.current_data["reels_prompt"] = reels_prompt_result
            result["stages_completed"].append("video_prompt")

            # Model'e göre doğru prompt'u seç
            def get_video_prompt_for_model(prompt_result: dict, model: str) -> str:
                """Model'e göre optimize edilmiş prompt seç"""
                if model and model.startswith("kling"):
                    if model == "kling_v3_pro":
                        return prompt_result.get("video_prompt_kling3") or prompt_result.get("video_prompt_kling", "")
                    return prompt_result.get("video_prompt_kling") or prompt_result.get("video_prompt_sora", "")
                elif model and (model == "veo3" or model.startswith("veo")):
                    return prompt_result.get("video_prompt_veo") or prompt_result.get("video_prompt_sora", "")
                else:  # Sora veya default
                    return prompt_result.get("video_prompt_sora") or prompt_result.get("video_prompt_veo", "")

            recommended_model = reels_prompt_result.get("recommended_model", "veo3")
            # force_model varsa onu kullan, yoksa recommended_model
            model_to_use = force_model or recommended_model
            video_prompt = get_video_prompt_for_model(reels_prompt_result, model_to_use)
            complexity = reels_prompt_result.get("complexity", "medium")

            # Video prompt'u kaydet
            if video_prompt and content_result.get("post_id"):
                prompt_style = reels_prompt_result.get("camera_movement") or complexity
                save_prompt(
                    post_id=content_result.get("post_id"),
                    prompt_text=video_prompt,
                    prompt_type='video',
                    style=prompt_style
                )
                self.log(f"[REELS] Prompt kaydedildi (style: {prompt_style})")

            self.log(f"[REELS] Prompt hazır")
            self.log(f"[REELS]   Complexity: {complexity}")
            self.log(f"[REELS]   Önerilen model: {recommended_model}")

            # ========== AŞAMA 4: Video Üretimi ==========
            model_duration = get_max_duration(model_to_use) if model_to_use else 8
            self.log(f"[REELS] Aşama 4: Video üretiliyor ({model_duration}s, {model_to_use})...")

            from app.sora_helper import generate_video_smart

            # model_to_use zaten yukarıda tanımlandı (prompt seçimi için)
            video_result = await generate_video_smart(
                prompt=video_prompt,
                topic=topic,
                force_model=model_to_use,
                duration=model_duration
            )

            if not video_result.get("success"):
                raise Exception(f"Video generation failed: {video_result.get('error', 'Unknown')}")

            video_path = video_result.get("video_path")
            model_used = video_result.get("model_used", "unknown")
            fallback_from = video_result.get("fallback_from")

            self.current_data["video_result"] = video_result
            result["stages_completed"].append("video_generation")
            result["model_used"] = model_used

            if fallback_from:
                self.log(f"[REELS] Video üretildi (fallback: {fallback_from} → {model_used})")
            else:
                self.log(f"[REELS] Video üretildi ({model_used})")

            await self.notify_telegram(
                message=f"🎥 *REELS* - Video Hazır\n\nModel: {model_used}\nComplexity: {complexity}",
                data={"video_path": video_path},
                buttons=[]
            )

            # ========== AŞAMA 5: Kalite Kontrol ==========
            self.log("[REELS] Aşama 5: Kalite kontrol...")
            self.state = PipelineState.REVIEWING

            # Caption için review
            review_result = await self.reviewer.execute({
                "action": "review_post",
                "post_text": content_result.get("post_text_ig", ""),
                "topic": topic,
                "post_id": content_result.get("post_id")
            })

            score = review_result.get("total_score", 0)
            result["review_score"] = score
            result["stages_completed"].append("review")

            self.log(f"[REELS] Review: {score}/10")

            # Düşük puan ise revizyon
            if score < 7:
                self.log("[REELS] Puan düşük, caption revize ediliyor...")
                revision_result = await self.creator.execute({
                    "action": "revise_post",
                    "post_text": content_result.get("post_text_ig", ""),
                    "feedback": review_result.get("feedback", "Daha kısa ve etkili yaz"),
                    "post_id": content_result.get("post_id")
                })
                content_result["post_text_ig"] = revision_result.get("revised_post", content_result.get("post_text_ig"))

            # ========== AŞAMA 6: Yayınla ==========
            self.log("[REELS] Aşama 6: Yayınlanıyor...")
            self.state = PipelineState.PUBLISHING

            publish_result = await self.publisher.execute({
                "action": "publish",
                "post_id": content_result.get("post_id"),
                "post_text": content_result.get("post_text_ig", ""),
                "post_text_ig": content_result.get("post_text_ig", ""),
                "video_path": video_path,
                "platform": "instagram"
            })

            if publish_result.get("success"):
                result["stages_completed"].append("published")
                result["success"] = True
                result["instagram_post_id"] = publish_result.get("instagram_post_id")

                self.log(f"[REELS] Başarıyla yayınlandı! Instagram Reels")

                await self.notify_telegram(
                    message=f"🎉 *REELS* - Yayınlandı!\n\n"
                    f"📝 Konu: {_escape_md(topic[:50])}...\n"
                    f"🎥 Model: {_escape_md(model_used)}\n"
                    f"📱 Platform: Instagram Reels\n"
                    f"⭐ Puan: {score}/10",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("[REELS] Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"[REELS] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *REELS* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def run_reels_voice_content(
        self,
        topic: str = None,
        force_model: str = None,
        target_duration: int = 15,
        manual_topic_mode: bool = False,
        model_id: str = "sora-2",
        visual_style: str = "cinematic_4k"
    ) -> Dict[str, Any]:
        """Sesli Reels — v2 VoiceReelsPipeline'a delege eder"""
        from app.production.voice_reels_pipeline import VoiceReelsPipeline
        vp = VoiceReelsPipeline(telegram_callback=self.telegram_callback)
        vp.approval_event = self.approval_event
        vp.approval_response = self.approval_response
        vp.set_approval = self.set_approval
        vp.wait_for_approval = self.wait_for_approval
        return await vp.run(topic=topic, force_model=force_model, target_duration=target_duration,
                            manual_topic_mode=manual_topic_mode, model_id=model_id, visual_style=visual_style)

    async def _run_reels_voice_content_original(
        self,
        topic: str = None,
        force_model: str = None,
        target_duration: int = 15,
        manual_topic_mode: bool = False,
        model_id: str = "sora-2",
        visual_style: str = "cinematic_4k"
    ) -> Dict[str, Any]:
        """
        Orijinal sesli reels — yedek.

        OpenAI TTS + Video + FFmpeg merge pipeline.
        Multi-model desteği: Sora 2, Veo 2, Kling 2.1, Wan 2.1, Minimax

        Pipeline Akışı:
        1. Konu seçimi (Planner) veya manuel konu işleme (Creator)
        2. Caption üretimi (Creator)
        3. Speech script üretimi (Creator)
        4. TTS ses üretimi (OpenAI TTS)
        5. Video prompt üretimi (Creator)
        6. Video üretimi (model_id'ye göre)
        7. Audio-video birleştirme (FFmpeg)
        8. Kalite kontrol (Reviewer)
        9. Instagram Reels yayını (Publisher)

        Args:
            topic: Konu (None ise Planner'dan alınır)
            force_model: Video modeli zorla (backward compat, deprecated)
            target_duration: Hedef süre (modele göre max sınır uygulanır)
            manual_topic_mode: True ise topic Creator ile profesyonelleştirilir
            model_id: Video model ID (sora-2, sora-2-pro, veo-3.1, kling-3.0-pro)
            visual_style: Görsel stil (cinematic_4k, anime, vb.)

        Returns:
            Pipeline sonucu
        """
        # Model konfigürasyonunu al
        model_config = get_model_config(model_id)
        model_name = model_config.get("name", model_id)

        self.log(f"🎙️ SESLİ REELS MOD: Pipeline başlatılıyor... (Model: {model_name})")
        self.state = PipelineState.PLANNING

        # Model'in max süresine göre duration'ı sınırla
        max_duration = model_config.get("max_duration", 12)
        target_duration = min(target_duration, max_duration)
        target_duration = validate_duration(model_id, target_duration)

        result = {
            "success": False,
            "stages_completed": [],
            "final_state": None,
            "reels": True,
            "voice_enabled": True,
            "target_duration": target_duration,
            "model_id": model_id,
            "model_name": model_name
        }

        try:
            # ========== AŞAMA 1: Konu Seçimi ==========
            if topic and manual_topic_mode:
                # Manuel topic: Creator ile profesyonelleştir
                self.log(f"[VOICE REELS] Manuel konu işleniyor: {topic[:50]}...")

                topic_result = await self.creator.execute({
                    "action": "process_manual_topic",
                    "user_input": topic
                })

                processed_topic = topic_result.get("processed_topic", topic)
                topic_data = {
                    "topic": processed_topic,
                    "category": topic_result.get("category", "tanitim"),
                    "suggested_visual": "video",
                    "hook_suggestion": topic_result.get("hook_suggestion", ""),
                    "key_points": topic_result.get("key_points", []),
                    "original_input": topic
                }
                topic = processed_topic
                self.log(f"[VOICE REELS] İşlenmiş konu: {topic[:50]}...")

            elif topic:
                topic_data = {
                    "topic": topic,
                    "category": "tanitim",
                    "suggested_visual": "video"
                }
                self.log(f"[VOICE REELS] Konu verildi: {topic[:50]}...")
            else:
                self.log("[VOICE REELS] Aşama 1: Konu seçiliyor...")
                topic_result = await self.planner.execute({"action": "suggest_topic"})

                if "error" in topic_result:
                    raise Exception(f"Planner error: {topic_result['error']}")

                topic_data = topic_result
                topic = topic_data.get("topic", "IoT ve akıllı tarım")
                self.log(f"[VOICE REELS] Konu: {topic}")

            self.current_data["topic"] = topic_data
            result["stages_completed"].append("topic_selection")
            result["topic"] = topic

            await self.notify_telegram(
                message=f"🎙️ *SESLİ REELS* - Başlatıldı\n\n"
                f"📝 Konu: {_escape_md(topic[:80])}...\n"
                f"⏱️ Hedef: {target_duration}s",
                data=topic_data,
                buttons=[]
            )

            # ========== AŞAMA 2: Caption Üretimi ==========
            self.log("[VOICE REELS] Aşama 2: Caption üretiliyor...")
            self.state = PipelineState.CREATING_CONTENT

            content_result = await self.creator.execute({
                "action": "create_post_multiplatform",
                "topic": topic,
                "category": topic_data.get("category", "tanitim"),
                "visual_type": "video"
            })

            if "error" in content_result:
                raise Exception(f"Creator error: {content_result['error']}")

            self.current_data["content"] = content_result
            result["stages_completed"].append("caption")
            result["post_id"] = content_result.get("post_id")

            self.log(f"[VOICE REELS] Caption: IG {content_result.get('ig_word_count', 0)} kelime")

            # ========== AŞAMA 3: Speech Script Üretimi ========== [YENİ]
            self.log("[VOICE REELS] Aşama 3: Voiceover scripti oluşturuluyor...")

            speech_result = await self.creator.execute({
                "action": "create_speech_script",
                "topic": topic,
                "target_duration": target_duration,
                "tone": "friendly",  # Samimi ton
                "post_id": content_result.get("post_id")
            })

            if not speech_result.get("success"):
                raise Exception(f"Speech script error: {speech_result.get('error', 'Unknown')}")

            speech_script = speech_result.get("speech_script", "")
            self.current_data["speech"] = speech_result
            result["stages_completed"].append("speech_script")

            self.log(f"[VOICE REELS] Script hazır: {speech_result.get('word_count')} kelime, ~{speech_result.get('estimated_duration'):.1f}s")

            # ========== AŞAMA 4: TTS ile Ses Üretimi ========== [YENİ]
            self.log("[VOICE REELS] Aşama 4: TTS ile ses üretiliyor...")

            audio_path = None
            audio_duration = 0
            voice_fallback = False

            try:
                from app.openai_tts_helper import generate_speech_with_retry, OpenAITTSError, QuotaExceededError

                tts_result = await generate_speech_with_retry(
                    text=speech_script,
                    max_retries=3
                )

                if tts_result.get("success"):
                    audio_path = tts_result.get("audio_path")
                    estimated_duration = tts_result.get("duration_seconds", 0)

                    # GERÇEK audio süresini ffprobe ile ölç (tahmini değil!)
                    from app.instagram_helper import get_audio_duration
                    actual_audio_duration = await get_audio_duration(audio_path)
                    self.log(f"[VOICE REELS] TTS süre karşılaştırma - Tahmini: {estimated_duration:.1f}s, Gerçek: {actual_audio_duration:.1f}s")

                    # Gerçek süreyi kullan (tahmini değil)
                    audio_duration = actual_audio_duration if actual_audio_duration > 0 else estimated_duration

                    # Audio süresini target_duration ile sınırla (Sora max 12s)
                    if audio_duration > target_duration:
                        self.log(f"[VOICE REELS] Ses çok uzun ({audio_duration:.1f}s), {target_duration}s'ye kırpılacak")
                        audio_duration = target_duration  # merge_audio_video -t ile kırpacak

                    result["stages_completed"].append("tts_generation")
                    result["actual_audio_duration"] = actual_audio_duration  # Gerçek süreyi kaydet
                    self.log(f"[VOICE REELS] Ses hazır: {audio_duration:.1f}s (gerçek: {actual_audio_duration:.1f}s)")
                else:
                    error = tts_result.get("error", "Unknown TTS error")
                    self.log(f"[VOICE REELS] TTS hatası: {error}")

                    if tts_result.get("quota_exceeded"):
                        await self.notify_telegram(
                            message=f"⚠️ *TTS Kota Aşıldı*\n\nSessiz video ile devam ediliyor...",
                            data={},
                            buttons=[]
                        )

                    voice_fallback = True

            except Exception as e:
                self.log(f"[VOICE REELS] TTS exception: {e}")
                voice_fallback = True

            if voice_fallback:
                self.log("[VOICE REELS] Sessiz video moduna geçiliyor...")
                result["voice_fallback"] = True

            # ========== AŞAMA 5: Video Prompt Üretimi ==========
            self.log("[VOICE REELS] Aşama 5: Video prompt oluşturuluyor...")
            self.state = PipelineState.CREATING_VISUAL

            # Speech-Video senkronizasyonu için shot yapısı çıkar
            speech_structure = extract_shot_structure(speech_script, target_duration)
            self.log(f"[VOICE REELS] Shot yapısı: {len(speech_structure)} shot")

            self.log(f"[VOICE REELS] create_reels_prompt cagriliyior: topic={topic[:50]}..., shots={len(speech_structure)}")

            reels_prompt_result = await self.creator.execute({
                "action": "create_reels_prompt",
                "topic": topic,
                "category": topic_data.get("category", "tanitim"),
                "post_text": content_result.get("post_text_ig", ""),
                "post_id": content_result.get("post_id"),
                "speech_structure": speech_structure,  # Senkronizasyon için
                "voice_mode": True,  # Sesli reels modu
                "visual_style": visual_style
            })

            if not reels_prompt_result.get("success"):
                # Hata detaylarını logla
                self.log(f"[VOICE REELS] HATA DETAY: {reels_prompt_result}")
                raw_resp = reels_prompt_result.get('raw_response', 'YOK')
                if raw_resp and raw_resp != 'YOK':
                    self.log(f"[VOICE REELS] Raw Response: {raw_resp[:500]}")
                raise Exception(f"Reels prompt error: {reels_prompt_result.get('error', 'Unknown')}")

            self.current_data["reels_prompt"] = reels_prompt_result
            result["stages_completed"].append("video_prompt")

            # Model'e göre video prompt seç
            # force_model varsa onu kullan (backward compat), yoksa model_id
            model_to_use = force_model or model_id
            prompt_key = get_prompt_key(model_to_use)
            video_prompt = reels_prompt_result.get(prompt_key)

            # Fallback: Ana prompt yoksa alternatiflere bak
            if not video_prompt:
                video_prompt = (
                    reels_prompt_result.get("video_prompt_sora") or
                    reels_prompt_result.get("video_prompt_wan") or
                    reels_prompt_result.get("video_prompt_veo", "")
                )

            complexity = reels_prompt_result.get("complexity", "medium")

            # Boş video prompt kontrolü - alakasız video üretimini önle
            if not video_prompt or not video_prompt.strip():
                raise Exception("Video prompt boş! LLM geçerli bir prompt üretemedi.")

            # Video prompt'u kaydet
            if video_prompt and content_result.get("post_id"):
                prompt_style = reels_prompt_result.get("camera_movement") or complexity
                save_prompt(
                    post_id=content_result.get("post_id"),
                    prompt_text=video_prompt,
                    prompt_type='video',
                    style=prompt_style
                )

            self.log(f"[VOICE REELS] Prompt hazır (model: {model_to_use}, prompt_key: {prompt_key})")

            # ========== AŞAMA 6: Video Üretimi ==========
            self.log(f"[VOICE REELS] Aşama 6: Video üretiliyor ({model_name})...")

            from app.sora_helper import generate_video_smart

            # Video süresini GERÇEK audio süresine göre belirle
            actual_dur = result.get("actual_audio_duration", target_duration)

            # Model'in desteklediği sürelere göre video_gen_duration belirle
            model_durations = model_config.get("durations", [8, 12])

            # Audio süresine en yakın desteklenen süreyi seç
            video_gen_duration = min(model_durations, key=lambda x: abs(x - actual_dur) if x >= actual_dur else float('inf'))
            if video_gen_duration < actual_dur:
                # Tüm süreler audio'dan kısa, en uzunu seç
                video_gen_duration = max(model_durations)

            if actual_dur > max_duration:
                self.log(f"[VOICE REELS] ⚠️ Audio {actual_dur:.1f}s > {max_duration}s max, video loop gerekecek")

            self.log(f"[VOICE REELS] Video süresi: {video_gen_duration}s (audio: {actual_dur:.1f}s, model: {model_name})")

            video_result = await generate_video_smart(
                prompt=video_prompt,
                topic=topic,
                force_model=model_to_use,
                duration=video_gen_duration,  # Gerçek audio süresine göre
                voice_mode=True  # TTS voiceover için NO dialogue suffix
            )

            if not video_result.get("success"):
                raise Exception(f"Video generation failed: {video_result.get('error', 'Unknown')}")

            video_path = video_result.get("video_path")
            model_used = video_result.get("model_used", "unknown")

            self.current_data["video_result"] = video_result
            result["stages_completed"].append("video_generation")
            result["model_used"] = model_used

            self.log(f"[VOICE REELS] Video üretildi ({model_used})")

            # ========== AŞAMA 7: Audio-Video Birleştirme ========== [YENİ]
            final_video_path = video_path

            if audio_path and not voice_fallback:
                self.log("[VOICE REELS] Aşama 7: Video ve ses birleştiriliyor...")

                from app.instagram_helper import merge_audio_video, get_video_duration
                from app.audio_sync_helper import sync_audio_to_video

                # Video süresini kontrol et
                video_duration = await get_video_duration(video_path)

                # Audio/Video sync - video loop yapmadan audio'yu adapte et
                if audio_duration > video_duration:
                    self.log(f"[VOICE REELS] Audio ({audio_duration:.1f}s) > Video ({video_duration:.1f}s) - sync yapılıyor...")

                    sync_result = await sync_audio_to_video(
                        audio_path=audio_path,
                        video_duration=video_duration,
                        original_script=speech_script
                    )

                    if sync_result.get("success"):
                        audio_path = sync_result["audio_path"]
                        audio_duration = sync_result["final_duration"]
                        self.log(f"[VOICE REELS] Sync: {sync_result['action']} ({sync_result.get('trimmed_seconds', 0):.1f}s kırpıldı)")

                merge_result = await merge_audio_video(
                    video_path=video_path,
                    audio_path=audio_path,
                    target_duration=audio_duration,
                    fade_out=True,
                    fade_duration=0.5
                )

                if merge_result.get("success"):
                    final_video_path = merge_result.get("output_path")
                    result["stages_completed"].append("audio_merge")
                    result["final_duration"] = merge_result.get("duration")
                    self.log(f"[VOICE REELS] Merge tamamlandı: {merge_result.get('duration'):.1f}s")

                    # ========== SUBTITLE GENERATION (Optional) ==========
                    if os.getenv("SUBTITLE_ENABLED", "false").lower() == "true":
                        self.log("[VOICE REELS] Altyazı ekleniyor...")
                        try:
                            from app.subtitle_helper import create_subtitle_file
                            from app.instagram_helper import add_subtitles_to_video

                            # Generate ASS subtitle from audio (hybrid: original script + Whisper timing)
                            sub_result = await create_subtitle_file(
                                audio_path=audio_path,
                                original_script=speech_script,
                                model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
                                language="tr"
                            )

                            if sub_result.get("success"):
                                # Burn subtitles into video
                                burn_result = await add_subtitles_to_video(
                                    video_path=final_video_path,
                                    ass_path=sub_result["ass_path"]
                                )

                                if burn_result.get("success"):
                                    final_video_path = burn_result["output_path"]
                                    result["stages_completed"].append("subtitles")
                                    result["subtitle_count"] = sub_result["subtitle_count"]
                                    self.log(f"[VOICE REELS] Altyazı eklendi: {sub_result['subtitle_count']} satır")
                                else:
                                    self.log(f"[VOICE REELS] Altyazı burn hatası: {burn_result.get('error')}")
                            else:
                                self.log(f"[VOICE REELS] Altyazı üretim hatası: {sub_result.get('error')}")
                        except Exception as e:
                            self.log(f"[VOICE REELS] Altyazı exception: {e}")
                            # Continue without subtitles - graceful degradation
                else:
                    self.log(f"[VOICE REELS] Merge hatası: {merge_result.get('error')}")
                    self.log("[VOICE REELS] Sessiz video ile devam ediliyor...")
                    result["merge_fallback"] = True
            else:
                self.log("[VOICE REELS] Audio yok, sessiz video kullanılacak")

            await self.notify_telegram(
                message=f"🎥 *SESLİ REELS* - Video Hazır\n\n"
                f"Model: {model_used}\n"
                f"Ses: {'✅ Eklendi' if audio_path and not voice_fallback else '❌ Yok (fallback)'}\n"
                f"Complexity: {complexity}",
                data={"video_path": final_video_path},
                buttons=[]
            )

            # ========== AŞAMA 8: Kalite Kontrol ==========
            self.log("[VOICE REELS] Aşama 8: Kalite kontrol...")
            self.state = PipelineState.REVIEWING

            review_result = await self.reviewer.execute({
                "action": "review_post",
                "post_text": content_result.get("post_text_ig", ""),
                "topic": topic,
                "post_id": content_result.get("post_id")
            })

            score = review_result.get("total_score", 0)
            result["review_score"] = score
            result["stages_completed"].append("review")

            self.log(f"[VOICE REELS] Review: {score}/10")

            # Düşük puan ise revizyon
            if score < 7:
                self.log("[VOICE REELS] Puan düşük, caption revize ediliyor...")
                revision_result = await self.creator.execute({
                    "action": "revise_post",
                    "post_text": content_result.get("post_text_ig", ""),
                    "feedback": review_result.get("feedback", "Daha kısa ve etkili yaz"),
                    "post_id": content_result.get("post_id")
                })
                content_result["post_text_ig"] = revision_result.get("revised_post", content_result.get("post_text_ig"))

            # ========== AŞAMA 9: Yayınla ==========
            self.log("[VOICE REELS] Aşama 9: Yayınlanıyor...")
            self.state = PipelineState.PUBLISHING

            publish_result = await self.publisher.execute({
                "action": "publish",
                "post_id": content_result.get("post_id"),
                "post_text": content_result.get("post_text_ig", ""),
                "post_text_ig": content_result.get("post_text_ig", ""),
                "video_path": final_video_path,
                "platform": "instagram"
            })

            if publish_result.get("success"):
                result["stages_completed"].append("published")
                result["success"] = True
                result["instagram_post_id"] = publish_result.get("instagram_post_id")

                self.log(f"[VOICE REELS] Başarıyla yayınlandı! Instagram Reels")

                voice_status = "🔊 Sesli" if (audio_path and not voice_fallback) else "🔇 Sessiz"

                await self.notify_telegram(
                    message=f"🎉 *SESLİ REELS* - Yayınlandı!\n\n"
                    f"📝 Konu: {_escape_md(topic[:50])}...\n"
                    f"🎥 Model: {_escape_md(model_used)}\n"
                    f"🎙️ Ses: {voice_status}\n"
                    f"⏱️ Süre: ~{target_duration}s\n"
                    f"📱 Platform: Instagram Reels\n"
                    f"⭐ Puan: {score}/10",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("[VOICE REELS] Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"[VOICE REELS] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *SESLİ REELS* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def run_carousel_pipeline(
        self,
        topic: str = None,
        dry_run: bool = False,
        carousel_type: str = "nano_banana",
        manual_topic: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Carousel — v2 CarouselPipeline'a delege eder"""
        from app.production.carousel_pipeline import CarouselPipeline
        cp = CarouselPipeline(telegram_callback=self.telegram_callback)
        cp.approval_event = self.approval_event
        cp.approval_response = self.approval_response
        cp.set_approval = self.set_approval
        cp.wait_for_approval = self.wait_for_approval
        return await cp.run(topic=topic, dry_run=dry_run, carousel_type=carousel_type,
                            manual_topic=manual_topic, **kwargs)

    async def _run_carousel_pipeline_original(
        self,
        topic: str = None,
        dry_run: bool = False,
        carousel_type: str = "html",
        manual_topic: str = None
    ) -> Dict[str, Any]:
        """
        Orijinal carousel — yedek.

        Akış:
        1. Konu seçimi (opsiyonel)
        2. Carousel içerik oluşturma (Creator)
        3. Her slide için görsel üretimi (HTML veya Nano Banana)
        4. Kalite kontrolü (Reviewer)
        5. Instagram'a paylaşım (Publisher)

        Args:
            topic: Carousel konusu (None ise Planner'dan al)
            dry_run: True ise paylaşım yapmadan dur
            carousel_type: Görsel tipi ("html" veya "nano_banana")
            manual_topic: Manuel konu (topic yerine kullanılır)

        Returns:
            Pipeline sonucu
        """
        # Manual topic varsa onu kullan
        if manual_topic:
            topic = manual_topic

        type_name = "Nano Banana AI" if carousel_type == "nano_banana" else "HTML Template"
        self.log(f"🎠 Carousel Pipeline başlatılıyor... (Tip: {type_name})")
        self.state = PipelineState.CREATING_CONTENT

        result = {
            "success": False,
            "stages_completed": [],
            "content_type": "carousel",
            "dry_run": dry_run
        }

        try:
            # ========== AŞAMA 1: Konu Seçimi ==========
            if not topic:
                self.log("[CAROUSEL] Aşama 1: Konu seçiliyor...")
                topic_result = await self.planner.execute({
                    "action": "suggest_topic",
                    "content_type": "carousel",
                    "category": "egitici"
                })
                topic = topic_result.get("topic", "LoRaWAN Temel Kavramlar")
                result["topic_suggestion"] = topic_result

            result["topic"] = topic
            result["stages_completed"].append("topic_selection")
            self.log(f"[CAROUSEL] Konu: {topic}")

            # ========== AŞAMA 2: Carousel İçerik Oluştur ==========
            self.log("[CAROUSEL] Aşama 2: İçerik oluşturuluyor...")

            carousel_content = await self.creator.execute({
                "action": "create_carousel_content",
                "topic": topic,
                "slide_count": 5,
                "category": "egitici"
            })

            if not carousel_content.get("success"):
                raise Exception(f"Creator error: {carousel_content.get('error')}")

            result["post_id"] = carousel_content.get("post_id")
            result["caption"] = carousel_content.get("caption")
            result["slides"] = carousel_content.get("slides")
            result["hashtags"] = carousel_content.get("hashtags")
            result["slide_count"] = carousel_content.get("slide_count", 0)
            result["stages_completed"].append("content_created")

            # ========== Carousel İçerik Validasyonu ==========
            self.log("[CAROUSEL] İçerik validasyonu yapılıyor...")
            validation = self.reviewer.validate_carousel_content(carousel_content)

            if not validation.get("valid"):
                self.log(f"[CAROUSEL] ⚠️ Validasyon uyarıları: {validation.get('issues')}")

            if validation.get("issues"):
                # Auto-fix uygula
                fixed_content = validation.get("auto_fixed", carousel_content)
                if fixed_content != carousel_content:
                    self.log("[CAROUSEL] 🔧 Otomatik düzeltmeler uygulandı")
                    carousel_content = fixed_content
                    result["caption"] = fixed_content.get("caption", result["caption"])
                    result["slides"] = fixed_content.get("slides", result["slides"])

            result["validation"] = validation

            # SON KONTROL: Cover'da hala KAYDET var mı?
            slides = carousel_content.get("slides", [])
            if slides:
                cover_str = str(slides[0]).lower()
                if "kaydet" in cover_str:
                    self.log("[CAROUSEL] ⚠️ UYARI: Cover'da hala KAYDET var! Zorla temizleniyor...")
                    carousel_content = self.reviewer._clean_cover_slide(carousel_content)
                    result["slides"] = carousel_content.get("slides", result["slides"])
                    self.log("[CAROUSEL] ✅ Cover slide zorla temizlendi")

            result["stages_completed"].append("content_validated")

            # Carousel slide prompt'larını kaydet
            post_id = carousel_content.get("post_id")
            if post_id:
                for i, slide in enumerate(carousel_content.get("slides", [])):
                    image_prompt = slide.get("image_prompt", "")
                    if image_prompt:
                        save_prompt(
                            post_id=post_id,
                            prompt_text=image_prompt,
                            prompt_type='image',
                            style=f'carousel_slide_{i+1}'
                        )
                self.log(f"[CAROUSEL] {len(carousel_content.get('slides', []))} slide prompt'u kaydedildi")

            self.log(f"[CAROUSEL] {result['slide_count']} slide oluşturuldu")

            if dry_run:
                self.log("[CAROUSEL] Dry-run modu - görsel üretimi atlanıyor")
                result["success"] = True
                result["final_state"] = "dry_run_completed"
                return result

            # ========== AŞAMA 3: Görsel Üretimi ==========
            self.state = PipelineState.CREATING_VISUAL
            from app.instagram_helper import upload_image_to_cdn
            from datetime import datetime

            image_urls = []
            slides = carousel_content.get("slides", [])
            total_slides = len(slides)

            # Nano Banana AI Carousel
            if carousel_type == "nano_banana":
                self.log("[CAROUSEL] Aşama 3: Görseller Nano Banana ile üretiliyor...")
                from app.nano_banana_helper import generate_carousel_infographics

                nano_result = await generate_carousel_infographics(
                    topic=topic,
                    slides=slides,
                    style="modern",
                    language="tr"
                )

                if nano_result.get("success"):
                    # Nano Banana başarılı - görselleri CDN'e yükle
                    image_paths = nano_result.get("image_paths", [])
                    for i, image_path in enumerate(image_paths):
                        slide_num = i + 1
                        self.log(f"[CAROUSEL] Slide {slide_num}/{total_slides} CDN'e yükleniyor...")
                        cdn_url = await upload_image_to_cdn(image_path)
                        if cdn_url:
                            image_urls.append(cdn_url)
                        else:
                            self.log(f"[CAROUSEL] ⚠️ Slide {slide_num} CDN yükleme hatası")
                else:
                    # Nano Banana başarısız - HTML'e fallback
                    self.log(f"[CAROUSEL] Nano Banana hatası: {nano_result.get('error')}, HTML'e fallback...")
                    carousel_type = "html"  # Fallback

            # HTML Template Carousel (veya fallback)
            if carousel_type == "html":
                self.log("[CAROUSEL] Aşama 3: Görseller HTML ile üretiliyor...")
                from app.claude_helper import generate_carousel_slide_html
                from app.renderer import render_html_to_png

            # HTML rendering loop (sadece html tipi için çalışır)
            if carousel_type == "html":
                for i, slide in enumerate(slides):
                    slide_num = i + 1
                    self.log(f"[CAROUSEL] Slide {slide_num}/{total_slides} HTML üretiliyor...")

                    # Retry mekanizması
                    for attempt in range(2):
                        try:
                            # HTML oluştur
                            html_content = await generate_carousel_slide_html(
                                slide_data=slide,
                                slide_number=slide_num,
                                total_slides=total_slides,
                                topic=topic
                            )

                            # Text validation - typo kontrolü
                            validation = validate_html_content(html_content)
                            if not validation["can_render"]:
                                self.log(f"[CAROUSEL] Slide {slide_num} yazım hatası tespit edildi")
                                for issue in validation["issues"]:
                                    if issue["severity"] == "high":
                                        self.log(f"  - '{issue['found']}' -> '{issue['expected']}'")

                                # Otomatik düzelt
                                html_content, fixes = fix_common_issues(html_content)
                                if fixes:
                                    self.log(f"[CAROUSEL] Otomatik düzeltmeler: {fixes}")

                                # Tekrar doğrula
                                validation = validate_html_content(html_content)
                                if not validation["can_render"]:
                                    self.log(f"[CAROUSEL] Slide {slide_num} hala hatalı, yeniden üretiliyor...")
                                    html_content = await generate_carousel_slide_html(
                                        slide_data=slide,
                                        slide_number=slide_num,
                                        total_slides=total_slides,
                                        topic=topic
                                    )

                            # PNG'ye render et
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            output_path = f"outputs/carousel_{timestamp}_{slide_num}.png"
                            image_path = await render_html_to_png(
                                html_content=html_content,
                                output_path=output_path,
                                width=1080,
                                height=1080
                            )

                            if image_path:
                                # CDN'e yükle - retry logic ile
                                cdn_url = None
                                for upload_attempt in range(3):
                                    cdn_url = await upload_image_to_cdn(image_path)
                                    if cdn_url:
                                        break
                                    elif upload_attempt < 2:
                                        self.log(f"[CAROUSEL] Slide {slide_num} CDN upload retry {upload_attempt + 1}...")
                                        await asyncio.sleep(2)

                                if cdn_url:
                                    image_urls.append(cdn_url)
                                    self.log(f"[CAROUSEL] Slide {slide_num} OK")
                                    break
                                else:
                                    self.log(f"[CAROUSEL] Slide {slide_num} CDN upload başarısız (3 deneme)")
                            else:
                                self.log(f"[CAROUSEL] Slide {slide_num} render hatası, retry...")

                        except Exception as e:
                            self.log(f"[CAROUSEL] Slide {slide_num} hata: {e}")
                            if attempt == 1:
                                self.log(f"[CAROUSEL] Slide {slide_num} atlanıyor")

            result["image_urls"] = image_urls
            result["images_generated"] = len(image_urls)
            result["stages_completed"].append("visuals_created")

            # Minimum 5 görsel gerekli (tüm slide'lar zorunlu)
            if len(image_urls) < 5:
                raise Exception(f"Yetersiz görsel üretildi: {len(image_urls)}/5 - Tüm slide'lar gerekli")

            self.log(f"[CAROUSEL] {len(image_urls)} görsel hazır")

            # ========== AŞAMA 4: Kalite Kontrolü ==========
            self.log("[CAROUSEL] Aşama 4: Kalite kontrolü...")
            self.state = PipelineState.REVIEWING

            MAX_CAROUSEL_RETRIES = 2
            MIN_CAROUSEL_SCORE = 6.5

            for attempt in range(MAX_CAROUSEL_RETRIES + 1):
                review_result = await self.reviewer.execute({
                    "action": "review_post",
                    "post_text": carousel_content.get("caption", ""),
                    "content_type": "carousel",
                    "slide_count": len(image_urls),
                    "topic": topic
                })

                score = review_result.get("total_score", 7)
                feedback = review_result.get("feedback", "")
                weaknesses = review_result.get("weaknesses", [])
                suggestions = review_result.get("revision_suggestions", [])

                result["review_score"] = score
                result["review_feedback"] = feedback
                result["stages_completed"].append("review")

                self.log(f"[CAROUSEL] Review score: {score}/10 (Deneme {attempt + 1}/{MAX_CAROUSEL_RETRIES + 1})")

                if feedback:
                    self.log(f"[CAROUSEL] Feedback: {feedback[:200]}...")
                if weaknesses:
                    self.log(f"[CAROUSEL] Zayıf yönler: {', '.join(weaknesses[:3])}")

                if score >= MIN_CAROUSEL_SCORE:
                    self.log(f"[CAROUSEL] Kalite onaylandı: {score}/10")
                    break  # Yeterli puan, devam et

                if attempt < MAX_CAROUSEL_RETRIES:
                    # Düşük puan - caption'ı revize et
                    self.log(f"[CAROUSEL] Düşük puan ({score}/10), caption revize ediliyor...")

                    revision_feedback = feedback or "Daha kısa, etkili ve dikkat çekici yaz"
                    if suggestions:
                        revision_feedback += f". Öneriler: {', '.join(suggestions[:2])}"

                    revision_result = await self.creator.execute({
                        "action": "revise_post",
                        "post_text": carousel_content.get("caption", ""),
                        "feedback": revision_feedback,
                        "post_id": carousel_content.get("post_id")
                    })

                    if revision_result.get("revised_post"):
                        carousel_content["caption"] = revision_result.get("revised_post")
                        self.log("[CAROUSEL] Caption revize edildi, tekrar değerlendiriliyor...")
                else:
                    # Son deneme de başarısız
                    self.log(f"[CAROUSEL] {MAX_CAROUSEL_RETRIES + 1} deneme sonrası hala düşük puan: {score}/10")

                    # Admin'e detaylı bildirim gönder
                    feedback_msg = f"❌ *CAROUSEL* - Düşük Kalite Puanı\n\n"
                    feedback_msg += f"📝 Konu: {topic[:50]}...\n"
                    feedback_msg += f"⭐ Puan: {score}/10\n"
                    feedback_msg += f"🔄 Deneme: {MAX_CAROUSEL_RETRIES + 1}\n\n"
                    if feedback:
                        feedback_msg += f"📋 *Feedback:*\n{feedback[:300]}\n\n"
                    if weaknesses:
                        feedback_msg += f"⚠️ *Zayıf Yönler:*\n• " + "\n• ".join(weaknesses[:3]) + "\n\n"
                    if suggestions:
                        feedback_msg += f"💡 *Öneriler:*\n• " + "\n• ".join(suggestions[:3])

                    await self.notify_telegram(
                        message=feedback_msg,
                        data={"score": score, "feedback": feedback},
                        buttons=[]
                    )

                    result["error"] = f"Kalite skoru düşük: {score}/10 - {feedback[:100] if feedback else 'Detay yok'}"
                    result["final_state"] = "review_failed"
                    return result

            # ========== AŞAMA 5: Instagram'a Paylaş ==========
            self.log("[CAROUSEL] Aşama 5: Instagram'a paylaşılıyor...")
            self.state = PipelineState.PUBLISHING

            publish_result = await self.publisher.execute({
                "action": "publish_carousel",
                "post_id": carousel_content.get("post_id"),
                "caption": carousel_content.get("caption", ""),
                "image_urls": image_urls,
                "hashtags": carousel_content.get("hashtags", []),
                "visual_type": "carousel"
            })

            if publish_result.get("success"):
                result["stages_completed"].append("published")
                result["success"] = True
                result["instagram_post_id"] = publish_result.get("instagram_post_id")

                self.log("[CAROUSEL] Başarıyla yayınlandı!")

                await self.notify_telegram(
                    message=f"🎠 *CAROUSEL* - Yayınlandı!\n\n"
                    f"📝 Konu: {_escape_md(topic[:50])}...\n"
                    f"📸 Slide sayısı: {len(image_urls)}\n"
                    f"⭐ Puan: {score}/10\n"
                    f"📱 Platform: Instagram",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("[CAROUSEL] Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"[CAROUSEL] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *CAROUSEL* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def run_ab_content(self, topic: str = None, enable_ab: bool = True) -> Dict[str, Any]:
        """
        A/B Testing Pipeline - İki caption varyantı üret, karşılaştır, kazananı yayınla.

        Akış:
        1. Konu seçimi
        2. A/B Variant üretimi (Creator.create_ab_variants)
        3. Karşılaştırmalı değerlendirme (Reviewer.compare_ab_variants)
        4. Kazanan variant ile görsel üretimi
        5. Yayınlama
        6. A/B sonuç loglama

        Args:
            topic: Konu (None ise Planner'dan al)
            enable_ab: False ise normal flow (A/B atlama)

        Returns:
            Pipeline sonucu
        """
        self.log("A/B TEST MOD: Pipeline başlatılıyor...")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "ab_test": enable_ab,
            "final_state": None
        }

        try:
            # ========== AŞAMA 1: Konu Seçimi ==========
            if topic:
                topic_data = {
                    "topic": topic,
                    "category": "egitici",
                    "suggested_visual": "flux"
                }
                self.log(f"[A/B] Konu verildi: {topic[:50]}...")
            else:
                self.log("[A/B] Aşama 1: Konu seçiliyor...")
                topic_result = await self.planner.execute({"action": "suggest_topic"})

                if "error" in topic_result:
                    raise Exception(f"Planner error: {topic_result['error']}")

                topic_data = topic_result
                topic = topic_data.get("topic", "IoT ve akıllı tarım")

            self.current_data["topic"] = topic_data
            result["stages_completed"].append("topic_selection")
            result["topic"] = topic

            self.log(f"[A/B] Konu: {topic}")

            # ========== AŞAMA 2: A/B Variant Üretimi ==========
            if enable_ab:
                self.log("[A/B] Aşama 2: İki variant üretiliyor...")
                self.state = PipelineState.CREATING_CONTENT

                ab_result = await self.creator.execute({
                    "action": "create_ab_variants",
                    "topic": topic,
                    "category": topic_data.get("category", "egitici"),
                    "visual_type": topic_data.get("suggested_visual", "flux"),
                    "platform": "instagram"
                })

                if not ab_result.get("success"):
                    raise Exception(f"A/B creation error: {ab_result.get('error')}")

                variant_a = ab_result.get("variant_a", {})
                variant_b = ab_result.get("variant_b", {})
                post_id = ab_result.get("post_id")

                self.current_data["ab_variants"] = ab_result
                result["stages_completed"].append("ab_variants_created")
                result["variant_a_hook"] = variant_a.get("hook_type")
                result["variant_b_hook"] = variant_b.get("hook_type")

                self.log(f"[A/B] Variant A: {variant_a.get('hook_type')} hook")
                self.log(f"[A/B] Variant B: {variant_b.get('hook_type')} hook")

                await self.notify_telegram(
                    message=f"🔬 *A/B TEST* - Variantlar Hazır\n\n"
                    f"📝 Konu: {_escape_md(topic[:50])}...\n"
                    f"🅰️ Variant A: {_escape_md(variant_a.get('hook_type'))} hook\n"
                    f"🅱️ Variant B: {_escape_md(variant_b.get('hook_type'))} hook",
                    data=ab_result,
                    buttons=[]
                )

                # ========== AŞAMA 3: Karşılaştırmalı Değerlendirme ==========
                self.log("[A/B] Aşama 3: Variantlar karşılaştırılıyor...")
                self.state = PipelineState.REVIEWING

                comparison_result = await self.reviewer.execute({
                    "action": "compare_ab_variants",
                    "variant_a": variant_a,
                    "variant_b": variant_b,
                    "topic": topic,
                    "platform": "instagram"
                })

                if "error" in comparison_result:
                    raise Exception(f"Comparison error: {comparison_result['error']}")

                winner = comparison_result.get("winner") or "A"  # None-safe
                margin = comparison_result.get("margin", 0)
                confidence = comparison_result.get("confidence") or "medium"  # None-safe
                winning_variant = comparison_result.get("winning_variant", {})
                reasoning = comparison_result.get("reasoning", "")
                learning = comparison_result.get("learning", "")

                self.current_data["comparison"] = comparison_result
                result["stages_completed"].append("ab_comparison")
                result["ab_winner"] = winner
                result["ab_margin"] = margin
                result["ab_confidence"] = confidence

                self.log(f"[A/B] Kazanan: Variant {winner} (fark: {margin}, güven: {confidence})")

                await self.notify_telegram(
                    message=f"🏆 *A/B TEST* - Kazanan Belirlendi\n\n"
                    f"🥇 Kazanan: Variant {winner}\n"
                    f"📊 Fark: {margin}\n"
                    f"🎯 Güven: {confidence}\n\n"
                    f"💡 Öğrenim: {learning[:100]}...",
                    data=comparison_result,
                    buttons=[]
                )

                # Kazanan variant'ı kullan
                post_text = winning_variant.get("post_text", "")
                hook_type = winning_variant.get("hook_type", "")
                tone = winning_variant.get("tone", "")

                # A/B sonucu kaydet
                from app.database import log_ab_test_result, update_post

                variant_a_score = comparison_result.get("variant_a_scores", {}).get("total", 0)
                variant_b_score = comparison_result.get("variant_b_scores", {}).get("total", 0)

                ab_test_id = log_ab_test_result(
                    topic=topic,
                    platform="instagram",
                    variant_a={
                        "hook_type": variant_a.get("hook_type"),
                        "tone": variant_a.get("tone"),
                        "score": variant_a_score,
                        "text": variant_a.get("post_text", "")[:500]
                    },
                    variant_b={
                        "hook_type": variant_b.get("hook_type"),
                        "tone": variant_b.get("tone"),
                        "score": variant_b_score,
                        "text": variant_b.get("post_text", "")[:500]
                    },
                    winner=winner,
                    margin=margin,
                    confidence=confidence,
                    reasoning=reasoning,
                    learning=learning,
                    post_id=post_id
                )

                result["ab_test_id"] = ab_test_id
                result["stages_completed"].append("ab_logged")

                # Post'u güncelle
                if post_id:
                    update_post(
                        post_id,
                        post_text=post_text,
                        hook_type=hook_type,
                        tone=tone,
                        ab_test_id=ab_test_id,
                        is_ab_winner=True
                    )

            else:
                # Normal içerik üretimi (A/B yok)
                self.log("[A/B] A/B devre dışı, normal içerik üretiliyor...")
                self.state = PipelineState.CREATING_CONTENT

                content_result = await self.creator.execute({
                    "action": "create_post_multiplatform",
                    "topic": topic,
                    "category": topic_data.get("category", "egitici"),
                    "visual_type": topic_data.get("suggested_visual", "flux")
                })

                if "error" in content_result:
                    raise Exception(f"Creator error: {content_result['error']}")

                post_text = content_result.get("post_text_ig", content_result.get("post_text", ""))
                post_id = content_result.get("post_id")
                hook_type = None
                tone = None

                result["stages_completed"].append("content_created")

            result["post_id"] = post_id

            # ========== AŞAMA 4: Görsel Üretimi ==========
            self.log("[A/B] Aşama 4: Görsel üretiliyor...")
            self.state = PipelineState.CREATING_VISUAL

            visual_type = topic_data.get("suggested_visual", "flux")

            visual_prompt_result = await self.creator.execute({
                "action": "create_visual_prompt",
                "post_text": post_text,
                "topic": topic,
                "visual_type": visual_type,
                "post_id": post_id
            })

            if "error" in visual_prompt_result:
                raise Exception(f"Visual prompt error: {visual_prompt_result['error']}")

            result["stages_completed"].append("visual_prompt")

            # Görsel üret
            image_path = None
            video_path = None

            if visual_type in ["flux", "single"]:
                from app.flux_helper import generate_image_flux
                visual_result = await generate_image_flux(
                    prompt=visual_prompt_result.get("visual_prompt"),
                    width=1024,
                    height=1024
                )
                if visual_result.get("success"):
                    image_path = visual_result.get("image_path")

            elif visual_type == "video":
                from app.veo_helper import generate_video_with_retry
                visual_result = await generate_video_with_retry(
                    prompt=visual_prompt_result.get("visual_prompt")
                )
                if visual_result.get("success"):
                    video_path = visual_result.get("video_path")

            if not image_path and not video_path:
                raise Exception("Görsel üretilemedi")

            result["stages_completed"].append("visual_created")
            self.log(f"[A/B] Görsel hazır: {image_path or video_path}")

            # ========== AŞAMA 5: Final Review (opsiyonel) ==========
            if enable_ab:
                # A/B'de zaten review yapıldı, winning score'u kullan
                score = comparison_result.get(f"variant_{(winner or 'a').lower()}_scores", {}).get("total", 7)
            else:
                # Normal review
                self.log("[A/B] Aşama 5: Kalite kontrol...")
                review_result = await self.reviewer.execute({
                    "action": "review_post",
                    "post_text": post_text,
                    "topic": topic,
                    "post_id": post_id
                })
                score = review_result.get("total_score", 0)

            result["review_score"] = score
            result["stages_completed"].append("review")
            self.log(f"[A/B] Final score: {score}/10")

            if score < 6:
                self.log("[A/B] Puan çok düşük, yayınlanmıyor")
                result["error"] = f"Review puanı düşük: {score}/10"
                return result

            # ========== AŞAMA 6: Yayınla ==========
            self.log("[A/B] Aşama 6: Yayınlanıyor...")
            self.state = PipelineState.PUBLISHING

            publish_result = await self.publisher.execute({
                "action": "publish",
                "post_id": post_id,
                "post_text": post_text,
                "post_text_ig": post_text,
                "image_path": image_path,
                "video_path": video_path,
                "platform": "instagram"
            })

            if publish_result.get("success"):
                result["stages_completed"].append("published")
                result["success"] = True
                result["instagram_post_id"] = publish_result.get("instagram_post_id")

                self.log("[A/B] Başarıyla yayınlandı!")

                # Hook performance güncelle
                if hook_type:
                    from app.database import update_hook_performance
                    update_hook_performance(
                        hook_type=hook_type,
                        topic_category=topic_data.get("category", "egitici"),
                        platform="instagram",
                        reach=0,  # Sonradan güncellenecek
                        engagement=0,
                        engagement_rate=0
                    )

                await self.notify_telegram(
                    message=f"🎉 *A/B TEST* - Yayınlandı!\n\n"
                    f"📝 Konu: {_escape_md(topic[:50])}...\n"
                    f"🏆 Kazanan: Variant {_escape_md(winner) if enable_ab else 'N/A'}\n"
                    f"🪝 Hook: {_escape_md(hook_type or 'N/A')}\n"
                    f"⭐ Puan: {score}/10",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("[A/B] Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"[A/B] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *A/B TEST* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def run_long_video_pipeline(
        self,
        topic: str = None,
        segment_count: int = 2,
        model_id: str = "kling-3.0-pro",
        transition_type: str = "crossfade",
        transition_duration: float = 0.5,
        manual_topic_mode: bool = False,
        visual_style: str = "cinematic_4k"
    ) -> Dict[str, Any]:
        """Long video — v2 LongVideoPipeline'a delege eder"""
        from app.production.long_video_pipeline import LongVideoPipeline
        lp = LongVideoPipeline(telegram_callback=self.telegram_callback)
        lp.approval_event = self.approval_event
        lp.approval_response = self.approval_response
        lp.set_approval = self.set_approval
        lp.wait_for_approval = self.wait_for_approval
        return await lp.run(topic=topic, segment_count=segment_count, model_id=model_id,
                            transition_type=transition_type, transition_duration=transition_duration,
                            manual_topic_mode=manual_topic_mode, visual_style=visual_style)

    async def _run_long_video_pipeline_original(
        self,
        topic: str = None,
        segment_count: int = 2,
        model_id: str = "kling-3.0-pro",
        transition_type: str = "crossfade",
        transition_duration: float = 0.5,
        manual_topic_mode: bool = False,
        visual_style: str = "cinematic_4k"
    ) -> Dict[str, Any]:
        """
        Orijinal long video — yedek.

        Birden fazla video segmenti üretip birleştirerek uzun videolar oluşturur.
        Segment süresi modele göre dinamik belirlenir.

        Pipeline Akışı:
        1. Konu seçimi (Planner/Creator)
        2. Caption üretimi (Creator)
        3. Speech script üretimi
        4. TTS ses üretimi (OpenAI TTS)
        5. Multi-scene prompt üretimi (Creator)
        6. Paralel video üretimi (N segment)
        7. Video birleştirme (FFmpeg crossfade)
        8. Audio-video merge (FFmpeg)
        9. Kalite kontrol (Reviewer)
        10. Instagram Reels yayını (Publisher)

        Args:
            topic: Konu (None ise Planner'dan alınır)
            segment_count: Segment sayısı (2-6 arası, default 2)
            model_id: Video model ID (kling-3.0-pro, sora-2, sora-2-pro, veo-3.1)
            transition_type: Geçiş tipi (crossfade, cut)
            transition_duration: Crossfade süresi (0.5s default)
            manual_topic_mode: True ise topic Creator ile işlenir
            visual_style: Görsel stil (cinematic_4k, anime, vb.)

        Returns:
            Pipeline sonucu
        """
        from app.sora_helper import generate_videos_parallel
        from app.instagram_helper import (
            concatenate_videos_with_crossfade,
            merge_audio_video
        )
        from app.openai_tts_helper import OpenAITTSHelper
        from app.database.crud import create_post, update_post

        # Model'in max süresine göre segment süresi belirlenir
        actual_segment_duration = get_max_duration(model_id)

        # Segment sayısını doğrula (2-6 arası)
        segment_count = max(2, min(6, segment_count))

        # Crossfade overlap'leri hesapla (N segment = N-1 crossfade)
        crossfade_overlap = (segment_count - 1) * transition_duration
        actual_video_duration = (segment_count * actual_segment_duration) - crossfade_overlap

        self.log(f"🎬 UZUN VIDEO: Pipeline başlatılıyor...")
        self.log(f"   Segment: {segment_count}x{actual_segment_duration}s - {crossfade_overlap}s crossfade = {actual_video_duration}s")
        self.log(f"   Model: {model_id}")
        self.log(f"   Geçiş: {transition_type} ({transition_duration}s)")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "final_state": None,
            "long_video": True,
            "voice_enabled": True,
            "segment_count": segment_count,
            "total_duration": actual_video_duration,
            "model_id": model_id
        }

        # Orijinal kullanıcı metnini pipeline boyunca taşı (teknik detaylar korunsun)
        original_user_brief = topic if (topic and manual_topic_mode) else None

        try:
            # ========== AŞAMA 1: Konu Seçimi ==========
            if topic and manual_topic_mode:
                self.log(f"[LONG VIDEO] Manuel konu işleniyor: {topic[:50]}...")

                topic_result = await self.creator.execute({
                    "action": "process_manual_topic",
                    "user_input": topic
                })

                processed_topic = topic_result.get("processed_topic", topic)
                topic_data = {
                    "topic": processed_topic,
                    "category": topic_result.get("category", "tanitim"),
                    "suggested_visual": "video",
                    "original_input": topic
                }
                topic = processed_topic

            elif topic:
                topic_data = {
                    "topic": topic,
                    "category": "tanitim",
                    "suggested_visual": "video"
                }
            else:
                self.log("[LONG VIDEO] Aşama 1: Konu seçiliyor...")
                topic_result = await self.planner.execute({"action": "suggest_topic"})

                if "error" in topic_result:
                    raise Exception(f"Planner error: {topic_result['error']}")

                topic_data = topic_result
                topic = topic_data.get("topic", "IoT ve akıllı tarım")

            self.log(f"[LONG VIDEO] Konu: {topic[:50]}...")
            result["stages_completed"].append("topic_selection")

            # ========== AŞAMA 2: Caption Üretimi ==========
            self.log("[LONG VIDEO] Aşama 2: Caption üretiliyor...")
            self.state = PipelineState.CREATING_CONTENT

            content_result = await self.creator.execute({
                "action": "create_post",
                "topic": topic,
                "platform": "instagram",
                "visual_type": "reels",
                "category": topic_data.get("category", "tanitim"),
                "original_user_brief": original_user_brief,
            })

            caption = content_result.get("post_text_ig") or content_result.get("post_text", "")
            post_id = content_result.get("post_id")

            # DEBUG: Caption değerini logla
            self.log(f"[LONG VIDEO] Caption uzunluk: {len(caption)} karakter")
            if not caption or len(caption.strip()) == 0:
                self.log("[LONG VIDEO] UYARI: Caption BOŞ!")
            else:
                self.log(f"[LONG VIDEO] Caption önizleme: {caption[:100]}...")
            self.log(f"[LONG VIDEO] Caption oluşturuldu (Post ID: {post_id})")
            result["stages_completed"].append("caption_creation")
            result["post_id"] = post_id

            # ========== AŞAMA 3: Speech Script Üretimi ==========
            self.log(f"[LONG VIDEO] Aşama 3: Voiceover scripti üretiliyor ({actual_video_duration}s)...")

            # Kelime hedefi: ~1.8 kelime/saniye (Türkçe TTS ölçümü)
            target_words = int(actual_video_duration * 1.8)

            speech_result = await self.creator.execute({
                "action": "create_speech_script",
                "topic": topic,
                "target_duration": actual_video_duration,
                "target_words": target_words,
                "segment_count": segment_count,
                "segment_duration": actual_segment_duration,
                "tone": "friendly",  # Samimi ton (voice reels ile aynı)
                "post_id": post_id,
                "original_user_brief": original_user_brief,
            })

            if not speech_result.get("success"):
                raise Exception(f"Speech script hatası: {speech_result.get('error')}")

            speech_script = speech_result.get("speech_script", "")
            self.log(f"[LONG VIDEO] Script: {len(speech_script.split())} kelime")
            result["stages_completed"].append("speech_script")

            # ========== AŞAMA 4: TTS Ses Üretimi ==========
            self.log("[LONG VIDEO] Aşama 4: TTS ses üretiliyor...")

            # Voice reels ile aynı fonksiyon - ENV'deki voice ID'yi kullanır
            from app.openai_tts_helper import generate_speech_with_retry
            tts_result = await generate_speech_with_retry(
                text=speech_script,
                max_retries=3
            )

            if not tts_result.get("success"):
                raise Exception(f"TTS hatası: {tts_result.get('error')}")

            audio_path = tts_result.get("audio_path")
            estimated_duration = tts_result.get("duration", actual_video_duration)

            # GERÇEK audio süresini ffprobe ile ölç (Voice Reels ile aynı)
            from app.instagram_helper import get_audio_duration
            actual_audio_duration = await get_audio_duration(audio_path)
            self.log(f"[LONG VIDEO] TTS süre - Tahmini: {estimated_duration:.1f}s, Gerçek: {actual_audio_duration:.1f}s")

            # Gerçek süreyi kullan (tahmini değil)
            audio_duration = actual_audio_duration if actual_audio_duration > 0 else estimated_duration

            self.log(f"[LONG VIDEO] Ses üretildi: {audio_duration:.1f}s")
            result["stages_completed"].append("tts_generation")
            result["audio_duration"] = audio_duration

            # Post-TTS süre validasyonu
            min_acceptable_duration = actual_video_duration * 0.85  # %15 tolerans
            if audio_duration < min_acceptable_duration:
                duration_deficit = actual_video_duration - audio_duration
                deficit_percent = (duration_deficit / actual_video_duration) * 100
                self.log(f"⚠️ [LONG VIDEO] Audio kısa ({audio_duration:.1f}s / {actual_video_duration}s), script uzatılıyor...")

                # Script'i uzat (1.8 WPS - Türkçe TTS ölçümü)
                extended_target_words = int(actual_video_duration * 1.8)
                extended_result = await self.creator.execute({
                    "action": "create_speech_script",
                    "topic": topic,
                    "target_duration": actual_video_duration,
                    "target_words": extended_target_words,
                    "segment_count": segment_count,
                    "segment_duration": actual_segment_duration,
                    "tone": "friendly",
                    "post_id": post_id
                })

                if extended_result.get("success") and extended_result.get("speech_script"):
                    extended_script = extended_result["speech_script"]
                    self.log(f"✅ Script uzatıldı: {len(extended_script.split())} kelime")

                    # TTS'i yeniden üret (aynı fonksiyon)
                    new_tts_result = await generate_speech_with_retry(
                        text=extended_script,
                        max_retries=3
                    )

                    if new_tts_result.get("success"):
                        audio_path = new_tts_result.get("audio_path")
                        new_audio_duration = await get_audio_duration(audio_path)
                        self.log(f"✅ Yeni audio: {new_audio_duration:.1f}s")

                        # Değişkenleri güncelle
                        audio_duration = new_audio_duration
                        speech_script = extended_script
                        result["audio_duration"] = audio_duration
                    else:
                        self.log(f"⚠️ TTS retry başarısız, orijinal audio kullanılacak")
                else:
                    self.log(f"⚠️ Script extension başarısız, orijinal audio kullanılacak")

            # ========== AŞAMA 5: Multi-Scene Prompt Üretimi ==========
            self.log(f"[LONG VIDEO] Aşama 5: {segment_count} sahne promptu üretiliyor...")

            # Shot structure'ı çıkar
            shot_structure = extract_shot_structure(speech_script, actual_video_duration)

            scene_result = await self.creator.execute({
                "action": "create_multi_scene_prompts",
                "topic": topic,
                "segment_count": segment_count,
                "segment_duration": actual_segment_duration,
                "speech_structure": shot_structure,
                "model_id": model_id,
                "visual_style": visual_style,
                "original_user_brief": original_user_brief,
            })

            if not scene_result.get("success"):
                raise Exception(f"Scene planning hatası: {scene_result.get('error')}")

            scenes = scene_result.get("scenes", [])
            style_prefix = scene_result.get("style_prefix", "")

            self.log(f"[LONG VIDEO] {len(scenes)} sahne planlandı")
            result["stages_completed"].append("scene_planning")

            # Segment promptlarını JSON olarak kaydet
            segment_prompts = json.dumps([s.get("prompt", "") for s in scenes], ensure_ascii=False)
            if post_id:
                update_post(
                    post_id,
                    segment_prompts=segment_prompts,
                    video_segment_count=segment_count,
                    video_model=model_id
                )

            # ========== AŞAMA 6: Paralel Video Üretimi ==========
            self.log(f"[LONG VIDEO] Aşama 6: {segment_count} video segmenti üretiliyor (paralel)...")
            self.state = PipelineState.CREATING_VISUAL

            # Her sahnenin prompt'unu al
            prompts = [scene.get("prompt", "") for scene in scenes]

            video_result = await generate_videos_parallel(
                prompts=prompts,
                model=model_id,
                duration=actual_segment_duration,
                style_prefix=style_prefix,
                max_concurrent=3,
                max_retries=3
            )

            if not video_result.get("success"):
                raise Exception(f"Video üretim hatası: {video_result.get('error', 'Yetersiz segment')}")

            video_paths = video_result.get("video_paths", [])
            self.log(f"[LONG VIDEO] {len(video_paths)} segment üretildi")
            result["stages_completed"].append("parallel_video_generation")
            result["segments_generated"] = len(video_paths)

            # ========== AŞAMA 7: Video Birleştirme ==========
            self.log(f"[LONG VIDEO] Aşama 7: {len(video_paths)} video birleştiriliyor ({transition_type})...")

            concat_result = await concatenate_videos_with_crossfade(
                video_paths=video_paths,
                crossfade_duration=transition_duration if transition_type == "crossfade" else 0,
                segment_duration=float(actual_segment_duration)
            )

            if not concat_result.get("success"):
                raise Exception(f"Video concat hatası: {concat_result.get('error')}")

            concat_video_path = concat_result.get("output_path")
            concat_duration = concat_result.get("total_duration", 0)

            self.log(f"[LONG VIDEO] Birleşik video: {concat_duration:.1f}s")
            result["stages_completed"].append("video_concatenation")

            # ========== AŞAMA 8: Audio-Video Merge ==========
            self.log("[LONG VIDEO] Aşama 8: Ses ve video birleştiriliyor...")

            from app.audio_sync_helper import sync_audio_to_video

            # Audio/Video sync - video loop yapmadan audio'yu adapte et
            if audio_duration > concat_duration:
                self.log(f"[LONG VIDEO] Audio ({audio_duration:.1f}s) > Video ({concat_duration:.1f}s) - sync yapılıyor...")

                sync_result = await sync_audio_to_video(
                    audio_path=audio_path,
                    video_duration=concat_duration,
                    original_script=speech_script
                )

                if sync_result.get("success"):
                    audio_path = sync_result["audio_path"]
                    audio_duration = sync_result["final_duration"]
                    self.log(f"[LONG VIDEO] Sync: {sync_result['action']} ({sync_result.get('trimmed_seconds', 0):.1f}s kırpıldı)")

            merge_result = await merge_audio_video(
                video_path=concat_video_path,
                audio_path=audio_path,
                target_duration=concat_duration
            )

            if not merge_result.get("success"):
                raise Exception(f"Merge hatası: {merge_result.get('error')}")

            final_video_path = merge_result.get("output_path")
            final_duration = merge_result.get("duration", 0)

            self.log(f"[LONG VIDEO] Final video: {final_duration:.1f}s")
            result["stages_completed"].append("audio_video_merge")

            # ========== SUBTITLE GENERATION (Optional) ==========
            if os.getenv("SUBTITLE_ENABLED", "false").lower() == "true":
                self.log("[LONG VIDEO] Altyazı ekleniyor...")
                try:
                    from app.subtitle_helper import create_subtitle_file
                    from app.instagram_helper import add_subtitles_to_video

                    # Generate ASS subtitle from audio (hybrid: original script + Whisper timing)
                    sub_result = await create_subtitle_file(
                        audio_path=audio_path,
                        original_script=speech_script,
                        model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
                        language="tr"
                    )

                    if sub_result.get("success"):
                        # Burn subtitles into video
                        burn_result = await add_subtitles_to_video(
                            video_path=final_video_path,
                            ass_path=sub_result["ass_path"]
                        )

                        if burn_result.get("success"):
                            final_video_path = burn_result["output_path"]
                            result["stages_completed"].append("subtitles")
                            result["subtitle_count"] = sub_result["subtitle_count"]
                            self.log(f"[LONG VIDEO] Altyazı eklendi: {sub_result['subtitle_count']} satır")
                        else:
                            self.log(f"[LONG VIDEO] Altyazı burn hatası: {burn_result.get('error')}")
                    else:
                        self.log(f"[LONG VIDEO] Altyazı üretim hatası: {sub_result.get('error')}")
                except Exception as e:
                    self.log(f"[LONG VIDEO] Altyazı exception: {e}")
                    # Continue without subtitles - graceful degradation

            # Post'u güncelle
            if post_id:
                update_post(
                    post_id,
                    visual_path=final_video_path,
                    total_video_duration=final_duration,
                    audio_path=audio_path,
                    audio_duration=audio_duration,
                    voice_mode=True
                )

            # ========== AŞAMA 9: Review ==========
            self.log("[LONG VIDEO] Aşama 9: Kalite kontrol...")
            self.state = PipelineState.REVIEWING

            review_result = await self.reviewer.execute({
                "action": "review_content",
                "post_id": post_id,
                "content_type": "reels",
                "caption": caption,
                "video_path": final_video_path
            })

            score = review_result.get("score", 7)
            self.log(f"[LONG VIDEO] Review skoru: {score}/10")
            result["stages_completed"].append("review")
            result["review_score"] = score

            # ========== AŞAMA 10: Yayın ==========
            self.log("[LONG VIDEO] Aşama 10: Instagram'a yayınlanıyor...")
            self.state = PipelineState.PUBLISHING

            # DEBUG: Publish öncesi caption kontrolü
            self.log(f"[LONG VIDEO] Publish edilecek caption: {len(caption)} karakter")

            publish_result = await self.publisher.execute({
                "action": "publish_reels",
                "post_id": post_id,
                "video_path": final_video_path,
                "post_text": caption,
                "audio_path": None  # Ses video'ya gömülü
            })

            if publish_result.get("success"):
                instagram_id = publish_result.get("instagram_post_id")
                self.log(f"[LONG VIDEO] ✓ Yayınlandı! ID: {instagram_id}")

                result["success"] = True
                result["instagram_post_id"] = instagram_id
                result["stages_completed"].append("publish")

                # Telegram bildirimi
                await self.notify_telegram(
                    message=f"🎬 *UZUN VIDEO* - Yayınlandı!\n\n"
                    f"📝 Konu: {_escape_md(topic[:50])}...\n"
                    f"⏱️ Süre: {final_duration:.0f}s ({segment_count} segment)\n"
                    f"🎥 Model: {_escape_md(model_id)}\n"
                    f"⭐ Puan: {score}/10",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish error: {publish_result.get('error')}")

            self.state = PipelineState.COMPLETED
            result["final_state"] = self.state.value

            self.log("[LONG VIDEO] Pipeline tamamlandı!")
            return result

        except Exception as e:
            self.log(f"[LONG VIDEO] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *UZUN VIDEO* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def run_conversational_reels(
        self,
        topic: str = None,
        manual_topic_mode: bool = False,
        visual_style: str = "cinematic_4k",
        model_id: str = "sora-2"
    ) -> Dict[str, Any]:
        """Conversational Reels — v2 ConversationalPipeline'a delege eder"""
        from app.production.conversational_pipeline import ConversationalPipeline
        cvp = ConversationalPipeline(telegram_callback=self.telegram_callback)
        cvp.approval_event = self.approval_event
        cvp.approval_response = self.approval_response
        cvp.set_approval = self.set_approval
        cvp.wait_for_approval = self.wait_for_approval
        return await cvp.run(topic=topic, manual_topic_mode=manual_topic_mode,
                             visual_style=visual_style, model_id=model_id)

    async def _run_conversational_reels_original(
        self,
        topic: str = None,
        manual_topic_mode: bool = False,
        visual_style: str = "cinematic_4k",
        model_id: str = "sora-2"
    ) -> Dict[str, Any]:
        """
        Orijinal conversational reels — yedek.

        Creates two-character dialog video (male problem, female solution)
        followed by B-roll segment with voiceover.

        Pipeline Steps (Simplified):
        1. Topic selection (Planner/manual)
        2. Conversation content generation (Creator)
        3. Conversation video generation:
           - Sora 2: Native Turkish speech (12s)
           - Other models: TTS + Video + Lipsync API
        4. B-roll video generation (8-12s)
        5. B-roll voiceover generation (OpenAI TTS narrator)
        6. B-roll merge (FFmpeg)
        7. Concat conversation + B-roll
        8. Whisper transcription + subtitles
        9. Review + Publish

        Args:
            topic: Topic (None uses Planner suggestion)
            manual_topic_mode: Process topic through Creator if True
            visual_style: Görsel stil (cinematic_4k, anime, vb.)
            model_id: Video model (sora-2, sora-2-pro, veo-3.1, kling-3.0-pro)

        Returns:
            Pipeline result dict
        """
        self.log(f"[CONV REELS] Pipeline başlatılıyor (model: {model_id})...")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "conversational_reels": True,
            "topic": topic,
            "model_id": model_id
        }

        post_id = None

        try:
            # ========== STAGE 1: Topic Selection ==========
            if not topic:
                self.log("[CONV REELS] Aşama 1: Konu seçimi...")
                planner_result = await self.planner.execute({
                    "action": "suggest_topic",
                    "content_type": "reels",
                    "count": 1
                })

                if planner_result.get("success") and planner_result.get("topics"):
                    topic_data = planner_result["topics"][0]
                    topic = topic_data.get("topic", "")
                    category = topic_data.get("category", "egitici")
                    self.log(f"[CONV REELS] Konu seçildi: {topic[:50]}...")
                else:
                    raise Exception("Konu seçilemedi")
            else:
                category = "egitici"
                if manual_topic_mode:
                    # Process manual topic
                    processed = await self.creator.execute({
                        "action": "process_manual_topic",
                        "user_input": topic
                    })
                    if processed.get("success"):
                        topic = processed.get("processed_topic", topic)
                        category = processed.get("category", "egitici")

            result["topic"] = topic
            result["category"] = category
            result["stages_completed"].append("topic_selection")

            # Model'e göre dialog süresi ayarla
            from app.video_models import get_model_config
            model_config = get_model_config(model_id)
            max_duration = model_config.get("max_duration", 12)

            native_speech_models = ["sora-2", "sora-2-pro", "veo-3.1"]
            if model_id in native_speech_models:
                if model_id in ["sora-2", "sora-2-pro"]:
                    target_duration = min(12, max_duration)  # Sora API max 12s
                else:
                    target_duration = min(8, max_duration)  # Veo = 8s
            else:
                target_duration = 12  # TTS+Lipsync için sabit

            self.log(f"[CONV REELS] Target duration: {target_duration}s (model: {model_id})")

            # ========== STAGE 2: Conversation Content ==========
            self.log("[CONV REELS] Aşama 2: Dialog içeriği oluşturuluyor...")
            self.state = PipelineState.CREATING_CONTENT

            conv_result = await self.creator.execute({
                "action": "create_conversation_content",
                "topic": topic,
                "category": category,
                "target_duration": target_duration,  # Model'e göre dinamik
                "visual_style": visual_style
            })

            if not conv_result.get("success"):
                raise Exception(f"Dialog içerik hatası: {conv_result.get('error')}")

            dialog_lines = conv_result.get("dialog_lines", [])
            video_prompt = conv_result.get("video_prompt", "")
            broll_prompt = conv_result.get("broll_prompt", "")
            broll_voiceover = conv_result.get("broll_voiceover", "")
            caption = conv_result.get("caption", "")
            hashtags = conv_result.get("hashtags", [])

            self.log(f"[CONV REELS] Dialog oluşturuldu: {len(dialog_lines)} satır")
            result["dialog_line_count"] = len(dialog_lines)
            result["stages_completed"].append("conversation_content")

            # Create post in database
            from app.database import create_post, update_post
            post_id = create_post(
                topic=topic,
                post_text=caption,
                post_text_ig=caption,
                visual_type="reels",
                platform="instagram",
                topic_category=category,
                voice_mode=True
            )
            result["post_id"] = post_id

            # ========== STAGE 3: Conversation Video Generation ==========
            self.log(f"[CONV REELS] Aşama 3: Conversation video ({model_id})...")
            self.state = PipelineState.CREATING_VISUAL

            if model_id in native_speech_models:
                # ===== NATIVE SPEECH MODELS (Sora 2, Veo 3.1) =====
                self.log(f"[CONV REELS] Native speech modu ({model_id})")

                if model_id in ["sora-2", "sora-2-pro"]:
                    from app.sora_helper import generate_video_sora
                    from app.video_models import get_model_config
                    sora_config = get_model_config(model_id)
                    sora_duration = sora_config.get("default_duration", 12)

                    conversation_result = await generate_video_sora(
                        prompt=video_prompt,
                        duration=sora_duration,
                        size="720x1280",
                        model=model_id
                    )
                elif model_id == "veo-3.1":  # veo-3.1
                    from app.veo_helper import generate_video_veo
                    conversation_result = await generate_video_veo(
                        prompt=video_prompt,
                        duration_seconds=8,
                        aspect_ratio="9:16",
                        model="veo-3.1-generate-preview"
                    )

                if not conversation_result.get("success"):
                    raise Exception(f"Conversation video hatası: {conversation_result.get('error')}")

                conversation_video_path = conversation_result.get("video_path")
                result["native_speech"] = True
                result["native_speech_model"] = model_id
                self.log(f"[CONV REELS] {model_id} native speech video üretildi")

            else:
                # ===== DİĞER MODELLER: TTS + Video + Lipsync =====
                self.log(f"[CONV REELS] TTS + Lipsync modu ({model_id})")

                # 3a. Dialog TTS üret
                from app.openai_tts_helper import generate_dialog_audio
                from app.video_styles import should_use_cartoon_voices
                from app.config import settings

                if should_use_cartoon_voices(visual_style):
                    male_voice = settings.openai_tts_voice_cartoon_male
                    female_voice = settings.openai_tts_voice_cartoon_female
                    self.log(f"[CONV REELS] Cartoon voices kullanılıyor")
                else:
                    male_voice = settings.openai_tts_voice_male
                    female_voice = settings.openai_tts_voice_female
                    self.log(f"[CONV REELS] Realistic voices kullanılıyor")

                dialog_tts_result = await generate_dialog_audio(
                    dialog_lines=dialog_lines,
                    male_voice_id=male_voice,
                    female_voice_id=female_voice
                )

                if not dialog_tts_result.get("success"):
                    raise Exception(f"Dialog TTS hatası: {dialog_tts_result.get('error')}")

                dialog_audio_path = dialog_tts_result.get("audio_path")
                dialog_duration = dialog_tts_result.get("total_duration", 12)
                self.log(f"[CONV REELS] Dialog TTS üretildi: {dialog_duration:.1f}s")
                result["stages_completed"].append("dialog_tts")

                # 3b. Avatar video üret (sessiz)
                avatar_prompt = self._create_avatar_prompt(video_prompt)

                from app.sora_helper import generate_video_smart
                avatar_result = await generate_video_smart(
                    prompt=avatar_prompt,
                    topic=topic,
                    force_model=model_id,
                    duration=min(int(dialog_duration) + 2, 12),
                    voice_mode=True
                )

                if not avatar_result.get("success"):
                    raise Exception(f"Avatar video hatası: {avatar_result.get('error')}")

                avatar_video_path = avatar_result.get("video_path")
                self.log("[CONV REELS] Avatar video üretildi")
                result["stages_completed"].append("avatar_video")

                # 3c. Lipsync uygula
                from app.cloudinary_helper import upload_video_to_cloudinary, upload_audio_to_cloudinary
                from app.sync_lipsync_helper import apply_lipsync

                video_upload = await upload_video_to_cloudinary(avatar_video_path)
                audio_upload = await upload_audio_to_cloudinary(dialog_audio_path)

                if not video_upload.get("success") or not audio_upload.get("success"):
                    raise Exception("Cloudinary upload hatası")

                self.log(f"[CONV REELS] Cloudinary upload tamamlandı, lipsync başlatılıyor...")

                lipsync_result = await apply_lipsync(
                    video_url=video_upload["url"],
                    audio_url=audio_upload["url"]
                )

                if not lipsync_result.get("success"):
                    raise Exception(f"Lipsync hatası: {lipsync_result.get('error')}")

                conversation_video_path = lipsync_result.get("video_path")
                result["lipsync_applied"] = True
                self.log("[CONV REELS] Lipsync uygulandı")
                result["stages_completed"].append("lipsync")

            result["stages_completed"].append("conversation_video")

            # ========== STAGE 4: B-roll Voiceover (TTS önce) ==========
            self.log("[CONV REELS] Aşama 4: B-roll voiceover...")

            from app.openai_tts_helper import generate_speech_with_retry
            from app.config import settings
            from app.video_styles import should_use_cartoon_voices

            # Stil bazlı narrator voice seçimi
            if should_use_cartoon_voices(visual_style):
                narrator_voice = settings.openai_tts_voice_cartoon_female
                self.log(f"[CONV REELS] Cartoon narrator voice kullanılıyor")
            else:
                narrator_voice = settings.openai_tts_voice_narrator
                self.log(f"[CONV REELS] Realistic narrator voice kullanılıyor")

            broll_audio_result = await generate_speech_with_retry(
                text=broll_voiceover,
                voice_id=narrator_voice,
                max_retries=3
            )

            if broll_audio_result.get("success"):
                broll_audio_path = broll_audio_result.get("audio_path")
                # TTS süresini ölç
                from app.instagram_helper import get_audio_duration
                tts_duration = await get_audio_duration(broll_audio_path)
                # Sora duration: 8 veya 12 (4'ün katları)
                if tts_duration <= 6:
                    broll_video_duration = 8
                elif tts_duration <= 10:
                    broll_video_duration = 12
                else:
                    broll_video_duration = 12  # max
                self.log(f"[CONV REELS] TTS süresi: {tts_duration:.1f}s → Video: {broll_video_duration}s")
            else:
                self.log(f"[CONV REELS] B-roll voiceover başarısız, sessiz B-roll kullanılacak")
                broll_audio_path = None
                broll_video_duration = 8  # fallback

            result["stages_completed"].append("broll_voiceover")

            # ========== STAGE 5: B-roll Video (TTS süresine göre dinamik) ==========
            self.log(f"[CONV REELS] Aşama 5: B-roll video üretimi (Sora {broll_video_duration}s)...")

            # Import Sora for B-roll (her zaman Sora kullanılır)
            from app.sora_helper import generate_video_sora

            broll_video_result = await generate_video_sora(
                prompt=broll_prompt,
                duration=broll_video_duration,  # Dinamik süre
                size="720x1280"  # 9:16 aspect ratio
            )

            if not broll_video_result.get("success"):
                raise Exception(f"B-roll video hatası: {broll_video_result.get('error')}")

            broll_video_path = broll_video_result.get("video_path")
            self.log(f"[CONV REELS] B-roll video üretildi")
            result["stages_completed"].append("broll_video")

            # ========== STAGE 6: B-roll Merge ==========
            self.log("[CONV REELS] Aşama 6: B-roll merge...")

            from app.instagram_helper import merge_audio_video
            from app.audio_utils import add_silence_prefix

            if broll_audio_path:
                # Add delay to B-roll audio (standard 1.5s silence at start)
                self.log(f"[CONV REELS] B-roll audio'ya {BROLL_AUDIO_DELAY}s delay ekleniyor...")
                try:
                    delayed_broll_audio = await add_silence_prefix(
                        audio_path=broll_audio_path,
                        silence_duration=BROLL_AUDIO_DELAY
                    )
                    self.log(f"[CONV REELS] Delay eklendi: {delayed_broll_audio}")
                except Exception as e:
                    self.log(f"[CONV REELS] Delay eklenemedi, orijinal kullanılıyor: {e}")
                    delayed_broll_audio = broll_audio_path

                broll_merge_result = await merge_audio_video(
                    video_path=broll_video_path,
                    audio_path=delayed_broll_audio,
                    target_duration=broll_video_duration
                )
                broll_final_path = broll_merge_result.get("output_path", broll_video_path)
            else:
                broll_final_path = broll_video_path

            result["stages_completed"].append("broll_merge")

            # ========== STAGE 6.5: Dynamic Freeze Frame (if needed) ==========
            # Apply freeze frame to conversation video if audio extends beyond video
            try:
                from app.subtitle_helper import extract_word_timestamps, get_last_word_end_time
                from app.instagram_helper import get_video_duration

                # Get conversation video duration
                conv_video_duration = await get_video_duration(conversation_video_path)

                # Extract audio and get last word timing
                from app.subtitle_helper import extract_audio_from_video
                conv_audio_extract = await extract_audio_from_video(conversation_video_path)

                if conv_audio_extract.get("success"):
                    whisper_result = await extract_word_timestamps(
                        conv_audio_extract["audio_path"],
                        model_size="small",
                        language="tr"
                    )

                    if whisper_result.get("success"):
                        last_word_end = get_last_word_end_time(whisper_result.get("words", []))
                        freeze_duration = calculate_freeze_duration(conv_video_duration, last_word_end)

                        if freeze_duration > 0:
                            self.log(f"[CONV REELS] Freeze frame gerekli: {freeze_duration:.1f}s (son kelime: {last_word_end:.1f}s, video: {conv_video_duration:.1f}s)")
                            conversation_video_path = await add_freeze_frame(conversation_video_path, freeze_duration)
                            self.log(f"[CONV REELS] Freeze frame eklendi")
                        else:
                            self.log(f"[CONV REELS] Freeze frame gerekmedi (son kelime: {last_word_end:.1f}s, video: {conv_video_duration:.1f}s)")
            except Exception as e:
                self.log(f"[CONV REELS] Freeze frame kontrolü başarısız: {e}")

            # ========== STAGE 7: Concat Videos ==========
            self.log("[CONV REELS] Aşama 7: Video birleştirme...")

            from app.instagram_helper import concatenate_videos_with_crossfade

            concat_result = await concatenate_videos_with_crossfade(
                video_paths=[conversation_video_path, broll_final_path],
                crossfade_duration=0.5
            )

            if not concat_result.get("success"):
                raise Exception(f"Video concat hatası: {concat_result.get('error')}")

            final_video_path = concat_result.get("output_path")
            final_duration = concat_result.get("total_duration", 15)

            self.log(f"[CONV REELS] Final video: {final_duration:.1f}s")
            result["final_duration"] = final_duration
            result["stages_completed"].append("concat")

            # ========== STAGE 8: Two-Phase Subtitle Generation ==========
            self.log("[CONV REELS] Aşama 8: İki aşamalı altyazı oluşturuluyor...")
            try:
                from app.subtitle_helper import create_subtitle_file, extract_audio_from_video, merge_ass_files
                from app.instagram_helper import add_subtitles_to_video

                conv_sub_path = None
                broll_sub_path = None
                conv_duration = 12.0  # Default fallback

                # Phase 1: Conversation Subtitle (Pure Whisper - Sora native speech)
                self.log("[CONV REELS] Phase 1: Conversation altyazısı (Pure Whisper)...")
                conv_audio = await extract_audio_from_video(conversation_video_path)

                if conv_audio.get("success"):
                    conv_duration = conv_audio.get("duration", 12.0)
                    self.log(f"[CONV REELS] Conversation audio: {conv_duration:.1f}s")

                    conv_sub = await create_subtitle_file(
                        audio_path=conv_audio["audio_path"],
                        original_script=None,  # Pure Whisper - Sora generates its own speech
                        model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
                        language="tr"
                    )

                    if conv_sub.get("success"):
                        conv_sub_path = conv_sub["ass_path"]
                        self.log(f"[CONV REELS] Conversation subtitle: {conv_sub.get('subtitle_count', 0)} satır")

                        # Subtitle verification with larger model
                        try:
                            from app.subtitle_helper import verify_and_correct_subtitles

                            initial_transcript = conv_sub.get("full_text", "")
                            if initial_transcript:
                                self.log("[CONV REELS] Altyazı doğrulanıyor (medium model)...")
                                verify_result = await verify_and_correct_subtitles(
                                    audio_path=conv_audio["audio_path"],
                                    initial_transcript=initial_transcript,
                                    model_size_verify="medium"
                                )

                                if verify_result.get("corrected"):
                                    self.log(f"[CONV REELS] Altyazı düzeltildi (benzerlik: {verify_result.get('similarity', 0):.1%})")
                                    # Regenerate ASS file with corrected transcript
                                    conv_sub = await create_subtitle_file(
                                        audio_path=conv_audio["audio_path"],
                                        original_script=verify_result["transcript"],
                                        model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
                                        language="tr"
                                    )
                                    if conv_sub.get("success"):
                                        conv_sub_path = conv_sub["ass_path"]
                                        self.log(f"[CONV REELS] Düzeltilmiş subtitle oluşturuldu")
                                else:
                                    self.log(f"[CONV REELS] Altyazı doğrulandı (benzerlik: {verify_result.get('similarity', 0):.1%})")
                        except Exception as e:
                            self.log(f"[CONV REELS] Altyazı doğrulama atlandı: {e}")
                    else:
                        self.log(f"[CONV REELS] Conversation subtitle hatası: {conv_sub.get('error')}")
                else:
                    self.log(f"[CONV REELS] Conversation audio extract hatası: {conv_audio.get('error')}")

                # Phase 2: B-roll Subtitle (TTS text - hybrid mode)
                self.log("[CONV REELS] Phase 2: B-roll altyazısı (TTS metni)...")
                if broll_audio_path:
                    broll_sub = await create_subtitle_file(
                        audio_path=broll_audio_path,  # TTS audio from Stage 5
                        original_script=broll_voiceover,  # TTS text - hybrid mode works here
                        model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
                        language="tr"
                    )

                    if broll_sub.get("success"):
                        broll_sub_path = broll_sub["ass_path"]
                        self.log(f"[CONV REELS] B-roll subtitle: {broll_sub.get('subtitle_count', 0)} satır")
                    else:
                        self.log(f"[CONV REELS] B-roll subtitle hatası: {broll_sub.get('error')}")
                else:
                    self.log("[CONV REELS] B-roll audio yok, B-roll subtitle atlanıyor")

                # Phase 3: Merge ASS files with timing offset
                if conv_sub_path or broll_sub_path:
                    self.log("[CONV REELS] Phase 3: ASS dosyaları birleştiriliyor...")

                    ass_files_to_merge = []
                    crossfade_duration = 0.5

                    if conv_sub_path:
                        ass_files_to_merge.append({"path": conv_sub_path, "offset": 0})

                    if broll_sub_path:
                        # B-roll starts at conversation_duration - crossfade
                        broll_offset = conv_duration - crossfade_duration
                        ass_files_to_merge.append({"path": broll_sub_path, "offset": broll_offset})
                        self.log(f"[CONV REELS] B-roll offset: {broll_offset:.1f}s")

                    if len(ass_files_to_merge) > 1:
                        merged_ass = merge_ass_files(ass_files_to_merge)
                        final_ass_path = merged_ass.get("ass_path") if merged_ass.get("success") else conv_sub_path
                        total_subtitle_count = merged_ass.get("subtitle_count", 0)
                    else:
                        final_ass_path = ass_files_to_merge[0]["path"] if ass_files_to_merge else None
                        total_subtitle_count = conv_sub.get("subtitle_count", 0) if conv_sub_path else broll_sub.get("subtitle_count", 0)

                    # Phase 4: Burn merged subtitles
                    if final_ass_path:
                        self.log(f"[CONV REELS] Phase 4: Subtitle burn ({total_subtitle_count} satır)...")
                        burn_result = await add_subtitles_to_video(
                            video_path=final_video_path,
                            ass_path=final_ass_path
                        )

                        if burn_result.get("success"):
                            final_video_path = burn_result["output_path"]
                            result["stages_completed"].append("subtitles")
                            self.log(f"[CONV REELS] Altyazı eklendi: {final_video_path}")
                        else:
                            self.log(f"[CONV REELS] Subtitle burn hatası: {burn_result.get('error', 'Bilinmeyen hata')}")
                else:
                    self.log("[CONV REELS] Hiçbir subtitle oluşturulamadı")

            except Exception as e:
                import traceback
                self.log(f"[CONV REELS] Altyazı hatası: {e}")
                self.log(f"[CONV REELS] Traceback: {traceback.format_exc()}")

            # Update post
            if post_id:
                update_post(
                    post_id,
                    visual_path=final_video_path,
                    total_video_duration=final_duration,
                    voice_mode=True
                )

            # ========== STAGE 9: Review & Approval ==========
            self.log("[CONV REELS] Aşama 9: Onay bekleniyor...")
            self.state = PipelineState.AWAITING_FINAL_APPROVAL

            # Hashtag string
            hashtag_str = " ".join(hashtags) if hashtags else "#Olivenet #KKTC #IoT"
            full_caption = f"{caption}\n\n{hashtag_str}"

            await self.notify_telegram(
                message=f"🎭 *CONVERSATIONAL REELS* - Onay Bekliyor\n\n"
                f"📋 *Konu:* {_escape_md(topic[:50])}...\n"
                f"💬 *Dialog:* {len(dialog_lines)} satır\n"
                f"⏱️ *Süre:* {final_duration:.0f}s\n"
                f"🗣️ *Sora Native Speech:* ✓\n\n"
                f"*Caption:*\n{_escape_md(full_caption[:200])}...",
                data={"video_path": final_video_path},
                buttons=[
                    {"text": "✅ Onayla ve Yayınla", "callback": f"conv_approve:{post_id}"},
                    {"text": "🔄 Yeniden Üret", "callback": f"conv_regenerate:{post_id}"},
                    {"text": "❌ İptal", "callback": f"conv_cancel:{post_id}"}
                ]
            )

            result["success"] = True
            result["awaiting_approval"] = True
            result["final_video_path"] = final_video_path
            result["caption"] = full_caption
            result["stages_completed"].append("awaiting_approval")

            self.log("[CONV REELS] Pipeline tamamlandı - onay bekleniyor")
            return result

        except Exception as e:
            self.log(f"[CONV REELS] Pipeline hatası: {str(e)}")
            self.state = PipelineState.ERROR
            result["error"] = str(e)
            result["final_state"] = self.state.value

            await self.notify_telegram(
                message=f"❌ *CONVERSATIONAL REELS* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def publish_conversational_reels(self, post_id: int) -> Dict[str, Any]:
        """Conversational Reels publish — v2 ConversationalPipeline'a delege eder"""
        from app.production.conversational_pipeline import ConversationalPipeline
        cvp = ConversationalPipeline(telegram_callback=self.telegram_callback)
        return await cvp.publish(post_id=post_id)

    async def _publish_conversational_reels_original(self, post_id: int) -> Dict[str, Any]:
        """Orijinal publish — yedek"""
        from app.database.crud import get_post, update_post

        result = {
            "success": False,
            "post_id": post_id,
            "instagram_post_id": None,
            "error": None
        }

        try:
            # Database'den post bilgilerini al
            post = get_post(post_id)
            if not post:
                raise Exception(f"Post bulunamadı: {post_id}")

            video_path = post.get("visual_path")
            caption = post.get("post_text_ig") or post.get("post_text", "")

            if not video_path:
                raise Exception(f"Video yolu bulunamadı: post_id={post_id}")

            self.log(f"[CONV REELS PUBLISH] Post {post_id} yayınlanıyor...")
            self.log(f"[CONV REELS PUBLISH] Video: {video_path}")

            # Instagram'a yayınla
            publish_result = await self.publisher.execute({
                "action": "publish",
                "post_id": post_id,
                "post_text": caption,
                "post_text_ig": caption,
                "video_path": video_path,
                "platform": "instagram"
            })

            if publish_result.get("success"):
                result["success"] = True
                result["instagram_post_id"] = publish_result.get("instagram_post_id")

                self.log(f"[CONV REELS PUBLISH] Başarıyla yayınlandı! IG: {publish_result.get('instagram_post_id')}")

                await self.notify_telegram(
                    message=f"🎉 *CONVERSATIONAL REELS* - Yayınlandı!\n\n"
                    f"📋 Post ID: {post_id}\n"
                    f"📸 IG Post: {publish_result.get('instagram_post_id', 'N/A')}",
                    data=publish_result,
                    buttons=[]
                )
            else:
                raise Exception(f"Publish hatası: {publish_result.get('error')}")

            return result

        except Exception as e:
            self.log(f"[CONV REELS PUBLISH] Hata: {str(e)}")
            result["error"] = str(e)

            await self.notify_telegram(
                message=f"❌ *CONVERSATIONAL REELS PUBLISH* - Hata\n\n{_escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
