import os
import traceback
from typing import Dict, Any

from app.production.base_pipeline import BasePipeline
from app.production.utils import (
    PipelineState,
    escape_md,
    BROLL_AUDIO_DELAY,
    CONV_FREEZE_BUFFER,
    calculate_freeze_duration,
    add_freeze_frame,
)
from app.video_models import get_model_config


class ConversationalPipeline(BasePipeline):

    def __init__(self, telegram_callback=None):
        super().__init__("conversational", telegram_callback)

    def _create_avatar_prompt(self, original_prompt: str) -> str:
        """Video prompt'u lipsync için sessiz avatar prompt'una çevir."""
        avatar_prompt = original_prompt

        remove_phrases = [
            "speaking Turkish", "Speaking Turkish",
            "clear lip movements", "Clear lip movements",
            "synchronized with speech", "Turkish dialogue",
            "DIALOGUE FLOW:", "AUDIO:", "talking", "speaking"
        ]

        for phrase in remove_phrases:
            avatar_prompt = avatar_prompt.replace(phrase, "")

        avatar_prompt += """

IMPORTANT: Characters should be SILENT (lip-sync added later).
Show natural gestures and expressions, NO actual speech.
"""
        return avatar_prompt

    async def run(
        self,
        topic: str = None,
        manual_topic_mode: bool = False,
        visual_style: str = "cinematic_4k",
        model_id: str = "sora-2",
        opportunity: Dict = None,
        content_tone: str = "educational"
    ) -> Dict[str, Any]:
        """
        Conversational Reels pipeline with multi-model support.

        Creates two-character dialog video (male problem, female solution)
        followed by B-roll segment with voiceover.

        Pipeline Steps (Simplified):
        1. Topic selection (Planner/manual)
        2. Conversation content generation (Creator)
        3. Conversation video generation:
           - Sora 2: Native Turkish speech (12s)
           - Other models: TTS + Video + Lipsync API
        4. B-roll video generation (8-12s)
        5. B-roll voiceover generation (ElevenLabs narrator)
        6. B-roll merge (FFmpeg)
        7. Concat conversation + B-roll
        8. Whisper transcription + subtitles
        9. Review + Publish

        Args:
            topic: Topic (None uses Planner suggestion)
            manual_topic_mode: Process topic through Creator if True
            visual_style: Görsel stil (cinematic_4k, anime, vb.)
            model_id: Video model (sora-2, sora-2-pro, veo-3.1, kling-3.0-pro)

        Returns:
            Pipeline result dict
        """
        self.log(f"[CONV REELS] Pipeline başlatılıyor (model: {model_id})...")
        self.state = PipelineState.PLANNING

        result = {
            "success": False,
            "stages_completed": [],
            "conversational_reels": True,
            "topic": topic,
            "model_id": model_id
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

            # Model'e göre dialog süresi ayarla
            from app.video_models import get_model_config
            model_config = get_model_config(model_id)
            max_duration = model_config.get("max_duration", 12)

            native_speech_models = ["sora-2", "sora-2-pro", "veo-3.1"]
            if model_id in native_speech_models:
                if model_id in ["sora-2", "sora-2-pro"]:
                    target_duration = min(12, max_duration)  # Sora API max 12s
                else:
                    target_duration = min(8, max_duration)  # Veo = 8s
            else:
                target_duration = 12  # TTS+Lipsync için sabit

            self.log(f"[CONV REELS] Target duration: {target_duration}s (model: {model_id})")

            # ========== STAGE 2: Conversation Content ==========
            self.log("[CONV REELS] Aşama 2: Dialog içeriği oluşturuluyor...")
            self.state = PipelineState.CREATING_CONTENT

            conv_result = await self.creator.execute({
                "action": "create_conversation_content",
                "topic": topic,
                "category": category,
                "target_duration": target_duration,  # Model'e göre dinamik
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

            # ========== STAGE 3: Conversation Video Generation ==========
            self.log(f"[CONV REELS] Aşama 3: Conversation video ({model_id})...")
            self.state = PipelineState.CREATING_VISUAL

            if model_id in native_speech_models:
                # ===== NATIVE SPEECH MODELS (Sora 2, Veo 3.1) =====
                self.log(f"[CONV REELS] Native speech modu ({model_id})")

                if model_id in ["sora-2", "sora-2-pro"]:
                    from app.sora_helper import generate_video_sora
                    from app.video_models import get_model_config
                    sora_config = get_model_config(model_id)
                    sora_duration = sora_config.get("default_duration", 12)

                    conversation_result = await generate_video_sora(
                        prompt=video_prompt,
                        duration=sora_duration,
                        size="720x1280",
                        model=model_id
                    )
                elif model_id == "veo-3.1":  # veo-3.1
                    from app.veo_helper import generate_video_veo
                    conversation_result = await generate_video_veo(
                        prompt=video_prompt,
                        duration_seconds=8,
                        aspect_ratio="9:16",
                        model="veo-3.1-generate-preview"
                    )

                if not conversation_result.get("success"):
                    raise Exception(f"Conversation video hatası: {conversation_result.get('error')}")

                conversation_video_path = conversation_result.get("video_path")
                result["native_speech"] = True
                result["native_speech_model"] = model_id
                self.log(f"[CONV REELS] {model_id} native speech video üretildi")

            else:
                # ===== DİĞER MODELLER: TTS + Video + Lipsync =====
                self.log(f"[CONV REELS] TTS + Lipsync modu ({model_id})")

                # 3a. Dialog TTS üret
                from app.elevenlabs_helper import generate_dialog_audio
                from app.video_styles import should_use_cartoon_voices
                from app.config import settings

                if should_use_cartoon_voices(visual_style):
                    male_voice = settings.elevenlabs_voice_id_cartoon_male
                    female_voice = settings.elevenlabs_voice_id_cartoon_female
                    self.log(f"[CONV REELS] Cartoon voices kullanılıyor")
                else:
                    male_voice = settings.elevenlabs_voice_id
                    female_voice = settings.elevenlabs_voice_id_female
                    self.log(f"[CONV REELS] Realistic voices kullanılıyor")

                dialog_tts_result = await generate_dialog_audio(
                    dialog_lines=dialog_lines,
                    male_voice_id=male_voice,
                    female_voice_id=female_voice
                )

                if not dialog_tts_result.get("success"):
                    raise Exception(f"Dialog TTS hatası: {dialog_tts_result.get('error')}")

                dialog_audio_path = dialog_tts_result.get("audio_path")
                dialog_duration = dialog_tts_result.get("total_duration", 12)
                self.log(f"[CONV REELS] Dialog TTS üretildi: {dialog_duration:.1f}s")
                result["stages_completed"].append("dialog_tts")

                # 3b. Avatar video üret (sessiz)
                avatar_prompt = self._create_avatar_prompt(video_prompt)

                from app.sora_helper import generate_video_smart
                avatar_result = await generate_video_smart(
                    prompt=avatar_prompt,
                    topic=topic,
                    force_model=model_id,
                    duration=min(int(dialog_duration) + 2, 12),
                    voice_mode=True
                )

                if not avatar_result.get("success"):
                    raise Exception(f"Avatar video hatası: {avatar_result.get('error')}")

                avatar_video_path = avatar_result.get("video_path")
                self.log("[CONV REELS] Avatar video üretildi")
                result["stages_completed"].append("avatar_video")

                # 3c. Lipsync uygula
                from app.cloudinary_helper import upload_video_to_cloudinary, upload_audio_to_cloudinary
                from app.sync_lipsync_helper import apply_lipsync

                video_upload = await upload_video_to_cloudinary(avatar_video_path)
                audio_upload = await upload_audio_to_cloudinary(dialog_audio_path)

                if not video_upload.get("success") or not audio_upload.get("success"):
                    raise Exception("Cloudinary upload hatası")

                self.log(f"[CONV REELS] Cloudinary upload tamamlandı, lipsync başlatılıyor...")

                lipsync_result = await apply_lipsync(
                    video_url=video_upload["url"],
                    audio_url=audio_upload["url"]
                )

                if not lipsync_result.get("success"):
                    raise Exception(f"Lipsync hatası: {lipsync_result.get('error')}")

                conversation_video_path = lipsync_result.get("video_path")
                result["lipsync_applied"] = True
                self.log("[CONV REELS] Lipsync uygulandı")
                result["stages_completed"].append("lipsync")

            result["stages_completed"].append("conversation_video")

            # ========== STAGE 4: B-roll Voiceover (TTS önce) ==========
            self.log("[CONV REELS] Aşama 4: B-roll voiceover...")

            from app.elevenlabs_helper import generate_speech_with_retry
            from app.config import settings
            from app.video_styles import should_use_cartoon_voices

            # Stil bazlı narrator voice seçimi
            if should_use_cartoon_voices(visual_style):
                narrator_voice = settings.elevenlabs_voice_id_cartoon_female
                self.log(f"[CONV REELS] Cartoon narrator voice kullanılıyor")
            else:
                narrator_voice = settings.elevenlabs_voice_id_narrator
                self.log(f"[CONV REELS] Realistic narrator voice kullanılıyor")

            broll_audio_result = await generate_speech_with_retry(
                text=broll_voiceover,
                voice_id=narrator_voice,
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

            # Import Sora for B-roll (her zaman Sora kullanılır)
            from app.sora_helper import generate_video_sora

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
            from app.audio_utils import add_silence_prefix

            if broll_audio_path:
                # Add delay to B-roll audio (standard 1.5s silence at start)
                self.log(f"[CONV REELS] B-roll audio'ya {BROLL_AUDIO_DELAY}s delay ekleniyor...")
                try:
                    delayed_broll_audio = await add_silence_prefix(
                        audio_path=broll_audio_path,
                        silence_duration=BROLL_AUDIO_DELAY
                    )
                    self.log(f"[CONV REELS] Delay eklendi: {delayed_broll_audio}")
                except Exception as e:
                    self.log(f"[CONV REELS] Delay eklenemedi, orijinal kullanılıyor: {e}")
                    delayed_broll_audio = broll_audio_path

                broll_merge_result = await merge_audio_video(
                    video_path=broll_video_path,
                    audio_path=delayed_broll_audio,
                    target_duration=broll_video_duration
                )
                broll_final_path = broll_merge_result.get("output_path", broll_video_path)
            else:
                broll_final_path = broll_video_path

            result["stages_completed"].append("broll_merge")

            # ========== STAGE 6.5: Dynamic Freeze Frame (if needed) ==========
            # Apply freeze frame to conversation video if audio extends beyond video
            try:
                from app.subtitle_helper import extract_word_timestamps, get_last_word_end_time
                from app.instagram_helper import get_video_duration

                # Get conversation video duration
                conv_video_duration = await get_video_duration(conversation_video_path)

                # Extract audio and get last word timing
                from app.subtitle_helper import extract_audio_from_video
                conv_audio_extract = await extract_audio_from_video(conversation_video_path)

                if conv_audio_extract.get("success"):
                    whisper_result = await extract_word_timestamps(
                        conv_audio_extract["audio_path"],
                        model_size="small",
                        language="tr"
                    )

                    if whisper_result.get("success"):
                        last_word_end = get_last_word_end_time(whisper_result.get("words", []))
                        freeze_duration = calculate_freeze_duration(conv_video_duration, last_word_end)

                        if freeze_duration > 0:
                            self.log(f"[CONV REELS] Freeze frame gerekli: {freeze_duration:.1f}s (son kelime: {last_word_end:.1f}s, video: {conv_video_duration:.1f}s)")
                            conversation_video_path = await add_freeze_frame(conversation_video_path, freeze_duration)
                            self.log(f"[CONV REELS] Freeze frame eklendi")
                        else:
                            self.log(f"[CONV REELS] Freeze frame gerekmedi (son kelime: {last_word_end:.1f}s, video: {conv_video_duration:.1f}s)")
            except Exception as e:
                self.log(f"[CONV REELS] Freeze frame kontrolü başarısız: {e}")

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

                        # Subtitle verification with larger model
                        try:
                            from app.subtitle_helper import verify_and_correct_subtitles

                            initial_transcript = conv_sub.get("full_text", "")
                            if initial_transcript:
                                self.log("[CONV REELS] Altyazı doğrulanıyor (medium model)...")
                                verify_result = await verify_and_correct_subtitles(
                                    audio_path=conv_audio["audio_path"],
                                    initial_transcript=initial_transcript,
                                    model_size_verify="medium"
                                )

                                if verify_result.get("corrected"):
                                    self.log(f"[CONV REELS] Altyazı düzeltildi (benzerlik: {verify_result.get('similarity', 0):.1%})")
                                    # Regenerate ASS file with corrected transcript
                                    conv_sub = await create_subtitle_file(
                                        audio_path=conv_audio["audio_path"],
                                        original_script=verify_result["transcript"],
                                        model_size=os.getenv("WHISPER_MODEL_SIZE", "base"),
                                        language="tr"
                                    )
                                    if conv_sub.get("success"):
                                        conv_sub_path = conv_sub["ass_path"]
                                        self.log(f"[CONV REELS] Düzeltilmiş subtitle oluşturuldu")
                                else:
                                    self.log(f"[CONV REELS] Altyazı doğrulandı (benzerlik: {verify_result.get('similarity', 0):.1%})")
                        except Exception as e:
                            self.log(f"[CONV REELS] Altyazı doğrulama atlandı: {e}")
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
                f"📋 *Konu:* {escape_md(topic[:50])}...\n"
                f"💬 *Dialog:* {len(dialog_lines)} satır\n"
                f"⏱️ *Süre:* {final_duration:.0f}s\n"
                f"🗣️ *Sora Native Speech:* ✓\n\n"
                f"*Caption:*\n{escape_md(full_caption[:200])}...",
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
                message=f"❌ *CONVERSATIONAL REELS* - Hata\n\n{escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result

    async def publish(self, post_id: int) -> Dict[str, Any]:
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
                message=f"❌ *CONVERSATIONAL REELS PUBLISH* - Hata\n\n{escape_md(str(e))}",
                data={"error": str(e)},
                buttons=[]
            )

            return result
