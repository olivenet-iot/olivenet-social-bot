"""
Facebook & Instagram Insights Helper
Page Access Token ile çalışır
"""

import os
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv('/opt/olivenet-social-bot/.env')

FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
GRAPH_API_URL = "https://graph.facebook.com/v21.0"


async def get_page_fans_count() -> Dict[str, Any]:
    """Sayfa takipçi sayısını al"""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{FACEBOOK_PAGE_ID}",
                params={
                    "fields": "followers_count,fan_count,name",
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "name": data.get("name"),
                    "followers": data.get("followers_count", 0),
                    "fans": data.get("fan_count", 0)
                }
            else:
                return {"success": False, "error": response.text[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_video_insights(video_id: str) -> Dict[str, Any]:
    """
    Video node için insights çek.

    Facebook Video node'ları farklı endpoint ve metrikler kullanır:
    - /video_insights endpoint'i
    - total_video_impressions, total_video_views, etc.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            insights = {}
            post_data = {
                "message": "",
                "created_time": None,
                "shares": 0,
                "comments": 0,
                "reactions": 0,
            }

            # ========== Video Insights Metrikleri ==========
            insights_response = await client.get(
                f"{GRAPH_API_URL}/{video_id}/video_insights",
                params={
                    "metric": "total_video_impressions,total_video_views,total_video_avg_time_watched,total_video_view_time",
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )

            if insights_response.status_code == 200:
                data = insights_response.json().get("data", [])
                for metric in data:
                    name = metric.get("name")
                    values = metric.get("values", [])
                    if values:
                        insights[name] = values[0].get("value", 0)

                # Standart post formatına dönüştür
                insights["post_impressions"] = insights.get("total_video_impressions", 0)
                insights["post_impressions_unique"] = insights.get("total_video_views", 0)
                insights["post_engaged_users"] = insights.get("total_video_views", 0)
            else:
                error_text = insights_response.text[:200]
                print(f"[VIDEO_INSIGHTS] Video insights error for {video_id}: {error_text}")

            # ========== Video Temel Bilgileri ==========
            try:
                video_response = await client.get(
                    f"{GRAPH_API_URL}/{video_id}",
                    params={
                        "fields": "created_time,description,title,likes.summary(true),comments.summary(true)",
                        "access_token": FACEBOOK_ACCESS_TOKEN
                    }
                )

                if video_response.status_code == 200:
                    video_data = video_response.json()
                    post_data["created_time"] = video_data.get("created_time")
                    post_data["message"] = (video_data.get("description") or video_data.get("title") or "")[:100]
                    post_data["reactions"] = video_data.get("likes", {}).get("summary", {}).get("total_count", 0)
                    post_data["comments"] = video_data.get("comments", {}).get("summary", {}).get("total_count", 0)
            except Exception as e:
                print(f"[VIDEO_INSIGHTS] Video data fetch warning for {video_id}: {e}")

            # Engagement rate hesapla
            reach = insights.get("post_impressions_unique", 1)
            engagements = post_data["reactions"] + post_data["comments"] + post_data["shares"]
            engagement_rate = (engagements / reach * 100) if reach > 0 else 0

            return {
                "success": True,
                "post_id": video_id,
                "post_data": post_data,
                "insights": insights,
                "engagement_rate": round(engagement_rate, 2),
                "node_type": "video"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "node_type": "video"}


async def get_page_insights(period: str = "day") -> Dict[str, Any]:
    """Sayfa genel istatistiklerini al"""
    metrics = [
        "page_impressions",
        "page_engaged_users",
        "page_post_engagements",
    ]
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{FACEBOOK_PAGE_ID}/insights",
                params={
                    "metric": ",".join(metrics),
                    "period": period,
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )
            
            if response.status_code == 200:
                data = response.json().get("data", [])
                result = {}
                for metric in data:
                    name = metric.get("name")
                    values = metric.get("values", [])
                    if values:
                        result[name] = values[-1].get("value", 0)
                return {"success": True, "insights": result}
            else:
                return {"success": False, "error": response.text[:300]}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_post_insights(post_id: str) -> Dict[str, Any]:
    """
    Tek bir post'un istatistiklerini al.

    Video ve normal post node'ları farklı API endpoint'leri kullanır:
    - Normal post: /{post_id}?fields=insights.metric(...)
    - Video: /{video_id}/video_insights

    Bu fonksiyon önce node tipini tespit eder, sonra doğru endpoint'i kullanır.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # ========== AŞAMA 0: Node Tip Tespiti ==========
            # Önce basit bir sorgu ile node tipini anlamaya çalış
            type_check_response = await client.get(
                f"{GRAPH_API_URL}/{post_id}",
                params={
                    "fields": "id",
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )

            # Hata mesajından Video node mu anlayalım
            if type_check_response.status_code != 200:
                error_text = type_check_response.text
                if "node type (Video)" in error_text or "Unsupported get request" in error_text:
                    # Video node - özel fonksiyona yönlendir
                    print(f"[INSIGHTS] Video node detected: {post_id}")
                    return await get_video_insights(post_id)
                else:
                    return {"success": False, "error": error_text[:200]}

            # ========== AŞAMA 1: Normal Post - Insights Metrics ==========
            insights = {}
            post_data = {
                "message": "",
                "created_time": None,
                "shares": 0,
                "comments": 0,
                "reactions": 0,
            }

            insights_response = await client.get(
                f"{GRAPH_API_URL}/{post_id}",
                params={
                    "fields": "created_time,insights.metric(post_impressions,post_impressions_unique,post_engaged_users,post_clicks)",
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )

            if insights_response.status_code == 200:
                data = insights_response.json()
                post_data["created_time"] = data.get("created_time")

                insights_data = data.get("insights", {}).get("data", [])
                for metric in insights_data:
                    name = metric.get("name")
                    values = metric.get("values", [])
                    if values:
                        insights[name] = values[0].get("value", 0)
            else:
                error_text = insights_response.text
                # Video olabilir - tekrar kontrol et
                if "node type (Video)" in error_text:
                    print(f"[INSIGHTS] Video node detected (late): {post_id}")
                    return await get_video_insights(post_id)
                return {"success": False, "error": f"Insights fetch failed: {error_text[:200]}"}

            # ========== AŞAMA 2: Engagement Counts ==========
            try:
                engagement_response = await client.get(
                    f"{GRAPH_API_URL}/{post_id}",
                    params={
                        "fields": "shares,comments.summary(true),reactions.summary(true)",
                        "access_token": FACEBOOK_ACCESS_TOKEN
                    }
                )

                if engagement_response.status_code == 200:
                    eng_data = engagement_response.json()
                    post_data["shares"] = eng_data.get("shares", {}).get("count", 0)
                    post_data["comments"] = eng_data.get("comments", {}).get("summary", {}).get("total_count", 0)
                    post_data["reactions"] = eng_data.get("reactions", {}).get("summary", {}).get("total_count", 0)
            except Exception as e:
                print(f"[INSIGHTS] Engagement fetch warning for {post_id}: {e}")

            # ========== AŞAMA 3: Message (opsiyonel) ==========
            try:
                msg_response = await client.get(
                    f"{GRAPH_API_URL}/{post_id}",
                    params={
                        "fields": "message",
                        "access_token": FACEBOOK_ACCESS_TOKEN
                    }
                )
                if msg_response.status_code == 200:
                    msg_data = msg_response.json()
                    post_data["message"] = (msg_data.get("message") or "")[:100]
            except:
                pass

            # Engagement rate hesapla
            reach = insights.get("post_impressions_unique", 1)
            engagements = post_data["reactions"] + post_data["comments"] + post_data["shares"]
            engagement_rate = (engagements / reach * 100) if reach > 0 else 0

            return {
                "success": True,
                "post_id": post_id,
                "post_data": post_data,
                "insights": insights,
                "engagement_rate": round(engagement_rate, 2),
                "node_type": "post"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_all_posts_insights(limit: int = 10) -> Dict[str, Any]:
    """Son N post'un istatistiklerini al"""
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{FACEBOOK_PAGE_ID}/posts",
                params={
                    "fields": "id,message,created_time,shares,comments.summary(true),reactions.summary(true)",
                    "limit": limit,
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )
            
            if response.status_code != 200:
                return {"success": False, "error": response.text[:200]}
            
            posts_data = response.json().get("data", [])
            
            results = []
            for post in posts_data:
                post_id = post.get("id")
                insights_result = await get_post_insights(post_id)
                
                reactions = post.get("reactions", {}).get("summary", {}).get("total_count", 0)
                comments = post.get("comments", {}).get("summary", {}).get("total_count", 0)
                shares = post.get("shares", {}).get("count", 0)
                
                if insights_result.get("success"):
                    results.append({
                        "post_id": post_id,
                        "message": (post.get("message") or "")[:50],
                        "created_time": post.get("created_time"),
                        "reactions": reactions,
                        "comments": comments,
                        "shares": shares,
                        "reach": insights_result.get("insights", {}).get("post_impressions_unique", 0),
                        "impressions": insights_result.get("insights", {}).get("post_impressions", 0),
                        "engagement_rate": insights_result.get("engagement_rate", 0)
                    })
                else:
                    results.append({
                        "post_id": post_id,
                        "message": (post.get("message") or "")[:50],
                        "created_time": post.get("created_time"),
                        "reactions": reactions,
                        "comments": comments,
                        "shares": shares,
                        "reach": 0,
                        "impressions": 0,
                        "engagement_rate": 0
                    })
                
                await asyncio.sleep(0.3)
            
            return {"success": True, "posts": results}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_instagram_account_info() -> Dict[str, Any]:
    """Instagram hesap bilgilerini al"""
    if not INSTAGRAM_ACCOUNT_ID:
        return {"success": False, "error": "INSTAGRAM_ACCOUNT_ID not set"}
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{INSTAGRAM_ACCOUNT_ID}",
                params={
                    "fields": "username,name,followers_count,follows_count,media_count",
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "username": data.get("username"),
                    "name": data.get("name"),
                    "followers": data.get("followers_count", 0),
                    "following": data.get("follows_count", 0),
                    "posts": data.get("media_count", 0)
                }
            else:
                return {"success": False, "error": response.text[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_instagram_insights(limit: int = 10) -> Dict[str, Any]:
    """Instagram post istatistiklerini al"""
    if not INSTAGRAM_ACCOUNT_ID:
        return {"success": False, "error": "INSTAGRAM_ACCOUNT_ID not set"}
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{INSTAGRAM_ACCOUNT_ID}/media",
                params={
                    "fields": "id,caption,timestamp,like_count,comments_count,media_type",
                    "limit": limit,
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )
            
            if response.status_code != 200:
                return {"success": False, "error": response.text[:200]}
            
            media = response.json().get("data", [])
            
            results = []
            for item in media:
                media_id = item.get("id")
                
                insights = {}
                try:
                    insights_response = await client.get(
                        f"{GRAPH_API_URL}/{media_id}/insights",
                        params={
                            "metric": "impressions,reach",
                            "access_token": FACEBOOK_ACCESS_TOKEN
                        }
                    )
                    
                    if insights_response.status_code == 200:
                        for metric in insights_response.json().get("data", []):
                            insights[metric.get("name")] = metric.get("values", [{}])[0].get("value", 0)
                except:
                    pass
                
                reach = insights.get("reach", 1)
                likes = item.get("like_count", 0)
                comments = item.get("comments_count", 0)
                engagement = likes + comments
                engagement_rate = (engagement / reach * 100) if reach > 0 else 0
                
                results.append({
                    "post_id": media_id,
                    "caption": (item.get("caption") or "")[:50],
                    "timestamp": item.get("timestamp"),
                    "media_type": item.get("media_type"),
                    "likes": likes,
                    "comments": comments,
                    "reach": reach,
                    "impressions": insights.get("impressions", 0),
                    "engagement_rate": round(engagement_rate, 2)
                })
                
                await asyncio.sleep(0.3)
            
            return {"success": True, "posts": results}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def get_best_performing_content() -> Dict[str, Any]:
    """En iyi performans gösteren içerikleri analiz et"""
    fb_posts = await get_all_posts_insights(limit=20)
    ig_posts = await get_instagram_insights(limit=20)
    
    analysis = {
        "facebook": {
            "total_posts": 0, "avg_reach": 0, "avg_engagement_rate": 0,
            "total_reactions": 0, "total_comments": 0, "total_shares": 0,
            "best_post": None, "worst_post": None
        },
        "instagram": {
            "total_posts": 0, "avg_reach": 0, "avg_engagement_rate": 0,
            "total_likes": 0, "total_comments": 0,
            "best_post": None, "worst_post": None
        },
        "insights": [], "recommendations": []
    }
    
    if fb_posts.get("success") and fb_posts.get("posts"):
        posts = fb_posts["posts"]
        analysis["facebook"]["total_posts"] = len(posts)
        analysis["facebook"]["avg_reach"] = sum(p.get("reach", 0) for p in posts) / len(posts) if posts else 0
        analysis["facebook"]["avg_engagement_rate"] = sum(p.get("engagement_rate", 0) for p in posts) / len(posts) if posts else 0
        analysis["facebook"]["total_reactions"] = sum(p.get("reactions", 0) for p in posts)
        analysis["facebook"]["total_comments"] = sum(p.get("comments", 0) for p in posts)
        analysis["facebook"]["total_shares"] = sum(p.get("shares", 0) for p in posts)
        
        sorted_posts = sorted(posts, key=lambda x: x.get("engagement_rate", 0), reverse=True)
        if sorted_posts:
            analysis["facebook"]["best_post"] = sorted_posts[0]
            analysis["facebook"]["worst_post"] = sorted_posts[-1]
    
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
    
    fb_eng = analysis["facebook"]["avg_engagement_rate"]
    ig_eng = analysis["instagram"]["avg_engagement_rate"]
    
    if fb_eng > 0 and ig_eng > 0:
        if fb_eng > ig_eng * 1.2:
            analysis["insights"].append("Facebook daha yüksek engagement alıyor")
        elif ig_eng > fb_eng * 1.2:
            analysis["insights"].append("Instagram daha yüksek engagement alıyor")
        else:
            analysis["insights"].append("Her iki platform benzer performans gösteriyor")
    
    return analysis


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
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(
                f"{GRAPH_API_URL}/{media_id}",
                params={
                    "fields": "media_type,media_product_type",
                    "access_token": FACEBOOK_ACCESS_TOKEN
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

    Instagram Graph API Reels Metrics:
    - plays (ig_reels_aggregated_all_plays_count)
    - reach
    - saved
    - shares
    - comments
    - likes
    - total_interactions
    - ig_reels_avg_watch_time
    - ig_reels_video_view_total_time

    Returns:
        {
            "success": True,
            "media_id": "...",
            "media_type": "REELS",
            "plays": 1234,
            "reach": 890,
            "reach_followers": 200,
            "reach_non_followers": 690,
            "avg_watch_time_seconds": 4.5,
            "total_watch_time_seconds": 5553,
            "saves": 12,
            "shares": 5,
            "comments": 3,
            "likes": 45,
            "total_interactions": 65,
            "engagement_rate": 7.3
        }
    """
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            result = {
                "success": True,
                "media_id": media_id,
                "media_type": "REELS",
                "plays": 0,
                "reach": 0,
                "reach_followers": 0,
                "reach_non_followers": 0,
                "avg_watch_time_seconds": 0,
                "total_watch_time_seconds": 0,
                "saves": 0,
                "shares": 0,
                "comments": 0,
                "likes": 0,
                "total_interactions": 0,
                "engagement_rate": 0.0
            }

            # ===== AŞAMA 1: Temel Reels Metrikleri =====
            # Reels için mevcut metrikler
            reels_metrics = [
                "plays",
                "reach",
                "saved",
                "shares",
                "comments",
                "likes",
                "total_interactions",
                "ig_reels_avg_watch_time",
                "ig_reels_video_view_total_time"
            ]

            insights_response = await client.get(
                f"{GRAPH_API_URL}/{media_id}/insights",
                params={
                    "metric": ",".join(reels_metrics),
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )

            if insights_response.status_code == 200:
                data = insights_response.json().get("data", [])
                for metric in data:
                    name = metric.get("name")
                    values = metric.get("values", [])
                    value = values[0].get("value", 0) if values else 0

                    # Metrik mapping
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
                        result["avg_watch_time_seconds"] = value
                    elif name == "ig_reels_video_view_total_time":
                        result["total_watch_time_seconds"] = value
            else:
                # Bazı metrikler mevcut olmayabilir - fallback dene
                error_text = insights_response.text
                print(f"[IG_REELS] Primary metrics failed for {media_id}: {error_text[:100]}")

                # Sadece temel metrikleri dene
                fallback_response = await client.get(
                    f"{GRAPH_API_URL}/{media_id}/insights",
                    params={
                        "metric": "reach,saved,shares,comments,likes",
                        "access_token": FACEBOOK_ACCESS_TOKEN
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

            # ===== AŞAMA 2: Follower/Non-Follower Breakdown =====
            # Bu metrik sadece bazı hesaplarda mevcut
            try:
                breakdown_response = await client.get(
                    f"{GRAPH_API_URL}/{media_id}/insights",
                    params={
                        "metric": "reach",
                        "breakdown": "follow_type",
                        "access_token": FACEBOOK_ACCESS_TOKEN
                    }
                )

                if breakdown_response.status_code == 200:
                    data = breakdown_response.json().get("data", [])
                    for metric in data:
                        if metric.get("name") == "reach":
                            total_value = metric.get("total_value", {})
                            breakdowns = total_value.get("breakdowns", [])
                            for bd in breakdowns:
                                results = bd.get("results", [])
                                for r in results:
                                    dim_value = r.get("dimension_values", [""])[0]
                                    if dim_value == "follower":
                                        result["reach_followers"] = r.get("value", 0)
                                    elif dim_value == "non_follower":
                                        result["reach_non_followers"] = r.get("value", 0)
            except Exception as e:
                # Breakdown mevcut değilse gracefully handle et
                print(f"[IG_REELS] Breakdown not available for {media_id}: {e}")

            # ===== AŞAMA 3: Temel Bilgiler (like_count, comments_count) =====
            try:
                basic_response = await client.get(
                    f"{GRAPH_API_URL}/{media_id}",
                    params={
                        "fields": "like_count,comments_count,media_type,media_product_type,caption,timestamp",
                        "access_token": FACEBOOK_ACCESS_TOKEN
                    }
                )

                if basic_response.status_code == 200:
                    basic_data = basic_response.json()
                    # Insights'tan gelen değer yoksa buradan al
                    if result["likes"] == 0:
                        result["likes"] = basic_data.get("like_count", 0)
                    if result["comments"] == 0:
                        result["comments"] = basic_data.get("comments_count", 0)
                    result["media_type"] = basic_data.get("media_product_type", "REELS")
                    result["caption"] = (basic_data.get("caption") or "")[:100]
                    result["timestamp"] = basic_data.get("timestamp")
            except Exception as e:
                print(f"[IG_REELS] Basic info fetch warning for {media_id}: {e}")

            # ===== AŞAMA 4: Engagement Rate Hesapla =====
            reach = result["reach"] if result["reach"] > 0 else 1
            total_engagement = result["likes"] + result["comments"] + result["saves"] + result["shares"]
            result["engagement_rate"] = round((total_engagement / reach) * 100, 2)

            # Total interactions yoksa hesapla
            if result["total_interactions"] == 0:
                result["total_interactions"] = total_engagement

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "media_id": media_id}


async def get_instagram_image_insights(media_id: str) -> Dict[str, Any]:
    """
    Instagram Image/Carousel için basit metrikler çek.

    Returns:
        {
            "success": True,
            "media_id": "...",
            "media_type": "IMAGE",
            "impressions": 1234,
            "reach": 890,
            "saves": 12,
            "likes": 45,
            "comments": 3,
            "engagement_rate": 6.7
        }
    """
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

            # Insights çek - önce /insights endpoint dene
            insights_response = await client.get(
                f"{GRAPH_API_URL}/{media_id}/insights",
                params={
                    "metric": "impressions,reach,saved",
                    "access_token": FACEBOOK_ACCESS_TOKEN
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
            else:
                # Fallback: nested format dene
                print(f"[IG_IMAGE] /insights failed for {media_id}, trying nested format...")

            # Eğer reach ve impressions hala 0 ise, nested format dene
            if result["reach"] == 0 and result["impressions"] == 0:
                try:
                    nested_response = await client.get(
                        f"{GRAPH_API_URL}/{media_id}",
                        params={
                            "fields": "insights.metric(impressions,reach,saved)",
                            "access_token": FACEBOOK_ACCESS_TOKEN
                        }
                    )

                    if nested_response.status_code == 200:
                        nested_data = nested_response.json()
                        insights_data = nested_data.get("insights", {}).get("data", [])
                        for metric in insights_data:
                            name = metric.get("name")
                            values = metric.get("values", [])
                            value = values[0].get("value", 0) if values else 0

                            if name == "impressions":
                                result["impressions"] = value
                            elif name == "reach":
                                result["reach"] = value
                            elif name == "saved":
                                result["saves"] = value

                        if result["impressions"] > 0 or result["reach"] > 0:
                            print(f"[IG_IMAGE] Nested format worked: impressions={result['impressions']}, reach={result['reach']}")
                except Exception as e:
                    print(f"[IG_IMAGE] Nested format failed for {media_id}: {e}")

            # Temel bilgiler
            basic_response = await client.get(
                f"{GRAPH_API_URL}/{media_id}",
                params={
                    "fields": "like_count,comments_count,media_type,caption,timestamp",
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )

            if basic_response.status_code == 200:
                basic_data = basic_response.json()
                result["likes"] = basic_data.get("like_count", 0)
                result["comments"] = basic_data.get("comments_count", 0)
                result["media_type"] = basic_data.get("media_type", "IMAGE")
                result["caption"] = (basic_data.get("caption") or "")[:100]
                result["timestamp"] = basic_data.get("timestamp")

            # Engagement rate - reach yoksa impressions kullan
            denominator = result["reach"] if result["reach"] > 0 else result["impressions"]
            denominator = denominator if denominator > 0 else 1
            total_engagement = result["likes"] + result["comments"] + result["saves"]
            result["engagement_rate"] = round((total_engagement / denominator) * 100, 2)

            return result

        except Exception as e:
            return {"success": False, "error": str(e), "media_id": media_id}


async def get_instagram_media_insights(media_id: str) -> Dict[str, Any]:
    """
    Instagram media için otomatik tip tespiti ve uygun metrikler çek.

    - REELS/VIDEO → get_instagram_reels_insights()
    - IMAGE/CAROUSEL → get_instagram_image_insights()

    Returns:
        Tipe göre uygun insights dict
    """
    # Önce media tipini tespit et
    type_info = await get_instagram_media_type(media_id)

    if not type_info.get("success"):
        return {"success": False, "error": type_info.get("error", "Media type detection failed")}

    is_reels = type_info.get("is_reels", False)
    media_type = type_info.get("media_type", "")
    product_type = type_info.get("media_product_type", "")

    print(f"[IG_INSIGHTS] Media {media_id}: type={media_type}, product={product_type}, is_reels={is_reels}")

    if is_reels:
        return await get_instagram_reels_insights(media_id)
    else:
        return await get_instagram_image_insights(media_id)


async def sync_insights_to_database() -> Dict[str, Any]:
    """Tüm insights'ları database'e kaydet"""
    from app.database import update_post_analytics, get_published_posts
    
    db_posts = get_published_posts(days=30)
    synced = 0
    errors = 0
    
    for post in db_posts:
        fb_post_id = post.get("facebook_post_id")
        analytics_data = {}
        
        if fb_post_id:
            fb_insights = await get_post_insights(fb_post_id)
            if fb_insights.get("success"):
                analytics_data["fb_reach"] = fb_insights.get("insights", {}).get("post_impressions_unique", 0)
                analytics_data["fb_likes"] = fb_insights.get("post_data", {}).get("reactions", 0)
                analytics_data["fb_comments"] = fb_insights.get("post_data", {}).get("comments", 0)
                analytics_data["fb_shares"] = fb_insights.get("post_data", {}).get("shares", 0)
                analytics_data["fb_engagement_rate"] = fb_insights.get("engagement_rate", 0)
        
        if analytics_data:
            try:
                update_post_analytics(post.get("id"), analytics_data)
                synced += 1
            except Exception as e:
                errors += 1
        
        await asyncio.sleep(0.3)
    
    return {"success": True, "synced": synced, "errors": errors, "total": len(db_posts)}
