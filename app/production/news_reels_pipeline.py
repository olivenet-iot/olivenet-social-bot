"""
News Reels Pipeline - Haber bazlı sesli reels üretimi

Bir content_opportunity'yi alıp, Olivenet perspektifinden
sesli video reels'e çevirir.

Pipeline akışı:
1. Haber -> TTS script (Creator)
2. Script -> Ses (OpenAI TTS)
3. Haber -> Video prompt (Creator)
4. Prompt -> Video (Sora/Kling)
5. Video + Ses -> Birleşik video (FFmpeg)
6. Altyazı (opsiyonel, Whisper)
7. Caption yazımı (Creator)
8. Kalite kontrol (Reviewer)
9. Yayın (Publisher)
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState, extract_shot_structure
from app.production.quality_gate import QualityGate
from app.utils.logger import get_logger
from app.database.crud import update_opportunity, update_post
from app.video_models import get_model_config, get_prompt_key, validate_duration, get_max_duration

logger = get_logger("news_reels")


class NewsReelsPipeline(BasePipeline):
    """Haber bazlı sesli reels üretimi."""

    def __init__(self, telegram_callback=None):
        super().__init__("news_reels", telegram_callback)
        self.quality_gate = QualityGate(min_score=7.0, autonomous_min=6.5)

    async def run(
        self,
        opportunity: Dict,
        model_id: str = "sora-2",
        target_duration: int = 15,
        visual_style: str = "cinematic_4k",
        autonomous: bool = True,
        content_tone: str = "news_commentary"
    ) -> Dict[str, Any]:
        """
        Haber fırsatını sesli reels'e çevir.

        Args:
            opportunity: content_opportunities tablosundan gelen dict
            model_id: Video model (sora-2, kling-3.0-pro)
            target_duration: Hedef video süresi (saniye)
            visual_style: Video görsel stili
            autonomous: True ise Telegram onayı beklemez

        Returns:
            {"success": bool, "post_id": int, ...}
        """
        opp_id = opportunity["id"]
        title = opportunity.get("title", "")
        summary = opportunity.get("summary", "")
        olivenet_angle = opportunity.get("olivenet_angle", "")
        hook_suggestion = opportunity.get("hook_suggestion", "")
        source_name = opportunity.get("source_name", "")
        tags = opportunity.get("tags", [])

        # Model config
        model_config = get_model_config(model_id)
        model_name = model_config.get("name", model_id)
        max_duration = get_max_duration(model_id)
        target_duration = min(target_duration, max_duration)
        target_duration = validate_duration(model_id, target_duration)

        self.log(f"News Reels Pipeline baslatildi: '{title[:50]}...' (model: {model_name})")
        self.state = PipelineState.CREATING_CONTENT

        result = {
            "success": False,
            "stages_completed": [],
            "opportunity_id": opp_id,
            "model_id": model_id,
            "model_name": model_name,
            "target_duration": target_duration
        }

        try:
            # ========== 1. NEWS TTS SCRIPT ==========
            self.log("Asama 1/7: Haber TTS scripti olusturuluyor...")

            news_context = (
                f"HABER: {title}\n"
                f"KAYNAK: {source_name}\n"
                f"OZET: {summary[:500]}\n"
                f"OLIVENET ACISI: {olivenet_angle}\n"
                f"HOOK ONERISI: {hook_suggestion}"
            )

            speech_result = await self.creator.execute({
                "action": "create_speech_script",
                "topic": title,
                "target_duration": target_duration,
                "tone": "informative",
                "news_context": news_context,
                "content_tone": content_tone,
            })

            if not speech_result.get("success"):
                raise Exception(f"Speech script error: {speech_result.get('error')}")

            speech_script = speech_result.get("speech_script", "")
            result["stages_completed"].append("speech_script")
            self.log(f"Script hazir: {speech_result.get('word_count', 0)} kelime")

            # ========== 2. CAPTION ==========
            self.log("Asama 2/7: Caption uretiliyor...")

            content_result = await self.creator.execute({
                "action": "create_post_multiplatform",
                "topic": title,
                "category": "haber",
                "visual_type": "video",
                "news_context": news_context,
                "content_tone": content_tone,
            })

            if "error" in content_result:
                raise Exception(f"Caption error: {content_result['error']}")

            result["post_id"] = content_result.get("post_id")
            result["stages_completed"].append("caption")

            # Persist tone to DB
            if content_result.get("post_id") and content_tone:
                update_post(content_result["post_id"], tone=content_tone)

            # ========== 3. TTS AUDIO ==========
            self.log("Asama 3/7: TTS ses uretiliyor...")

            audio_path = None
            audio_duration = 0
            voice_fallback = False

            try:
                from app.openai_tts_helper import generate_speech_with_retry

                tts_result = await generate_speech_with_retry(
                    text=speech_script,
                    max_retries=3
                )

                if tts_result.get("success"):
                    audio_path = tts_result.get("audio_path")
                    estimated_duration = tts_result.get("duration_seconds", 0)

                    # Gercek süreyi ölc
                    from app.instagram_helper import get_audio_duration
                    actual_duration = await get_audio_duration(audio_path)
                    audio_duration = actual_duration if actual_duration > 0 else estimated_duration

                    result["stages_completed"].append("tts")
                    result["audio_duration"] = audio_duration
                    self.log(f"Ses hazir: {audio_duration:.1f}s")
                else:
                    self.log(f"TTS hatasi: {tts_result.get('error')}")
                    voice_fallback = True
            except Exception as e:
                self.log(f"TTS exception: {e}")
                voice_fallback = True

            if voice_fallback:
                self.log("Sessiz video moduna geciliyor...")
                result["voice_fallback"] = True

            # ========== 4. VIDEO PROMPT ==========
            self.log("Asama 4/7: Video prompt olusturuluyor...")
            self.state = PipelineState.CREATING_VISUAL

            speech_structure = extract_shot_structure(speech_script, target_duration)

            reels_prompt_result = await self.creator.execute({
                "action": "create_reels_prompt",
                "topic": title,
                "category": "haber",
                "post_text": content_result.get("post_text_ig", ""),
                "post_id": content_result.get("post_id"),
                "speech_structure": speech_structure,
                "voice_mode": True,
                "visual_style": visual_style,
                "news_context": news_context,
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

            # ========== 5. VIDEO GENERATION ==========
            self.log(f"Asama 5/7: Video uretiliyor ({model_name})...")

            from app.sora_helper import generate_video_smart

            actual_dur = audio_duration if audio_duration > 0 else target_duration
            model_durations = model_config.get("durations", [8, 12])
            video_gen_duration = min(model_durations, key=lambda x: abs(x - actual_dur) if x >= actual_dur else float('inf'))
            if video_gen_duration < actual_dur:
                video_gen_duration = max(model_durations)

            video_result = await generate_video_smart(
                prompt=video_prompt,
                topic=title,
                force_model=model_id,
                duration=video_gen_duration,
                voice_mode=True
            )

            if not video_result.get("success"):
                raise Exception(f"Video generation failed: {video_result.get('error')}")

            video_path = video_result.get("video_path")
            result["stages_completed"].append("video_generation")
            result["model_used"] = video_result.get("model_used", model_id)
            self.log(f"Video hazir: {video_path}")

            # ========== 6. AUDIO-VIDEO MERGE ==========
            final_video_path = video_path

            if audio_path and not voice_fallback:
                self.log("Asama 6/7: Audio-video birlestiriliyor...")
                from app.instagram_helper import merge_audio_video

                merged = await merge_audio_video(video_path, audio_path)
                if merged:
                    final_video_path = merged
                    result["stages_completed"].append("audio_merge")
                    self.log(f"Merge tamamlandi: {merged}")
                else:
                    self.log("Merge basarisiz, sessiz video kullanilacak")

            # ========== 7. REVIEW + PUBLISH ==========
            self.log("Asama 7/7: Kalite kontrol ve yayin...")
            self.state = PipelineState.REVIEWING

            post_text = content_result.get("post_text_ig", content_result.get("post_text", ""))

            if autonomous:
                # Otonom mod: review et, skoru yeterli ise yayinla
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

                    # Yayinla
                    self.state = PipelineState.PUBLISHING
                    publish_result = await self.publisher.execute({
                        "action": "publish",
                        "post_id": content_result.get("post_id"),
                        "visual_path": final_video_path,
                        "visual_type": "video",
                        "post_text": post_text,
                        "platform": "instagram"
                    })

                    if publish_result.get("success"):
                        result["success"] = True
                        result["stages_completed"].append("published")
                        update_opportunity(opp_id, status="used", used_at=datetime.utcnow().isoformat(),
                                         post_id=content_result.get("post_id"))
                        self.log("Yayinlandi!")
                    else:
                        raise Exception(f"Publish error: {publish_result.get('error')}")
                else:
                    self.log(f"Review basarisiz (skor: {gate_result['score']})")
                    result["review_failed"] = True
                    update_opportunity(opp_id, status="ready")  # Tekrar denenebilir
            else:
                # Manuel mod: Telegram'a gönder onay bekle
                await self.notify_telegram(
                    message=f"News Reels hazir!\n\nKonu: {title[:60]}\nSkor: Review bekleniyor",
                    data={"post_id": content_result.get("post_id"), "video": final_video_path}
                )
                result["stages_completed"].append("awaiting_approval")

            self.state = PipelineState.COMPLETED
            result["final_video"] = final_video_path

        except Exception as e:
            result = await self.handle_error(e, "news_reels")
            result["opportunity_id"] = opp_id
            # Fırsatı tekrar kullanılabilir yap
            update_opportunity(opp_id, status="ready")

        return result
