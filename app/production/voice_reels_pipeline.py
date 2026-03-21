"""
Voice Reels Pipeline - Sesli Instagram Reels icerigi uret ve yayinla.

OpenAI TTS + Video + FFmpeg merge pipeline.
ContentPipeline.run_reels_voice_content() metodundan extract edilmistir.
"""

import os
from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import PipelineState, escape_md, extract_shot_structure
from app.database import save_prompt
from app.database.crud import update_post
from app.video_models import get_model_config, get_prompt_key, validate_duration, get_max_duration


class VoiceReelsPipeline(BasePipeline):
    """Sesli Instagram Reels pipeline."""

    def __init__(self, telegram_callback=None):
        super().__init__("voice_reels", telegram_callback)

    async def run(
        self,
        topic: str = None,
        force_model: str = None,
        target_duration: int = 15,
        manual_topic_mode: bool = False,
        model_id: str = "sora-2",
        visual_style: str = "cinematic_4k",
        opportunity: Dict = None,
        content_tone: str = "educational"
    ) -> Dict[str, Any]:
        """
        Sesli Instagram Reels içeriği üret ve yayınla.

        OpenAI TTS + Video + FFmpeg merge pipeline.
        Multi-model desteği: Sora 2, Sora 2 Pro, Kling 3.0 Pro

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
            model_id: Video model ID (sora-2, sora-2-pro, kling-3.0-pro)
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
                f"📝 Konu: {escape_md(topic[:80])}...\n"
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
                "visual_type": "video",
                "content_tone": content_tone,
                "news_context": self._build_news_context(opportunity) if opportunity else None,
            })

            if "error" in content_result:
                raise Exception(f"Creator error: {content_result['error']}")

            self.current_data["content"] = content_result
            result["stages_completed"].append("caption")
            result["post_id"] = content_result.get("post_id")

            self.log(f"[VOICE REELS] Caption: IG {content_result.get('ig_word_count', 0)} kelime")

            # Persist tone to DB
            if content_result.get("post_id") and content_tone:
                update_post(content_result["post_id"], tone=content_tone)

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
                    reels_prompt_result.get("video_prompt_kling3", "")
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
                "post_id": content_result.get("post_id"),
                "content_tone": content_tone
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
                    f"📝 Konu: {escape_md(topic[:50])}...\n"
                    f"🎥 Model: {escape_md(model_used)}\n"
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
                message=f"❌ *SESLİ REELS* - Hata\n\n{escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
