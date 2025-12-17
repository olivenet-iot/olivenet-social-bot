#!/usr/bin/env python3
"""
Olivenet AI Content System - Başlatıcı
"""

import asyncio
import sys
import os

# Path ayarla
sys.path.insert(0, '/opt/olivenet-social-bot')
os.chdir('/opt/olivenet-social-bot')

from dotenv import load_dotenv
load_dotenv()

async def main():
    """Ana başlatıcı"""
    print("=" * 50)
    print("🤖 Olivenet AI Content System")
    print("=" * 50)
    print()

    # Database kontrolü
    print("[1/4] Database kontrol ediliyor...")
    from app.database import init_database, create_default_strategy
    init_database()
    create_default_strategy()
    print("      ✅ Database hazır")

    # Agent'ları test et
    print("[2/4] Agent'lar kontrol ediliyor...")
    from app.agents import (
        OrchestratorAgent, PlannerAgent, CreatorAgent,
        ReviewerAgent, PublisherAgent, AnalyticsAgent
    )
    print("      ✅ Tüm agent'lar yüklendi")

    # Pipeline oluştur
    print("[3/4] Pipeline oluşturuluyor...")
    from app.scheduler import ContentPipeline, create_default_scheduler
    pipeline = ContentPipeline()
    scheduler = create_default_scheduler(pipeline)
    print("      ✅ Pipeline ve scheduler hazır")

    # Telegram bot başlat
    print("[4/4] Telegram bot başlatılıyor...")
    from app.telegram_pipeline import main as telegram_main
    await telegram_main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Sistem kapatılıyor...")
        sys.exit(0)
