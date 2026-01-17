"""
Story Boost Helper - Post sonrası otomatik Story promosyonu

Post/Reels yayınlandıktan sonra Story boost sequence'ı başlatır:
1. Hemen: "Yeni içerik!" story
2. 15 dakika sonra: "Kaçırdın mı?" reminder
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("story_boost")

# Story template'leri (Türkçe)
STORY_TEMPLATES = {
    "immediate": {
        "emoji": "🔥",
        "text": "Yeni içerik yayında!",
        "cta": "Kaydır ve keşfet 👆"
    },
    "reminder": {
        "emoji": "👀",
        "text": "Kaçırdın mı?",
        "cta": "Son paylaşımımıza göz at 👆"
    },
    "engagement": {
        "emoji": "💬",
        "text": "Yorumunu bekliyorum!",
        "cta": "Fikrini paylaş 👆"
    }
}


async def trigger_story_boost(
    post_id: int,
    instagram_post_id: str,
    post_type: str = "post",
    image_url: str = None,
    video_url: str = None,
    caption_preview: str = None
) -> Dict[str, Any]:
    """
    Post yayınlandıktan sonra Story boost sequence'ı başlat.

    Args:
        post_id: Database post ID
        instagram_post_id: Instagram media ID
        post_type: 'post', 'reels', or 'carousel'
        image_url: Public CDN URL for image
        video_url: Public CDN URL for video
        caption_preview: First 50 chars of caption

    Returns:
        {"success": bool, "scheduled": int}
    """
    if not settings.story_boost_enabled:
        logger.info("[STORY BOOST] Feature disabled, skipping")
        return {"success": True, "scheduled": 0, "reason": "disabled"}

    logger.info(f"[STORY BOOST] Starting for post {post_id} (IG: {instagram_post_id})")

    # Immediate story - hemen
    asyncio.create_task(_execute_story_boost(
        post_id=post_id,
        instagram_post_id=instagram_post_id,
        post_type=post_type,
        sequence_type="immediate",
        image_url=image_url,
        video_url=video_url,
        caption_preview=caption_preview,
        delay=0
    ))

    # Reminder story - 15 dakika sonra
    asyncio.create_task(_execute_story_boost(
        post_id=post_id,
        instagram_post_id=instagram_post_id,
        post_type=post_type,
        sequence_type="reminder",
        image_url=image_url,
        video_url=video_url,
        caption_preview=caption_preview,
        delay=settings.story_boost_reminder_delay * 60
    ))

    return {"success": True, "scheduled": 2}


async def _execute_story_boost(
    post_id: int,
    instagram_post_id: str,
    post_type: str,
    sequence_type: str,
    image_url: str,
    video_url: str,
    caption_preview: str,
    delay: int
):
    """Background task: Story boost execute"""
    from app.database.crud import log_story_boost, update_story_boost

    try:
        # DB kayıt oluştur
        boost_id = log_story_boost(
            post_id=post_id,
            instagram_post_id=instagram_post_id,
            post_type=post_type,
            sequence_type=sequence_type
        )

        # Bekle
        if delay > 0:
            logger.info(f"[STORY BOOST] Waiting {delay}s for {sequence_type}")
            await asyncio.sleep(delay)

        # Instagram API dene
        api_result = await _try_instagram_story_api(
            instagram_post_id=instagram_post_id,
            sequence_type=sequence_type,
            image_url=image_url,
            video_url=video_url
        )

        if api_result.get("success"):
            update_story_boost(
                boost_id=boost_id,
                status="published",
                method="api",
                story_id=api_result.get("story_id")
            )
            logger.info(f"[STORY BOOST] {sequence_type} published via API!")
        else:
            # Fallback: Telegram bildirimi
            logger.warning(f"[STORY BOOST] API failed: {api_result.get('error')}")

            if settings.story_boost_telegram_fallback:
                await _send_telegram_fallback(
                    boost_id=boost_id,
                    post_id=post_id,
                    post_type=post_type,
                    sequence_type=sequence_type,
                    caption_preview=caption_preview,
                    api_error=api_result.get("error", "Unknown error")
                )
                update_story_boost(
                    boost_id=boost_id,
                    status="manual_sent",
                    method="telegram",
                    error=api_result.get("error")
                )
            else:
                update_story_boost(
                    boost_id=boost_id,
                    status="failed",
                    error=api_result.get("error")
                )

    except asyncio.CancelledError:
        logger.info(f"[STORY BOOST] Task cancelled for post {post_id}")
    except Exception as e:
        logger.error(f"[STORY BOOST] Error: {e}")


async def _try_instagram_story_api(
    instagram_post_id: str,
    sequence_type: str,
    image_url: str,
    video_url: str
) -> Dict[str, Any]:
    """
    Instagram Story API ile publish dene.

    NOT: Instagram Graph API Story desteği sınırlı.
    Çoğu Business hesapta çalışmayabilir.
    """
    import aiohttp

    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    user_id = os.getenv("INSTAGRAM_USER_ID", "")

    if not access_token or not user_id:
        return {"success": False, "error": "Instagram credentials missing"}

    # Media URL gerekli
    media_url = video_url or image_url
    if not media_url:
        return {"success": False, "error": "No media URL for Story"}

    # Instagram Stories endpoint
    url = f"https://graph.instagram.com/v21.0/{user_id}/stories"

    data = {"access_token": access_token}

    if video_url:
        data["video_url"] = video_url
        data["media_type"] = "VIDEO"
    else:
        data["image_url"] = image_url

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=data) as resp:
                result = await resp.json()

                if "error" in result:
                    error = result["error"]
                    error_msg = f"[{error.get('code', 'N/A')}] {error.get('message', 'Unknown')}"
                    return {"success": False, "error": error_msg}

                if result.get("id"):
                    return {"success": True, "story_id": result["id"]}

                return {"success": False, "error": "No story_id in response"}

    except aiohttp.ClientError as e:
        return {"success": False, "error": f"HTTP error: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Exception: {str(e)}"}


async def _send_telegram_fallback(
    boost_id: int,
    post_id: int,
    post_type: str,
    sequence_type: str,
    caption_preview: str,
    api_error: str
):
    """Telegram ile manuel Story bildirimi gönder"""
    from app.telegram_pipeline import telegram_notify

    template = STORY_TEMPLATES.get(sequence_type, STORY_TEMPLATES["immediate"])
    type_emoji = {"post": "📝", "reels": "🎬", "carousel": "🎠"}.get(post_type, "📌")

    message = (
        f"📢 *STORY BOOST - Manuel Gerekli*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Tip:* {type_emoji} {post_type.capitalize()}\n"
        f"*Sekans:* {sequence_type.capitalize()}\n"
        f"*Post ID:* {post_id}\n"
    )

    if caption_preview:
        # Escape markdown
        safe_preview = caption_preview[:40].replace("*", "").replace("_", "").replace("`", "")
        message += f"*Caption:* {safe_preview}...\n"

    message += (
        f"\n*Önerilen Story Metni:*\n"
        f"```\n{template['emoji']} {template['text']}\n{template['cta']}\n```\n\n"
        f"⚠️ *API:* {api_error[:80]}\n\n"
        f"_Post'a link sticker ile Story oluşturun._"
    )

    buttons = [
        {"text": "✅ Yapıldı", "callback": f"story_done:{boost_id}"},
        {"text": "⏭️ Atla", "callback": f"story_skip:{boost_id}"}
    ]

    try:
        await telegram_notify(message=message, buttons=buttons)
        logger.info(f"[STORY BOOST] Telegram fallback sent for boost {boost_id}")
    except Exception as e:
        logger.error(f"[STORY BOOST] Telegram notification failed: {e}")


def get_story_boost_status(post_id: int) -> Dict[str, Any]:
    """Post için story boost durumunu getir"""
    from app.database.crud import get_story_boosts_for_post

    boosts = get_story_boosts_for_post(post_id)

    return {
        "post_id": post_id,
        "total": len(boosts),
        "published": sum(1 for b in boosts if b.get("status") == "published"),
        "manual_sent": sum(1 for b in boosts if b.get("status") == "manual_sent"),
        "pending": sum(1 for b in boosts if b.get("status") == "scheduled"),
        "failed": sum(1 for b in boosts if b.get("status") == "failed"),
        "boosts": boosts
    }
