"""
Instagram Helper - Instagram Graph API Entegrasyonu
Facebook Business Suite üzerinden Instagram'a içerik paylaşımı
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

# Instagram Graph API URL
GRAPH_API_URL = "https://graph.facebook.com/v18.0"

# Video conversion output directory
OUTPUT_DIR = str(settings.outputs_dir)


async def convert_video_for_instagram(input_path: str) -> Dict[str, Any]:
    """
    Video'yu Instagram Reels formatina donustur

    Instagram Gereksinimleri:
    - Codec: H.264 (video), AAC (audio)
    - Cozunurluk: 720x1280 (9:16)
    - FPS: 30
    - Max sure: 90 saniye
    - Format: MP4

    Args:
        input_path: Giris video dosyasi

    Returns:
        {"success": True, "output_path": "...", "converted": True/False}
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Video bulunamadi: {input_path}"}

    print(f"[VIDEO CONVERT] Kaynak: {input_path}")

    # ffmpeg kontrolu
    try:
        result = subprocess.run(["which", "ffmpeg"], capture_output=True)
        if result.returncode != 0:
            print("[VIDEO CONVERT] ffmpeg yuklu degil!")
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

        # Parse: codec,width,height,fps
        parts = probe_output.split(",")
        if len(parts) >= 4:
            codec = parts[0]
            width = int(parts[1])
            height = int(parts[2])
            fps_str = parts[3]

            # fps parse (30/1 -> 30)
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = int(num) / int(den) if int(den) > 0 else 30
            else:
                fps = float(fps_str)

            print(f"[VIDEO CONVERT] Codec: {codec}, Size: {width}x{height}, FPS: {fps:.1f}")

            # Instagram uyumlu mu kontrol et
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
        print(f"[VIDEO CONVERT] Probe hatasi: {e}")
        # Hata olsa bile donusturmeye devam et

    # Donusturulmus dosya yolu
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{OUTPUT_DIR}/ig_ready_{timestamp}.mp4"

    print(f"[VIDEO CONVERT] Donusturuluyor: {output_path}")

    # ffmpeg komutu
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",          # H.264 codec
        "-preset", "medium",         # Encoding hizi/kalite dengesi
        "-crf", "23",                # Kalite (18-28 arasi, dusuk = daha iyi)
        "-c:a", "aac",               # AAC audio codec
        "-b:a", "128k",              # Audio bitrate
        "-ar", "44100",              # Audio sample rate
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "30",                  # 30 FPS
        "-movflags", "+faststart",   # Web streaming icin optimize
        "-t", "90",                  # Max 90 saniye
        output_path
    ]

    try:
        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 dakika timeout
        )

        if process.returncode != 0:
            print(f"[VIDEO CONVERT] ffmpeg hatasi: {process.stderr[:500]}")
            return {"success": False, "error": f"ffmpeg error: {process.stderr[:200]}"}

        if not os.path.exists(output_path):
            return {"success": False, "error": "Output file not created"}

        file_size = os.path.getsize(output_path) / 1024 / 1024
        print(f"[VIDEO CONVERT] Basarili! Boyut: {file_size:.2f} MB")

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


async def get_instagram_account_id() -> Optional[str]:
    """
    Facebook Page'e bağlı Instagram Business Account ID'sini al

    Returns:
        Instagram Business Account ID veya None
    """
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    page_id = os.getenv("FACEBOOK_PAGE_ID")

    if not access_token or not page_id:
        print("[INSTAGRAM] FACEBOOK_ACCESS_TOKEN veya FACEBOOK_PAGE_ID eksik!")
        return None

    url = f"{GRAPH_API_URL}/{page_id}"
    params = {
        "fields": "instagram_business_account",
        "access_token": access_token
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if "error" in data:
                    print(f"[INSTAGRAM] API Error: {data['error'].get('message', 'Unknown error')}")
                    return None

                ig_account = data.get("instagram_business_account", {})
                ig_id = ig_account.get("id")

                if ig_id:
                    print(f"[INSTAGRAM] Instagram Account ID: {ig_id}")
                    return ig_id
                else:
                    print("[INSTAGRAM] Instagram Business Account bulunamadi!")
                    print("[INSTAGRAM] Facebook Page'in bir Instagram Business Account'a bagli olmasi gerekiyor.")
                    return None

    except Exception as e:
        print(f"[INSTAGRAM] Connection error: {e}")
        return None


async def create_media_container(
    ig_account_id: str,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    caption: str = "",
    media_type: str = "IMAGE",
    is_carousel_item: bool = False
) -> Optional[str]:
    """
    Instagram Media Container oluştur (2-aşamalı yükleme için)

    Args:
        ig_account_id: Instagram Business Account ID
        image_url: Görsel URL'i (public erişilebilir olmalı)
        video_url: Video URL'i (public erişilebilir olmalı)
        caption: Post caption'ı
        media_type: IMAGE, VIDEO, veya REELS
        is_carousel_item: Carousel item mi?

    Returns:
        Container ID veya None
    """
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")

    if not access_token:
        return None

    url = f"{GRAPH_API_URL}/{ig_account_id}/media"

    data = {
        "access_token": access_token
    }

    # Carousel item değilse caption ekle
    if not is_carousel_item:
        data["caption"] = caption

    # Media type'a göre URL ekle
    if media_type == "IMAGE":
        data["image_url"] = image_url
    elif media_type == "VIDEO":
        data["video_url"] = video_url
        data["media_type"] = "VIDEO"
    elif media_type == "REELS":
        data["video_url"] = video_url
        data["media_type"] = "REELS"

    # Carousel item flag
    if is_carousel_item:
        data["is_carousel_item"] = True

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                result = await response.json()

                if "error" in result:
                    print(f"[INSTAGRAM] Container Error: {result['error'].get('message', 'Unknown error')}")
                    return None

                container_id = result.get("id")
                print(f"[INSTAGRAM] Media Container olusturuldu: {container_id}")
                return container_id

    except Exception as e:
        print(f"[INSTAGRAM] Container creation error: {e}")
        return None


async def check_container_status(container_id: str) -> Dict[str, Any]:
    """
    Media container durumunu kontrol et (video için gerekli)

    Args:
        container_id: Media container ID

    Returns:
        Status dictionary
    """
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")

    url = f"{GRAPH_API_URL}/{container_id}"
    params = {
        "fields": "status_code,status",
        "access_token": access_token
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                return await response.json()
    except Exception as e:
        return {"error": str(e)}


async def publish_media(ig_account_id: str, container_id: str) -> Dict[str, Any]:
    """
    Media container'ı yayınla

    Args:
        ig_account_id: Instagram Business Account ID
        container_id: Media container ID

    Returns:
        Publish result dictionary
    """
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")

    url = f"{GRAPH_API_URL}/{ig_account_id}/media_publish"
    data = {
        "creation_id": container_id,
        "access_token": access_token
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                result = await response.json()

                if "error" in result:
                    print(f"[INSTAGRAM] Publish Error: {result['error'].get('message', 'Unknown error')}")
                    return {"success": False, "error": result["error"].get("message")}

                post_id = result.get("id")
                print(f"[INSTAGRAM] Post yayinlandi! ID: {post_id}")
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
        image_url: Görsel URL'i (PUBLIC erişilebilir olmalı!)
        caption: Post caption'ı

    Returns:
        Result dictionary with success status and post id

    Note:
        Instagram Graph API lokal dosya kabul etmez!
        Görsel önce bir CDN veya public URL'e yüklenmeli.
    """
    print(f"[INSTAGRAM] Fotograf paylasiliyor...")
    print(f"[INSTAGRAM] Image URL: {image_url[:50]}...")

    # Instagram Account ID al
    ig_account_id = await get_instagram_account_id()
    if not ig_account_id:
        return {"success": False, "error": "Instagram Account ID alinamadi"}

    # Media container oluştur
    container_id = await create_media_container(
        ig_account_id=ig_account_id,
        image_url=image_url,
        caption=caption,
        media_type="IMAGE"
    )

    if not container_id:
        return {"success": False, "error": "Media container olusturulamadi"}

    # Biraz bekle (Instagram processing)
    await asyncio.sleep(2)

    # Yayınla
    return await publish_media(ig_account_id, container_id)


async def post_video_to_instagram(
    video_url: str,
    caption: str = "",
    as_reels: bool = True
) -> Dict[str, Any]:
    """
    Instagram'a video/Reels paylaş

    Args:
        video_url: Video URL'i (PUBLIC erişilebilir olmalı!)
        caption: Post caption'ı
        as_reels: Reels olarak mı paylaşılsın? (default: True)

    Returns:
        Result dictionary with success status and post id

    Note:
        - Video önce bir CDN veya public URL'e yüklenmeli
        - Reels için 9:16 aspect ratio önerilir
        - Video max 15 dakika (Reels için 90 saniye)
    """
    print(f"[INSTAGRAM] Video paylasiliyor (Reels: {as_reels})...")

    # Instagram Account ID al
    ig_account_id = await get_instagram_account_id()
    if not ig_account_id:
        return {"success": False, "error": "Instagram Account ID alinamadi"}

    # Media container oluştur
    media_type = "REELS" if as_reels else "VIDEO"
    container_id = await create_media_container(
        ig_account_id=ig_account_id,
        video_url=video_url,
        caption=caption,
        media_type=media_type
    )

    if not container_id:
        return {"success": False, "error": "Media container olusturulamadi"}

    # Video processing bekle (uzun sürebilir)
    print("[INSTAGRAM] Video isleniyor, bekleyin...")
    max_attempts = 30
    for attempt in range(max_attempts):
        await asyncio.sleep(10)  # 10 saniye bekle

        status = await check_container_status(container_id)
        status_code = status.get("status_code")

        if status_code == "FINISHED":
            print("[INSTAGRAM] Video isleme tamamlandi!")
            break
        elif status_code == "ERROR":
            error_msg = status.get("status", "Unknown error")
            return {"success": False, "error": f"Video processing error: {error_msg}"}
        elif status_code == "IN_PROGRESS":
            print(f"[INSTAGRAM] Video isleniyor... ({attempt + 1}/{max_attempts})")
        else:
            print(f"[INSTAGRAM] Status: {status_code}")
    else:
        return {"success": False, "error": "Video processing timeout"}

    # Yayınla
    return await publish_media(ig_account_id, container_id)


async def post_carousel_to_instagram(
    image_urls: List[str],
    caption: str = ""
) -> Dict[str, Any]:
    """
    Instagram'a carousel (çoklu görsel) paylaş

    Args:
        image_urls: Görsel URL listesi (2-10 arası, PUBLIC erişilebilir!)
        caption: Post caption'ı

    Returns:
        Result dictionary with success status and post id
    """
    if len(image_urls) < 2 or len(image_urls) > 10:
        return {"success": False, "error": "Carousel 2-10 arasi gorsel icermeli"}

    print(f"[INSTAGRAM] Carousel paylasiliyor ({len(image_urls)} gorsel)...")

    # Instagram Account ID al
    ig_account_id = await get_instagram_account_id()
    if not ig_account_id:
        return {"success": False, "error": "Instagram Account ID alinamadi"}

    # Her görsel için container oluştur
    children_ids = []
    for i, image_url in enumerate(image_urls):
        print(f"[INSTAGRAM] Carousel item {i+1}/{len(image_urls)} olusturuluyor...")
        container_id = await create_media_container(
            ig_account_id=ig_account_id,
            image_url=image_url,
            media_type="IMAGE",
            is_carousel_item=True
        )

        if container_id:
            children_ids.append(container_id)
        else:
            print(f"[INSTAGRAM] Item {i+1} olusturulamadi, devam ediliyor...")

    if len(children_ids) < 2:
        return {"success": False, "error": "En az 2 carousel item gerekli"}

    # Ana carousel container oluştur
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN")
    url = f"{GRAPH_API_URL}/{ig_account_id}/media"

    data = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
        "caption": caption,
        "access_token": access_token
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                result = await response.json()

                if "error" in result:
                    return {"success": False, "error": result["error"].get("message")}

                carousel_container_id = result.get("id")
                print(f"[INSTAGRAM] Carousel container: {carousel_container_id}")

                # Biraz bekle
                await asyncio.sleep(3)

                # Yayınla
                return await publish_media(ig_account_id, carousel_container_id)

    except Exception as e:
        return {"success": False, "error": str(e)}


async def upload_image_to_cdn(local_path: str) -> Optional[str]:
    """
    Lokal görseli CDN'e yükle ve public URL döndür

    Bu fonksiyon placeholder - gerçek implementasyon için
    bir CDN servisi (AWS S3, Cloudinary, etc.) gerekli

    Args:
        local_path: Lokal dosya yolu

    Returns:
        Public URL veya None
    """
    # TODO: Gerçek CDN implementasyonu
    # Seçenekler:
    # 1. AWS S3 + CloudFront
    # 2. Cloudinary
    # 3. Imgbb (ücretsiz)
    # 4. Firebase Storage

    print(f"[INSTAGRAM] CDN upload gerekli: {local_path}")
    print("[INSTAGRAM] CDN servisi henuz ayarlanmamis!")

    # Imgbb kullanarak upload (ücretsiz, API key gerekli)
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
                        print(f"[INSTAGRAM] Gorsel yuklendi: {url}")
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
        Result dictionary with success status, post id, and CDN URL

    Note:
        - Video önce Instagram formatına dönüştürülür (H.264, AAC, 720x1280)
        - Sonra Cloudinary'ye yüklenir
        - Reels için 9:16 aspect ratio
        - Süre: 3-90 saniye
    """
    if not os.path.exists(video_path):
        return {"success": False, "error": f"Video dosyası bulunamadı: {video_path}"}

    print(f"[INSTAGRAM REELS] Reels paylaşılıyor...")
    print(f"[INSTAGRAM REELS] Video: {video_path}")

    # 0. Video'yu Instagram formatına dönüştür
    upload_path = video_path
    if not skip_conversion:
        print("[INSTAGRAM REELS] Video Instagram formatına dönüştürülüyor...")
        convert_result = await convert_video_for_instagram(video_path)

        if not convert_result.get("success"):
            print(f"[INSTAGRAM REELS] Dönüşüm hatası: {convert_result.get('error')}")
            # Dönüşüm başarısız olsa bile orijinal video ile devam et
            print("[INSTAGRAM REELS] Orijinal video ile devam ediliyor...")
        else:
            upload_path = convert_result.get("output_path", video_path)
            if convert_result.get("converted"):
                print(f"[INSTAGRAM REELS] Dönüştürüldü: {upload_path}")
            else:
                print("[INSTAGRAM REELS] Video zaten uyumlu, dönüşüm gerekmedi")

    # 1. Video'yu Cloudinary'ye yükle
    try:
        from app.cloudinary_helper import upload_video_to_cloudinary

        cdn_result = await upload_video_to_cloudinary(upload_path)

        if not cdn_result.get("success"):
            print(f"[INSTAGRAM REELS] CDN yükleme hatası: {cdn_result.get('error')}")
            return {"success": False, "error": f"CDN upload failed: {cdn_result.get('error')}"}

        video_url = cdn_result.get("url")
        print(f"[INSTAGRAM REELS] CDN URL: {video_url}")

    except ImportError:
        print("[INSTAGRAM REELS] cloudinary_helper import edilemedi")
        return {"success": False, "error": "cloudinary_helper not available"}
    except Exception as e:
        print(f"[INSTAGRAM REELS] CDN hata: {e}")
        return {"success": False, "error": f"CDN error: {str(e)}"}

    # 2. Instagram Reels olarak paylaş
    for attempt in range(max_retries):
        try:
            print(f"[INSTAGRAM REELS] Deneme {attempt + 1}/{max_retries}")

            result = await post_video_to_instagram(
                video_url=video_url,
                caption=caption,
                as_reels=True
            )

            if result.get("success"):
                result["cdn_url"] = video_url
                result["platform"] = "instagram_reels"
                print(f"[INSTAGRAM REELS] Başarıyla yayınlandı! ID: {result.get('id')}")
                return result

            # Hata varsa ve retry kaldıysa tekrar dene
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


# Test fonksiyonu
async def test_instagram_connection():
    """Instagram bağlantısını test et"""
    print("\n=== Instagram Baglanti Testi ===\n")

    ig_id = await get_instagram_account_id()

    if ig_id:
        print(f"\n[OK] Instagram baglamtisi basarili!")
        print(f"[OK] Account ID: {ig_id}")
        return True
    else:
        print("\n[FAIL] Instagram baglantisi basarisiz!")
        print("[INFO] Kontrol edilecekler:")
        print("  1. FACEBOOK_ACCESS_TOKEN .env'de tanimli mi?")
        print("  2. FACEBOOK_PAGE_ID .env'de tanimli mi?")
        print("  3. Facebook Page bir Instagram Business Account'a bagli mi?")
        print("  4. Access token 'instagram_basic' ve 'instagram_content_publish' izinlerine sahip mi?")
        return False


if __name__ == "__main__":
    asyncio.run(test_instagram_connection())
