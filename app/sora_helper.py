"""
OpenAI Sora Video Generation API
Docs: https://platform.openai.com/docs/api-reference/videos
"""

import os
import httpx
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Tuple

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("sora")

OPENAI_API_KEY = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1"
OUTPUT_DIR = str(settings.outputs_dir)

# No-text suffix for video generation
# AI video generation cannot reliably render text, so we avoid it
VIDEO_NO_TEXT_SUFFIX = """

IMPORTANT VISUAL RULES:
- NO TEXT in the video - avoid any written words, labels, or titles
- NO LOGOS or brand names visible
- Focus on visual storytelling without text overlays
- Any signage or screens should be blurred or generic
"""

# Voice reels suffix - video will have TTS voiceover added
VOICE_REELS_SUFFIX = """

AUDIO/DIALOGUE RULES (voiceover will be added separately):
- NO spoken dialogue or talking in the video
- NO lip movements or talking heads
- NO people speaking to camera
- Cinematic ambient sounds only (nature, city, atmosphere)
- Visual storytelling without on-screen narration
"""


async def generate_video_sora(
    prompt: str,
    duration: int = 8,
    size: str = "720x1280",
    model: str = "sora-2",
    voice_mode: bool = False
) -> Dict[str, Any]:
    """
    Sora ile video uret

    Args:
        prompt: Video aciklamasi
        duration: 4, 8, veya 12 saniye
        size: "720x1280" (9:16) veya "1280x720" (16:9)
        model: "sora-2" veya "sora-2-pro"
        voice_mode: True ise TTS voiceover eklenecek, video dialogue'suz olmalı
    """

    if not OPENAI_API_KEY:
        print("[SORA] ❌ OPENAI_API_KEY not set")
        return {"success": False, "error": "OPENAI_API_KEY not set", "fallback": "veo3"}

    # Add no-text suffix to avoid AI text rendering issues
    prompt = prompt + VIDEO_NO_TEXT_SUFFIX

    # Voice mode için dialogue/talking kısıtlamaları ekle
    if voice_mode:
        prompt = prompt + VOICE_REELS_SUFFIX

    # Duration validation - model'e göre
    if model == "sora-2-pro":
        valid_durations = [10, 15, 25]
    else:
        valid_durations = [4, 8, 12]

    if duration not in valid_durations:
        duration = min(valid_durations, key=lambda x: abs(x - duration))

    print(f"[SORA] 🎬 Video uretimi baslatiliyor...")
    print(f"[SORA] Model: {model}, Sure: {duration}s, Boyut: {size}")
    print(f"[SORA] Prompt: {prompt[:80]}...")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    # CRITICAL: multipart/form-data icin files= kullan, data= degil!
    # httpx'te files= kullaninca Content-Type: multipart/form-data olur
    # Bos dosya ile field'lari gonderiyoruz
    files = {
        "model": (None, model),
        "prompt": (None, prompt),
        "seconds": (None, str(duration)),
        "size": (None, size)
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            print(f"[SORA] API'ye istek gonderiliyor (multipart/form-data)...")

            # POST with files= for true multipart/form-data
            response = await client.post(
                f"{OPENAI_API_URL}/videos",
                headers=headers,
                files=files  # files= for multipart/form-data
            )

            print(f"[SORA] Response: {response.status_code}")

            if response.status_code not in [200, 201]:
                error_text = response.text[:500]
                print(f"[SORA] ❌ API hatasi: {error_text}")
                return {"success": False, "error": error_text, "fallback": "veo3"}

            job_data = response.json()
            video_id = job_data.get("id")
            status = job_data.get("status")

            print(f"[SORA] ✅ Job baslatildi: {video_id}")
            print(f"[SORA] Status: {status}")

        # 2. Job tamamlanana kadar bekle (polling)
        async with httpx.AsyncClient(timeout=600) as client:
            start_time = datetime.now()
            max_wait = 300  # 5 dakika

            while True:
                await asyncio.sleep(10)

                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > max_wait:
                    return {"success": False, "error": "Timeout", "fallback": "veo3"}

                # GET /videos/{video_id}
                status_response = await client.get(
                    f"{OPENAI_API_URL}/videos/{video_id}",
                    headers=headers
                )

                if status_response.status_code != 200:
                    print(f"[SORA] Status check failed: {status_response.status_code}")
                    continue

                status_data = status_response.json()
                current_status = status_data.get("status")
                progress = status_data.get("progress", 0)

                print(f"[SORA] Status: {current_status}, Progress: {progress}% ({int(elapsed)}s)")

                if current_status == "completed":
                    print(f"[SORA] ✅ Video tamamlandi!")
                    break
                elif current_status == "failed":
                    error = status_data.get("error", {})
                    error_msg = error.get("message", "Unknown") if isinstance(error, dict) else str(error)
                    print(f"[SORA] ❌ Failed: {error_msg}")
                    return {"success": False, "error": error_msg, "fallback": "veo3"}

        # 3. Video'yu indir - GET /videos/{video_id}/content
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            print(f"[SORA] Video indiriliyor...")

            content_response = await client.get(
                f"{OPENAI_API_URL}/videos/{video_id}/content",
                headers=headers
            )

            if content_response.status_code != 200:
                print(f"[SORA] ❌ Download failed: {content_response.status_code}")
                return {"success": False, "error": f"Download failed: {content_response.status_code}"}

            # Dosyaya kaydet
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = f"{OUTPUT_DIR}/sora_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

            with open(output_path, 'wb') as f:
                f.write(content_response.content)

            file_size = os.path.getsize(output_path) / 1024 / 1024
            print(f"[SORA] ✅ Kaydedildi: {output_path}")
            print(f"[SORA] Boyut: {file_size:.2f} MB")

            return {
                "success": True,
                "video_path": output_path,
                "video_id": video_id,
                "duration": duration,
                "model": model,
                "model_used": model,
                "file_size_mb": round(file_size, 2)
            }

    except httpx.TimeoutException:
        print(f"[SORA] ⚠️ Timeout")
        return {"success": False, "error": "timeout", "fallback": "veo3"}
    except Exception as e:
        print(f"[SORA] ❌ Exception: {str(e)}")
        return {"success": False, "error": str(e), "fallback": "veo3"}


def analyze_prompt_complexity(prompt: str, topic: str = "") -> Dict[str, Any]:
    """Prompt karmasikligini analiz et"""
    combined = f"{(prompt or '').lower()} {(topic or '').lower()}"  # None-safe

    high_keywords = ["transformation", "morphing", "cinematic", "epic", "dramatic"]
    medium_keywords = ["tracking", "dolly", "movement", "animation", "transition"]

    for kw in high_keywords:
        if kw in combined:
            return {"complexity": "high", "model": "veo3", "duration": 8}

    for kw in medium_keywords:
        if kw in combined:
            return {"complexity": "medium", "model": "veo3", "duration": 8}

    return {"complexity": "low", "model": "veo3", "duration": 6}


async def generate_video_smart(
    prompt: str,
    topic: str = "",
    force_model: str = None,
    duration: int = 8,
    voice_mode: bool = False
) -> Dict[str, Any]:
    """Akilli video uretimi - Kling / Sora / Veo secimi

    Args:
        voice_mode: True ise TTS voiceover eklenecek, Sora'ya NO dialogue suffix eklenir
    """

    if force_model:
        model = force_model
        complexity = {"complexity": "forced", "model": force_model, "duration": duration}
    else:
        complexity = analyze_prompt_complexity(prompt, topic)
        model = complexity.get("model", "veo3")
        duration = complexity.get("duration", duration)

    # Model isim normalizasyonu (UI'dan gelen kısa isimler ve video_models.py ID'leri)
    model_aliases = {
        "sora2": "sora-2",
        "sora2-pro": "sora-2-pro",
        "veo": "veo3",
        # Multi-model voice reels ID'leri (video_models.py → fal_helper.py)
        "kling-2.5-pro": "kling_pro",
        "kling-2.6-pro": "kling_26_pro",
        "kling-2.1": "kling_pro",  # Backward compatibility
        "wan-2.1": "wan_26",
        "veo-2": "veo3",
        "minimax": "hailuo_pro"
    }
    if model in model_aliases:
        model = model_aliases[model]

    print(f"[VIDEO] 🎯 Complexity: {complexity.get('complexity')}")
    print(f"[VIDEO] Model: {model}")

    # Kling modelleri icin fal.ai kullan
    if model and model.startswith("kling"):
        print(f"[VIDEO] → Kling AI ({model}) kullaniliyor...")
        try:
            from app.fal_helper import FalVideoGenerator
            # Voice mode'da native audio KAPATILIR (TTS voiceover eklenecek)
            # Kling 2.6 için normalde audio aktif, ama voice_mode'da kapalı
            if voice_mode:
                generate_audio = False  # TTS voiceover için native audio kapat
                print(f"[VIDEO] → Voice mode: Native audio KAPALI")
            else:
                generate_audio = True if model == "kling_26_pro" else None
            result = await FalVideoGenerator.generate_video(
                prompt=prompt,
                model=model,
                duration=min(duration, 10),  # Kling 10 saniyeye kadar destekliyor
                aspect_ratio="9:16",
                generate_audio=generate_audio
            )
            if result.get("success"):
                return result
            # Kling basarisiz - Veo'ya fallback
            print(f"[VIDEO] ⚠️ Kling basarisiz: {result.get('error')}, Veo'ya geciliyor...")
        except Exception as e:
            print(f"[VIDEO] ⚠️ Kling hatasi: {e}, Veo'ya geciliyor...")

        # Fallback to Veo
        from app.veo_helper import generate_video_veo3
        result = await generate_video_veo3(prompt, aspect_ratio="9:16", duration_seconds=duration)
        if result.get("success"):
            result["fallback_from"] = model
            result["model_used"] = result.get("model", "veo-3")
        return result

    # Hailuo modelleri icin fal.ai kullan
    if model and model.startswith("hailuo"):
        print(f"[VIDEO] → Hailuo AI ({model}) kullaniliyor...")
        try:
            from app.fal_helper import FalVideoGenerator
            result = await FalVideoGenerator.generate_video(
                prompt=prompt,
                model=model,
                duration=min(duration, 6),  # Hailuo max 6s
                aspect_ratio="9:16"
            )
            if result.get("success"):
                return result
            print(f"[VIDEO] ⚠️ Hailuo basarisiz: {result.get('error')}, Veo'ya geciliyor...")
        except Exception as e:
            print(f"[VIDEO] ⚠️ Hailuo hatasi: {e}, Veo'ya geciliyor...")

        # Fallback to Veo
        from app.veo_helper import generate_video_veo3
        result = await generate_video_veo3(prompt, aspect_ratio="9:16", duration_seconds=duration)
        if result.get("success"):
            result["fallback_from"] = model
            result["model_used"] = result.get("model", "veo-3")
        return result

    # Wan modeli icin fal.ai kullan
    if model == "wan_26":
        print(f"[VIDEO] → Wan 2.6 kullaniliyor...")
        try:
            from app.fal_helper import FalVideoGenerator
            result = await FalVideoGenerator.generate_video(
                prompt=prompt,
                model="wan_26",
                duration=min(duration, 15),  # Wan max 15s
                aspect_ratio="9:16"
            )
            if result.get("success"):
                return result
            print(f"[VIDEO] ⚠️ Wan basarisiz: {result.get('error')}, Veo'ya geciliyor...")
        except Exception as e:
            print(f"[VIDEO] ⚠️ Wan hatasi: {e}, Veo'ya geciliyor...")

        # Fallback to Veo
        from app.veo_helper import generate_video_veo3
        result = await generate_video_veo3(prompt, aspect_ratio="9:16", duration_seconds=duration)
        if result.get("success"):
            result["fallback_from"] = model
            result["model_used"] = result.get("model", "veo-3")
        return result

    # Veo secildiyse direkt Veo'ya git
    if model == "veo3" or model.startswith("veo"):
        print(f"[VIDEO] → Veo kullaniliyor...")
        from app.veo_helper import generate_video_veo3
        result = await generate_video_veo3(prompt, aspect_ratio="9:16", duration_seconds=duration)
        if result.get("success"):
            result["model_used"] = result.get("model", "veo-3")
        return result

    # Sora dene
    print(f"[VIDEO] → {model} deneniyor...")

    sora_result = await generate_video_sora(
        prompt=prompt,
        duration=duration,
        size="720x1280",
        model=model if model in ["sora-2", "sora-2-pro"] else "sora-2",
        voice_mode=voice_mode
    )

    if sora_result.get("success"):
        return sora_result

    # Sora basarisiz - Veo'ya fallback
    if sora_result.get("fallback") == "veo3":
        print(f"[VIDEO] ⚠️ Sora basarisiz, Veo'ya geciliyor...")
        from app.veo_helper import generate_video_veo3
        result = await generate_video_veo3(prompt, aspect_ratio="9:16", duration_seconds=duration)
        if result.get("success"):
            result["fallback_from"] = model
            result["model_used"] = result.get("model", "veo-3")
        return result

    return sora_result


async def generate_videos_parallel(
    prompts: List[str],
    model: str = "kling-2.6-pro",
    duration: int = 10,
    style_prefix: str = "",
    max_concurrent: int = 3,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Birden fazla videoyu paralel olarak üret.

    Args:
        prompts: Her segment için video promptları listesi
        model: Kullanılacak video modeli
        duration: Her segment'in süresi (saniye)
        style_prefix: Tüm promptlara eklenecek stil prefix'i
        max_concurrent: Aynı anda çalışacak maksimum API çağrısı
        max_retries: Başarısız segment için yeniden deneme sayısı

    Returns:
        {
            "success": bool,
            "video_paths": [str],  # Sıralı video yolları
            "failed_indices": [int],  # Başarısız segment indeksleri
            "model_used": str,
            "total_duration": float
        }
    """
    if not prompts:
        return {"success": False, "error": "Prompt listesi boş"}

    print(f"[PARALLEL VIDEO] {len(prompts)} segment üretiliyor...")
    print(f"[PARALLEL VIDEO] Model: {model}, Segment süresi: {duration}s")
    print(f"[PARALLEL VIDEO] Max concurrent: {max_concurrent}")

    # Segment-specific shot type ve kamera prefix'leri (görsel çeşitlilik için)
    SEGMENT_PREFIXES = [
        "WIDE ESTABLISHING SHOT, slow dolly forward, cinematic depth of field, ",
        "MEDIUM SHOT, tracking alongside subject, dynamic camera movement, ",
        "CLOSE-UP DETAIL SHOT, smooth push in, macro focus, emotional impact, "
    ]

    # Her segment için farklı prefix + style prefix ekle
    full_prompts = []
    for i, prompt in enumerate(prompts):
        seg_prefix = SEGMENT_PREFIXES[i % len(SEGMENT_PREFIXES)]
        if style_prefix:
            full_prompt = f"{seg_prefix}{style_prefix}\n\n{prompt}"
        else:
            full_prompt = f"{seg_prefix}{prompt}"
        full_prompts.append(full_prompt)
        print(f"   Prompt {i+1}: {full_prompt[:80]}...")

    # Semaphore ile concurrent limit
    semaphore = asyncio.Semaphore(max_concurrent)

    async def generate_single_with_limit(
        index: int,
        prompt: str
    ) -> Tuple[int, Dict[str, Any]]:
        """Tek bir video üret (semaphore ile sınırlı)"""
        async with semaphore:
            print(f"[PARALLEL VIDEO] Segment {index + 1}/{len(prompts)} başlıyor...")

            result = await generate_video_smart(
                prompt=prompt,
                force_model=model,
                duration=duration,
                voice_mode=True
            )

            if result.get("success"):
                print(f"[PARALLEL VIDEO] ✓ Segment {index + 1} tamamlandı")
            else:
                print(f"[PARALLEL VIDEO] ✗ Segment {index + 1} başarısız: {result.get('error', 'Unknown')}")

            return (index, result)

    # İlk deneme - tüm segmentleri paralel başlat
    tasks = [
        generate_single_with_limit(i, prompt)
        for i, prompt in enumerate(full_prompts)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Sonuçları işle
    video_paths: List[Tuple[int, str]] = []
    failed_indices: List[int] = []

    for i, item in enumerate(results):
        if isinstance(item, Exception):
            # Task exception fırlattı - index'i koru
            failed_indices.append(i)
            print(f"[PARALLEL VIDEO] ✗ Segment {i + 1} exception: {item}")
            continue

        index, result = item

        if result.get("success") and result.get("video_path"):
            video_paths.append((index, result["video_path"]))
        else:
            failed_indices.append(index)

    # Başarısız segmentleri yeniden dene
    for retry in range(max_retries):
        if not failed_indices:
            break

        print(f"[PARALLEL VIDEO] Retry {retry + 1}/{max_retries} - {len(failed_indices)} segment")

        retry_tasks = [
            generate_single_with_limit(idx, full_prompts[idx])
            for idx in failed_indices
            if isinstance(idx, int)  # Exception olanları atla
        ]

        retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)

        new_failed = []
        for item in retry_results:
            if isinstance(item, Exception):
                continue

            index, result = item

            if result.get("success") and result.get("video_path"):
                video_paths.append((index, result["video_path"]))
                # Başarılı olanları failed listesinden çıkar
                if index in failed_indices:
                    failed_indices.remove(index)
            else:
                new_failed.append(index)

        failed_indices = [idx for idx in failed_indices if idx in new_failed]

    # Sıraya göre düzenle
    video_paths.sort(key=lambda x: x[0])
    ordered_paths = [path for _, path in video_paths]

    # Başarı durumu - en az 2 segment gerekli
    success = len(ordered_paths) >= 2

    if success:
        print(f"[PARALLEL VIDEO] ✓ {len(ordered_paths)}/{len(prompts)} segment tamamlandı")
    else:
        print(f"[PARALLEL VIDEO] ✗ Yeterli segment üretilemedi: {len(ordered_paths)}/{len(prompts)}")

    return {
        "success": success,
        "video_paths": ordered_paths,
        "failed_indices": list(set([idx for idx in failed_indices if isinstance(idx, int)])),
        "model_used": model,
        "total_duration": len(ordered_paths) * duration,
        "segment_count": len(ordered_paths),
        "requested_count": len(prompts)
    }
