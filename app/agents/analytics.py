"""
Analytics Agent - Performans takip
Metrikleri toplar ve analiz eder
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from .base_agent import BaseAgent
from app.database import (
    get_published_posts, get_analytics_summary,
    record_analytics, log_agent_action
)

class AnalyticsAgent(BaseAgent):
    """Performans takip - metrikleri analiz eder"""

    def __init__(self):
        super().__init__("analytics")

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ana yürütme metodu"""
        action = input_data.get("action", "daily_report")

        if action == "daily_report":
            return await self.generate_daily_report()
        elif action == "weekly_report":
            return await self.generate_weekly_report()
        elif action == "analyze_performance":
            return await self.analyze_performance()
        elif action == "fetch_metrics":
            return await self.fetch_metrics(input_data)
        else:
            return {"error": f"Unknown action: {action}"}

    async def generate_daily_report(self) -> Dict[str, Any]:
        """Günlük performans raporu"""
        self.log("Günlük rapor oluşturuluyor...")

        # Bugünün postlarını al
        today = datetime.now().date()
        posts = get_published_posts(days=1)

        # Özet metrikleri al
        summary = get_analytics_summary(days=1)

        report = {
            "date": str(today),
            "posts_published": len(posts),
            "total_views": summary.get("total_views", 0),
            "total_likes": summary.get("total_likes", 0),
            "total_comments": summary.get("total_comments", 0),
            "total_shares": summary.get("total_shares", 0),
            "avg_engagement_rate": summary.get("avg_engagement_rate", 0),
            "posts": [
                {
                    "topic": p.get("topic"),
                    "visual_type": p.get("visual_type"),
                    "published_at": str(p.get("published_at"))
                }
                for p in posts
            ]
        }

        log_agent_action(
            agent_name=self.name,
            action="daily_report",
            output_data=report,
            success=True
        )

        self.log(f"Günlük rapor: {len(posts)} post, {summary.get('total_likes', 0)} beğeni")
        return report

    async def generate_weekly_report(self) -> Dict[str, Any]:
        """Haftalık performans raporu"""
        self.log("Haftalık rapor oluşturuluyor...")

        posts = get_published_posts(days=7)
        summary = get_analytics_summary(days=7)

        # Önceki hafta ile karşılaştır
        prev_summary = get_analytics_summary(days=14)  # Son 14 gün

        report = {
            "week_start": str((datetime.now() - timedelta(days=7)).date()),
            "week_end": str(datetime.now().date()),
            "posts_published": len(posts),
            "metrics": {
                "total_views": summary.get("total_views", 0),
                "total_likes": summary.get("total_likes", 0),
                "total_comments": summary.get("total_comments", 0),
                "total_shares": summary.get("total_shares", 0),
                "avg_engagement_rate": summary.get("avg_engagement_rate", 0),
                "avg_reach": summary.get("avg_reach", 0)
            },
            "comparison": {
                "vs_previous_week": "improved" if summary.get("avg_engagement_rate", 0) > (prev_summary.get("avg_engagement_rate", 0) / 2) else "declined"
            },
            "top_performing_posts": [
                {
                    "topic": p.get("topic"),
                    "visual_type": p.get("visual_type")
                }
                for p in posts[:3]  # İlk 3
            ]
        }

        log_agent_action(
            agent_name=self.name,
            action="weekly_report",
            output_data=report,
            success=True
        )

        self.log(f"Haftalık rapor: {len(posts)} post")
        return report

    async def analyze_performance(self) -> Dict[str, Any]:
        """Performans analizi - stratejiye feedback"""
        self.log("Performans analizi yapılıyor...")

        posts = get_published_posts(days=30)
        summary = get_analytics_summary(days=30)

        if not posts:
            return {"status": "no_data", "message": "Analiz için yeterli veri yok"}

        # Kategorilere göre grupla
        category_performance = {}
        visual_performance = {}

        for post in posts:
            cat = post.get("topic_category", "unknown")
            vis = post.get("visual_type", "unknown")

            if cat not in category_performance:
                category_performance[cat] = {"count": 0}
            category_performance[cat]["count"] += 1

            if vis not in visual_performance:
                visual_performance[vis] = {"count": 0}
            visual_performance[vis]["count"] += 1

        prompt = f"""
## GÖREV: Performans Analizi

### Son 30 Gün Verileri
- Toplam post: {len(posts)}
- Toplam beğeni: {summary.get('total_likes', 0)}
- Toplam yorum: {summary.get('total_comments', 0)}
- Ortalama engagement: {summary.get('avg_engagement_rate', 0):.2f}%

### Kategori Dağılımı
{json.dumps(category_performance, ensure_ascii=False)}

### Görsel Tipi Dağılımı
{json.dumps(visual_performance, ensure_ascii=False)}

---

Bu verileri analiz et ve strateji önerileri sun.

ÇIKTI FORMATI (JSON):
```json
{{
  "insights": [
    "İçgörü 1",
    "İçgörü 2"
  ],
  "recommendations": [
    "Öneri 1",
    "Öneri 2"
  ],
  "best_performing": {{
    "category": "en iyi kategori",
    "visual_type": "en iyi görsel tipi"
  }},
  "areas_to_improve": ["Alan 1", "Alan 2"],
  "suggested_changes": {{
    "content_mix": {{}},
    "visual_mix": {{}},
    "posting_frequency": ""
  }}
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=90)

        try:
            result = json.loads(self._clean_json_response(response))

            log_agent_action(
                agent_name=self.name,
                action="analyze_performance",
                input_data={"post_count": len(posts)},
                output_data=result,
                success=True
            )

            self.log("Performans analizi tamamlandı")
            return result

        except json.JSONDecodeError:
            return {"error": "JSON parse error", "raw_response": response}

    async def fetch_metrics(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Facebook'tan metrikleri çek (TODO: Facebook Insights API)"""
        self.log("Metrikler çekiliyor...")

        post_id = input_data.get("post_id")
        facebook_post_id = input_data.get("facebook_post_id")

        # TODO: Facebook Insights API entegrasyonu
        # Şimdilik placeholder

        return {
            "status": "not_implemented",
            "message": "Facebook Insights API entegrasyonu yapılacak"
        }
