"""
Instagram Insights Helper
Instagram Graph API ile çalışır (graph.instagram.com v21.0)
"""

import os
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.utils.logger import get_logger

logger = get_logger("insights")

# Instagram Graph API (Yeni endpoint)
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
GRAPH_API_URL = "https://graph.instagram.com/v21.0"


async def get_instagram_account_info() -> Dict[str, Any]:
    """Instagram hesap bilgilerini al"""
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_USER_ID:
        return {"success": False, "error": "Instagram credentials not set"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{INSTAGRAM_USER_ID}",
                params={
                    "fields": "id,username,media_count,followers_count",
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "id": data.get("id"),
                    "username": data.get("username"),
                    "followers": data.get("followers_count", 0),
                    "posts": data.get("media_count", 0)
                }
            else:
                return {"success": False, "error": response.text[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_instagram_media_type(media_id: str) -> Dict[str, Any]:
    """
    Instagram media tipini tespit et.

    Returns:
        {
            "success": True,
            "media_id": "...",
            "media_type": "VIDEO",           # VIDEO, IMAGE, CAROUSEL_ALBUM
            "media_product_type": "REELS",   # REELS, FEED, STORY
            "is_reels": True
        }
    """
    if not INSTAGRAM_ACCESS_TOKEN:
        return {"success": False, "error": "Instagram token not set"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{media_id}",
                params={
                    "fields": "media_type,media_product_type",
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if response.status_code == 200:
                data = response.json()
                media_type = data.get("media_type", "")
                product_type = data.get("media_product_type", "")

                return {
                    "success": True,
                    "media_id": media_id,
                    "media_type": media_type,
                    "media_product_type": product_type,
                    "is_reels": product_type == "REELS" or (media_type == "VIDEO" and product_type != "STORY")
                }
            else:
                return {"success": False, "error": response.text[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_instagram_reels_insights(media_id: str) -> Dict[str, Any]:
    """
    Instagram Reels/Video için detaylı metrikler çek.
    """
    if not INSTAGRAM_ACCESS_TOKEN:
        return {"success": False, "error": "Instagram token not set"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            result = {
                "success": True,
                "media_id": media_id,
                "media_type": "REELS",
                "plays": 0,
                "reach": 0,
                "saves": 0,
                "shares": 0,
                "comments": 0,
                "likes": 0,
                "total_interactions": 0,
                "avg_watch_time": 0.0,  # Reels ortalama izleme süresi (ms)
                "engagement_rate": 0.0
            }

            # Reels metrikleri (2025 güncel - impressions deprecated)
            reels_metrics = [
                "plays", "reach", "saved", "shares", "comments", "likes",
                "total_interactions", "ig_reels_avg_watch_time"
            ]

            insights_response = await client.get(
                f"{GRAPH_API_URL}/{media_id}/insights",
                params={
                    "metric": ",".join(reels_metrics),
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if insights_response.status_code == 200:
                data = insights_response.json().get("data", [])
                for metric in data:
                    name = metric.get("name")
                    values = metric.get("values", [])
                    value = values[0].get("value", 0) if values else 0

                    if name == "plays":
                        result["plays"] = value
                    elif name == "reach":
                        result["reach"] = value
                    elif name == "saved":
                        result["saves"] = value
                    elif name == "shares":
                        result["shares"] = value
                    elif name == "comments":
                        result["comments"] = value
                    elif name == "likes":
                        result["likes"] = value
                    elif name == "total_interactions":
                        result["total_interactions"] = value
                    elif name == "ig_reels_avg_watch_time":
                        result["avg_watch_time"] = value  # milliseconds
            else:
                # Fallback: temel metrikler
                fallback_response = await client.get(
                    f"{GRAPH_API_URL}/{media_id}/insights",
                    params={
                        "metric": "reach,saved,shares,comments,likes",
                        "access_token": INSTAGRAM_ACCESS_TOKEN
                    }
                )

                if fallback_response.status_code == 200:
                    data = fallback_response.json().get("data", [])
                    for metric in data:
                        name = metric.get("name")
                        values = metric.get("values", [])
                        value = values[0].get("value", 0) if values else 0

                        if name == "reach":
                            result["reach"] = value
                        elif name == "saved":
                            result["saves"] = value
                        elif name == "shares":
                            result["shares"] = value
                        elif name == "comments":
                            result["comments"] = value
                        elif name == "likes":
                            result["likes"] = value

            # Temel bilgiler
            try:
                basic_response = await client.get(
                    f"{GRAPH_API_URL}/{media_id}",
                    params={
                        "fields": "like_count,comments_count,media_type,media_product_type,caption,timestamp",
                        "access_token": INSTAGRAM_ACCESS_TOKEN
                    }
                )

                if basic_response.status_code == 200:
                    basic_data = basic_response.json()
                    if result["likes"] == 0:
                        result["likes"] = basic_data.get("like_count", 0)
                    if result["comments"] == 0:
                        result["comments"] = basic_data.get("comments_count", 0)
                    result["media_type"] = basic_data.get("media_product_type", "REELS")
                    result["caption"] = (basic_data.get("caption") or "")[:100]
                    result["timestamp"] = basic_data.get("timestamp")
            except Exception as e:
                print(f"[IG_REELS] Basic info warning for {media_id}: {e}")

            # Engagement rate - reach yeterli değilse 0 döndür (anlamsız %700+ değerler önlenir)
            reach = result["reach"]
            total_engagement = result["likes"] + result["comments"] + result["saves"] + result["shares"]
            if reach >= 10:  # Minimum 10 reach gerekli anlamlı engagement için
                result["engagement_rate"] = round((total_engagement / reach) * 100, 2)
            else:
                result["engagement_rate"] = 0.0  # Yetersiz veri

            if result["total_interactions"] == 0:
                result["total_interactions"] = total_engagement

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "media_id": media_id}


async def get_instagram_image_insights(media_id: str) -> Dict[str, Any]:
    """
    Instagram Image/Carousel için basit metrikler çek.
    """
    if not INSTAGRAM_ACCESS_TOKEN:
        return {"success": False, "error": "Instagram token not set"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            result = {
                "success": True,
                "media_id": media_id,
                "media_type": "IMAGE",
                "impressions": 0,
                "reach": 0,
                "saves": 0,
                "likes": 0,
                "comments": 0,
                "engagement_rate": 0.0
            }

            # Insights çek
            insights_response = await client.get(
                f"{GRAPH_API_URL}/{media_id}/insights",
                params={
                    "metric": "impressions,reach,saved",
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if insights_response.status_code == 200:
                data = insights_response.json().get("data", [])
                for metric in data:
                    name = metric.get("name")
                    values = metric.get("values", [])
                    value = values[0].get("value", 0) if values else 0

                    if name == "impressions":
                        result["impressions"] = value
                    elif name == "reach":
                        result["reach"] = value
                    elif name == "saved":
                        result["saves"] = value

            # Temel bilgiler
            basic_response = await client.get(
                f"{GRAPH_API_URL}/{media_id}",
                params={
                    "fields": "like_count,comments_count,media_type,caption,timestamp",
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if basic_response.status_code == 200:
                basic_data = basic_response.json()
                result["likes"] = basic_data.get("like_count", 0)
                result["comments"] = basic_data.get("comments_count", 0)
                result["media_type"] = basic_data.get("media_type", "IMAGE")
                result["caption"] = (basic_data.get("caption") or "")[:100]
                result["timestamp"] = basic_data.get("timestamp")

            # Engagement rate - yetersiz reach/impressions varsa 0 döndür
            denominator = result["reach"] if result["reach"] > 0 else result["impressions"]
            total_engagement = result["likes"] + result["comments"] + result["saves"]
            if denominator >= 10:  # Minimum 10 reach/impression gerekli
                result["engagement_rate"] = round((total_engagement / denominator) * 100, 2)
            else:
                result["engagement_rate"] = 0.0  # Yetersiz veri

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "media_id": media_id}


async def get_instagram_media_insights(media_id: str) -> Dict[str, Any]:
    """
    Instagram media için otomatik tip tespiti ve uygun metrikler çek.

    - REELS/VIDEO → get_instagram_reels_insights()
    - IMAGE/CAROUSEL → get_instagram_image_insights()
    """
    type_info = await get_instagram_media_type(media_id)

    if not type_info.get("success"):
        return {"success": False, "error": type_info.get("error", "Media type detection failed")}

    is_reels = type_info.get("is_reels", False)

    if is_reels:
        return await get_instagram_reels_insights(media_id)
    else:
        return await get_instagram_image_insights(media_id)


async def get_instagram_insights(limit: int = 10) -> Dict[str, Any]:
    """Instagram post istatistiklerini al"""
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_USER_ID:
        return {"success": False, "error": "Instagram credentials not set"}

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{INSTAGRAM_USER_ID}/media",
                params={
                    "fields": "id,caption,timestamp,like_count,comments_count,media_type",
                    "limit": limit,
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if response.status_code != 200:
                return {"success": False, "error": response.text[:200]}

            media = response.json().get("data", [])

            results = []
            for item in media:
                media_id = item.get("id")

                # Insights çek
                insights = await get_instagram_media_insights(media_id)

                results.append({
                    "post_id": media_id,
                    "caption": (item.get("caption") or "")[:50],
                    "timestamp": item.get("timestamp"),
                    "media_type": item.get("media_type"),
                    "likes": insights.get("likes", item.get("like_count", 0)),
                    "comments": insights.get("comments", item.get("comments_count", 0)),
                    "reach": insights.get("reach", 0),
                    "impressions": insights.get("impressions", 0),
                    "engagement_rate": insights.get("engagement_rate", 0)
                })

                await asyncio.sleep(0.3)

            return {"success": True, "posts": results}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_best_performing_content() -> Dict[str, Any]:
    """En iyi performans gösteren içerikleri analiz et"""
    ig_posts = await get_instagram_insights(limit=20)

    analysis = {
        "instagram": {
            "total_posts": 0, "avg_reach": 0, "avg_engagement_rate": 0,
            "total_likes": 0, "total_comments": 0,
            "best_post": None, "worst_post": None
        },
        "insights": [], "recommendations": []
    }

    if ig_posts.get("success") and ig_posts.get("posts"):
        posts = ig_posts["posts"]
        analysis["instagram"]["total_posts"] = len(posts)
        analysis["instagram"]["avg_reach"] = sum(p.get("reach", 0) for p in posts) / len(posts) if posts else 0
        analysis["instagram"]["avg_engagement_rate"] = sum(p.get("engagement_rate", 0) for p in posts) / len(posts) if posts else 0
        analysis["instagram"]["total_likes"] = sum(p.get("likes", 0) for p in posts)
        analysis["instagram"]["total_comments"] = sum(p.get("comments", 0) for p in posts)

        sorted_posts = sorted(posts, key=lambda x: x.get("likes", 0), reverse=True)
        if sorted_posts:
            analysis["instagram"]["best_post"] = sorted_posts[0]
            analysis["instagram"]["worst_post"] = sorted_posts[-1]

    return analysis


async def sync_insights_to_database() -> Dict[str, Any]:
    """
    Instagram insights'ları database'e kaydet.
    Sadece Instagram post'ları için çalışır.
    """
    from app.database import update_post_analytics, get_published_posts

    db_posts = get_published_posts(days=30)
    synced = 0
    errors = 0

    for post in db_posts:
        ig_post_id = post.get("instagram_post_id")
        analytics_data = {}

        if ig_post_id:
            try:
                ig_insights = await get_instagram_media_insights(ig_post_id)
                if ig_insights.get("success"):
                    # Temel metrikler
                    analytics_data["ig_reach"] = ig_insights.get("reach", 0)
                    analytics_data["ig_likes"] = ig_insights.get("likes", 0)
                    analytics_data["ig_comments"] = ig_insights.get("comments", 0)
                    analytics_data["ig_saves"] = ig_insights.get("saves", 0)
                    analytics_data["ig_shares"] = ig_insights.get("shares", 0)
                    analytics_data["ig_engagement_rate"] = ig_insights.get("engagement_rate", 0)

                    # Reels/Video metrikleri
                    if ig_insights.get("plays", 0) > 0:
                        analytics_data["ig_plays"] = ig_insights.get("plays", 0)
                    if ig_insights.get("avg_watch_time", 0) > 0:
                        analytics_data["ig_avg_watch_time"] = ig_insights.get("avg_watch_time", 0)

                    # Update database
                    update_post_analytics(post.get("id"), analytics_data)
                    synced += 1
            except Exception as e:
                print(f"[INSIGHTS] Error syncing {ig_post_id}: {e}")
                errors += 1

        await asyncio.sleep(0.3)

    return {"success": True, "synced": synced, "errors": errors, "total": len(db_posts)}


async def test_instagram_connection():
    """Instagram bağlantısını test et"""
    print("\n=== Instagram Insights API Test ===\n")
    print(f"Endpoint: {GRAPH_API_URL}")
    print(f"User ID: {INSTAGRAM_USER_ID or 'NOT SET'}")
    print(f"Token: {'SET' if INSTAGRAM_ACCESS_TOKEN else 'NOT SET'}\n")

    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_USER_ID:
        print("[FAIL] Credentials not set!")
        return False

    result = await get_instagram_account_info()

    if result.get("success"):
        print(f"[OK] Instagram bağlantısı başarılı!")
        print(f"[OK] Username: @{result.get('username')}")
        print(f"[OK] Followers: {result.get('followers', 0)}")
        print(f"[OK] Posts: {result.get('posts', 0)}")
        return True
    else:
        print(f"[FAIL] {result.get('error')}")
        return False


if __name__ == "__main__":
    asyncio.run(test_instagram_connection())
