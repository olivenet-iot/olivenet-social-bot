"""
Post Pipeline - Günlük içerik üretim pipeline'ı.
ContentPipeline.run_daily_content() metodundan extract edilmiştir.
"""

from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState, escape_md
from app.database import save_prompt


class PostPipeline(BasePipeline):
    """Günlük post üretim pipeline'ı."""

    def __init__(self, telegram_callback=None):
        super().__init__("post", telegram_callback)

    async def run(self, topic=None, manual_topic_mode=False, visual_type=None) -> Dict[str, Any]:
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

🎯 *Konu:* {escape_md(topic_result.get('topic', 'N/A'))}
📂 *Kategori:* {escape_md(topic_result.get('category', 'N/A'))}
🎨 *Görsel:* {escape_md(topic_result.get('suggested_visual', 'N/A'))}
⏰ *Önerilen Saat:* {escape_md(topic_result.get('best_time', 'N/A'))}

💡 *Neden bu konu?*
{escape_md(topic_result.get('reasoning', 'N/A'))}

🪝 *Hook Önerileri:*
{chr(10).join(['• ' + escape_md(h) for h in topic_result.get('suggested_hooks', [])])}
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
                return await self.run()

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

{escape_md(content_result.get('post_text', 'N/A'))}

---
📊 *Detaylar:*
- Kelime sayısı: {escape_md(content_result.get('word_count', 'N/A'))}
- Emoji sayısı: {escape_md(content_result.get('emoji_count', 'N/A'))}
- Ton: {escape_md(content_result.get('tone', 'N/A'))}
- Hook: {escape_md(content_result.get('hook_used', 'N/A'))}
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
                            message=f"❌ Görsel üretim hatası: {escape_md(error_msg)}",
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
                message=f"❌ *Pipeline Hatası*\n\n{escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
