"""
Veo 3 Video Generation Helper
Google Gemini Veo 3 API ile video üretimi
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Veo modelleri - en iyiden en hızlıya
VEO_MODELS = {
    "veo-3": "veo-3.0-generate-001",
    "veo-3-fast": "veo-3.0-fast-generate-001",
    "veo-2": "veo-2.0-generate-001",
}


async def generate_video(
    prompt: str,
    output_path: Optional[str] = None,
    model: str = "veo-3",
    duration_seconds: int = 5,
    aspect_ratio: str = "16:9",
    max_wait_seconds: int = 300
) -> Dict[str, Any]:
    """
    Veo 3 ile video üret.

    Args:
        prompt: Video için detaylı prompt (İngilizce)
        output_path: Çıktı dosya yolu (None ise otomatik oluşturulur)
        model: "veo-3", "veo-3-fast", veya "veo-2"
        duration_seconds: Video süresi (5-8 saniye)
        aspect_ratio: "16:9" veya "9:16"
        max_wait_seconds: Maximum bekleme süresi

    Returns:
        {
            "success": bool,
            "video_path": str,
            "duration": float,
            "error": str (if failed)
        }
    """
    from .config import settings

    api_key = settings.gemini_api_key
    if not api_key:
        return {"success": False, "error": "GEMINI_API_KEY not set"}

    model_id = VEO_MODELS.get(model, VEO_MODELS["veo-3"])

    # Çıktı yolu
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/opt/olivenet-social/outputs/veo_video_{timestamp}.mp4"

    # API endpoint
    base_url = "https://generativelanguage.googleapis.com/v1beta"
    generate_url = f"{base_url}/models/{model_id}:predictLongRunning?key={api_key}"

    # Request payload
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "durationSeconds": duration_seconds,
            "personGeneration": "allow_adult"
        }
    }

    logger.info(f"Veo {model} video üretimi başlatılıyor...")
    print(f"🎬 Veo {model} video üretimi başlatılıyor...")
    print(f"   Prompt: {prompt[:100]}...")

    start_time = datetime.now()

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Video üretimini başlat
            async with session.post(generate_url, json=payload, timeout=60) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Veo API Error: {error_text}")
                    return {"success": False, "error": f"API Error {resp.status}: {error_text[:200]}"}

                result = await resp.json()
                operation_name = result.get("name")

                if not operation_name:
                    return {"success": False, "error": "No operation name returned"}

            print(f"   Operation: {operation_name}")
            logger.info(f"Veo operation started: {operation_name}")

            # 2. Polling - tamamlanana kadar bekle
            poll_url = f"{base_url}/{operation_name}?key={api_key}"

            while True:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > max_wait_seconds:
                    return {"success": False, "error": f"Timeout after {max_wait_seconds}s"}

                await asyncio.sleep(5)

                async with session.get(poll_url, timeout=30) as poll_resp:
                    if poll_resp.status != 200:
                        continue

                    poll_data = await poll_resp.json()

                    if poll_data.get("done"):
                        print(f"   ✅ Video hazır! ({elapsed:.1f}s)")
                        logger.info(f"Veo video ready in {elapsed:.1f}s")
                        break

                    metadata = poll_data.get("metadata", {})
                    progress = metadata.get("progressPercent", 0)
                    print(f"   ⏳ İşleniyor... {progress}% ({elapsed:.0f}s)")

            # 3. Video URI'sini al
            response = poll_data.get("response", {})
            videos = response.get("generateVideoResponse", {}).get("generatedSamples", [])

            if not videos:
                videos = response.get("generatedSamples", [])

            if not videos:
                return {"success": False, "error": "No video generated"}

            video_uri = videos[0].get("video", {}).get("uri")
            if not video_uri:
                return {"success": False, "error": "No video URI"}

            # 4. Video'yu indir
            download_url = f"{video_uri}&key={api_key}"

            async with session.get(download_url, timeout=120) as dl_resp:
                if dl_resp.status != 200:
                    return {"success": False, "error": f"Download failed: {dl_resp.status}"}

                video_data = await dl_resp.read()

                with open(output_path, "wb") as f:
                    f.write(video_data)

            total_time = (datetime.now() - start_time).total_seconds()
            file_size = os.path.getsize(output_path)

            print(f"   📁 Kaydedildi: {output_path}")
            print(f"   📊 Boyut: {file_size/1024/1024:.2f} MB")
            print(f"   ⏱️ Toplam süre: {total_time:.1f}s")

            logger.info(f"Veo video saved: {output_path} ({file_size/1024/1024:.2f} MB)")

            return {
                "success": True,
                "video_path": output_path,
                "duration": total_time,
                "file_size": file_size,
                "model": model_id
            }

    except asyncio.TimeoutError:
        return {"success": False, "error": "Request timeout"}
    except Exception as e:
        logger.error(f"Veo error: {str(e)}")
        return {"success": False, "error": str(e)}


async def generate_video_with_retry(
    prompt: str,
    output_path: Optional[str] = None,
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Retry mekanizmalı video üretimi.
    Önce Veo 3, başarısız olursa Veo 3 Fast, sonra Veo 2.
    """

    models_to_try = ["veo-3", "veo-3-fast", "veo-2"]

    for i, model in enumerate(models_to_try):
        print(f"\n🎬 Deneme {i+1}/{len(models_to_try)}: {model}")
        logger.info(f"Trying Veo model: {model}")

        result = await generate_video(
            prompt=prompt,
            output_path=output_path,
            model=model
        )

        if result["success"]:
            return result

        print(f"   ❌ Başarısız: {result.get('error', 'Unknown error')[:100]}")
        logger.warning(f"Veo {model} failed: {result.get('error')}")

    return {"success": False, "error": "All models failed"}
