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
    """Tek bir post'un istatistiklerini al"""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            post_response = await client.get(
                f"{GRAPH_API_URL}/{post_id}",
                params={
                    "fields": "message,created_time,shares,comments.summary(true),reactions.summary(true),insights.metric(post_impressions,post_impressions_unique,post_engaged_users,post_clicks)",
                    "access_token": FACEBOOK_ACCESS_TOKEN
                }
            )
            
            if post_response.status_code != 200:
                return {"success": False, "error": post_response.text[:200]}
            
            data = post_response.json()
            
            post_data = {
                "message": (data.get("message") or "")[:100],
                "created_time": data.get("created_time"),
                "shares": data.get("shares", {}).get("count", 0),
                "comments": data.get("comments", {}).get("summary", {}).get("total_count", 0),
                "reactions": data.get("reactions", {}).get("summary", {}).get("total_count", 0),
            }
            
            insights = {}
            insights_data = data.get("insights", {}).get("data", [])
            for metric in insights_data:
                name = metric.get("name")
                values = metric.get("values", [])
                if values:
                    insights[name] = values[0].get("value", 0)
            
            reach = insights.get("post_impressions_unique", 1)
            engagements = post_data["reactions"] + post_data["comments"] + post_data["shares"]
            engagement_rate = (engagements / reach * 100) if reach > 0 else 0
            
            return {
                "success": True,
                "post_id": post_id,
                "post_data": post_data,
                "insights": insights,
                "engagement_rate": round(engagement_rate, 2)
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
