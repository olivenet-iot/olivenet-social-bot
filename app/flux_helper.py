"""
FLUX.2 Pro Image Generation Helper
Black Forest Labs API ile görsel üretimi
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv('/opt/olivenet-social-bot/.env')

# API Base URL
BFL_API_BASE = "https://api.bfl.ai/v1"


async def generate_image_flux(
    prompt: str,
    output_path: Optional[str] = None,
    width: int = 1024,
    height: int = 1024,
    output_format: str = "png",
    max_wait_seconds: int = 120
) -> Dict[str, Any]:
    """
    FLUX.2 Pro ile görsel üret.

    Args:
        prompt: Görsel için detaylı prompt (İngilizce)
        output_path: Çıktı dosya yolu (None ise otomatik)
        width: Görsel genişliği (default 1024)
        height: Görsel yüksekliği (default 1024)
        output_format: "png" veya "jpeg"
        max_wait_seconds: Maximum bekleme süresi

    Returns:
        {
            "success": bool,
            "image_path": str,
            "cost": float,
            "error": str (if failed)
        }
    """

    api_key = os.getenv("BFL_API_KEY")
    if not api_key:
        return {"success": False, "error": "BFL_API_KEY not set"}

    # Çıktı yolu
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/opt/olivenet-social-bot/outputs/flux_{timestamp}.{output_format}"

    headers = {
        "x-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "output_format": output_format,
        "safety_tolerance": 2
    }

    print(f"🎨 FLUX.2 Pro görsel üretimi başlatılıyor...")
    print(f"   Prompt: {prompt[:100]}...")

    start_time = datetime.now()

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Görsel üretimini başlat
            generate_url = f"{BFL_API_BASE}/flux-2-pro"

            async with session.post(generate_url, headers=headers, json=payload, timeout=60) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return {"success": False, "error": f"API Error {resp.status}: {error_text[:200]}"}

                result = await resp.json()
                task_id = result.get("id")
                polling_url = result.get("polling_url")
                cost = result.get("cost")

                if not task_id:
                    return {"success": False, "error": "No task ID returned"}

            print(f"   Task ID: {task_id}")
            if cost:
                print(f"   Maliyet: {cost} credits (${cost * 0.01:.3f})")

            # 2. Polling - tamamlanana kadar bekle
            result_url = f"{BFL_API_BASE}/get_result?id={task_id}"

            while True:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > max_wait_seconds:
                    return {"success": False, "error": f"Timeout after {max_wait_seconds}s"}

                await asyncio.sleep(2)  # 2 saniye bekle

                async with session.get(result_url, headers=headers, timeout=30) as poll_resp:
                    if poll_resp.status != 200:
                        continue

                    poll_data = await poll_resp.json()
                    status = poll_data.get("status")

                    if status == "Ready":
                        print(f"   ✅ Görsel hazır! ({elapsed:.1f}s)")
                        break
                    elif status == "Error":
                        return {"success": False, "error": poll_data.get("details", "Unknown error")}
                    elif status == "Content Moderated":
                        return {"success": False, "error": "İçerik moderasyon filtresi tarafından engellendi"}
                    elif status == "Request Moderated":
                        return {"success": False, "error": "İstek moderasyon filtresi tarafından engellendi"}

                    # İlerleme göster
                    progress = poll_data.get("progress")
                    if progress:
                        print(f"   ⏳ İşleniyor... {progress}% ({elapsed:.0f}s)")

            # 3. Görseli indir
            image_url = poll_data.get("result", {}).get("sample")
            if not image_url:
                return {"success": False, "error": "No image URL in result"}

            async with session.get(image_url, timeout=60) as dl_resp:
                if dl_resp.status != 200:
                    return {"success": False, "error": f"Download failed: {dl_resp.status}"}

                image_data = await dl_resp.read()

                with open(output_path, "wb") as f:
                    f.write(image_data)

            total_time = (datetime.now() - start_time).total_seconds()
            file_size = os.path.getsize(output_path)

            print(f"   📁 Kaydedildi: {output_path}")
            print(f"   📊 Boyut: {file_size/1024:.1f} KB")
            print(f"   ⏱️ Toplam süre: {total_time:.1f}s")

            return {
                "success": True,
                "image_path": output_path,
                "duration": total_time,
                "file_size": file_size,
                "cost": cost
            }

    except asyncio.TimeoutError:
        return {"success": False, "error": "Request timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_credits() -> Dict[str, Any]:
    """
    Kullanıcının kalan kredisini sorgula.
    """
    api_key = os.getenv("BFL_API_KEY")
    if not api_key:
        return {"success": False, "error": "BFL_API_KEY not set"}

    headers = {"x-key": api_key}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BFL_API_BASE}/credits", headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"success": True, "credits": data.get("credits", 0)}
                else:
                    return {"success": False, "error": f"API Error {resp.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
