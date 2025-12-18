"""
Scheduler - Zamanlanmış görevler
Full Autonomous Mode - Plana göre saatlerde paylaşım
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, List
import json

def get_kktc_now():
    """KKTC saatini al (UTC+2)"""
    return datetime.utcnow() + timedelta(hours=2)


class ScheduledTask:
    """Zamanlanmış görev"""
    
    def __init__(
        self,
        name: str,
        callback: Callable,
        hour: int = None,
        minute: int = 0,
        days: List[str] = None,
        interval_minutes: int = None
    ):
        self.name = name
        self.callback = callback
        self.hour = hour
        self.minute = minute
        self.days = days or ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        self.interval_minutes = interval_minutes
        self.last_run = None
        self.enabled = True
    
    def should_run(self) -> bool:
        """Şimdi çalışmalı mı?"""
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
    """Ana scheduler - Plana göre içerik paylaşımı"""
    
    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self.running = False
        self.pipeline = None
        self.last_calendar_check = None
    
    def add_task(self, task: ScheduledTask):
        """Görev ekle"""
        self.tasks.append(task)
        print(f"[SCHEDULER] Task added: {task.name}")
    
    def set_pipeline(self, pipeline):
        """Pipeline referansı ayarla"""
        self.pipeline = pipeline
    
    async def check_calendar_and_publish(self):
        """Content calendar'ı kontrol et ve zamanı gelen içeriği paylaş"""
        from app.database import get_todays_calendar, update_calendar_status
        
        now = get_kktc_now()
        current_day = now.weekday()  # 0=Monday, 6=Sunday
        
        # Bugünün planlarını al
        todays_plans = get_todays_calendar(current_day)
        
        for plan in todays_plans:
            plan_time = plan.get('scheduled_time', '')
            plan_status = plan.get('status', '')
            plan_id = plan.get('id')
            
            # Zaten yayınlandıysa atla
            if plan_status == 'published':
                continue
            
            # Saat kontrolü (±5 dakika tolerans)
            if plan_time:
                try:
                    plan_hour, plan_min = map(int, str(plan_time).split(':')[:2])
                    now_minutes = now.hour * 60 + now.minute
                    plan_minutes = plan_hour * 60 + plan_min
                    
                    # ±5 dakika içindeyse paylaş
                    if abs(now_minutes - plan_minutes) <= 5:
                        print(f"[SCHEDULER] 📅 Planlı içerik zamanı geldi: {plan_time}")
                        print(f"[SCHEDULER] Konu: {plan.get('topic_suggestion', 'N/A')}")
                        
                        # Otonom içerik üret ve paylaş
                        if self.pipeline:
                            result = await self.pipeline.run_autonomous_content_with_plan(plan)
                            
                            if result.get('success'):
                                update_calendar_status(plan_id, 'published', result.get('post_id'))
                                print(f"[SCHEDULER] ✅ Planlı içerik paylaşıldı!")
                            else:
                                print(f"[SCHEDULER] ❌ Paylaşım hatası: {result.get('error')}")
                except Exception as e:
                    print(f"[SCHEDULER] Time parse error: {e}")
    
    async def check_and_run(self):
        """Görevleri ve takvimi kontrol et"""
        # Standart görevleri kontrol et
        for task in self.tasks:
            if task.should_run():
                print(f"[SCHEDULER] Running task: {task.name}")
                await task.run()
        
        # Her 5 dakikada bir content calendar kontrol et
        now = get_kktc_now()
        if not self.last_calendar_check or (now - self.last_calendar_check).total_seconds() >= 300:
            await self.check_calendar_and_publish()
            self.last_calendar_check = now
    
    async def start(self, check_interval: int = 60):
        """Scheduler'ı başlat"""
        now = get_kktc_now()
        print(f"[SCHEDULER] Starting... (check every {check_interval}s)")
        print(f"[SCHEDULER] Mode: FULL-AUTONOMOUS")
        print(f"[SCHEDULER] KKTC Time (UTC+2): {now.strftime('%Y-%m-%d %H:%M:%S')}")
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
            "mode": "FULL-AUTONOMOUS",
            "kktc_time": get_kktc_now().strftime("%Y-%m-%d %H:%M:%S"),
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


def create_default_scheduler(pipeline) -> ContentScheduler:
    """Varsayılan scheduler'ı oluştur"""
    scheduler = ContentScheduler()
    scheduler.set_pipeline(pipeline)
    
    # Haftalık planlama (Pazartesi 08:00 KKTC)
    async def weekly_planning():
        from app.agents import OrchestratorAgent
        orchestrator = OrchestratorAgent()
        result = await orchestrator.execute({"action": "plan_week"})
        
        if pipeline and hasattr(pipeline, 'notify_telegram'):
            plan_count = len(result.get('week_plan', []))
            await pipeline.notify_telegram(
                f"📅 Haftalık Plan Oluşturuldu!\n\n"
                f"Bu hafta {plan_count} içerik planlandı.\n"
                f"Detaylar için /start yazın.",
                {},
                []
            )
        return result
    
    scheduler.add_task(ScheduledTask(
        name="weekly_planning",
        callback=weekly_planning,
        hour=8,
        minute=0,
        days=["monday"]
    ))
    
    # Günlük analytics raporu (20:00 KKTC)
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
    
    # Haftalık strateji güncelleme (Pazar 21:00 KKTC)
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
