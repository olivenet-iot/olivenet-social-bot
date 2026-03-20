#!/usr/bin/env python3
"""
Olivenet Social Bot v2 — Ana giriş noktası

v1 Telegram bot + v2 Feed/Brain döngüleri paralel çalışır.
"""

import asyncio
import sys
import os

sys.path.insert(0, '/opt/olivenet-social-bot')
os.chdir('/opt/olivenet-social-bot')

from dotenv import load_dotenv
load_dotenv()


async def main():
    """Olivenet Social Bot v2 başlatıcı."""
    print("=" * 50)
    print("Olivenet Social Bot v2")
    print("=" * 50)
    print()

    # 1. Database
    print("[1/5] Database kontrol ediliyor...")
    from app.database import init_database, create_default_strategy
    init_database()
    create_default_strategy()
    print("      Database hazir")

    # 2. Event Bus
    print("[2/5] Event bus olusturuluyor...")
    from app.engine.event_bus import EventBus
    event_bus = EventBus()
    print("      Event bus hazir")

    # 3. v2 Components
    print("[3/5] v2 bilesenleri yukleniyor...")
    from app.sources.feed_aggregator import FeedAggregator
    from app.agents.brain import BrainAgent
    from app.engine.scheduler import V2Scheduler

    aggregator = FeedAggregator()
    brain = BrainAgent()
    brain.event_bus = event_bus

    v2_scheduler = V2Scheduler(
        brain_agent=brain,
        feed_aggregator=aggregator,
        event_bus=event_bus
    )

    dry_run_status = "ON (kararlar loglanir, uretim yapilmaz)" if brain.is_dry_run else "OFF (full otonom)"
    print(f"      Brain dry-run: {dry_run_status}")
    print("      v2 bilesenleri hazir")

    # 4. v1 Pipeline + Scheduler
    print("[4/5] v1 pipeline yukleniyor...")
    try:
        from app.scheduler import ContentPipeline, create_default_scheduler
        pipeline = ContentPipeline()
        v1_scheduler = create_default_scheduler(pipeline)
        print("      v1 pipeline hazir")
    except ImportError as e:
        print(f"      v1 pipeline yuklenemedi (normal: {e})")
        pipeline = None
        v1_scheduler = None

    # 5. Baslat
    print("[5/5] Sistem baslatiliyor...")
    print()

    tasks = []

    # v1 Telegram bot + v2 monitoring globals
    try:
        import app.telegram_pipeline as telegram_pipeline_mod
        telegram_pipeline_mod.brain_agent = brain
        telegram_pipeline_mod.feed_aggregator = aggregator
        from app.telegram_pipeline import main as telegram_main
        tasks.append(telegram_main())
        print("  -> v1 Telegram bot baslatildi (v2 monitoring aktif)")
    except ImportError as e:
        print(f"  -> v1 Telegram bot atlanıyor: {e}")

    # v2 Scheduler (feed + brain loops)
    tasks.append(v2_scheduler.start())
    print("  -> v2 Scheduler baslatildi (feed + brain)")

    print()
    print("Sistem calisiyor. Ctrl+C ile durdurun.")
    print("=" * 50)

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nSistem kapatiliyor...")
        sys.exit(0)
