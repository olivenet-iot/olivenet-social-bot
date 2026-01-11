"""
ElevenLabs TTS Helper - Türkçe Sesli Reels için Text-to-Speech

ElevenLabs Multilingual v2 modeli kullanarak Türkçe voiceover üretimi.
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

logger = get_logger("elevenlabs")

# API Sabitleri
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"  # Türkçe destekli
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"

# Varsayılan ses ayarları (doğal Türkçe için optimize edildi)
# stability: 0.5 = doğal varyasyon, similarity_boost: 0.75 = orijinal sese benzerlik
# style: 0.15 = hafif stil ekler (0.0 robotik, 0.3+ aşırı dramatik)
DEFAULT_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.15,
    "use_speaker_boost": True
}

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


class ElevenLabsError(Exception):
    """ElevenLabs API hataları"""
    pass


class RateLimitError(ElevenLabsError):
    """Rate limit aşıldı"""
    pass


class QuotaExceededError(ElevenLabsError):
    """Aylık karakter limiti aşıldı"""
    pass


class ElevenLabsHelper:
    """ElevenLabs TTS API wrapper"""

    @staticmethod
    def _get_api_key() -> str:
        """API key'i environment'tan al"""
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if not api_key:
            raise ElevenLabsError("ELEVENLABS_API_KEY environment variable not set")
        return api_key

    @staticmethod
    def _get_voice_id() -> str:
        """Varsayılan voice ID'yi al"""
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
        if not voice_id:
            raise ElevenLabsError("ELEVENLABS_VOICE_ID environment variable not set")
        return voice_id

    @staticmethod
    def _ensure_output_dir():
        """Audio output dizinini oluştur"""
        AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def estimate_duration(text: str, speed: float = 1.0) -> float:
        """
        Metin uzunluğundan ses süresini tahmin et.

        Türkçe için ortalama: ~1.8 kelime/saniye
        (ElevenLabs TTS gerçek ölçümlere göre ayarlandı)

        Args:
            text: Metin
            speed: Konuşma hızı (1.0 = normal)

        Returns:
            Tahmini süre (saniye)
        """
        # Kelime bazlı hesaplama (daha doğru)
        word_count = len(text.split())
        # ~1.8 kelime/saniye baz alarak (ElevenLabs Türkçe TTS gerçek ölçüm)
        # NOT: Eski 2.5 wps tahmini %30-40 eksik kalıyordu
        base_duration = word_count / 1.8
        return base_duration / speed

    @staticmethod
    def get_cache_key(text: str, voice_id: str) -> str:
        """Text + voice ID'den unique hash oluştur"""
        content = f"{text}:{voice_id}"
        return hashlib.md5(content.encode()).hexdigest()

    @staticmethod
    async def generate_speech(
        text: str,
        voice_id: Optional[str] = None,
        model_id: str = DEFAULT_MODEL,
        voice_settings: Optional[Dict] = None,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        speed: float = 1.0
    ) -> Dict[str, Any]:
        """
        Text'i sese dönüştür.

        Args:
            text: Türkçe metin (max 5000 karakter)
            voice_id: ElevenLabs voice ID (None ise env'den alınır)
            model_id: TTS modeli (eleven_multilingual_v2)
            voice_settings: Ses ayarları (stability, similarity_boost vb.)
            output_format: Çıktı formatı (mp3_44100_128)
            speed: Konuşma hızı (0.5-2.0)

        Returns:
            {
                "success": bool,
                "audio_path": str,  # Lokal dosya yolu
                "duration_seconds": float,
                "character_count": int,
                "voice_id": str,
                "error": str (hata durumunda)
            }
        """
        ElevenLabsHelper._ensure_output_dir()

        # Parametreleri hazırla
        api_key = ElevenLabsHelper._get_api_key()
        voice_id = voice_id or ElevenLabsHelper._get_voice_id()
        settings_to_use = voice_settings or DEFAULT_VOICE_SETTINGS.copy()

        # Karakter kontrolü
        char_count = len(text)
        if char_count > 5000:
            logger.warning(f"[TTS] Text too long ({char_count} chars), truncating to 5000")
            text = text[:5000]
            char_count = 5000

        if char_count < 1:
            return {
                "success": False,
                "error": "Text is empty"
            }

        logger.info(f"[TTS] Generating speech: {char_count} chars, voice={voice_id[:8]}...")

        # API endpoint
        url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"

        # Headers
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }

        # Telaffuz düzeltmeleri uygula
        fixed_text = fix_pronunciation(text)
        if text != fixed_text:
            logger.info("[TTS] Telaffuz düzeltmesi uygulandı")

        # Request body
        body = {
            "text": fixed_text,
            "model_id": model_id,
            "voice_settings": settings_to_use
        }

        # Output format query param
        params = {
            "output_format": output_format
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=body,
                    params=params
                )

                # Rate limit kontrolü
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"[TTS] Rate limited, retry after {retry_after}s")
                    raise RateLimitError(f"Rate limited. Retry after {retry_after}s")

                # Quota kontrolü
                if response.status_code == 401:
                    raise ElevenLabsError("Invalid API key")

                if response.status_code == 400:
                    error_text = response.text
                    if "quota" in error_text.lower() or "limit" in error_text.lower():
                        raise QuotaExceededError("Monthly character quota exceeded")
                    raise ElevenLabsError(f"Bad request: {error_text[:200]}")

                if response.status_code != 200:
                    raise ElevenLabsError(f"API error {response.status_code}: {response.text[:200]}")

                # Audio verisini al
                audio_data = response.content

                if len(audio_data) < 1000:
                    raise ElevenLabsError("Audio data too small, generation may have failed")

                # Dosyayı kaydet
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"tts_{timestamp}_{voice_id[:8]}.mp3"
                output_path = AUDIO_OUTPUT_DIR / filename

                with open(output_path, "wb") as f:
                    f.write(audio_data)

                # Süre tahmini
                estimated_duration = ElevenLabsHelper.estimate_duration(text, speed)

                logger.info(f"[TTS] Audio saved: {output_path} (~{estimated_duration:.1f}s)")

                return {
                    "success": True,
                    "audio_path": str(output_path),
                    "duration_seconds": estimated_duration,
                    "character_count": char_count,
                    "voice_id": voice_id,
                    "file_size_bytes": len(audio_data)
                }

        except (RateLimitError, QuotaExceededError):
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

    @staticmethod
    async def get_available_voices(language: str = "tr") -> Dict[str, Any]:
        """
        Kullanılabilir sesleri listele.

        Args:
            language: Dil kodu (tr = Türkçe)

        Returns:
            {
                "success": bool,
                "voices": [
                    {"voice_id": "...", "name": "...", "labels": {...}}
                ]
            }
        """
        api_key = ElevenLabsHelper._get_api_key()

        url = f"{ELEVENLABS_API_URL}/voices"
        headers = {
            "xi-api-key": api_key
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}"
                    }

                data = response.json()
                voices = data.get("voices", [])

                # Türkçe sesleri filtrele (varsa)
                # ElevenLabs'da dil filtresi labels içinde olabilir
                turkish_voices = []
                for voice in voices:
                    labels = voice.get("labels", {})
                    # Multilingual modeller tüm dilleri destekler
                    turkish_voices.append({
                        "voice_id": voice.get("voice_id"),
                        "name": voice.get("name"),
                        "labels": labels,
                        "preview_url": voice.get("preview_url")
                    })

                return {
                    "success": True,
                    "voices": turkish_voices,
                    "count": len(turkish_voices)
                }

        except Exception as e:
            logger.error(f"[TTS] Get voices error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def get_usage_stats() -> Dict[str, Any]:
        """
        ElevenLabs hesap kullanımını al.

        Returns:
            {
                "success": bool,
                "character_count": int,  # Kullanılan
                "character_limit": int,  # Limit
                "remaining": int,
                "reset_date": str
            }
        """
        api_key = ElevenLabsHelper._get_api_key()

        url = f"{ELEVENLABS_API_URL}/user/subscription"
        headers = {
            "xi-api-key": api_key
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}"
                    }

                data = response.json()

                char_count = data.get("character_count", 0)
                char_limit = data.get("character_limit", 10000)

                return {
                    "success": True,
                    "character_count": char_count,
                    "character_limit": char_limit,
                    "remaining": char_limit - char_count,
                    "tier": data.get("tier", "unknown"),
                    "next_reset": data.get("next_character_count_reset_unix")
                }

        except Exception as e:
            logger.error(f"[TTS] Get usage error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


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
            result = await ElevenLabsHelper.generate_speech(
                text=text,
                voice_id=voice_id
            )

            if result.get("success"):
                return result

            last_error = result.get("error", "Unknown error")

        except RateLimitError as e:
            # Rate limit - bekle ve tekrar dene
            wait_time = retry_delay * (2 ** attempt)
            logger.warning(f"[TTS] Rate limit, waiting {wait_time}s...")
            await asyncio.sleep(wait_time)
            last_error = str(e)

        except QuotaExceededError as e:
            # Quota aşıldı - devam etme
            logger.error(f"[TTS] Quota exceeded: {e}")
            return {
                "success": False,
                "error": str(e),
                "quota_exceeded": True
            }

        except Exception as e:
            last_error = str(e)
            logger.error(f"[TTS] Attempt {attempt + 1} failed: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    return {
        "success": False,
        "error": f"All retries failed: {last_error}"
    }
