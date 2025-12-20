#!/usr/bin/env python3
"""
Mevcut published post'lar için retroaktif metrik çekme.

Kullanım:
    python scripts/backfill_metrics.py
    python scripts/backfill_metrics.py --days 30
    python scripts/backfill_metrics.py --limit 10
"""
import asyncio
import sys
import argparse
from datetime import datetime, timedelta

# Proje root'unu path'e ekle
sys.path.insert(0, '/opt/olivenet-social-bot')

from app.database import get_posts_by_status
from app.agents import AnalyticsAgent


async def backfill_all_metrics(days: int = None, limit: int = None):
    """
    Tüm published post'lar için metrikleri çek ve DB'ye kaydet.

    Args:
        days: Son kaç günün post'larını işle (None = tümü)
        limit: Maksimum kaç post işlensin (None = tümü)
    """
    print("=" * 60)
    print("OLIVENET SOCIAL BOT - Metrik Backfill Script")
    print("=" * 60)

    analytics = AnalyticsAgent()
    posts = get_posts_by_status('published')

    # Tarih filtresi
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        posts = [p for p in posts if p.get('published_at') and
                 datetime.fromisoformat(str(p['published_at']).replace('Z', '')) > cutoff]
        print(f"[FILTER] Son {days} günün post'ları filtrelendi")

    # fb_reach veya ig_reach NULL olanları filtrele
    to_update = [p for p in posts if
                 (p.get('facebook_post_id') or p.get('instagram_post_id')) and
                 (p.get('fb_reach') is None or p.get('ig_reach') is None)]

    # Limit uygula
    if limit:
        to_update = to_update[:limit]
        print(f"[LIMIT] Maksimum {limit} post işlenecek")

    total = len(to_update)
    success = 0
    errors = []

    print(f"\n[BACKFILL] {total} post işlenecek...")
    print("-" * 60)

    for i, post in enumerate(to_update, 1):
        post_id = post.get("id")
        fb_id = post.get("facebook_post_id")
        ig_id = post.get("instagram_post_id")

        platform_info = []
        if fb_id:
            platform_info.append("FB")
        if ig_id:
            platform_info.append("IG")

        try:
            result = await analytics.fetch_metrics({
                "post_id": post_id,
                "facebook_post_id": fb_id,
                "instagram_post_id": ig_id
            })

            if result.get("success"):
                success += 1
                fb_reach = result.get("facebook", {}).get("insights", {}).get("post_impressions_unique", 0) if result.get("facebook") else 0
                ig_reach = result.get("instagram", {}).get("reach", 0) if result.get("instagram") else 0
                print(f"[{i}/{total}] Post {post_id} ({'+'.join(platform_info)}) - OK (FB:{fb_reach}, IG:{ig_reach})")
            else:
                error_msg = result.get('error', 'Unknown error')
                errors.append((post_id, error_msg))
                print(f"[{i}/{total}] Post {post_id} ({'+'.join(platform_info)}) - FAIL: {error_msg}")

        except Exception as e:
            errors.append((post_id, str(e)))
            print(f"[{i}/{total}] Post {post_id} ({'+'.join(platform_info)}) - ERROR: {e}")

        # Rate limit - 2 saniye bekle
        await asyncio.sleep(2)

    # Özet rapor
    print("\n" + "=" * 60)
    print("BACKFILL TAMAMLANDI")
    print("=" * 60)
    print(f"  Toplam işlenen: {total}")
    print(f"  Başarılı:       {success}")
    print(f"  Başarısız:      {len(errors)}")

    if errors:
        print(f"\n  İlk 5 hata:")
        for pid, err in errors[:5]:
            print(f"    - Post {pid}: {err[:50]}...")

    print("=" * 60)

    return {
        "total": total,
        "success": success,
        "errors": len(errors),
        "error_details": errors
    }


def main():
    parser = argparse.ArgumentParser(description='Olivenet Social Bot - Metrik Backfill')
    parser.add_argument('--days', type=int, help='Son kaç günün post\'larını işle')
    parser.add_argument('--limit', type=int, help='Maksimum kaç post işlensin')

    args = parser.parse_args()

    asyncio.run(backfill_all_metrics(days=args.days, limit=args.limit))


if __name__ == "__main__":
    main()
