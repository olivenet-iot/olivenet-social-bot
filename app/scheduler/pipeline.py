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
    num_shots = max(1, target_duration // 4)  # Her 4s = 1 shot
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
        """Günlük içerik pipeline'ı çalıştır"""
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
                self.log(f"Manuel konu kullanılıyor: {topic}, görsel: {visual_type or 'infographic'}")
                topic_result = {
                    "topic": topic,
                    "category": "manuel",
                    "suggested_visual": visual_type or "infographic",
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
        """Plana göre otonom içerik üret ve paylaş"""
        topic = plan.get('topic_suggestion', 'Genel IoT konusu')
        self.log(f"Planlı içerik üretiliyor: {topic[:50]}...")

        result = {
            "success": False,
            "stages_completed": [],
            "post_id": None
        }

        try:
            category = plan.get('topic_category', 'egitici')
            visual_type = plan.get('visual_type_suggestion', 'flux')

            # ========== CONTENT TYPE ROUTING ==========
            # Reels/video içerik için özel pipeline kullan
            if visual_type in ["reels", "video"]:
                self.log(f"[ROUTING] Reels pipeline'a yönlendiriliyor: {topic[:50]}...")
                return await self.run_reels_content(topic=topic)

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

    async def run_reels_content(self, topic: str = None, force_model: str = None, manual_topic_mode: bool = False, visual_style: str = "cinematic_4k") -> Dict[str, Any]:
        """
        Instagram Reels içeriği üret ve yayınla
        Sora 2 Pro → Sora 2 → Veo 3 fallback zinciri ile

        Args:
            topic: Konu (None ise Planner'dan alınır)
            force_model: Model zorla ("sora-2", "sora-2-pro", "veo3")
            manual_topic_mode: Manuel konu modu (planner atlanır)
            visual_style: Görsel stil (cinematic_4k, anime, vb.)

        Returns:
            Pipeline sonucu
        """
        mode_text = "Manuel Konu" if manual_topic_mode else "Otomatik"
        self.log(f"REELS MOD ({mode_text}): Pipeline başlatılıyor...")
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
                "visual_style": visual_style
            })

            if not reels_prompt_result.get("success"):
                raise Exception(f"Reels prompt error: {reels_prompt_result.get('error', 'Unknown')}")

            self.current_data["reels_prompt"] = reels_prompt_result
            result["stages_completed"].append("video_prompt")

            # Model'e göre doğru prompt'u seç
            def get_video_prompt_for_model(prompt_result: dict, model: str) -> str:
                """Model'e göre optimize edilmiş prompt seç"""
                if model == "wan_26":
                    return prompt_result.get("video_prompt_wan") or prompt_result.get("video_prompt_veo", "")
                elif model and model.startswith("hailuo"):
                    return prompt_result.get("video_prompt_hailuo") or prompt_result.get("video_prompt_kling", "")
                elif model and model.startswith("kling"):
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
            self.log("[REELS] Aşama 4: Video üretiliyor...")

            from app.sora_helper import generate_video_smart

            # model_to_use zaten yukarıda tanımlandı (prompt seçimi için)
            video_result = await generate_video_smart(
                prompt=video_prompt,
                topic=topic,
                force_model=model_to_use
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
        """
        Sesli Instagram Reels içeriği üret ve yayınla.

        ElevenLabs TTS + Video + FFmpeg merge pipeline.
        Multi-model desteği: Sora 2, Veo 2, Kling 2.1, Wan 2.1, Minimax

        Pipeline Akışı:
        1. Konu seçimi (Planner) veya manuel konu işleme (Creator)
        2. Caption üretimi (Creator)
        3. Speech script üretimi (Creator)
        4. TTS ses üretimi (ElevenLabs)
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
            model_id: Video model ID (sora-2, veo-2, kling-2.1, wan-2.1, minimax)
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
                from app.elevenlabs_helper import generate_speech_with_retry, ElevenLabsError, QuotaExceededError

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
                            message=f"⚠️ *ElevenLabs Kota Aşıldı*\n\nSessiz video ile devam ediliyor...",
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
        carousel_type: str = "html",
        manual_topic: str = None
    ) -> Dict[str, Any]:
        """
        Instagram Carousel içerik üretim pipeline'ı.

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
                score = comparison_result.get(f"variant_{winner.lower()}_scores", {}).get("total", 7)
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
        total_duration: int = 30,
        segment_duration: int = 10,
        model_id: str = "kling-2.6-pro",
        transition_type: str = "crossfade",
        transition_duration: float = 0.5,
        manual_topic_mode: bool = False,
        visual_style: str = "cinematic_4k"
    ) -> Dict[str, Any]:
        """
        Multi-segment uzun video pipeline.

        Birden fazla video segmenti üretip birleştirerek 20-60 saniyelik
        uzun videolar oluşturur.

        Pipeline Akışı:
        1. Konu seçimi (Planner/Creator)
        2. Caption üretimi (Creator)
        3. Speech script üretimi (30s için)
        4. TTS ses üretimi (ElevenLabs)
        5. Multi-scene prompt üretimi (Creator)
        6. Paralel video üretimi (N segment)
        7. Video birleştirme (FFmpeg crossfade)
        8. Audio-video merge (FFmpeg)
        9. Kalite kontrol (Reviewer)
        10. Instagram Reels yayını (Publisher)

        Args:
            topic: Konu (None ise Planner'dan alınır)
            total_duration: Toplam video süresi (20-60 saniye)
            segment_duration: Her segment süresi (10 saniye default)
            model_id: Video model ID (kling-2.6-pro, sora-2, veo-2, wan-2.1)
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
        from app.elevenlabs_helper import ElevenLabsHelper
        from app.database.crud import create_post, update_post

        # Model'in max süresine göre segment duration'ı dinamik ayarla
        model_max_duration = get_max_duration(model_id)
        actual_segment_duration = min(segment_duration, model_max_duration)

        # Segment sayısını hesapla (yeni segment süresine göre)
        segment_count = max(2, min(6, total_duration // actual_segment_duration))
        actual_total_duration = segment_count * actual_segment_duration

        self.log(f"🎬 UZUN VIDEO: Pipeline başlatılıyor...")
        self.log(f"   Model max süre: {model_max_duration}s → Segment: {actual_segment_duration}s")
        self.log(f"   Toplam süre: {actual_total_duration}s ({segment_count} segment x {actual_segment_duration}s)")
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
            "total_duration": actual_total_duration,
            "model_id": model_id
        }

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
                "category": topic_data.get("category", "tanitim")
            })

            caption = content_result.get("post_text_ig") or content_result.get("post_text", "")
            post_id = content_result.get("post_id")

            self.log(f"[LONG VIDEO] Caption oluşturuldu (Post ID: {post_id})")
            result["stages_completed"].append("caption_creation")
            result["post_id"] = post_id

            # ========== AŞAMA 3: Speech Script Üretimi ==========
            self.log(f"[LONG VIDEO] Aşama 3: Voiceover scripti üretiliyor ({actual_total_duration}s)...")

            # Kelime hedefi: ~1.9 kelime/saniye (ElevenLabs gerçek ölçümü)
            target_words = int(actual_total_duration * 1.9)

            speech_result = await self.creator.execute({
                "action": "create_speech_script",
                "topic": topic,
                "target_duration": actual_total_duration,
                "target_words": target_words,
                "segment_count": segment_count,
                "segment_duration": actual_segment_duration,
                "tone": "friendly",  # Samimi ton (voice reels ile aynı)
                "post_id": post_id
            })

            if not speech_result.get("success"):
                raise Exception(f"Speech script hatası: {speech_result.get('error')}")

            speech_script = speech_result.get("speech_script", "")
            self.log(f"[LONG VIDEO] Script: {len(speech_script.split())} kelime")
            result["stages_completed"].append("speech_script")

            # ========== AŞAMA 4: TTS Ses Üretimi ==========
            self.log("[LONG VIDEO] Aşama 4: TTS ses üretiliyor...")

            # Voice reels ile aynı fonksiyon - ENV'deki voice ID'yi kullanır
            from app.elevenlabs_helper import generate_speech_with_retry
            tts_result = await generate_speech_with_retry(
                text=speech_script,
                max_retries=3
            )

            if not tts_result.get("success"):
                raise Exception(f"TTS hatası: {tts_result.get('error')}")

            audio_path = tts_result.get("audio_path")
            estimated_duration = tts_result.get("duration", actual_total_duration)

            # GERÇEK audio süresini ffprobe ile ölç (Voice Reels ile aynı)
            from app.instagram_helper import get_audio_duration
            actual_audio_duration = await get_audio_duration(audio_path)
            self.log(f"[LONG VIDEO] TTS süre - Tahmini: {estimated_duration:.1f}s, Gerçek: {actual_audio_duration:.1f}s")

            # Gerçek süreyi kullan (tahmini değil)
            audio_duration = actual_audio_duration if actual_audio_duration > 0 else estimated_duration

            self.log(f"[LONG VIDEO] Ses üretildi: {audio_duration:.1f}s")
            result["stages_completed"].append("tts_generation")
            result["audio_duration"] = audio_duration

            # ========== AŞAMA 5: Multi-Scene Prompt Üretimi ==========
            self.log(f"[LONG VIDEO] Aşama 5: {segment_count} sahne promptu üretiliyor...")

            # Shot structure'ı çıkar
            shot_structure = extract_shot_structure(speech_script, actual_total_duration)

            scene_result = await self.creator.execute({
                "action": "create_multi_scene_prompts",
                "topic": topic,
                "segment_count": segment_count,
                "segment_duration": actual_segment_duration,
                "speech_structure": shot_structure,
                "model_id": model_id,
                "visual_style": visual_style
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
        visual_style: str = "cinematic_4k"
    ) -> Dict[str, Any]:
        """
        Conversational Reels pipeline with Sora native speech.

        Creates two-character dialog video (male problem, female solution)
        followed by B-roll segment with voiceover.

        Pipeline Steps (Simplified):
        1. Topic selection (Planner/manual)
        2. Conversation content generation (Creator)
        3. Conversation video generation (Sora 12s - native Turkish speech)
        4. B-roll video generation (Sora 10s)
        5. B-roll voiceover generation (ElevenLabs narrator)
        6. B-roll merge (FFmpeg)
        7. Concat conversation + B-roll
        8. Whisper transcription + subtitles
        9. Review + Publish

        Note: Sora natively generates Turkish dialog with lip-sync.
        No TTS or Lipsync API needed.

        Args:
            topic: Topic (None uses Planner suggestion)
            manual_topic_mode: Process topic through Creator if True
            visual_style: Görsel stil (cinematic_4k, anime, vb.)

        Returns:
            Pipeline result dict
        """
        self.log("[CONV REELS] Pipeline başlatılıyor...")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "conversational_reels": True,
            "topic": topic
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

            # ========== STAGE 2: Conversation Content ==========
            self.log("[CONV REELS] Aşama 2: Dialog içeriği oluşturuluyor...")
            self.state = PipelineState.CREATING_CONTENT

            conv_result = await self.creator.execute({
                "action": "create_conversation_content",
                "topic": topic,
                "category": category,
                "target_duration": 12,  # ~12 seconds dialog (Sora max)
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

            # ========== STAGE 3: Conversation Video (Sora Native Speech) ==========
            self.log("[CONV REELS] Aşama 3: Conversation video üretimi (Sora 12s)...")
            self.state = PipelineState.CREATING_VISUAL

            from app.sora_helper import generate_video_sora

            conversation_result = await generate_video_sora(
                prompt=video_prompt,
                duration=12,  # Sora max duration
                size="720x1280"
            )

            if not conversation_result.get("success"):
                raise Exception(f"Conversation video hatası: {conversation_result.get('error')}")

            conversation_video_path = conversation_result.get("video_path")
            self.log(f"[CONV REELS] Conversation video üretildi: {conversation_video_path}")
            result["stages_completed"].append("conversation_video")
            result["sora_native_speech"] = True

            # ========== STAGE 4: B-roll Voiceover (TTS önce) ==========
            self.log("[CONV REELS] Aşama 4: B-roll voiceover...")

            from app.elevenlabs_helper import generate_speech_with_retry
            from app.config import settings

            broll_audio_result = await generate_speech_with_retry(
                text=broll_voiceover,
                voice_id=settings.elevenlabs_voice_id_narrator,  # Narrator voice for B-roll
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

            if broll_audio_path:
                broll_merge_result = await merge_audio_video(
                    video_path=broll_video_path,
                    audio_path=broll_audio_path,
                    target_duration=broll_video_duration
                    # keep_video_duration kaldırıldı - artık süreler uyumlu
                )
                broll_final_path = broll_merge_result.get("output_path", broll_video_path)
            else:
                broll_final_path = broll_video_path

            result["stages_completed"].append("broll_merge")

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
        """Conversational Reels'i Instagram'a yayınla (Telegram onayı sonrası)"""
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
