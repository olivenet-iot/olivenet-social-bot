"""
Cloudinary Helper - Video CDN Upload
Instagram Reels icin public URL gerekli
"""

import os
from typing import Dict, Any
import asyncio
from datetime import datetime

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("cloudinary")

CLOUDINARY_CLOUD_NAME = settings.cloudinary_cloud_name or os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = settings.cloudinary_api_key or os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = settings.cloudinary_api_secret or os.getenv("CLOUDINARY_API_SECRET")

# Cloudinary'yi configure et
_configured = False

def configure_cloudinary():
    """Cloudinary'yi configure et"""
    global _configured

    if _configured:
        return True

    if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        print("[CLOUDINARY] ❌ Credentials eksik:")
        print(f"   CLOUD_NAME: {'✅' if CLOUDINARY_CLOUD_NAME else '❌'}")
        print(f"   API_KEY: {'✅' if CLOUDINARY_API_KEY else '❌'}")
        print(f"   API_SECRET: {'✅' if CLOUDINARY_API_SECRET else '❌'}")
        return False

    try:
        import cloudinary

        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True
        )

        _configured = True
        print(f"[CLOUDINARY] ✅ Configured: {CLOUDINARY_CLOUD_NAME}")
        return True

    except ImportError:
        print("[CLOUDINARY] ❌ cloudinary paketi yuklu degil: pip install cloudinary")
        return False
    except Exception as e:
        print(f"[CLOUDINARY] ❌ Config hatasi: {e}")
        return False


async def upload_video_to_cloudinary(video_path: str, folder: str = "olivenet-reels") -> Dict[str, Any]:
    """
    Video'yu Cloudinary'ye yukle

    Args:
        video_path: Yerel video dosyasi yolu
        folder: Cloudinary klasoru

    Returns:
        {"success": True, "url": "https://...", "public_id": "..."}
    """

    if not configure_cloudinary():
        return {"success": False, "error": "Cloudinary not configured"}

    if not os.path.exists(video_path):
        print(f"[CLOUDINARY] ❌ Dosya bulunamadi: {video_path}")
        return {"success": False, "error": f"File not found: {video_path}"}

    file_size = os.path.getsize(video_path) / 1024 / 1024
    print(f"[CLOUDINARY] 📤 Video yukleniyor: {video_path}")
    print(f"[CLOUDINARY] Boyut: {file_size:.2f} MB")

    try:
        import cloudinary.uploader

        # Async upload icin thread pool kullan
        loop = asyncio.get_event_loop()

        def do_upload():
            return cloudinary.uploader.upload(
                video_path,
                resource_type="video",
                folder=folder,
                overwrite=True
            )

        result = await loop.run_in_executor(None, do_upload)

        secure_url = result.get("secure_url")
        public_id = result.get("public_id")
        duration = result.get("duration")

        print(f"[CLOUDINARY] ✅ Yukleme basarili!")
        print(f"[CLOUDINARY] URL: {secure_url}")

        return {
            "success": True,
            "url": secure_url,
            "public_id": public_id,
            "duration": duration,
            "format": result.get("format", "mp4")
        }

    except Exception as e:
        print(f"[CLOUDINARY] ❌ Yukleme hatasi: {str(e)}")
        return {"success": False, "error": str(e)}


async def delete_from_cloudinary(public_id: str) -> Dict[str, Any]:
    """Cloudinary'den video sil"""

    if not configure_cloudinary():
        return {"success": False, "error": "Cloudinary not configured"}

    try:
        import cloudinary.uploader

        loop = asyncio.get_event_loop()

        def do_delete():
            return cloudinary.uploader.destroy(public_id, resource_type="video")

        result = await loop.run_in_executor(None, do_delete)

        if result.get("result") == "ok":
            return {"success": True}
        else:
            return {"success": False, "error": result}

    except Exception as e:
        return {"success": False, "error": str(e)}
