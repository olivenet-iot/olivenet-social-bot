"""
Pipeline Manager - Agent iş akışını yönetir
Semi-autonomous mod: Her aşamada Telegram onayı bekler
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from enum import Enum

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

    async def run_daily_content(self) -> Dict[str, Any]:
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

🎯 *Konu:* {topic_result.get('topic', 'N/A')}
📂 *Kategori:* {topic_result.get('category', 'N/A')}
🎨 *Görsel:* {topic_result.get('suggested_visual', 'N/A')}
⏰ *Önerilen Saat:* {topic_result.get('best_time', 'N/A')}

💡 *Neden bu konu?*
{topic_result.get('reasoning', 'N/A')}

🪝 *Hook Önerileri:*
{chr(10).join(['• ' + h for h in topic_result.get('suggested_hooks', [])])}
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

{content_result.get('post_text', 'N/A')}

---
📊 *Detaylar:*
- Kelime sayısı: {content_result.get('word_count', 'N/A')}
- Emoji sayısı: {content_result.get('emoji_count', 'N/A')}
- Ton: {content_result.get('tone', 'N/A')}
- Hook: {content_result.get('hook_used', 'N/A')}
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

            # Görsel üret
            self.log(f"Görsel üretiliyor ({visual_type})...")

            image_path = None
            video_path = None

            if visual_type == "flux":
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
                from app.gemini_helper import generate_image_gemini
                visual_result = await generate_image_gemini(
                    prompt=visual_prompt_result.get("visual_prompt")
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
                # render_html_to_png direkt path döndürür
                image_path = await render_html_to_png(html)
                visual_result = {"success": True, "image_path": image_path}

            self.current_data["visual_result"] = {
                "image_path": image_path,
                "video_path": video_path,
                "visual_type": visual_type
            }

            # Görsel üretimi başarısız olduysa hata ver
            if not image_path and not video_path:
                error_msg = visual_result.get("error", "Görsel üretilemedi") if visual_result else "Görsel üretilemedi"
                self.log(f"Görsel üretim hatası: {error_msg}")
                await self.notify_telegram(
                    message=f"❌ Görsel üretim hatası: {error_msg}",
                    buttons=[
                        {"text": "🔄 Tekrar Dene", "callback": "retry_visual"},
                        {"text": "🎨 Tip Değiştir", "callback": "change_visual_type"},
                        {"text": "❌ İptal", "callback": "cancel"}
                    ]
                )
                self.state = PipelineState.AWAITING_VISUAL_APPROVAL
                approval = await self.wait_for_approval()
                if approval.get("action") == "cancel":
                    return {"success": False, "reason": "Görsel üretilemedi"}
                # retry_visual ve change_visual_type için ayrı handler gerekli
                return {"success": False, "reason": error_msg, "retry_available": True}

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

            # ========== AŞAMA 4: Review ==========
            self.log("Aşama 4: Kalite kontrol...")
            self.state = PipelineState.REVIEWING

            review_result = await self.reviewer.execute({
                "action": "review_post",
                "post_text": content_result.get("post_text"),
                "topic": topic_result.get("topic"),
                "post_id": content_result.get("post_id")
            })

            self.current_data["review"] = review_result
            result["stages_completed"].append("review")

            # ========== AŞAMA 5: Final Onay ==========
            self.state = PipelineState.AWAITING_FINAL_APPROVAL

            score = review_result.get("total_score", 0)
            decision = review_result.get("decision", "revise")

            await self.notify_telegram(
                message=f"""
✅ *Final Onay*

📊 *Review Sonucu:*
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
                    {"text": "✏️ Revize Et", "callback": "revise"},
                    {"text": "❌ İptal", "callback": "cancel"}
                ]
            )

            approval = await self.wait_for_approval()

            if approval.get("action") == "cancel":
                self.state = PipelineState.IDLE
                return {"success": False, "reason": "Kullanıcı iptal etti"}

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
                    "platform": "facebook"
                })

                if publish_result.get("success"):
                    result["stages_completed"].append("published")
                    result["success"] = True

                    await self.notify_telegram(
                        message=f"""
🎉 *YAYINLANDI!*

✅ Post başarıyla Facebook'a gönderildi.

📊 Post ID: {publish_result.get('facebook_post_id', 'N/A')}
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
                message=f"❌ *Pipeline Hatası*\n\n{str(e)}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
