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
    log_agent_action, get_best_performing_hooks,
    get_ab_test_learnings, get_connection
)

class OrchestratorAgent(BaseAgent):
    """Merkezi koordinatör - tüm süreci yönetir"""

    # Haftalık schedule template - Organik büyüme optimizasyonu
    # 7 Reels (58%) + 2 Carousel (17%) + 3 Post (25%) = 12 içerik
    # Reels ağırlıklı: Non-follower reach 3x daha yüksek
    WEEKLY_SCHEDULE = [
        # Pazartesi - Hafta başı momentum
        {"day": 0, "day_name": "monday", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 0, "day_name": "monday", "time": "19:00", "type": "post", "platform": "instagram"},
        # Salı - Yoğun gün
        {"day": 1, "day_name": "tuesday", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 1, "day_name": "tuesday", "time": "19:00", "type": "carousel", "platform": "instagram"},
        # Çarşamba - Orta hafta
        {"day": 2, "day_name": "wednesday", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 2, "day_name": "wednesday", "time": "19:00", "type": "post", "platform": "instagram"},
        # Perşembe - Etkileşim zirvesi
        {"day": 3, "day_name": "thursday", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 3, "day_name": "thursday", "time": "19:00", "type": "reels", "platform": "instagram"},
        # Cuma - Hafta sonu öncesi
        {"day": 4, "day_name": "friday", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 4, "day_name": "friday", "time": "19:00", "type": "post", "platform": "instagram"},
        # Cumartesi - Rahat izleme
        {"day": 5, "day_name": "saturday", "time": "14:00", "type": "carousel", "platform": "instagram"},
        # Pazar - Hafta özeti
        {"day": 6, "day_name": "sunday", "time": "14:00", "type": "reels", "platform": "instagram"},
    ]

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
        elif action == "optimize_non_follower_reach":
            return await self.optimize_non_follower_reach()
        elif action == "get_optimization_insights":
            return await self.get_optimization_insights()
        else:
            return {"error": f"Unknown action: {action}"}

    async def plan_week(self) -> Dict[str, Any]:
        """Haftalık içerik planı oluştur (12 içerik: 7 Reels + 2 Carousel + 3 Post)"""
        self.log("Haftalık plan oluşturuluyor (12 içerik, %58 Reels)...")

        # Mevcut stratejiyi al
        strategy = get_current_strategy()

        # Geçmiş performans verilerini al
        analytics = get_analytics_summary(days=30) or {}
        published_posts = get_published_posts(days=30) or []

        # Context dosyalarını yükle
        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")
        schedule_strategy = self.load_context("schedule-strategy.md")

        # Schedule template'ini JSON'a çevir
        schedule_json = json.dumps(self.WEEKLY_SCHEDULE, ensure_ascii=False, indent=2)

        prompt = f"""
## GÖREV: Haftalık İçerik Planı Oluştur

### Şirket Profili
{company_profile[:2000]}

### İçerik Stratejisi
{content_strategy[:2000]}

### Schedule Template (12 içerik/hafta)
{schedule_json}

### Mevcut Strateji
- Haftalık içerik: 12 (7 Reels + 2 Carousel + 3 Post = %58 Reels ağırlıklı)
- En iyi günler: {strategy.get('best_days', [])}
- En iyi saatler: {strategy.get('best_hours', [])}
- İçerik mix: {strategy.get('content_mix', {})}

### Son 30 Gün Performans
- Toplam post: {analytics.get('total_posts') or 0}
- Ortalama engagement: {(analytics.get('avg_engagement_rate') or 0):.2f}%

### Son Paylaşılan Konular (tekrar önlemek için)
{json.dumps([p.get('topic') for p in published_posts[:10]], ensure_ascii=False)}

---

Schedule template'indeki her slot için konu öner.
Her content type için uygun konular seç:
- **reels**: Kısa, dinamik, hook'lu (demo, teknik, problem-çözüm)
- **carousel**: Eğitici, adım adım, karşılaştırmalı
- **post**: Detaylı, bilgilendirici

ÇIKTI FORMATI (JSON):
```json
{{
  "week_plan": [
    {{
      "day": "monday",
      "day_of_week": 0,
      "time": "10:00",
      "content_type": "post",
      "platform": "instagram",
      "topic_category": "egitici",
      "topic": "Konu başlığı",
      "visual_type": "flux",
      "reasoning": "Neden bu konu?"
    }},
    {{
      "day": "monday",
      "day_of_week": 0,
      "time": "19:00",
      "content_type": "reels",
      "platform": "instagram",
      "topic_category": "tanitim",
      "topic": "Reels konusu",
      "visual_type": "video",
      "reasoning": "Neden bu konu?"
    }}
  ],
  "strategy_notes": "Genel notlar",
  "content_distribution": {{
    "reels": 7,
    "carousel": 2,
    "post": 3
  }}
}}
```

Tam 12 entry olmalı. Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=120)

        try:
            # JSON parse et
            result = json.loads(self._clean_json_response(response))

            # Takvime kaydet
            week_start = datetime.now() - timedelta(days=datetime.now().weekday())

            for entry in result.get("week_plan", []):
                content_type = entry.get("content_type", "post")
                # visual_type'ı content_type'a göre ayarla
                if content_type == "reels":
                    visual_type = "video"
                elif content_type == "carousel":
                    visual_type = "carousel"
                else:
                    visual_type = entry.get("visual_type", "flux")

                create_calendar_entry(
                    week_start=week_start.date(),
                    day_of_week=entry.get("day_of_week", 0),
                    scheduled_time=entry.get("time", "10:00"),
                    topic_category=entry.get("topic_category", "egitici"),
                    topic_suggestion=entry.get("topic", ""),
                    visual_type_suggestion=visual_type
                )

            # Log
            log_agent_action(
                agent_name=self.name,
                action="plan_week",
                input_data={"strategy": strategy},
                output_data=result,
                success=True
            )

            plan_count = len(result.get('week_plan', []))
            reels_count = sum(1 for e in result.get('week_plan', []) if e.get('content_type') == 'reels')
            carousel_count = sum(1 for e in result.get('week_plan', []) if e.get('content_type') == 'carousel')

            self.log(f"Haftalık plan: {plan_count} içerik ({reels_count} Reels, {carousel_count} Carousel)")
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
                # Best hooks'u da ekle (feedback loop için)
                best_hooks_data = get_best_performing_hooks(limit=5)
                best_hooks = [h['hook_type'] for h in best_hooks_data] if best_hooks_data else []
                result["updated_strategy"]["best_hooks"] = best_hooks

                new_version = update_strategy(**result["updated_strategy"])
                self.log(f"Strategy v{new_version} güncellendi, best_hooks: {best_hooks[:3]}")

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

    def _get_non_follower_reach_data(self) -> Dict[str, Any]:
        """Non-follower reach verilerini al"""
        conn = get_connection()
        cursor = conn.cursor()

        # Content type bazında non-follower reach analizi
        cursor.execute('''
            SELECT
                visual_type,
                COUNT(*) as post_count,
                AVG(ig_reach) as avg_reach,
                AVG(ig_reach_non_followers) as avg_non_follower_reach,
                AVG(CASE WHEN ig_reach > 0
                    THEN (ig_reach_non_followers * 100.0 / ig_reach)
                    ELSE 0 END) as avg_non_follower_pct,
                AVG(ig_engagement_rate) as avg_engagement,
                AVG(ig_saves) as avg_saves,
                AVG(ig_shares) as avg_shares
            FROM posts
            WHERE status = 'published'
              AND published_at > datetime('now', '-90 days')
              AND ig_reach > 0
            GROUP BY visual_type
            ORDER BY avg_non_follower_pct DESC
        ''')

        content_type_stats = []
        for row in cursor.fetchall():
            content_type_stats.append({
                'type': row['visual_type'],
                'count': row['post_count'],
                'avg_reach': round(row['avg_reach'] or 0, 0),
                'avg_non_follower_reach': round(row['avg_non_follower_reach'] or 0, 0),
                'non_follower_pct': round(row['avg_non_follower_pct'] or 0, 2),
                'avg_engagement': round(row['avg_engagement'] or 0, 2),
                'avg_saves': round(row['avg_saves'] or 0, 0),
                'avg_shares': round(row['avg_shares'] or 0, 0)
            })

        # Hook type bazında non-follower reach analizi
        cursor.execute('''
            SELECT
                hook_type,
                COUNT(*) as post_count,
                AVG(CASE WHEN ig_reach > 0
                    THEN (ig_reach_non_followers * 100.0 / ig_reach)
                    ELSE 0 END) as avg_non_follower_pct,
                AVG(ig_engagement_rate) as avg_engagement
            FROM posts
            WHERE status = 'published'
              AND published_at > datetime('now', '-90 days')
              AND ig_reach > 0
              AND hook_type IS NOT NULL
            GROUP BY hook_type
            HAVING post_count >= 2
            ORDER BY avg_non_follower_pct DESC
        ''')

        hook_stats = []
        for row in cursor.fetchall():
            hook_stats.append({
                'hook_type': row['hook_type'],
                'count': row['post_count'],
                'non_follower_pct': round(row['avg_non_follower_pct'] or 0, 2),
                'avg_engagement': round(row['avg_engagement'] or 0, 2)
            })

        # Posting time bazında analiz
        cursor.execute('''
            SELECT
                strftime('%H', published_at) as hour,
                COUNT(*) as post_count,
                AVG(CASE WHEN ig_reach > 0
                    THEN (ig_reach_non_followers * 100.0 / ig_reach)
                    ELSE 0 END) as avg_non_follower_pct
            FROM posts
            WHERE status = 'published'
              AND published_at > datetime('now', '-90 days')
              AND ig_reach > 0
            GROUP BY hour
            HAVING post_count >= 2
            ORDER BY avg_non_follower_pct DESC
        ''')

        time_stats = []
        for row in cursor.fetchall():
            time_stats.append({
                'hour': row['hour'],
                'count': row['post_count'],
                'non_follower_pct': round(row['avg_non_follower_pct'] or 0, 2)
            })

        conn.close()

        return {
            'content_types': content_type_stats,
            'hooks': hook_stats,
            'posting_times': time_stats
        }

    async def optimize_non_follower_reach(self) -> Dict[str, Any]:
        """Non-follower reach optimizasyonu için analiz ve öneriler"""
        self.log("Non-follower reach optimizasyonu analiz ediliyor...")

        # Veri topla
        reach_data = self._get_non_follower_reach_data()
        hook_performance = get_best_performing_hooks(limit=5)
        ab_learnings = get_ab_test_learnings()

        prompt = f"""
## GÖREV: Non-Follower Reach Optimizasyonu

### Instagram Algoritma Bilgisi
Non-follower reach için kritik faktörler:
1. İlk 30 dakikada yüksek engagement
2. Kaydetme (save) ve paylaşma (share) oranları
3. Reels için watch time ve tamamlama oranı
4. Explore page uygunluğu

### Mevcut Performance Verileri

**Content Type Bazında:**
{json.dumps(reach_data['content_types'], ensure_ascii=False, indent=2)}

**Hook Type Bazında:**
{json.dumps(reach_data['hooks'], ensure_ascii=False, indent=2)}

**Posting Time Bazında:**
{json.dumps(reach_data['posting_times'], ensure_ascii=False, indent=2)}

**En İyi Performans Gösteren Hook'lar:**
{json.dumps(hook_performance, ensure_ascii=False, indent=2)}

**A/B Test Öğrenimleri:**
{json.dumps(ab_learnings, ensure_ascii=False, indent=2)}

---

Bu verileri analiz et ve non-follower reach'i artırmak için öneriler sun.

ÇIKTI FORMATI (JSON):
```json
{{
  "analysis": {{
    "best_content_type": "video/carousel/flux",
    "best_hook_types": ["hook1", "hook2"],
    "best_posting_times": ["10:00", "19:00"],
    "current_non_follower_avg": 15.5,
    "top_performers_avg": 35.2
  }},
  "optimizations": [
    {{
      "area": "content_type",
      "current": "post ağırlıklı",
      "recommended": "Reels ağırlığını %40'a çıkar",
      "expected_impact": "+20% non-follower reach",
      "priority": "high"
    }},
    {{
      "area": "hooks",
      "current": "karışık hook kullanımı",
      "recommended": "Soru ve istatistik hook'larını önceliklendir",
      "expected_impact": "+15% engagement",
      "priority": "medium"
    }}
  ],
  "reels_strategy": {{
    "optimal_length": "15-30 saniye",
    "hook_timing": "İlk 3 saniyede hook",
    "recommended_hooks": ["question", "statistic", "before_after"],
    "cta_placement": "Son 3 saniye",
    "hashtag_strategy": "15-20 mixed (5 branded + 10 niche + 5 trending)"
  }},
  "weekly_mix_recommendation": {{
    "reels": 5,
    "carousel": 2,
    "post": 5,
    "reels_ratio_change": "+1 (önceki: 4)"
  }},
  "immediate_actions": [
    "Aksiyon 1",
    "Aksiyon 2"
  ]
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=120)

        try:
            result = json.loads(self._clean_json_response(response))

            # Sonuçları logla
            log_agent_action(
                agent_name=self.name,
                action="optimize_non_follower_reach",
                input_data={"reach_data_summary": {
                    "content_types_count": len(reach_data['content_types']),
                    "hooks_count": len(reach_data['hooks'])
                }},
                output_data=result,
                success=True
            )

            self.log(f"Non-follower reach optimizasyonu tamamlandı: {len(result.get('optimizations', []))} öneri")
            return result

        except json.JSONDecodeError:
            log_agent_action(
                agent_name=self.name,
                action="optimize_non_follower_reach",
                success=False,
                error_message="JSON parse error"
            )
            return {"error": "JSON parse error", "raw_response": response}

    async def get_optimization_insights(self) -> Dict[str, Any]:
        """Quick insights - AI çağrısı yapmadan mevcut datadan özetler"""
        self.log("Optimization insights toplanıyor...")

        reach_data = self._get_non_follower_reach_data()
        hook_performance = get_best_performing_hooks(limit=5)
        ab_learnings = get_ab_test_learnings()

        # En iyi content type
        best_content = max(reach_data['content_types'],
                          key=lambda x: x['non_follower_pct']) if reach_data['content_types'] else None

        # En iyi hook
        best_hook = max(reach_data['hooks'],
                       key=lambda x: x['non_follower_pct']) if reach_data['hooks'] else None

        # En iyi saat
        best_time = max(reach_data['posting_times'],
                       key=lambda x: x['non_follower_pct']) if reach_data['posting_times'] else None

        insights = {
            "summary": {
                "best_content_type": best_content['type'] if best_content else "N/A",
                "best_content_non_follower_pct": best_content['non_follower_pct'] if best_content else 0,
                "best_hook_type": best_hook['hook_type'] if best_hook else "N/A",
                "best_hook_non_follower_pct": best_hook['non_follower_pct'] if best_hook else 0,
                "best_posting_hour": f"{best_time['hour']}:00" if best_time else "N/A",
            },
            "top_hooks": [h['hook_type'] for h in hook_performance[:3]] if hook_performance else [],
            "ab_test_insights": {
                "total_tests": ab_learnings.get('total_tests', 0),
                "prediction_accuracy": ab_learnings.get('prediction_accuracy', 0),
                "top_winning_hooks": ab_learnings.get('top_hooks', [])
            },
            "recommendations": []
        }

        # Quick recommendations
        if best_content and best_content['type'] in ['video', 'reels']:
            insights['recommendations'].append(
                f"Reels/Video içerikleri %{best_content['non_follower_pct']:.1f} non-follower reach sağlıyor - artır"
            )

        if best_hook:
            insights['recommendations'].append(
                f"'{best_hook['hook_type']}' hook tipi en iyi performansı gösteriyor - önceliklendir"
            )

        if best_time:
            insights['recommendations'].append(
                f"{best_time['hour']}:00 en iyi non-follower reach saati - bu saatte Reels paylaş"
            )

        self.log(f"Insights hazır: {len(insights['recommendations'])} öneri")
        return insights
