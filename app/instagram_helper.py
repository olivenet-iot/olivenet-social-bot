"""
Instagram Helper - Instagram Graph API Entegrasyonu
Yeni API: graph.instagram.com v21.0 (Instagram Login)
"""

import os
import asyncio
import aiohttp
import subprocess
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("instagram")

# Instagram Graph API URL (YENİ - graph.instagram.com)
GRAPH_API_URL = "https://graph.instagram.com/v21.0"

# Video conversion output directory
OUTPUT_DIR = str(settings.outputs_dir)


def get_instagram_credentials() -> Dict[str, str]:
    """Instagram API credentials'ları al"""
    return {
        "access_token": os.getenv("INSTAGRAM_ACCESS_TOKEN", ""),
        "user_id": os.getenv("INSTAGRAM_USER_ID", ""),
        "business_id": os.getenv("INSTAGRAM_BUSINESS_ID", "")
    }


async def convert_video_for_instagram(input_path: str) -> Dict[str, Any]:
    """
    Video'yu Instagram Reels formatına dönüştür

    Instagram Gereksinimleri:
    - Codec: H.264 (video), AAC (audio)
    - Çözünürlük: 720x1280 (9:16)
    - FPS: 30
    - Max süre: 90 saniye
    - Format: MP4
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Video bulunamadı: {input_path}"}

    print(f"[VIDEO CONVERT] Kaynak: {input_path}")

    # ffmpeg kontrolü
    try:
        result = subprocess.run(["which", "ffmpeg"], capture_output=True)
        if result.returncode != 0:
            print("[VIDEO CONVERT] ffmpeg yüklü değil!")
            return {"success": False, "error": "ffmpeg not installed"}
    except Exception as e:
        return {"success": False, "error": f"ffmpeg check failed: {e}"}

    # Video bilgilerini al
    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,r_frame_rate",
            "-of", "csv=p=0",
            input_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        probe_output = probe_result.stdout.strip()
        print(f"[VIDEO CONVERT] Probe: {probe_output}")

        parts = probe_output.split(",")
        if len(parts) >= 4:
            codec = parts[0]
            width = int(parts[1])
            height = int(parts[2])
            fps_str = parts[3]

            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = int(num) / int(den) if int(den) > 0 else 30
            else:
                fps = float(fps_str)

            print(f"[VIDEO CONVERT] Codec: {codec}, Size: {width}x{height}, FPS: {fps:.1f}")

            is_compatible = (
                codec == "h264" and
                width == 720 and
                height == 1280 and
                abs(fps - 30) < 1
            )

            if is_compatible:
                print("[VIDEO CONVERT] Video zaten Instagram uyumlu!")
                return {
                    "success": True,
                    "output_path": input_path,
                    "converted": False,
                    "original_codec": codec,
                    "original_size": f"{width}x{height}"
                }
    except Exception as e:
        print(f"[VIDEO CONVERT] Probe hatası: {e}")

    # Dönüştürülmüş dosya yolu
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{OUTPUT_DIR}/ig_ready_{timestamp}.mp4"

    print(f"[VIDEO CONVERT] Dönüştürülüyor: {output_path}")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "30",
        "-movflags", "+faststart",
        "-t", "90",
        output_path
    ]

    try:
        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if process.returncode != 0:
            print(f"[VIDEO CONVERT] ffmpeg hatası: {process.stderr[:500]}")
            return {"success": False, "error": f"ffmpeg error: {process.stderr[:200]}"}

        if not os.path.exists(output_path):
            return {"success": False, "error": "Output file not created"}

        file_size = os.path.getsize(output_path) / 1024 / 1024
        print(f"[VIDEO CONVERT] Başarılı! Boyut: {file_size:.2f} MB")

        return {
            "success": True,
            "output_path": output_path,
            "converted": True,
            "file_size_mb": round(file_size, 2)
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "ffmpeg timeout (5 min)"}
    except Exception as e:
        print(f"[VIDEO CONVERT] Exception: {e}")
        return {"success": False, "error": str(e)}


async def get_account_info() -> Dict[str, Any]:
    """
    Instagram hesap bilgilerini al

    Returns:
        {"id": "...", "username": "...", "media_count": N, "followers_count": N}
    """
    creds = get_instagram_credentials()

    if not creds["access_token"] or not creds["user_id"]:
        return {"success": False, "error": "Instagram credentials eksik"}

    url = f"{GRAPH_API_URL}/{creds['user_id']}"
    params = {
        "fields": "id,username,media_count,followers_count",
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if "error" in data:
                    print(f"[INSTAGRAM] API Error: {data['error'].get('message', 'Unknown')}")
                    return {"success": False, "error": data["error"].get("message")}

                print(f"[INSTAGRAM] Hesap: @{data.get('username')} | Takipçi: {data.get('followers_count', 0)}")
                return {"success": True, **data}

    except Exception as e:
        print(f"[INSTAGRAM] Connection error: {e}")
        return {"success": False, "error": str(e)}


async def create_media_container(
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    caption: str = "",
    media_type: str = "IMAGE",
    is_carousel_item: bool = False
) -> Optional[str]:
    """
    Instagram Media Container oluştur (2-aşamalı yükleme için)

    Args:
        image_url: Görsel URL'i (public erişilebilir, direkt .jpg/.png)
        video_url: Video URL'i (public erişilebilir)
        caption: Post caption'ı
        media_type: IMAGE, REELS, veya CAROUSEL
        is_carousel_item: Carousel child item mi?

    Returns:
        Container ID veya None
    """
    creds = get_instagram_credentials()

    if not creds["access_token"] or not creds["user_id"]:
        print("[INSTAGRAM] Credentials eksik!")
        return None

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media"

    data = {
        "access_token": creds["access_token"]
    }

    # Carousel item değilse caption ekle
    if not is_carousel_item and caption:
        data["caption"] = caption

    # Media type'a göre URL ekle
    if media_type == "IMAGE":
        data["image_url"] = image_url
    elif media_type == "REELS":
        data["video_url"] = video_url
        data["media_type"] = "REELS"

    # Carousel item flag
    if is_carousel_item:
        data["is_carousel_item"] = "true"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                result = await response.json()

                if "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    print(f"[INSTAGRAM] Container Error: {error_msg}")
                    return None

                container_id = result.get("id")
                print(f"[INSTAGRAM] Media Container oluşturuldu: {container_id}")
                return container_id

    except Exception as e:
        print(f"[INSTAGRAM] Container creation error: {e}")
        return None


async def create_carousel_container(
    children_ids: List[str],
    caption: str = ""
) -> Optional[str]:
    """
    Carousel ana container oluştur

    Args:
        children_ids: Child container ID listesi
        caption: Post caption'ı

    Returns:
        Carousel container ID veya None
    """
    creds = get_instagram_credentials()

    if not creds["access_token"] or not creds["user_id"]:
        return None

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media"

    data = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                result = await response.json()

                if "error" in result:
                    print(f"[INSTAGRAM] Carousel Container Error: {result['error'].get('message')}")
                    return None

                container_id = result.get("id")
                print(f"[INSTAGRAM] Carousel Container: {container_id}")
                return container_id

    except Exception as e:
        print(f"[INSTAGRAM] Carousel container error: {e}")
        return None


async def check_container_status(container_id: str) -> Dict[str, Any]:
    """
    Media container durumunu kontrol et (video için gerekli)
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{container_id}"
    params = {
        "fields": "status_code,status",
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                return await response.json()
    except Exception as e:
        return {"error": str(e)}


async def publish_media(container_id: str) -> Dict[str, Any]:
    """
    Media container'ı yayınla

    Args:
        container_id: Media container ID

    Returns:
        {"success": True, "id": "post_id"} veya {"success": False, "error": "..."}
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media_publish"
    data = {
        "creation_id": container_id,
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                result = await response.json()

                if "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    print(f"[INSTAGRAM] Publish Error: {error_msg}")
                    return {"success": False, "error": error_msg}

                post_id = result.get("id")
                print(f"[INSTAGRAM] Post yayınlandı! ID: {post_id}")
                return {"success": True, "id": post_id}

    except Exception as e:
        print(f"[INSTAGRAM] Publish error: {e}")
        return {"success": False, "error": str(e)}


async def post_photo_to_instagram(
    image_url: str,
    caption: str = ""
) -> Dict[str, Any]:
    """
    Instagram'a fotoğraf paylaş

    Args:
        image_url: Görsel URL'i (PUBLIC, direkt .jpg/.png - redirect yok!)
        caption: Post caption'ı

    Returns:
        {"success": True, "id": "..."} veya {"success": False, "error": "..."}
    """
    print(f"[INSTAGRAM] Fotoğraf paylaşılıyor...")
    print(f"[INSTAGRAM] Image URL: {image_url[:80]}...")

    # Adım 1: Container oluştur
    container_id = await create_media_container(
        image_url=image_url,
        caption=caption,
        media_type="IMAGE"
    )

    if not container_id:
        return {"success": False, "error": "Media container oluşturulamadı"}

    # Biraz bekle
    await asyncio.sleep(2)

    # Adım 2: Yayınla
    result = await publish_media(container_id)
    if result.get("success"):
        result["platform"] = "instagram"
    return result


async def post_video_to_instagram(
    video_url: str,
    caption: str = ""
) -> Dict[str, Any]:
    """
    Instagram'a Reels paylaş

    Args:
        video_url: Video URL'i (PUBLIC erişilebilir!)
        caption: Reels caption'ı

    Returns:
        {"success": True, "id": "..."} veya {"success": False, "error": "..."}
    """
    print(f"[INSTAGRAM] Reels paylaşılıyor...")

    # Adım 1: REELS container oluştur
    container_id = await create_media_container(
        video_url=video_url,
        caption=caption,
        media_type="REELS"
    )

    if not container_id:
        return {"success": False, "error": "Media container oluşturulamadı"}

    # Video processing bekle
    print("[INSTAGRAM] Video işleniyor, bekleyin...")
    max_attempts = 30
    for attempt in range(max_attempts):
        await asyncio.sleep(10)

        status = await check_container_status(container_id)
        status_code = status.get("status_code")

        if status_code == "FINISHED":
            print("[INSTAGRAM] Video işleme tamamlandı!")
            break
        elif status_code == "ERROR":
            error_msg = status.get("status", "Unknown error")
            return {"success": False, "error": f"Video processing error: {error_msg}"}
        elif status_code == "IN_PROGRESS":
            print(f"[INSTAGRAM] Video işleniyor... ({attempt + 1}/{max_attempts})")
        else:
            print(f"[INSTAGRAM] Status: {status_code}")
    else:
        return {"success": False, "error": "Video processing timeout"}

    # Adım 2: Yayınla
    result = await publish_media(container_id)
    if result.get("success"):
        result["platform"] = "instagram_reels"
    return result


async def post_carousel_to_instagram(
    image_urls: List[str],
    caption: str = ""
) -> Dict[str, Any]:
    """
    Instagram'a Carousel (çoklu görsel) paylaş

    Args:
        image_urls: Görsel URL listesi (2-10 arası, PUBLIC!)
        caption: Post caption'ı

    Returns:
        {"success": True, "id": "..."} veya {"success": False, "error": "..."}
    """
    if len(image_urls) < 2 or len(image_urls) > 10:
        return {"success": False, "error": "Carousel 2-10 arası görsel içermeli"}

    print(f"[INSTAGRAM] Carousel paylaşılıyor ({len(image_urls)} görsel)...")

    # Adım 1: Her görsel için child container oluştur
    children_ids = []
    for i, image_url in enumerate(image_urls):
        print(f"[INSTAGRAM] Carousel item {i+1}/{len(image_urls)} oluşturuluyor...")
        container_id = await create_media_container(
            image_url=image_url,
            media_type="IMAGE",
            is_carousel_item=True
        )

        if container_id:
            children_ids.append(container_id)
            await asyncio.sleep(2)  # Rate limit
        else:
            print(f"[INSTAGRAM] Item {i+1} oluşturulamadı!")

    if len(children_ids) < 2:
        return {"success": False, "error": "En az 2 carousel item gerekli"}

    # Adım 2: Ana carousel container oluştur
    carousel_container_id = await create_carousel_container(
        children_ids=children_ids,
        caption=caption
    )

    if not carousel_container_id:
        return {"success": False, "error": "Carousel container oluşturulamadı"}

    # Biraz bekle
    await asyncio.sleep(3)

    # Adım 3: Yayınla
    result = await publish_media(carousel_container_id)
    if result.get("success"):
        result["platform"] = "instagram_carousel"
        result["slide_count"] = len(children_ids)
    return result


async def upload_image_to_cdn(local_path: str) -> Optional[str]:
    """
    Lokal görseli CDN'e yükle ve public URL döndür

    Args:
        local_path: Lokal dosya yolu

    Returns:
        Public URL veya None
    """
    imgbb_key = os.getenv("IMGBB_API_KEY")

    if imgbb_key and os.path.exists(local_path):
        try:
            import base64

            with open(local_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.imgbb.com/1/upload",
                    data={
                        "key": imgbb_key,
                        "image": image_data
                    }
                ) as response:
                    result = await response.json()

                    if result.get("success"):
                        url = result["data"]["url"]
                        print(f"[INSTAGRAM] Görsel yüklendi: {url}")
                        return url
                    else:
                        print(f"[INSTAGRAM] Imgbb error: {result}")

        except Exception as e:
            print(f"[INSTAGRAM] CDN upload error: {e}")

    return None


async def post_reels_to_instagram(
    video_path: str,
    caption: str = "",
    max_retries: int = 3,
    skip_conversion: bool = False
) -> Dict[str, Any]:
    """
    Lokal video dosyasını Instagram Reels olarak paylaş

    Args:
        video_path: Lokal video dosyası yolu
        caption: Reels caption'ı
        max_retries: Maksimum deneme sayısı
        skip_conversion: Video dönüşümünü atla

    Returns:
        {"success": True, "id": "...", "cdn_url": "..."} veya hata
    """
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video dosyası bulunamadı: {video_path}"}

    print(f"[INSTAGRAM REELS] Reels paylaşılıyor...")
    print(f"[INSTAGRAM REELS] Video: {video_path}")

    # Video'yu Instagram formatına dönüştür
    upload_path = video_path
    if not skip_conversion:
        print("[INSTAGRAM REELS] Video Instagram formatına dönüştürülüyor...")
        convert_result = await convert_video_for_instagram(video_path)

        if not convert_result.get("success"):
            print(f"[INSTAGRAM REELS] Dönüşüm hatası: {convert_result.get('error')}")
            print("[INSTAGRAM REELS] Orijinal video ile devam ediliyor...")
        else:
            upload_path = convert_result.get("output_path", video_path)
            if convert_result.get("converted"):
                print(f"[INSTAGRAM REELS] Dönüştürüldü: {upload_path}")

    # Video'yu Cloudinary'ye yükle
    try:
        from app.cloudinary_helper import upload_video_to_cloudinary

        cdn_result = await upload_video_to_cloudinary(upload_path)

        if not cdn_result.get("success"):
            return {"success": False, "error": f"CDN upload failed: {cdn_result.get('error')}"}

        video_url = cdn_result.get("url")
        print(f"[INSTAGRAM REELS] CDN URL: {video_url}")

    except ImportError:
        return {"success": False, "error": "cloudinary_helper not available"}
    except Exception as e:
        return {"success": False, "error": f"CDN error: {str(e)}"}

    # Instagram Reels olarak paylaş
    for attempt in range(max_retries):
        try:
            print(f"[INSTAGRAM REELS] Deneme {attempt + 1}/{max_retries}")

            result = await post_video_to_instagram(
                video_url=video_url,
                caption=caption
            )

            if result.get("success"):
                result["cdn_url"] = video_url
                print(f"[INSTAGRAM REELS] Başarıyla yayınlandı! ID: {result.get('id')}")
                return result

            error = result.get("error", "Unknown error")
            print(f"[INSTAGRAM REELS] Hata: {error}")

            if attempt < max_retries - 1:
                print(f"[INSTAGRAM REELS] 15 saniye sonra tekrar deneniyor...")
                await asyncio.sleep(15)

        except Exception as e:
            print(f"[INSTAGRAM REELS] Exception: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(10)

    return {"success": False, "error": "Max retries exceeded", "cdn_url": video_url}


async def get_media_insights(media_id: str) -> Dict[str, Any]:
    """
    Post insights al

    Args:
        media_id: Instagram post ID

    Returns:
        Insights dictionary
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{media_id}/insights"
    params = {
        "metric": "impressions,reach,engagement,saved",
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if "error" in data:
                    return {"success": False, "error": data["error"].get("message")}

                # Parse insights
                insights = {}
                for item in data.get("data", []):
                    insights[item["name"]] = item["values"][0]["value"]

                return {"success": True, "insights": insights}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_recent_media(limit: int = 10) -> Dict[str, Any]:
    """
    Son paylaşılan medyaları al

    Args:
        limit: Kaç post alınacak

    Returns:
        Media listesi
    """
    creds = get_instagram_credentials()

    url = f"{GRAPH_API_URL}/{creds['user_id']}/media"
    params = {
        "fields": "id,caption,timestamp,media_type,like_count,comments_count",
        "limit": limit,
        "access_token": creds["access_token"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if "error" in data:
                    return {"success": False, "error": data["error"].get("message")}

                return {"success": True, "media": data.get("data", [])}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def test_instagram_connection():
    """Instagram bağlantısını test et"""
    print("\n=== Instagram API Bağlantı Testi ===\n")
    print(f"Endpoint: {GRAPH_API_URL}\n")

    creds = get_instagram_credentials()

    if not creds["access_token"]:
        print("[FAIL] INSTAGRAM_ACCESS_TOKEN tanımlı değil!")
        return False

    if not creds["user_id"]:
        print("[FAIL] INSTAGRAM_USER_ID tanımlı değil!")
        return False

    # Hesap bilgisi al
    result = await get_account_info()

    if result.get("success"):
        print(f"\n[OK] Instagram bağlantısı başarılı!")
        print(f"[OK] Username: @{result.get('username')}")
        print(f"[OK] User ID: {result.get('id')}")
        print(f"[OK] Followers: {result.get('followers_count', 0)}")
        print(f"[OK] Posts: {result.get('media_count', 0)}")
        return True
    else:
        print(f"\n[FAIL] Instagram bağlantısı başarısız!")
        print(f"[ERROR] {result.get('error')}")
        print("\n[INFO] Kontrol edilecekler:")
        print("  1. INSTAGRAM_ACCESS_TOKEN .env'de tanımlı mı?")
        print("  2. INSTAGRAM_USER_ID .env'de tanımlı mı?")
        print("  3. Access token geçerli mi?")
        return False


if __name__ == "__main__":
    asyncio.run(test_instagram_connection())
