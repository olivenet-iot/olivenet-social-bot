"""
V2 Scheduler - Feed aggregation + Brain decision döngüleri
Mevcut v1 scheduler ile paralel çalışır.
"""

import os
import asyncio
import traceback
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger("v2_scheduler")

# Konfigürasyon (env vars)
FEED_POLL_MINUTES = int(os.getenv("FEED_POLL_MINUTES", "30"))
BRAIN_CYCLE_MINUTES = int(os.getenv("BRAIN_CYCLE_MINUTES", "120"))
EXPIRY_CHECK_HOURS = 6


class V2Scheduler:
    """
    v2 scheduler. Feed aggregation ve Brain karar döngülerini yönetir.
    v1 scheduler ile paralel çalışabilir.
    """

    def __init__(self, brain_agent=None, feed_aggregator=None, event_bus=None):
        self.brain = brain_agent
        self.feeds = feed_aggregator
        self.event_bus = event_bus
        self._running = False

    async def start(self):
        """Tüm v2 döngülerini başlat."""
        self._running = True
        logger.info(
            f"V2 Scheduler starting "
            f"(feed: {FEED_POLL_MINUTES}m, brain: {BRAIN_CYCLE_MINUTES}m, "
            f"expiry: {EXPIRY_CHECK_HOURS}h)"
        )

        tasks = []

        if self.feeds:
            tasks.append(self._feed_loop())

        if self.brain:
            tasks.append(self._brain_loop())
            tasks.append(self._analytics_loop())

        tasks.append(self._expiry_loop())

        await asyncio.gather(*tasks)

    async def stop(self):
        """Scheduler'ı durdur."""
        self._running = False
        if self.feeds:
            self.feeds.stop()
        logger.info("V2 Scheduler stopped")

    async def _feed_loop(self):
        """Feed aggregation döngüsü."""
        logger.info(f"Feed loop started (every {FEED_POLL_MINUTES}m)")

        # İlk çalıştırmada 10 saniye bekle (sistemin başlamasını bekle)
        await asyncio.sleep(10)

        while self._running:
            try:
                await self.feeds.run_feed_pipeline()

                if self.event_bus:
                    from app.database.crud import get_opportunity_stats
                    stats = get_opportunity_stats()
                    await self.event_bus.publish("feed_updated", {
                        "active_count": stats.get("active_count", 0),
                        "by_status": stats.get("by_status", {})
                    })

            except Exception as e:
                logger.error(f"Feed loop error: {e}\n{traceback.format_exc()}")

            await asyncio.sleep(FEED_POLL_MINUTES * 60)

    async def _brain_loop(self):
        """Brain karar döngüsü."""
        logger.info(f"Brain loop started (every {BRAIN_CYCLE_MINUTES}m)")

        # İlk çalıştırmada feed'lerin dolmasını bekle
        await asyncio.sleep(FEED_POLL_MINUTES * 60 + 30)

        while self._running:
            try:
                decision = await self.brain.decide()
                logger.info(
                    f"Brain decision: {decision.get('action')} — "
                    f"{decision.get('reason', '')[:100]}"
                )

            except Exception as e:
                logger.error(f"Brain loop error: {e}\n{traceback.format_exc()}")

            await asyncio.sleep(BRAIN_CYCLE_MINUTES * 60)

    async def _analytics_loop(self):
        """Daily prediction accuracy check."""
        logger.info("Analytics loop started (every 24h)")

        # İlk çalıştırmada 24 saat bekle
        await asyncio.sleep(86400)

        while self._running:
            try:
                result = await self.brain.check_prediction_accuracy()
                logger.info(
                    f"Analytics check: {result.get('checked', 0)} posts, "
                    f"avg_score={result.get('avg_actual_score', 0)}"
                )
            except Exception as e:
                logger.error(f"Analytics loop error: {e}")

            await asyncio.sleep(86400)  # Every 24h

    async def _expiry_loop(self):
        """Eski fırsatları temizleme döngüsü."""
        logger.info(f"Expiry loop started (every {EXPIRY_CHECK_HOURS}h)")

        # İlk çalıştırmada 1 saat bekle
        await asyncio.sleep(3600)

        while self._running:
            try:
                from app.database.crud import expire_old_opportunities
                expired = expire_old_opportunities(max_age_hours=72)
                if expired:
                    logger.info(f"Expired {expired} old opportunities")
            except Exception as e:
                logger.error(f"Expiry loop error: {e}")

            await asyncio.sleep(EXPIRY_CHECK_HOURS * 3600)

    def get_status(self) -> dict:
        """Scheduler durumu."""
        return {
            "running": self._running,
            "feed_interval_min": FEED_POLL_MINUTES,
            "brain_interval_min": BRAIN_CYCLE_MINUTES,
            "brain_dry_run": self.brain.is_dry_run if self.brain else None,
            "brain_paused": self.brain.state_manager.is_paused if self.brain else None,
        }
