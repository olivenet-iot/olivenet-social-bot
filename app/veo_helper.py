"""
Google Veo Video Generation API
Veo 3.1 ve Veo 2 destekli
Docs: https://ai.google.dev/gemini-api/docs/veo
"""

import os
import asyncio
import time
from datetime import datetime
from typing import Dict, Any

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("veo")

GEMINI_API_KEY = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
OUTPUT_DIR = str(settings.outputs_dir)

# No-text suffix for video generation
# AI video generation cannot reliably render text, so we avoid it
VIDEO_NO_TEXT_SUFFIX = """

IMPORTANT VISUAL RULES:
- NO TEXT, TITLES, or SUBTITLES anywhere in the video
- NO watermarks, logos, or text overlays
- NO on-screen captions or written words
- NO signage with readable text (blur or use generic symbols)
- Focus on pure visual storytelling

NEGATIVE (avoid these elements):
subtitles, captions, watermark, logo, text overlay, title card,
written words, labels, signs with text, credits, lower thirds
"""

# Google GenAI client
_client = None

def get_client():
    """Google GenAI client al"""
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


async def generate_video_veo3(
    prompt: str,
    aspect_ratio: str = "9:16",
    duration_seconds: int = 8,
    model: str = "veo-3.1-generate-preview"
) -> Dict[str, Any]:
    """
    Google Veo ile video uret

    Args:
        prompt: Video aciklamasi
        aspect_ratio: "9:16" (Reels), "16:9" (YouTube)
        duration_seconds: 4, 6, veya 8 saniye
        model: "veo-3.1-generate-preview", "veo-3.1-fast-generate-preview", "veo-2"
    """

    if not GEMINI_API_KEY:
        return {"success": False, "error": "GEMINI_API_KEY not set"}

    # Add no-text suffix to avoid AI text rendering issues
    prompt = prompt + VIDEO_NO_TEXT_SUFFIX

    # Duration validation (4, 6, 8)
    valid_durations = [4, 6, 8]
    if duration_seconds not in valid_durations:
        duration_seconds = min(valid_durations, key=lambda x: abs(x - duration_seconds))

    print(f"🎬 Veo video uretimi baslatiliyor...")
    print(f"   Model: {model}")
    print(f"   Prompt: {prompt[:80]}...")
    print(f"   Aspect: {aspect_ratio}, Duration: {duration_seconds}s")

    # Model listesi - sirayla dene
    models_to_try = [
        ("veo-3.1-generate-preview", "Veo 3.1"),
        ("veo-3.1-fast-generate-preview", "Veo 3.1 Fast"),
        ("veo-2", "Veo 2")
    ]

    # Eger belirli model istendiyse once onu dene
    if model and model != "veo-3.1-generate-preview":
        models_to_try.insert(0, (model, model))

    for model_id, model_name in models_to_try:
        print(f"   → {model_name} deneniyor...")

        result = await _generate_with_veo_sdk(
            model_id=model_id,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds
        )

        if result.get("success"):
            result["model"] = model_name
            return result

        error = result.get("error", "")
        print(f"   ❌ {model_name}: {error[:80]}")

        # 404 veya model not found ise sonrakine gec
        if "404" in str(error) or "not found" in error.lower():
            continue

        # Diger hatalar icin de sonrakine gec
        await asyncio.sleep(2)

    return {"success": False, "error": "Tum Veo modelleri basarisiz oldu"}


async def _generate_with_veo_sdk(
    model_id: str,
    prompt: str,
    aspect_ratio: str,
    duration_seconds: int
) -> Dict[str, Any]:
    """Google GenAI SDK ile video uret"""

    try:
        from google.genai import types

        client = get_client()

        # Config olustur
        config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            number_of_videos=1,
            person_generation="allow_all"  # Text-to-video icin
        )

        print(f"   API'ye istek gonderiliyor...")

        # Video generation baslat
        operation = client.models.generate_videos(
            model=model_id,
            prompt=prompt,
            config=config
        )

        print(f"   Operation baslatildi, bekleniyor...")

        # Islem tamamlanana kadar bekle
        start_time = datetime.now()
        max_wait = 300  # 5 dakika

        while not operation.done:
            elapsed = (datetime.now() - start_time).total_seconds()

            if elapsed > max_wait:
                return {"success": False, "error": "Timeout - 5 dakika icinde tamamlanamadi"}

            if int(elapsed) % 10 == 0:
                print(f"   ⏳ Isleniyor... ({int(elapsed)}s)")

            await asyncio.sleep(5)
            operation = client.operations.get(operation)

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"   ✅ Video hazir! ({elapsed:.1f}s)")

        # Video'yu indir
        if not operation.response or not operation.response.generated_videos:
            return {"success": False, "error": "Video response bos"}

        generated_video = operation.response.generated_videos[0]

        # Dosyaya kaydet
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"{OUTPUT_DIR}/veo_{timestamp}.mp4"

        # Video'yu indir ve kaydet
        client.files.download(file=generated_video.video)
        generated_video.video.save(output_path)

        file_size = os.path.getsize(output_path) / 1024 / 1024
        print(f"   📁 Kaydedildi: {output_path}")
        print(f"   📊 Boyut: {file_size:.2f} MB")

        return {
            "success": True,
            "video_path": output_path,
            "file_size_mb": round(file_size, 2),
            "model": model_id,
            "duration": duration_seconds
        }

    except ImportError as e:
        print(f"   ❌ google-genai paketi eksik: {e}")
        return {"success": False, "error": f"google-genai package missing: {e}"}

    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ Hata: {error_msg[:100]}")
        return {"success": False, "error": error_msg}


async def generate_video_with_retry(
    prompt: str,
    aspect_ratio: str = "9:16",
    duration_seconds: int = 8,
    max_retries: int = 2
) -> Dict[str, Any]:
    """Retry mekanizmasi ile video uret"""

    for attempt in range(max_retries):
        result = await generate_video_veo3(prompt, aspect_ratio, duration_seconds)

        if result.get("success"):
            return result

        if attempt < max_retries - 1:
            print(f"   Retry {attempt + 2}/{max_retries}...")
            await asyncio.sleep(3)

    return result


# Backward compatibility
async def generate_video_veo(prompt: str, **kwargs) -> Dict[str, Any]:
    """Eski fonksiyon adi icin wrapper"""
    return await generate_video_veo3(prompt, **kwargs)


# Legacy function for pipeline compatibility
async def generate_video(
    prompt: str,
    output_path: str = None,
    model: str = "veo-3",
    duration_seconds: int = 5,
    aspect_ratio: str = "16:9",
    max_wait_seconds: int = 300
) -> Dict[str, Any]:
    """Legacy function - pipeline.py icin"""
    return await generate_video_veo3(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds
    )
