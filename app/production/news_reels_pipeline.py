"""
News Reels Pipeline - Saf sinematik haber reels üretimi

Bir content_opportunity'yi alıp, Olivenet perspektifinden
sinematik video reels'e çevirir. Kling 3.0 Pro native ambient
ses üretir — TTS veya altyazı kullanılmaz.

Pipeline akışı:
1. Caption yazımı (Creator)
2. Haber -> Video prompt (Creator)
3. Prompt -> Video (Kling 3.0 Pro, ambient audio dahil)
4. Kalite kontrol (Reviewer)
5. Yayın (Publisher)
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState
from app.production.quality_gate import QualityGate
from app.utils.logger import get_logger
from app.database import save_prompt
from app.database.crud import update_opportunity, update_post
from app.video_models import get_model_config, get_prompt_key, validate_duration, get_max_duration

logger = get_logger("news_reels")


class NewsReelsPipeline(BasePipeline):
    """Saf sinematik haber reels üretimi — TTS/altyazı yok."""

    def __init__(self, telegram_callback=None):
        super().__init__("news_reels", telegram_callback)
        self.quality_gate = QualityGate(min_score=7.0, autonomous_min=6.5)

    async def run(
        self,
        opportunity: Dict,
        model_id: str = "kling-3.0-pro",
        target_duration: int = 15,
        visual_style: str = "cinematic_4k",
        autonomous: bool = True,
        content_tone: str = "news_commentary",
        content_concept: str = None,
        inspiration_source: str = None,
    ) -> Dict[str, Any]:
        """
        Haber fırsatını sinematik reels'e çevir.

        Args:
            opportunity: content_opportunities tablosundan gelen dict
            model_id: Video model (kling-3.0-pro varsayılan)
            target_duration: Hedef video süresi (saniye)
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

        self.log(f"News Reels Pipeline baslatildi: '{title[:50]}...' (model: {model_name})")
        self.state = PipelineState.CREATING_CONTENT

        news_context = self._build_news_context(opportunity, content_concept, inspiration_source)

        result = {
            "success": False,
            "stages_completed": [],
            "opportunity_id": opp_id,
            "model_id": model_id,
            "model_name": model_name,
            "target_duration": target_duration
        }

        try:
            # ========== 1. CAPTION ==========
            self.log("Asama 1/5: Caption uretiliyor...")

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

            # ========== 2. VIDEO PROMPT ==========
            self.log("Asama 2/5: Video prompt olusturuluyor...")
            self.state = PipelineState.CREATING_VISUAL

            reels_prompt_result = await self.creator.execute({
                "action": "create_reels_prompt",
                "topic": title,
                "category": "haber",
                "post_text": content_result.get("post_text_ig", ""),
                "post_id": content_result.get("post_id"),
                "voice_mode": False,
                "visual_style": visual_style,
                "news_context": news_context,
                "content_concept": content_concept,
                "inspiration_source": inspiration_source,
            })

            if not reels_prompt_result.get("success"):
                raise Exception(f"Video prompt error: {reels_prompt_result.get('error')}")

            prompt_key = get_prompt_key(model_id)
            video_prompt = (
                reels_prompt_result.get(prompt_key) or
                reels_prompt_result.get("video_prompt_sora") or
                reels_prompt_result.get("video_prompt_kling3", "")
            )

            if not video_prompt or not video_prompt.strip():
                raise Exception("Video prompt bos!")

            result["stages_completed"].append("video_prompt")

            # Save video prompt to DB
            if video_prompt and content_result.get("post_id"):
                save_prompt(post_id=content_result.get("post_id"),
                            prompt_text=video_prompt, prompt_type='video',
                            style=visual_style)

            # ========== 3. VIDEO GENERATION ==========
            self.log(f"Asama 3/5: Video uretiliyor ({model_name})...")

            from app.sora_helper import generate_video_smart

            model_durations = model_config.get("durations", [8, 12])
            video_gen_duration = min(model_durations, key=lambda x: abs(x - target_duration))

            video_result = await generate_video_smart(
                prompt=video_prompt,
                topic=title,
                force_model=model_id,
                duration=video_gen_duration,
                voice_mode=False
            )

            if not video_result.get("success"):
                raise Exception(f"Video generation failed: {video_result.get('error')}")

            video_path = video_result.get("video_path")
            result["stages_completed"].append("video_generation")
            result["model_used"] = video_result.get("model_used", model_id)
            self.log(f"Video hazir: {video_path}")

            # ========== 4. REVIEW ==========
            self.log("Asama 4/5: Kalite kontrol...")
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

                    # ========== 5. PUBLISH ==========
                    self.log("Asama 5/5: Yayinlaniyor...")
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
                    message=f"News Reels hazir!\n\nKonu: {title[:60]}\nSkor: Review bekleniyor",
                    data={"post_id": content_result.get("post_id"), "video": video_path}
                )
                result["stages_completed"].append("awaiting_approval")

            self.state = PipelineState.COMPLETED
            result["final_video"] = video_path

        except Exception as e:
            result = await self.handle_error(e, "news_reels")
            result["opportunity_id"] = opp_id
            update_opportunity(opp_id, status="ready")

        return result
