"""
OpenAI TTS Helper - Türkçe Sesli Reels için Text-to-Speech

OpenAI gpt-4o-mini-tts modeli kullanarak Türkçe voiceover üretimi.
ElevenLabs'ın drop-in replacement'ı — aynı return format.
"""

import os
import asyncio
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("openai_tts")

# API Sabitleri
OPENAI_TTS_API_URL = "https://api.openai.com/v1/audio/speech"
DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_OUTPUT_FORMAT = "mp3"

# Türkçe ton yönlendirmesi (gpt-4o-mini-tts instructions parametresi)
DEFAULT_INSTRUCTIONS = (
    "Türkçe konuş. Doğal, sıcak ve profesyonel bir tonla. "
    "Teknik terimleri net ve anlaşılır telaffuz et. "
    "Hız ve vurgu doğal konuşma gibi olsun."
)

# Output directory
AUDIO_OUTPUT_DIR = settings.outputs_dir / "audio"

# Türkçe TTS için telaffuz düzeltmeleri
PRONUNCIATION_FIXES = {
    # Marka isimleri
    "Olivenet": "Olivnet",
    "olivenet": "olivnet",
    "OLIVENET": "OLİVNET",
    # Teknik terimler
    "IoT": "nesnelerin interneti",
    "iot": "nesnelerin interneti",
    "LoRaWAN": "lora van",
    "LoRa": "lora",
    "MQTT": "em ku ti ti",
    "API": "ey pi ay",
    "AI": "ey ay",
    # Kısaltmalar
    "vs.": "karşı",
    "vb.": "ve benzeri",
    "vb": "ve benzeri",
    # Türkçe-İngilizce çakışan kelimeler
    "fire": "firé",  # Türkçe: atık/israf (İngilizce yangın ile karışmasın)
}


def fix_pronunciation(text: str) -> str:
    """TTS için telaffuz düzeltmeleri uygula"""
    for wrong, correct in PRONUNCIATION_FIXES.items():
        text = text.replace(wrong, correct)
    return text


# === Exception sınıfları ===

class OpenAITTSError(Exception):
    """OpenAI TTS API hataları"""
    pass


class TTSRateLimitError(OpenAITTSError):
    """Rate limit aşıldı"""
    pass


class TTSQuotaExceededError(OpenAITTSError):
    """Kullanım limiti aşıldı"""
    pass


# Backward-compat aliases (callers import these names from elevenlabs_helper)
ElevenLabsError = OpenAITTSError
RateLimitError = TTSRateLimitError
QuotaExceededError = TTSQuotaExceededError


class OpenAITTSHelper:
    """OpenAI TTS API wrapper — ElevenLabsHelper drop-in replacement"""

    @staticmethod
    def _get_api_key() -> str:
        """API key'i al"""
        api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise OpenAITTSError("OPENAI_API_KEY environment variable not set")
        return api_key

    @staticmethod
    def _get_default_voice() -> str:
        """Varsayılan voice'u al"""
        return settings.openai_tts_voice_male or "onyx"

    @staticmethod
    def _ensure_output_dir():
        """Audio output dizinini oluştur"""
        AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def estimate_duration(text: str, speed: float = 1.0) -> float:
        """
        Metin uzunluğundan ses süresini tahmin et.

        Türkçe için ortalama: ~1.8 kelime/saniye
        """
        word_count = len(text.split())
        base_duration = word_count / 1.8
        return base_duration / speed

    @staticmethod
    def get_cache_key(text: str, voice_id: str) -> str:
        """Text + voice'dan unique hash oluştur"""
        content = f"{text}:{voice_id}"
        return hashlib.md5(content.encode()).hexdigest()

    @staticmethod
    async def generate_speech(
        text: str,
        voice_id: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        instructions: Optional[str] = None,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        speed: float = 1.0
    ) -> Dict[str, Any]:
        """
        Text'i sese dönüştür.

        Args:
            text: Türkçe metin (max 4096 karakter)
            voice_id: OpenAI voice adı (onyx, nova, fable, echo, shimmer vb.)
            model: TTS modeli (gpt-4o-mini-tts)
            instructions: Ton/stil yönlendirmesi (Türkçe varsayılan)
            output_format: Çıktı formatı (mp3)
            speed: Konuşma hızı (0.25-4.0)

        Returns:
            {
                "success": bool,
                "audio_path": str,
                "duration_seconds": float,
                "character_count": int,
                "voice_id": str,
                "file_size_bytes": int,
                "error": str (hata durumunda)
            }
        """
        OpenAITTSHelper._ensure_output_dir()

        api_key = OpenAITTSHelper._get_api_key()
        voice_id = voice_id or OpenAITTSHelper._get_default_voice()

        # Karakter kontrolü
        char_count = len(text)
        if char_count > 4096:
            logger.warning(f"[TTS] Text too long ({char_count} chars), truncating to 4096")
            text = text[:4096]
            char_count = 4096

        if char_count < 1:
            return {
                "success": False,
                "error": "Text is empty"
            }

        logger.info(f"[TTS] Generating speech: {char_count} chars, voice={voice_id}")

        # Telaffuz düzeltmeleri uygula
        fixed_text = fix_pronunciation(text)
        if text != fixed_text:
            logger.info("[TTS] Telaffuz düzeltmesi uygulandı")

        # Request body
        body = {
            "model": model,
            "input": fixed_text,
            "voice": voice_id,
            "response_format": output_format,
            "speed": speed,
        }

        # instructions sadece gpt-4o-mini-tts destekler
        if "mini-tts" in model:
            body["instructions"] = instructions or DEFAULT_INSTRUCTIONS

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    OPENAI_TTS_API_URL,
                    headers=headers,
                    json=body,
                )

                # Rate limit kontrolü
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"[TTS] Rate limited, retry after {retry_after}s")
                    raise TTSRateLimitError(f"Rate limited. Retry after {retry_after}s")

                # Auth hatası
                if response.status_code == 401:
                    raise OpenAITTSError("Invalid API key")

                # Quota/billing hatası
                if response.status_code == 402:
                    raise TTSQuotaExceededError("Payment required - billing quota exceeded")

                if response.status_code == 400:
                    error_text = response.text
                    if "quota" in error_text.lower() or "limit" in error_text.lower():
                        raise TTSQuotaExceededError("Usage limit exceeded")
                    raise OpenAITTSError(f"Bad request: {error_text[:200]}")

                if response.status_code != 200:
                    raise OpenAITTSError(f"API error {response.status_code}: {response.text[:200]}")

                # Audio verisini al
                audio_data = response.content

                if len(audio_data) < 1000:
                    raise OpenAITTSError("Audio data too small, generation may have failed")

                # Dosyayı kaydet
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"tts_{timestamp}_{voice_id}.mp3"
                output_path = AUDIO_OUTPUT_DIR / filename

                with open(output_path, "wb") as f:
                    f.write(audio_data)

                # Süre tahmini
                estimated_duration = OpenAITTSHelper.estimate_duration(text, speed)

                logger.info(f"[TTS] Audio saved: {output_path} (~{estimated_duration:.1f}s)")

                return {
                    "success": True,
                    "audio_path": str(output_path),
                    "duration_seconds": estimated_duration,
                    "character_count": char_count,
                    "voice_id": voice_id,
                    "file_size_bytes": len(audio_data),
                }

        except (TTSRateLimitError, TTSQuotaExceededError):
            raise
        except httpx.TimeoutException:
            logger.error("[TTS] Request timeout")
            return {
                "success": False,
                "error": "Request timeout"
            }
        except Exception as e:
            logger.error(f"[TTS] Error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Backward-compat alias
ElevenLabsHelper = OpenAITTSHelper


async def generate_speech_with_retry(
    text: str,
    voice_id: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> Dict[str, Any]:
    """
    Retry mekanizması ile TTS üret.

    Rate limit durumunda exponential backoff uygular.
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            result = await OpenAITTSHelper.generate_speech(
                text=text,
                voice_id=voice_id
            )

            if result.get("success"):
                return result

            last_error = result.get("error", "Unknown error")

        except TTSRateLimitError as e:
            wait_time = retry_delay * (2 ** attempt)
            logger.warning(f"[TTS] Rate limit, waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
            last_error = str(e)

        except TTSQuotaExceededError as e:
            logger.error(f"[TTS] Quota exceeded: {e}")
            return {
                "success": False,
                "error": str(e),
                "quota_exceeded": True,
            }

        except Exception as e:
            last_error = str(e)
            logger.error(f"[TTS] Attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    return {
        "success": False,
        "error": f"All retries failed: {last_error}",
    }


async def generate_dialog_audio(
    dialog_lines: list,
    male_voice_id: Optional[str] = None,
    female_voice_id: Optional[str] = None,
    pause_between_ms: int = 300
) -> Dict[str, Any]:
    """
    Generate multi-voice dialog audio for conversational reels.

    Each line is generated with the appropriate voice and concatenated
    with pauses between lines using pydub.

    Args:
        dialog_lines: List of dialog items, each containing:
            - "speaker": "male" or "female"
            - "text": Line text
        male_voice_id: OpenAI voice name for male (default from config)
        female_voice_id: OpenAI voice name for female (default from config)
        pause_between_ms: Silence gap between lines (default 300ms)

    Returns:
        {
            "success": bool,
            "audio_path": str,
            "audio_segments": list,
            "total_duration": float,
            "line_count": int,
            "error": str (if failed)
        }
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.error("[TTS] pydub not installed. Run: pip install pydub")
        return {
            "success": False,
            "error": "pydub not installed. Run: pip install pydub",
        }

    OpenAITTSHelper._ensure_output_dir()

    # Get voice IDs
    if not male_voice_id:
        male_voice_id = settings.openai_tts_voice_male or "onyx"
    if not female_voice_id:
        female_voice_id = settings.openai_tts_voice_female or "nova"

    if not male_voice_id:
        return {"success": False, "error": "Male voice not configured"}
    if not female_voice_id:
        return {"success": False, "error": "Female voice not configured"}

    logger.info(f"[TTS] Generating dialog audio: {len(dialog_lines)} lines")
    logger.info(f"[TTS] Male voice: {male_voice_id}, Female voice: {female_voice_id}")

    audio_segments = []
    temp_audio_paths = []
    combined_audio = AudioSegment.empty()
    current_position_ms = 0

    try:
        for i, line in enumerate(dialog_lines):
            speaker = line.get("speaker", "male")
            text = line.get("text", "")

            if not text.strip():
                logger.warning(f"[TTS] Skipping empty line {i}")
                continue

            # Select voice based on speaker
            voice_id = male_voice_id if speaker == "male" else female_voice_id

            logger.info(f"[TTS] Line {i+1}/{len(dialog_lines)}: {speaker} - '{text[:30]}...'")

            # Generate TTS for this line
            tts_result = await OpenAITTSHelper.generate_speech(
                text=text,
                voice_id=voice_id,
            )

            if not tts_result.get("success"):
                error_msg = tts_result.get("error", "Unknown TTS error")
                logger.error(f"[TTS] Failed to generate line {i+1}: {error_msg}")
                return {
                    "success": False,
                    "error": f"TTS failed for line {i+1}: {error_msg}",
                }

            audio_path = tts_result.get("audio_path")
            temp_audio_paths.append(audio_path)

            # Load audio segment
            segment = AudioSegment.from_mp3(audio_path)
            duration_ms = len(segment)

            # Record segment timing
            audio_segments.append({
                "speaker": speaker,
                "start_ms": current_position_ms,
                "end_ms": current_position_ms + duration_ms,
                "duration_ms": duration_ms,
                "text": text,
                "temp_audio_path": audio_path,
            })

            # Add to combined audio
            combined_audio += segment
            current_position_ms += duration_ms

            # Add pause between lines (except after last line)
            if i < len(dialog_lines) - 1:
                silence = AudioSegment.silent(duration=pause_between_ms)
                combined_audio += silence
                current_position_ms += pause_between_ms

        if len(combined_audio) == 0:
            return {
                "success": False,
                "error": "No audio generated (all lines were empty)",
            }

        # Export combined audio
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"dialog_{timestamp}.mp3"
        output_path = AUDIO_OUTPUT_DIR / output_filename

        combined_audio.export(str(output_path), format="mp3")

        total_duration = len(combined_audio) / 1000.0

        logger.info(f"[TTS] Dialog audio generated: {output_path}")
        logger.info(f"[TTS] Total duration: {total_duration:.2f}s, Lines: {len(audio_segments)}")

        return {
            "success": True,
            "audio_path": str(output_path),
            "audio_segments": audio_segments,
            "total_duration": total_duration,
            "line_count": len(audio_segments),
        }

    except Exception as e:
        logger.error(f"[TTS] Dialog audio generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import sys

    async def test():
        text = sys.argv[1] if len(sys.argv) > 1 else (
            "Endüstriyel IoT sensörleri fabrikadaki veriyi gerçek zamanlı topluyor."
        )
        print(f"Testing OpenAI TTS with: {text}")
        result = await generate_speech_with_retry(text=text, max_retries=1)
        print(result)

    asyncio.run(test())
