"""
Reels Pipeline - Instagram Reels içerik üretim pipeline'ı.
pipeline.py'daki run_reels_content metodundan extract edilmiştir.
"""

from datetime import datetime
from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState, escape_md
from app.database import save_prompt
from app.database.crud import update_post, update_opportunity
from app.video_models import get_max_duration


class ReelsPipeline(BasePipeline):
    """Instagram Reels üretim pipeline'ı."""

    def __init__(self, telegram_callback=None):
        super().__init__("reels", telegram_callback)

    async def run(self, topic=None, force_model=None, manual_topic_mode=False, visual_style="cinematic_4k", viral_format=None, hook_type=None, opportunity=None, content_tone="educational") -> Dict[str, Any]:
        """
        Instagram Reels içeriği üret ve yayınla
        Sora 2 Pro → Sora 2 → Kling 3.0 fallback zinciri ile

        Args:
            topic: Konu (None ise Planner'dan alınır)
            force_model: Model zorla ("sora-2", "sora-2-pro", "kling_v3_pro")
            manual_topic_mode: Manuel konu modu (planner atlanır)
            visual_style: Görsel stil (cinematic_4k, anime, vb.)
            viral_format: Planlanmış viral format (pov, myth_busting, etc.)
            hook_type: Planlanmış hook tipi (statistic, question, etc.)

        Returns:
            Pipeline sonucu
        """
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
                message=f"🎬 *REELS MOD* - Başlatıldı\n\nKonu: {escape_md(topic[:80])}...",
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
                "visual_type": "video",
                "content_tone": content_tone,
                "news_context": self._build_news_context(opportunity) if opportunity else None,
            })

            if "error" in content_result:
                raise Exception(f"Creator error: {content_result['error']}")

            self.current_data["content"] = content_result
            result["stages_completed"].append("caption")
            result["post_id"] = content_result.get("post_id")

            self.log(f"[REELS] Caption: IG {content_result.get('ig_word_count', 0)} kelime")

            # Persist tone to DB
            if content_result.get("post_id") and content_tone:
                update_post(content_result["post_id"], tone=content_tone)

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
                "hook_type": hook_type,
                "content_tone": content_tone,
                "news_context": self._build_news_context(opportunity) if opportunity else None,
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
                else:  # Sora veya default
                    return prompt_result.get("video_prompt_sora") or prompt_result.get("video_prompt_kling3", "")

            recommended_model = reels_prompt_result.get("recommended_model", "kling_v3_pro")
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
                "post_id": content_result.get("post_id"),
                "content_tone": content_tone,
                "news_context": self._build_news_context(opportunity) if opportunity else None
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

                # Persist metadata to DB
                post_id = content_result.get("post_id")
                if post_id:
                    update_post(post_id, video_model=model_used, visual_path=video_path)
                    if opportunity:
                        update_opportunity(opportunity["id"], status="used",
                                          used_at=datetime.utcnow().isoformat(),
                                          post_id=post_id)

                await self.notify_telegram(
                    message=f"🎉 *REELS* - Yayınlandı!\n\n"
                    f"📝 Konu: {escape_md(topic[:50])}...\n"
                    f"🎥 Model: {escape_md(model_used)}\n"
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
                message=f"❌ *REELS* - Hata\n\n{escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
