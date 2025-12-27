"""
Meta Ads API Helper
Reklam performans verilerini çeker ve analiz eder.

Gerekli İzinler:
- ads_read: Reklam verilerini okuma
- business_management: Business hesap erişimi

Kullanım:
    from app.meta_ads_helper import get_ads_summary, get_campaign_insights
    summary = await get_ads_summary(days=30)
"""

import os
import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

# API Configuration
GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Credentials
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID = os.getenv("META_AD_ACCOUNT_ID", "")
META_BUSINESS_ID = os.getenv("META_BUSINESS_ID", "")

# Çekilecek reklam metrikleri
AD_INSIGHTS_FIELDS = [
    "campaign_id",
    "campaign_name",
    "adset_id",
    "adset_name",
    "ad_id",
    "ad_name",
    "impressions",
    "reach",
    "clicks",
    "spend",
    "cpc",
    "cpm",
    "frequency",
    "actions",
    "cost_per_action_type",
    "video_play_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p100_watched_actions",
]


def _log(message: str):
    """Internal logging"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[META_ADS {timestamp}] {message}")


async def get_ad_account_info() -> Dict[str, Any]:
    """
    Ad Account bilgilerini al.

    Returns:
        Dict with account info or error
    """
    if not META_AD_ACCOUNT_ID:
        return {"success": False, "error": "META_AD_ACCOUNT_ID not set in .env"}

    if not INSTAGRAM_ACCESS_TOKEN:
        return {"success": False, "error": "INSTAGRAM_ACCESS_TOKEN not set"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/{META_AD_ACCOUNT_ID}",
                params={
                    "fields": "name,account_status,currency,business,amount_spent",
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "account_id": META_AD_ACCOUNT_ID,
                    "name": data.get("name", "Unknown"),
                    "status": data.get("account_status"),
                    "currency": data.get("currency", "USD"),
                    "amount_spent": float(data.get("amount_spent", 0)) / 100,  # cents to dollars
                    "business": data.get("business", {}).get("name", "N/A")
                }
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                _log(f"Ad account error: {error_msg}")
                return {"success": False, "error": error_msg}

    except Exception as e:
        _log(f"Ad account fetch error: {e}")
        return {"success": False, "error": str(e)}


async def get_campaign_insights(
    date_start: Optional[str] = None,
    date_stop: Optional[str] = None,
    level: str = "campaign"
) -> Dict[str, Any]:
    """
    Kampanya performans verilerini çek.

    Args:
        date_start: YYYY-MM-DD format (default: 30 days ago)
        date_stop: YYYY-MM-DD format (default: today)
        level: Detay seviyesi - campaign, adset, or ad

    Returns:
        Dict with campaigns list or error
    """
    if not META_AD_ACCOUNT_ID:
        return {"success": False, "error": "META_AD_ACCOUNT_ID not set", "data": []}

    if not date_start:
        date_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_stop:
        date_stop = datetime.now().strftime("%Y-%m-%d")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/{META_AD_ACCOUNT_ID}/insights",
                params={
                    "fields": ",".join(AD_INSIGHTS_FIELDS),
                    "level": level,
                    "time_range": f'{{"since":"{date_start}","until":"{date_stop}"}}',
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if response.status_code == 200:
                data = response.json()
                campaigns = data.get("data", [])
                _log(f"Fetched {len(campaigns)} {level}(s) from {date_start} to {date_stop}")
                return {"success": True, "data": campaigns, "count": len(campaigns)}
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                _log(f"Campaign insights error: {error_msg}")
                return {"success": False, "error": error_msg, "data": []}

    except Exception as e:
        _log(f"Campaign insights fetch error: {e}")
        return {"success": False, "error": str(e), "data": []}


def parse_actions(actions: Optional[List[Dict]]) -> Dict[str, int]:
    """
    Actions listesini parse et.

    Instagram action types:
    - like, comment, save, share
    - follow, onsite_follow (Instagram takip)
    - link_click, video_view, post_engagement

    Returns:
        Dict with parsed action counts
    """
    result = {
        "likes": 0,
        "comments": 0,
        "saves": 0,
        "shares": 0,
        "follows": 0,
        "link_clicks": 0,
        "video_views": 0,
        "engagements": 0,
    }

    if not actions:
        return result

    action_mapping = {
        "like": "likes",
        "comment": "comments",
        "save": "saves",
        "share": "shares",
        "follow": "follows",
        "onsite_follow": "follows",
        "page_engagement": "engagements",
        "post_engagement": "engagements",
        "link_click": "link_clicks",
        "video_view": "video_views",
    }

    for action in actions:
        action_type = action.get("action_type", "")
        value = int(action.get("value", 0))

        if action_type in action_mapping:
            result[action_mapping[action_type]] += value

    return result


def parse_cost_per_action(cost_per_action: Optional[List[Dict]]) -> Dict[str, float]:
    """
    Cost per action listesini parse et.

    Returns:
        Dict with cost per action type
    """
    result = {
        "cost_per_like": 0.0,
        "cost_per_follow": 0.0,
        "cost_per_engagement": 0.0,
        "cost_per_save": 0.0,
        "cost_per_click": 0.0,
    }

    if not cost_per_action:
        return result

    for cpa in cost_per_action:
        action_type = cpa.get("action_type", "")
        value = float(cpa.get("value", 0))

        if action_type == "like":
            result["cost_per_like"] = value
        elif action_type in ["follow", "onsite_follow"]:
            result["cost_per_follow"] = value
        elif action_type in ["post_engagement", "page_engagement"]:
            result["cost_per_engagement"] = value
        elif action_type == "save":
            result["cost_per_save"] = value
        elif action_type == "link_click":
            result["cost_per_click"] = value

    return result


def parse_video_metrics(campaign: Dict) -> Dict[str, int]:
    """
    Video izleme metriklerini parse et.

    Returns:
        Dict with video view percentages
    """
    result = {
        "video_plays": 0,
        "video_25_pct": 0,
        "video_50_pct": 0,
        "video_75_pct": 0,
        "video_100_pct": 0,
    }

    # Video play actions
    video_plays = campaign.get("video_play_actions", [])
    if video_plays:
        result["video_plays"] = int(video_plays[0].get("value", 0))

    # Percentage watched
    for key, field in [
        ("video_25_pct", "video_p25_watched_actions"),
        ("video_50_pct", "video_p50_watched_actions"),
        ("video_75_pct", "video_p75_watched_actions"),
        ("video_100_pct", "video_p100_watched_actions"),
    ]:
        data = campaign.get(field, [])
        if data:
            result[key] = int(data[0].get("value", 0))

    return result


async def get_ads_summary(days: int = 30) -> Dict[str, Any]:
    """
    Özet reklam performansı.

    Args:
        days: Kaç günlük veri çekilecek

    Returns:
        Dict with aggregated ad performance metrics
    """
    date_start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_stop = datetime.now().strftime("%Y-%m-%d")

    result = await get_campaign_insights(date_start, date_stop, level="campaign")

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Unknown error"),
            "period_days": days
        }

    campaigns = result.get("data", [])

    # Aggregate metrics
    total_spend = 0.0
    total_impressions = 0
    total_reach = 0
    total_clicks = 0
    total_follows = 0
    total_saves = 0
    total_likes = 0
    total_engagements = 0
    total_video_views = 0

    for campaign in campaigns:
        total_spend += float(campaign.get("spend", 0))
        total_impressions += int(campaign.get("impressions", 0))
        total_reach += int(campaign.get("reach", 0))
        total_clicks += int(campaign.get("clicks", 0))

        actions = parse_actions(campaign.get("actions", []))
        total_follows += actions["follows"]
        total_saves += actions["saves"]
        total_likes += actions["likes"]
        total_engagements += actions["engagements"]
        total_video_views += actions["video_views"]

    return {
        "success": True,
        "period_days": days,
        "date_range": f"{date_start} - {date_stop}",
        "campaigns_count": len(campaigns),

        # Spend
        "total_spend": round(total_spend, 2),
        "currency": "USD",  # TODO: Get from account

        # Reach & Impressions
        "total_impressions": total_impressions,
        "total_reach": total_reach,
        "frequency": round(total_impressions / total_reach, 2) if total_reach > 0 else 0,

        # Clicks
        "total_clicks": total_clicks,
        "ctr": round((total_clicks / total_impressions) * 100, 2) if total_impressions > 0 else 0,
        "cpc": round(total_spend / total_clicks, 2) if total_clicks > 0 else 0,

        # Actions
        "total_follows": total_follows,
        "total_saves": total_saves,
        "total_likes": total_likes,
        "total_engagements": total_engagements,
        "total_video_views": total_video_views,

        # Cost per action
        "cost_per_follow": round(total_spend / total_follows, 2) if total_follows > 0 else 0,
        "cost_per_save": round(total_spend / total_saves, 2) if total_saves > 0 else 0,
        "cost_per_1000_reach": round((total_spend / total_reach) * 1000, 2) if total_reach > 0 else 0,
        "cost_per_engagement": round(total_spend / total_engagements, 2) if total_engagements > 0 else 0,
    }


async def get_active_campaigns() -> Dict[str, Any]:
    """
    Aktif kampanyaları listele.

    Returns:
        Dict with active campaigns list
    """
    if not META_AD_ACCOUNT_ID:
        return {"success": False, "error": "META_AD_ACCOUNT_ID not set", "data": []}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GRAPH_API_BASE}/{META_AD_ACCOUNT_ID}/campaigns",
                params={
                    "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time",
                    "filtering": '[{"field":"effective_status","operator":"IN","value":["ACTIVE","PAUSED"]}]',
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if response.status_code == 200:
                data = response.json()
                campaigns = data.get("data", [])
                return {"success": True, "data": campaigns, "count": len(campaigns)}
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                return {"success": False, "error": error_msg, "data": []}

    except Exception as e:
        return {"success": False, "error": str(e), "data": []}


async def get_promoted_post_insights(ig_media_id: str) -> Dict[str, Any]:
    """
    Belirli bir Instagram post'unun reklam verilerini çek.

    Bu, post'un promote edilip edilmediğini ve
    promote edildiyse performansını gösterir.

    Args:
        ig_media_id: Instagram media ID

    Returns:
        Dict with promoted post metrics or None if not promoted
    """
    if not META_AD_ACCOUNT_ID:
        return {"success": False, "error": "META_AD_ACCOUNT_ID not set"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Search for ads linked to this media
            response = await client.get(
                f"{GRAPH_API_BASE}/{META_AD_ACCOUNT_ID}/ads",
                params={
                    "fields": "id,name,effective_object_story_id,insights{impressions,reach,spend,clicks,actions,cost_per_action_type}",
                    "filtering": f'[{{"field":"effective_object_story_id","operator":"CONTAIN","value":"{ig_media_id}"}}]',
                    "access_token": INSTAGRAM_ACCESS_TOKEN
                }
            )

            if response.status_code == 200:
                data = response.json()
                ads = data.get("data", [])

                if not ads:
                    return {"success": True, "is_promoted": False, "message": "Post is not promoted"}

                # Get first matching ad
                ad = ads[0]
                insights = ad.get("insights", {}).get("data", [{}])[0]

                return {
                    "success": True,
                    "is_promoted": True,
                    "ad_id": ad.get("id"),
                    "ad_name": ad.get("name"),
                    "impressions": int(insights.get("impressions", 0)),
                    "reach": int(insights.get("reach", 0)),
                    "spend": float(insights.get("spend", 0)),
                    "clicks": int(insights.get("clicks", 0)),
                    "actions": parse_actions(insights.get("actions", [])),
                    "cost_per_action": parse_cost_per_action(insights.get("cost_per_action_type", []))
                }
            else:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
                return {"success": False, "error": error_msg}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def test_ads_api_connection() -> bool:
    """
    Meta Ads API bağlantısını test et.

    Returns:
        True if connection successful
    """
    print("\n=== Meta Ads API Connection Test ===\n")
    print(f"API Version: {GRAPH_API_VERSION}")
    print(f"Ad Account ID: {META_AD_ACCOUNT_ID or 'NOT SET'}")
    print(f"Access Token: {'SET' if INSTAGRAM_ACCESS_TOKEN else 'NOT SET'}\n")

    if not META_AD_ACCOUNT_ID:
        print("[WARN] META_AD_ACCOUNT_ID not set in .env")
        print("       To get your Ad Account ID:")
        print("       1. Go to Meta Business Suite")
        print("       2. Settings > Ad Account Settings")
        print("       3. Copy the Account ID (format: act_XXXXXXXXXX)")
        return False

    if not INSTAGRAM_ACCESS_TOKEN:
        print("[FAIL] INSTAGRAM_ACCESS_TOKEN not set")
        return False

    # Test account access
    result = await get_ad_account_info()

    if result.get("success"):
        print(f"[OK] Ad Account: {result.get('name')}")
        print(f"[OK] Status: {result.get('status')}")
        print(f"[OK] Currency: {result.get('currency')}")
        print(f"[OK] Total Spent: ${result.get('amount_spent', 0):.2f}")
        print(f"[OK] Business: {result.get('business')}")

        # Test insights access
        summary = await get_ads_summary(days=7)
        if summary.get("success"):
            print(f"\n[OK] Last 7 days:")
            print(f"     Campaigns: {summary.get('campaigns_count')}")
            print(f"     Spend: ${summary.get('total_spend', 0):.2f}")
            print(f"     Reach: {summary.get('total_reach', 0):,}")
            print(f"     Follows: {summary.get('total_follows', 0)}")
        else:
            print(f"\n[WARN] Could not fetch insights: {summary.get('error')}")

        return True
    else:
        print(f"[FAIL] {result.get('error')}")

        # Common error hints
        error = result.get("error", "")
        if "permission" in error.lower():
            print("\n[HINT] Missing permissions. Required:")
            print("       - ads_read")
            print("       - business_management")
        elif "invalid" in error.lower() and "account" in error.lower():
            print("\n[HINT] Invalid Ad Account ID format.")
            print("       Should be: act_XXXXXXXXXX")

        return False


# CLI entry point for testing
if __name__ == "__main__":
    asyncio.run(test_ads_api_connection())
