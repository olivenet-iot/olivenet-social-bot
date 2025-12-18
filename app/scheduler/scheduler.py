"""
Scheduler - Zamanlanmış görevler
KKTC timezone (Europe/Istanbul - UTC+3) kullanır
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Callable, List
import json

# KKTC timezone (UTC+3 - Europe/Istanbul ile aynı)
KKTC_TIMEZONE = timezone(timedelta(hours=3))


def get_kktc_now() -> datetime:
    """KKTC saatini döndür (UTC+3)"""
    return datetime.now(KKTC_TIMEZONE)

class ScheduledTask:
    """Zamanlanmış görev"""

    def __init__(
        self,
        name: str,
        callback: Callable,
        hour: int = None,
        minute: int = 0,
        days: List[str] = None,  # ["monday", "tuesday", ...]
        interval_minutes: int = None  # Alternatif: her X dakikada bir
    ):
        self.name = name
        self.callback = callback
        self.hour = hour
        self.minute = minute
        self.days = days or ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        self.interval_minutes = interval_minutes
        self.last_run = None
        self.next_run = None
        self.enabled = True

    def should_run(self) -> bool:
        """Şimdi çalışmalı mı? (KKTC saati kullanır)"""
        if not self.enabled:
            return False

        now = get_kktc_now()

        # Interval bazlı
        if self.interval_minutes:
            if not self.last_run:
                return True
            elapsed = (now - self.last_run).total_seconds() / 60
            return elapsed >= self.interval_minutes

        # Saat bazlı
        if self.hour is not None:
            day_name = now.strftime("%A").lower()
            if day_name not in self.days:
                return False

            if now.hour == self.hour and now.minute == self.minute:
                # Bugün zaten çalıştı mı?
                if self.last_run and self.last_run.date() == now.date():
                    return False
                return True

        return False

    async def run(self):
        """Görevi çalıştır"""
        self.last_run = get_kktc_now()
        try:
            if asyncio.iscoroutinefunction(self.callback):
                return await self.callback()
            else:
                return self.callback()
        except Exception as e:
            print(f"[SCHEDULER] Task '{self.name}' error: {e}")
            return {"error": str(e)}


class ContentScheduler:
    """Ana scheduler - tüm görevleri yönetir"""

    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self.running = False
        self.pipeline = None

    def add_task(self, task: ScheduledTask):
        """Görev ekle"""
        self.tasks.append(task)
        print(f"[SCHEDULER] Task added: {task.name}")

    def remove_task(self, name: str):
        """Görev kaldır"""
        self.tasks = [t for t in self.tasks if t.name != name]

    def set_pipeline(self, pipeline):
        """Pipeline referansı ayarla"""
        self.pipeline = pipeline

    async def check_and_run(self):
        """Görevleri kontrol et ve çalıştır"""
        for task in self.tasks:
            if task.should_run():
                print(f"[SCHEDULER] Running task: {task.name}")
                await task.run()

    async def start(self, check_interval: int = 60):
        """Scheduler'ı başlat"""
        kktc_time = get_kktc_now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[SCHEDULER] Starting... (check every {check_interval}s)")
        print(f"[SCHEDULER] KKTC Time (UTC+3): {kktc_time}")
        self.running = True

        while self.running:
            await self.check_and_run()
            await asyncio.sleep(check_interval)

    def stop(self):
        """Scheduler'ı durdur"""
        print("[SCHEDULER] Stopping...")
        self.running = False

    def get_status(self) -> Dict[str, Any]:
        """Durum bilgisi"""
        return {
            "running": self.running,
            "tasks": [
                {
                    "name": t.name,
                    "enabled": t.enabled,
                    "last_run": str(t.last_run) if t.last_run else None,
                    "hour": t.hour,
                    "minute": t.minute,
                    "days": t.days
                }
                for t in self.tasks
            ]
        }


def create_default_scheduler(pipeline, autonomous: bool = False) -> ContentScheduler:
    """
    Varsayılan scheduler'ı oluştur

    Args:
        pipeline: ContentPipeline instance
        autonomous: True = Tam otonom (onay beklemez), False = Semi-autonomous (onay bekler)
    """
    scheduler = ContentScheduler()
    scheduler.set_pipeline(pipeline)

    # Mod seçimi
    if autonomous:
        content_callback = lambda: pipeline.run_autonomous_content(min_score=7)
        mode_text = "OTONOM"
    else:
        content_callback = lambda: pipeline.run_daily_content()
        mode_text = "SEMI-AUTONOMOUS"

    print(f"[SCHEDULER] Mode: {mode_text}")

    # Sabah günlük içerik kontrolü (09:00)
    scheduler.add_task(ScheduledTask(
        name="daily_content_check",
        callback=content_callback,
        hour=9,
        minute=0,
        days=["monday", "tuesday", "wednesday", "thursday", "friday"]
    ))

    # Haftalık planlama (Pazartesi 08:00)
    async def weekly_planning():
        from app.agents import OrchestratorAgent
        orchestrator = OrchestratorAgent()
        return await orchestrator.execute({"action": "plan_week"})

    scheduler.add_task(ScheduledTask(
        name="weekly_planning",
        callback=weekly_planning,
        hour=8,
        minute=0,
        days=["monday"]
    ))

    # Günlük analytics raporu (20:00)
    async def daily_analytics():
        from app.agents import AnalyticsAgent
        analytics = AnalyticsAgent()
        return await analytics.execute({"action": "daily_report"})

    scheduler.add_task(ScheduledTask(
        name="daily_analytics",
        callback=daily_analytics,
        hour=20,
        minute=0
    ))

    # Haftalık strateji güncelleme (Pazar 21:00)
    async def strategy_update():
        from app.agents import OrchestratorAgent
        orchestrator = OrchestratorAgent()
        return await orchestrator.execute({"action": "update_strategy"})

    scheduler.add_task(ScheduledTask(
        name="weekly_strategy_update",
        callback=strategy_update,
        hour=21,
        minute=0,
        days=["sunday"]
    ))

    return scheduler
