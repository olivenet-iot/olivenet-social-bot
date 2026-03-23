"""
Image Post Pipeline - Tek görsel post üretimi

Bir content_opportunity'yi alıp, Olivenet perspektifinden
çarpıcı tek görsel + caption'a çevirir. Nano Banana Pro ile
görsel üretir — en hızlı ve ucuz pipeline (~$0.10).

Pipeline akışı:
1. Caption yazımı (Creator)
2. Image prompt + görsel üretimi (Creator + Nano Banana Pro)
3. Kalite kontrol (Reviewer)
4. Yayın (Publisher)
"""

from datetime import datetime
from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState
from app.production.quality_gate import QualityGate
from app.utils.logger import get_logger
from app.database import save_prompt
from app.database.crud import update_opportunity, update_post

logger = get_logger("image_post")


class ImagePostPipeline(BasePipeline):
    """Tek görsel post — AI image + caption, autonomous."""

    def __init__(self, telegram_callback=None):
        super().__init__("image_post", telegram_callback)
        self.quality_gate = QualityGate(min_score=7.0, autonomous_min=6.5)

    async def run(
        self,
        opportunity: Dict,
        aspect_ratio: str = "1:1",
        autonomous: bool = True,
        content_tone: str = "educational",
    ) -> Dict[str, Any]:
        """
        Haber fırsatını tek görsel post'a çevir.

        Args:
            opportunity: content_opportunities tablosundan gelen dict
            aspect_ratio: Görsel oranı (1:1 veya 4:5)
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

        self.log(f"Image Post Pipeline baslatildi: '{title[:50]}...'")
        self.state = PipelineState.CREATING_CONTENT

        news_context = (
            f"HABER: {title}\n"
            f"KAYNAK: {source_name}\n"
            f"OZET: {summary[:500]}\n"
            f"OLIVENET ACISI: {olivenet_angle}\n"
            f"HOOK ONERISI: {hook_suggestion}"
        )

        result = {
            "success": False,
            "stages_completed": [],
            "opportunity_id": opp_id,
        }

        try:
            # ========== 1. CAPTION ==========
            self.log("Asama 1/4: Caption uretiliyor...")

            content_result = await self.creator.execute({
                "action": "create_post_multiplatform",
                "topic": title,
                "category": "haber",
                "visual_type": "image",
                "news_context": news_context,
                "content_tone": content_tone,
            })

            if "error" in content_result:
                raise Exception(f"Caption error: {content_result['error']}")

            result["post_id"] = content_result.get("post_id")
            result["stages_completed"].append("caption")

            if content_result.get("post_id") and content_tone:
                update_post(content_result["post_id"], tone=content_tone)

            # ========== 2. IMAGE PROMPT + GENERATION ==========
            self.log("Asama 2/4: Gorsel prompt ve uretim...")
            self.state = PipelineState.CREATING_VISUAL

            prompt_result = await self.creator.execute({
                "action": "create_image_prompt",
                "topic": title,
                "post_text_ig": content_result.get("post_text_ig", ""),
                "content_tone": content_tone,
                "news_context": news_context,
                "aspect_ratio": aspect_ratio,
            })

            if not prompt_result.get("success"):
                raise Exception(f"Image prompt error: {prompt_result.get('error')}")

            image_prompt = prompt_result.get("image_prompt", "")
            if not image_prompt or not image_prompt.strip():
                raise Exception("Image prompt bos!")

            # Save prompt to DB
            if content_result.get("post_id"):
                save_prompt(
                    post_id=content_result["post_id"],
                    prompt_text=image_prompt,
                    prompt_type='image',
                    style='image_post'
                )

            # Generate image
            from app.nano_banana_helper import generate_image

            image_result = await generate_image(
                prompt=image_prompt,
                aspect_ratio=aspect_ratio,
            )

            if not image_result.get("success"):
                raise Exception(f"Image generation failed: {image_result.get('error')}")

            image_path = image_result.get("image_path")
            result["stages_completed"].append("image_generation")
            self.log(f"Gorsel hazir: {image_path}")

            # ========== 3. REVIEW ==========
            self.log("Asama 3/4: Kalite kontrol...")
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

                    # ========== 4. PUBLISH ==========
                    self.log("Asama 4/4: Yayinlaniyor...")
                    self.state = PipelineState.PUBLISHING

                    publish_result = await self.publisher.execute({
                        "action": "publish",
                        "post_id": content_result.get("post_id"),
                        "image_path": image_path,
                        "post_text": post_text,
                        "platform": "instagram"
                    })

                    if publish_result.get("success"):
                        result["success"] = True
                        result["stages_completed"].append("published")
                        update_opportunity(opp_id, status="used", used_at=datetime.utcnow().isoformat(),
                                         post_id=content_result.get("post_id"))
                        update_post(content_result.get("post_id"), visual_path=image_path)
                        self.log("Yayinlandi!")
                    else:
                        raise Exception(f"Publish error: {publish_result.get('error')}")
                else:
                    self.log(f"Review basarisiz (skor: {gate_result['score']})")
                    result["review_failed"] = True
                    update_opportunity(opp_id, status="ready")
            else:
                await self.notify_telegram(
                    message=f"Image Post hazir!\n\nKonu: {title[:60]}\nSkor: Review bekleniyor",
                    data={"post_id": content_result.get("post_id"), "image": image_path}
                )
                result["stages_completed"].append("awaiting_approval")

            self.state = PipelineState.COMPLETED
            result["final_image"] = image_path

        except Exception as e:
            result = await self.handle_error(e, "image_post")
            result["opportunity_id"] = opp_id
            update_opportunity(opp_id, status="ready")

        return result
