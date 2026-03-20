"""
System State Manager - Sistemin anlık durumunu takip eder
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.utils.logger import get_logger
from app.database.crud import (
    get_kktc_now, get_weekly_progress, get_published_posts,
    get_analytics_summary, get_opportunity_stats, get_top_opportunities,
    get_best_performing_hooks
)

logger = get_logger("state")


class SystemState:
    """Sistem durumunu yönetir. Brain Agent karar verirken bu bilgileri kullanır."""

    def __init__(self):
        self._active_productions = {}  # pipeline_name -> start_time
        self._last_production_times = {}  # content_type -> last_completed_at
        self._paused = False

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self):
        """Sistemi duraklat."""
        self._paused = True
        logger.info("System PAUSED")

    def resume(self):
        """Sistemi devam ettir."""
        self._paused = False
        logger.info("System RESUMED")

    def get_weekly_stats(self) -> Dict[str, Any]:
        """Bu haftanın üretim istatistikleri."""
        try:
            progress = get_weekly_progress()
            return progress
        except Exception as e:
            logger.error(f"Error getting weekly stats: {e}")
            return {}

    def get_pool_status(self) -> Dict[str, Any]:
        """Content opportunity havuzu durumu."""
        try:
            stats = get_opportunity_stats()
            top = get_top_opportunities(limit=5, min_score=50)
            return {
                **stats,
                "top_opportunities": [
                    {
                        "id": o["id"],
                        "title": o["title"][:60],
                        "score": o["combined_score"],
                        "source": o["source_type"],
                        "suggestion": o.get("content_type_suggestion", ""),
                        "hook": o.get("hook_suggestion", "")
                    }
                    for o in top
                ]
            }
        except Exception as e:
            logger.error(f"Error getting pool status: {e}")
            return {"active_count": 0, "top_opportunities": []}

    def get_performance_summary(self, days: int = 7) -> Dict[str, Any]:
        """Son N günün performans özeti."""
        try:
            return get_analytics_summary(days=days)
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return {}

    def get_recent_topics(self, days: int = 14) -> list:
        """Son N günde kullanılan konular."""
        try:
            posts = get_published_posts(days=days)
            return [p.get("topic", "") for p in posts if p.get("topic")]
        except Exception:
            return []

    def get_best_hooks(self, limit: int = 5) -> list:
        """En iyi performans gösteren hook tipleri."""
        try:
            return get_best_performing_hooks(limit=limit)
        except Exception:
            return []

    def is_production_active(self) -> bool:
        """Aktif pipeline var mı?"""
        # 2 saatten eski active production'ları temizle
        now = datetime.utcnow()
        stale = [k for k, v in self._active_productions.items()
                 if (now - v).total_seconds() > 7200]
        for k in stale:
            del self._active_productions[k]

        return len(self._active_productions) > 0

    def register_production(self, pipeline_name: str):
        """Pipeline başladığında kaydet."""
        self._active_productions[pipeline_name] = datetime.utcnow()
        logger.info(f"Production started: {pipeline_name}")

    def complete_production(self, pipeline_name: str, content_type: str = None):
        """Pipeline tamamlandığında kaydet."""
        self._active_productions.pop(pipeline_name, None)
        if content_type:
            self._last_production_times[content_type] = datetime.utcnow()
        logger.info(f"Production completed: {pipeline_name}")

    def check_cooldown(self, content_type: str, min_hours: int = 4) -> bool:
        """Belirli bir içerik türü için cooldown kontrolü."""
        last = self._last_production_times.get(content_type)
        if not last:
            return True  # Hiç üretilmemiş, devam et

        elapsed = (datetime.utcnow() - last).total_seconds() / 3600
        return elapsed >= min_hours

    def get_hours_since_last_post(self) -> float:
        """Son paylaşımdan bu yana geçen saat."""
        try:
            posts = get_published_posts(days=7)
            if posts and posts[0].get("published_at"):
                pub = posts[0]["published_at"]
                if isinstance(pub, str):
                    pub = datetime.fromisoformat(pub.replace("Z", "+00:00")).replace(tzinfo=None)
                return (datetime.utcnow() - pub).total_seconds() / 3600
        except Exception:
            pass
        return 999  # Bilinmiyor, üretim yapılabilir

    def get_full_state(self) -> Dict[str, Any]:
        """Brain Agent için tam durum bilgisi."""
        now = get_kktc_now()
        return {
            "current_time": now.strftime("%Y-%m-%d %H:%M"),
            "day_of_week": now.strftime("%A"),
            "hour": now.hour,
            "is_paused": self._paused,
            "is_production_active": self.is_production_active(),
            "active_productions": list(self._active_productions.keys()),
            "hours_since_last_post": round(self.get_hours_since_last_post(), 1),
            "weekly_stats": self.get_weekly_stats(),
            "pool_status": self.get_pool_status(),
            "performance_7d": self.get_performance_summary(days=7),
            "recent_topics_14d": self.get_recent_topics(days=14),
        }
