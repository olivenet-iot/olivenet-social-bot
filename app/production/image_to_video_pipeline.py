"""
Image-to-Video Pipeline - Referans görsel → Kling i2v ile canlandırma

Bir content_opportunity'yi alıp:
1. Nano Banana Pro ile referans görsel üretir
2. Kling i2v ile bu görseli canlandırır
Premium hybrid pipeline (~$1.80).

Pipeline akışı:
1. Caption yazımı (Creator)
2. Image + animation prompt (Creator)
3. Referans görsel üretimi (Nano Banana Pro)
4. Video üretimi (Kling i2v)
5. Kalite kontrol (Reviewer)
6. Yayın (Publisher)
"""

from datetime import datetime
from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState
from app.production.quality_gate import QualityGate
from app.utils.logger import get_logger
from app.database import save_prompt
from app.database.crud import update_opportunity, update_post
from app.video_models import get_model_config, validate_duration, get_max_duration

logger = get_logger("image_to_video")


class ImageToVideoPipeline(BasePipeline):
    """Referans görsel → Kling i2v ile canlandırma."""

    def __init__(self, telegram_callback=None):
        super().__init__("image_to_video", telegram_callback)
        self.quality_gate = QualityGate(min_score=7.0, autonomous_min=6.5)

    async def run(
        self,
        opportunity: Dict,
        model_id: str = "kling-3.0-pro",
        target_duration: int = 5,
        visual_style: str = "cinematic_4k",
        autonomous: bool = True,
        content_tone: str = "news_commentary",
        content_concept: str = None,
        inspiration_source: str = None,
    ) -> Dict[str, Any]:
        """
        Haber fırsatını referans görsel + video'ya çevir.

        Args:
            opportunity: content_opportunities tablosundan gelen dict
            model_id: Kling model (pro veya std)
            target_duration: Hedef video süresi (5 veya 10s)
            visual_style: Video görsel stili
            autonomous: True ise Telegram onayı beklemez
            content_tone: İçerik tonu

        Returns:
            {"success": bool, "post_id": int, ...}
        """
        opp_id = opportunity["id"]
        title = opportunity.get("title", "")
        summary = opportunity.get("summary", "")
        olivenet_angle = opportunity.get("olivenet_angle", "")
        hook_suggestion = opportunity.get("hook_suggestion", "")
        source_name = opportunity.get("source_name", "")

        # Model config
        model_config = get_model_config(model_id)
        model_name = model_config.get("name", model_id)
        max_duration = get_max_duration(model_id)
        target_duration = min(target_duration, max_duration)
        target_duration = validate_duration(model_id, target_duration)

        self.log(f"Image-to-Video Pipeline baslatildi: '{title[:50]}...' (model: {model_name})")
        self.state = PipelineState.CREATING_CONTENT

        news_context = self._build_news_context(opportunity, content_concept, inspiration_source)

        result = {
            "success": False,
            "stages_completed": [],
            "opportunity_id": opp_id,
            "model_id": model_id,
            "model_name": model_name,
            "target_duration": target_duration,
        }

        try:
            # ========== 1. CAPTION ==========
            self.log("Asama 1/6: Caption uretiliyor...")

            content_result = await self.creator.execute({
                "action": "create_post_multiplatform",
                "topic": title,
                "category": "haber",
                "visual_type": "video",
                "news_context": news_context,
                "content_tone": content_tone,
                "content_concept": content_concept,
                "inspiration_source": inspiration_source,
            })

            if "error" in content_result:
                raise Exception(f"Caption error: {content_result['error']}")

            result["post_id"] = content_result.get("post_id")
            result["stages_completed"].append("caption")

            if content_result.get("post_id") and content_tone:
                update_post(content_result["post_id"], tone=content_tone)

            # ========== 2. IMAGE + ANIMATION PROMPT ==========
            self.log("Asama 2/6: Image + animation prompt olusturuluyor...")
            self.state = PipelineState.CREATING_VISUAL

            prompt_result = await self.creator.execute({
                "action": "create_image_and_animation_prompt",
                "topic": title,
                "post_text_ig": content_result.get("post_text_ig", ""),
                "content_tone": content_tone,
                "news_context": news_context,
                "visual_style": visual_style,
                "content_concept": content_concept,
                "inspiration_source": inspiration_source,
            })

            if not prompt_result.get("success"):
                raise Exception(f"i2v prompt error: {prompt_result.get('error')}")

            image_prompt = prompt_result.get("image_prompt", "")
            animation_prompt = prompt_result.get("animation_prompt", "")

            if not image_prompt or not image_prompt.strip():
                raise Exception("Image prompt bos!")
            if not animation_prompt or not animation_prompt.strip():
                raise Exception("Animation prompt bos!")

            result["stages_completed"].append("i2v_prompt")

            # Save prompts to DB
            if content_result.get("post_id"):
                save_prompt(
                    post_id=content_result["post_id"],
                    prompt_text=image_prompt,
                    prompt_type='image',
                    style='i2v_reference'
                )

            # ========== 3. REFERENCE IMAGE GENERATION ==========
            self.log("Asama 3/6: Referans gorsel uretiliyor...")

            from app.nano_banana_helper import generate_image

            image_result = await generate_image(
                prompt=image_prompt,
                aspect_ratio="9:16",  # Reels format
            )

            if not image_result.get("success"):
                raise Exception(f"Reference image generation failed: {image_result.get('error')}")

            ref_image_path = image_result.get("image_path")
            result["stages_completed"].append("reference_image")
            self.log(f"Referans gorsel hazir: {ref_image_path}")

            # ========== 4. VIDEO FROM IMAGE ==========
            self.log(f"Asama 4/6: Video uretiliyor ({model_name}, i2v)...")

            # Upload reference image to CDN for fal.ai access
            from app.instagram_helper import upload_image_to_cdn
            cdn_result = upload_image_to_cdn(ref_image_path)

            if not cdn_result or not cdn_result.get("success", True):
                raise Exception(f"CDN upload failed: {cdn_result}")

            image_url = cdn_result.get("url") or cdn_result.get("image_url")
            if not image_url:
                raise Exception("CDN upload returned no URL")

            self.log(f"Referans gorsel CDN'e yuklendi: {image_url[:60]}...")

            # Save animation prompt
            if content_result.get("post_id"):
                save_prompt(
                    post_id=content_result["post_id"],
                    prompt_text=animation_prompt,
                    prompt_type='video',
                    style=visual_style
                )

            from app.sora_helper import generate_video_from_image_smart

            video_result = await generate_video_from_image_smart(
                image_url=image_url,
                prompt=animation_prompt,
                model_id=model_id,
                duration=target_duration,
                aspect_ratio="9:16",
            )

            if not video_result.get("success"):
                raise Exception(f"i2v video generation failed: {video_result.get('error')}")

            video_path = video_result.get("video_path")
            result["stages_completed"].append("video_generation")
            result["model_used"] = video_result.get("model_used", model_id)
            self.log(f"i2v video hazir: {video_path}")

            # ========== 5. REVIEW ==========
            self.log("Asama 5/6: Kalite kontrol...")
            self.state = PipelineState.REVIEWING

            post_text = content_result.get("post_text_ig", content_result.get("post_text", ""))

            if autonomous:
                gate_result = await self.quality_gate.review_and_revise(
                    reviewer=self.reviewer,
                    creator=self.creator,
                    post_text=post_text,
                    topic=title,
                    is_autonomous=True,
                    content_tone=content_tone,
                    news_context=news_context
                )

                if gate_result["passed"]:
                    self.log(f"Review gecti (skor: {gate_result['score']})")
                    post_text = gate_result.get("post_text", post_text)

                    # ========== 6. PUBLISH ==========
                    self.log("Asama 6/6: Yayinlaniyor...")
                    self.state = PipelineState.PUBLISHING

                    publish_result = await self.publisher.execute({
                        "action": "publish",
                        "post_id": content_result.get("post_id"),
                        "video_path": video_path,
                        "post_text": post_text,
                        "platform": "instagram"
                    })

                    if publish_result.get("success"):
                        result["success"] = True
                        result["stages_completed"].append("published")
                        update_opportunity(opp_id, status="used", used_at=datetime.utcnow().isoformat(),
                                         post_id=content_result.get("post_id"))
                        model_used = video_result.get("model_used", model_id)
                        update_post(content_result.get("post_id"), video_model=model_used,
                                    visual_path=video_path)
                        self.log("Yayinlandi!")
                    else:
                        raise Exception(f"Publish error: {publish_result.get('error')}")
                else:
                    self.log(f"Review basarisiz (skor: {gate_result['score']})")
                    result["review_failed"] = True
                    update_opportunity(opp_id, status="ready")
            else:
                await self.notify_telegram(
                    message=f"Image-to-Video hazir!\n\nKonu: {title[:60]}\nSkor: Review bekleniyor",
                    data={"post_id": content_result.get("post_id"), "video": video_path}
                )
                result["stages_completed"].append("awaiting_approval")

            self.state = PipelineState.COMPLETED
            result["final_video"] = video_path
            result["reference_image"] = ref_image_path

        except Exception as e:
            result = await self.handle_error(e, "image_to_video")
            result["opportunity_id"] = opp_id
            update_opportunity(opp_id, status="ready")

        return result
