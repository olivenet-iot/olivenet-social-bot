"""
Instagram Helper - Instagram Graph API Entegrasyonu
Facebook Business Suite üzerinden Instagram'a içerik paylaşımı
"""

import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List


# Instagram Graph API URL
GRAPH_API_URL = "https://graph.facebook.com/v18.0"


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
