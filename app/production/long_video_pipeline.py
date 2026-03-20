"""
Long Video Pipeline - Multi-segment uzun video üretimi.

ContentPipeline.run_long_video_pipeline() metodundan extract edilmiştir.
"""

import os
import json
from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState, escape_md, extract_shot_structure
from app.database import save_prompt
from app.database.crud import create_post, update_post
from app.video_models import get_model_config, get_max_duration, validate_duration


class LongVideoPipeline(BasePipeline):
    """
    Multi-segment uzun video pipeline.

    Birden fazla video segmenti üretip birleştirerek uzun videolar oluşturur.
    """

    def __init__(self, telegram_callback=None):
        super().__init__("long_video", telegram_callback)

    async def run(
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
        Multi-segment uzun video pipeline.

        Birden fazla video segmenti üretip birleştirerek uzun videolar oluşturur.
        Segment süresi modele göre dinamik belirlenir.

        Pipeline Akışı:
        1. Konu seçimi (Planner/Creator)
        2. Caption üretimi (Creator)
        3. Speech script üretimi
        4. TTS ses üretimi (ElevenLabs)
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
        from app.elevenlabs_helper import ElevenLabsHelper

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

            # Kelime hedefi: ~1.8 kelime/saniye (ElevenLabs Türkçe TTS ölçümü)
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
            from app.elevenlabs_helper import generate_speech_with_retry
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

                # Script'i uzat (1.8 WPS - ElevenLabs Türkçe TTS ölçümü)
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
                    f"📝 Konu: {escape_md(topic[:50])}...\n"
                    f"⏱️ Süre: {final_duration:.0f}s ({segment_count} segment)\n"
                    f"🎥 Model: {escape_md(model_id)}\n"
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
                message=f"❌ *UZUN VIDEO* - Hata\n\n{escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
