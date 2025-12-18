"""
Orchestrator Agent - Merkezi koordinatör
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from .base_agent import BaseAgent
from app.database import (
    get_current_strategy, update_strategy,
    get_published_posts, get_analytics_summary,
    create_calendar_entry, get_week_calendar,
    log_agent_action
)

class OrchestratorAgent(BaseAgent):
    """Merkezi koordinatör - tüm süreci yönetir"""

    def __init__(self):
        super().__init__("orchestrator")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ana yürütme metodu"""
        action = input_data.get("action", "plan_week")

        if action == "plan_week":
            return await self.plan_week()
        elif action == "daily_check":
            return await self.daily_check()
        elif action == "update_strategy":
            return await self.analyze_and_update_strategy()
        else:
            return {"error": f"Unknown action: {action}"}

    async def plan_week(self) -> Dict[str, Any]:
        """Haftalık içerik planı oluştur"""
        self.log("Haftalık plan oluşturuluyor...")

        # Mevcut stratejiyi al
        strategy = get_current_strategy()

        # Geçmiş performans verilerini al
        analytics = get_analytics_summary(days=30) or {}
        published_posts = get_published_posts(days=30) or []

        # Context dosyalarını yükle
        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        prompt = f"""
## GÖREV: Haftalık İçerik Planı Oluştur

### Şirket Profili
{company_profile}

### İçerik Stratejisi
{content_strategy}

### Mevcut Strateji
- Haftalık post sayısı: {strategy.get('posts_per_week', 5)}
- En iyi günler: {strategy.get('best_days', [])}
- En iyi saatler: {strategy.get('best_hours', [])}
- İçerik mix: {strategy.get('content_mix', {})}
- Görsel mix: {strategy.get('visual_mix', {})}

### Son 30 Gün Performans
- Toplam post: {analytics.get('total_posts') or 0}
- Ortalama engagement: {(analytics.get('avg_engagement_rate') or 0):.2f}%
- Ortalama reach: {analytics.get('avg_reach') or 0}

### Son Paylaşılan Konular
{json.dumps([p.get('topic') for p in published_posts[:10]], ensure_ascii=False)}

---

Yukarıdaki bilgilere dayanarak bu hafta için içerik planı oluştur.

ÇIKTI FORMATI (JSON):
```json
{{
  "week_plan": [
    {{
      "day": "monday",
      "day_of_week": 0,
      "time": "10:00",
      "topic_category": "egitici",
      "topic": "Konu başlığı",
      "visual_type": "flux",
      "reasoning": "Neden bu konu ve bu gün?"
    }}
  ],
  "strategy_notes": "Genel strateji notları",
  "expected_performance": "Beklenen performans tahmini"
}}
```

Sadece JSON döndür, başka açıklama yapma.
"""

        response = await self.call_claude(prompt)

        try:
            # JSON parse et
            result = json.loads(self._clean_json_response(response))

            # Takvime kaydet
            week_start = datetime.now() - timedelta(days=datetime.now().weekday())

            for entry in result.get("week_plan", []):
                create_calendar_entry(
                    week_start=week_start.date(),
                    day_of_week=entry.get("day_of_week", 0),
                    scheduled_time=entry.get("time", "10:00"),
                    topic_category=entry.get("topic_category", "egitici"),
                    topic_suggestion=entry.get("topic", ""),
                    visual_type_suggestion=entry.get("visual_type", "flux")
                )

            # Log
            log_agent_action(
                agent_name=self.name,
                action="plan_week",
                input_data={"strategy": strategy},
                output_data=result,
                success=True
            )

            self.log(f"Haftalık plan oluşturuldu: {len(result.get('week_plan', []))} post planlandı")
            return result

        except json.JSONDecodeError:
            log_agent_action(
                agent_name=self.name,
                action="plan_week",
                success=False,
                error_message="JSON parse error"
            )
            return {"error": "JSON parse error", "raw_response": response}

    async def daily_check(self) -> Dict[str, Any]:
        """Günlük kontrol - bugün ne yapılacak?"""
        self.log("Günlük kontrol yapılıyor...")

        from app.database import get_todays_calendar

        today_entries = get_todays_calendar()

        if not today_entries:
            return {
                "status": "no_content_planned",
                "message": "Bugün için planlanmış içerik yok"
            }

        return {
            "status": "content_planned",
            "entries": today_entries,
            "count": len(today_entries)
        }

    async def analyze_and_update_strategy(self) -> Dict[str, Any]:
        """Performans verilerini analiz et ve stratejiyi güncelle"""
        self.log("Strateji analizi yapılıyor...")

        # Verileri topla
        analytics = get_analytics_summary(days=30)
        published_posts = get_published_posts(days=30)
        current_strategy = get_current_strategy()

        prompt = f"""
## GÖREV: Performans Analizi ve Strateji Güncelleme

### Mevcut Strateji
{json.dumps(current_strategy, ensure_ascii=False, indent=2)}

### Son 30 Gün Performans
{json.dumps(analytics, ensure_ascii=False, indent=2)}

### Son 30 Gün Postları
{json.dumps([{
    'topic': p.get('topic'),
    'visual_type': p.get('visual_type'),
    'published_at': str(p.get('published_at'))
} for p in published_posts], ensure_ascii=False, indent=2)}

---

Yukarıdaki verileri analiz et ve stratejiyi güncelle.

ÇIKTI FORMATI (JSON):
```json
{{
  "analysis": {{
    "best_performing_topics": ["konu1", "konu2"],
    "best_performing_visuals": ["tip1", "tip2"],
    "best_days": ["monday", "wednesday"],
    "best_hours": ["10:00", "14:00"],
    "insights": ["insight1", "insight2"]
  }},
  "updated_strategy": {{
    "posts_per_week": 5,
    "best_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "best_hours": ["10:00", "14:00", "18:00"],
    "content_mix": {{"egitici": 30, "tanitim": 25, "ipucu": 20, "haber": 15, "basari_hikayesi": 10}},
    "visual_mix": {{"flux": 35, "infographic": 30, "gemini": 25, "video": 10}}
  }},
  "recommendations": ["öneri1", "öneri2"]
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt)

        try:
            result = json.loads(self._clean_json_response(response))

            # Stratejiyi güncelle
            if "updated_strategy" in result:
                update_strategy(**result["updated_strategy"])

            log_agent_action(
                agent_name=self.name,
                action="update_strategy",
                input_data={"analytics": analytics},
                output_data=result,
                success=True
            )

            self.log("Strateji güncellendi")
            return result

        except json.JSONDecodeError:
            return {"error": "JSON parse error", "raw_response": response}
