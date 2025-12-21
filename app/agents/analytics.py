"""
Analytics Agent - Performans takip
Metrikleri toplar, viral score hesaplar ve strateji önerileri sunar

Viral Score Formula:
- Save Rate x 2 (saves / reach)
- Share Rate x 3 (shares / reach)
- Engagement Rate x 1
- Non-follower Reach Bonus x 1.5

Higher viral score = More likely to go viral
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from .base_agent import BaseAgent
from app.database import (
    get_published_posts, get_analytics_summary,
    record_analytics, log_agent_action, update_post_analytics,
    get_connection
)
from app.insights_helper import get_instagram_insights, get_instagram_media_insights
from app.config import settings


def calculate_viral_score(
    reach: int,
    saves: int,
    shares: int,
    engagement_rate: float,
    non_follower_reach: int = 0
) -> Tuple[float, Dict[str, float]]:
    """
    Viral score hesapla.

    Formula:
    - Save Rate (saves/reach) x 2
    - Share Rate (shares/reach) x 3
    - Engagement Rate x 1
    - Non-follower Reach % x 1.5 (bonus)

    Returns:
        Tuple of (viral_score, breakdown_dict)
    """
    if reach <= 0:
        return 0.0, {"save_rate": 0, "share_rate": 0, "engagement": 0, "non_follower_bonus": 0}

    save_rate = (saves / reach) * 100
    share_rate = (shares / reach) * 100
    non_follower_pct = (non_follower_reach / reach) * 100 if non_follower_reach > 0 else 0

    breakdown = {
        "save_rate": round(save_rate, 2),
        "share_rate": round(share_rate, 2),
        "engagement": round(engagement_rate, 2),
        "non_follower_pct": round(non_follower_pct, 2),
        "non_follower_bonus": round(non_follower_pct * 0.015, 2)  # 1.5% weight
    }

    viral_score = (
        save_rate * 2 +
        share_rate * 3 +
        engagement_rate * 1 +
        non_follower_pct * 0.015
    )

    return round(viral_score, 2), breakdown


def get_viral_content_analysis(days: int = 30, min_viral_score: float = None) -> Dict[str, Any]:
    """
    Viral potansiyeli yüksek içerikleri analiz et.
    Uses settings.min_viral_score if not specified.

    Returns:
        Dict with viral posts, patterns, and recommendations
    """
    if min_viral_score is None:
        min_viral_score = settings.min_viral_score
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            id, topic, visual_type,
            ig_reach, ig_likes, ig_comments, ig_saves, ig_shares,
            ig_engagement_rate, ig_reach_non_followers,
            published_at
        FROM posts
        WHERE status = 'published'
          AND published_at > datetime('now', ? || ' days')
          AND ig_reach > 0
        ORDER BY ig_engagement_rate DESC
    ''', (f'-{days}',))

    viral_posts = []
    all_scores = []

    for row in cursor.fetchall():
        score, breakdown = calculate_viral_score(
            reach=row['ig_reach'],
            saves=row['ig_saves'] or 0,
            shares=row['ig_shares'] or 0,
            engagement_rate=row['ig_engagement_rate'] or 0,
            non_follower_reach=row['ig_reach_non_followers'] or 0
        )

        post_data = {
            'id': row['id'],
            'topic': row['topic'],
            'visual_type': row['visual_type'],
            'viral_score': score,
            'breakdown': breakdown,
            'reach': row['ig_reach'],
            'published_at': row['published_at']
        }

        all_scores.append(score)

        if score >= min_viral_score:
            viral_posts.append(post_data)

    conn.close()

    # Patterns analizi
    visual_type_scores = {}
    for post in viral_posts:
        vtype = post['visual_type'] or 'unknown'
        if vtype not in visual_type_scores:
            visual_type_scores[vtype] = []
        visual_type_scores[vtype].append(post['viral_score'])

    best_visual_type = None
    best_avg_score = 0
    for vtype, scores in visual_type_scores.items():
        avg = sum(scores) / len(scores) if scores else 0
        if avg > best_avg_score:
            best_avg_score = avg
            best_visual_type = vtype

    return {
        'total_analyzed': len(all_scores),
        'viral_posts_count': len(viral_posts),
        'viral_posts': viral_posts[:10],  # Top 10
        'avg_viral_score': round(sum(all_scores) / len(all_scores), 2) if all_scores else 0,
        'max_viral_score': max(all_scores) if all_scores else 0,
        'best_visual_type': best_visual_type,
        'patterns': {
            'visual_type_scores': {k: round(sum(v)/len(v), 2) for k, v in visual_type_scores.items() if v}
        }
    }


class AnalyticsAgent(BaseAgent):
    """Performans takip - metrikleri analiz eder ve viral potansiyeli ölçer"""

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
        elif action == "viral_analysis":
            return await self.analyze_viral_potential(input_data)
        elif action == "calculate_viral_score":
            return await self.get_post_viral_score(input_data)
        else:
            return {"error": f"Unknown action: {action}"}

    async def analyze_viral_potential(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Viral potansiyel analizi yap"""
        self.log("Viral potansiyel analizi yapılıyor...")

        days = input_data.get("days", 30)
        min_score = input_data.get("min_viral_score", 10.0)

        analysis = get_viral_content_analysis(days=days, min_viral_score=min_score)

        # AI ile pattern analizi
        if analysis['viral_posts']:
            prompt = f"""
## GÖREV: Viral İçerik Pattern Analizi

### Viral Postlar (score > {min_score})
{json.dumps(analysis['viral_posts'][:5], ensure_ascii=False, indent=2)}

### İstatistikler
- Toplam analiz edilen: {analysis['total_analyzed']}
- Viral post sayısı: {analysis['viral_posts_count']}
- Ortalama viral score: {analysis['avg_viral_score']}
- En iyi visual type: {analysis['best_visual_type']}

---

Bu verileri analiz et ve viral içerik patternleri çıkar.

ÇIKTI FORMATI (JSON):
```json
{{
  "patterns": [
    "Pattern 1: Açıklama",
    "Pattern 2: Açıklama"
  ],
  "recommendations": [
    "Viral içerik için öneri 1",
    "Viral içerik için öneri 2"
  ],
  "best_topics": ["Konu 1", "Konu 2"],
  "optimal_visual_type": "reels|flux|carousel",
  "hook_recommendations": [
    "Hook tipi önerisi 1",
    "Hook tipi önerisi 2"
  ]
}}
```

Sadece JSON döndür.
"""
            response = await self.call_claude(prompt, timeout=60)
            try:
                ai_analysis = json.loads(self._clean_json_response(response))
                analysis['ai_insights'] = ai_analysis
            except json.JSONDecodeError:
                analysis['ai_insights'] = {"error": "AI analizi başarısız"}

        log_agent_action(
            agent_name=self.name,
            action="viral_analysis",
            input_data={"days": days, "min_score": min_score},
            output_data={"viral_count": analysis['viral_posts_count']},
            success=True
        )

        self.log(f"Viral analiz tamamlandı: {analysis['viral_posts_count']} viral post bulundu")
        return analysis

    async def get_post_viral_score(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tek bir post için viral score hesapla"""
        post_id = input_data.get("post_id")

        if not post_id:
            return {"error": "post_id gerekli"}

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ig_reach, ig_saves, ig_shares, ig_engagement_rate, ig_reach_non_followers
            FROM posts WHERE id = ?
        ''', (post_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"error": f"Post {post_id} bulunamadı"}

        score, breakdown = calculate_viral_score(
            reach=row['ig_reach'] or 0,
            saves=row['ig_saves'] or 0,
            shares=row['ig_shares'] or 0,
            engagement_rate=row['ig_engagement_rate'] or 0,
            non_follower_reach=row['ig_reach_non_followers'] or 0
        )

        return {
            "post_id": post_id,
            "viral_score": score,
            "breakdown": breakdown,
            "is_viral": score >= settings.min_viral_score,
            "potential": "high" if score >= settings.min_viral_score * 1.5 else "medium" if score >= settings.min_viral_score * 0.8 else "low"
        }

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
        """Instagram'dan metrikleri çek"""
        self.log("Metrikler çekiliyor...")

        post_id = input_data.get("post_id")
        instagram_post_id = input_data.get("instagram_post_id")

        result = {"success": True, "instagram": None}
        analytics_data = {}

        try:
            # Instagram metrikleri
            if instagram_post_id:
                self.log(f"Instagram metrikleri çekiliyor: {instagram_post_id}")
                ig_insights = await get_instagram_media_insights(instagram_post_id)
                if ig_insights.get("success"):
                    result["instagram"] = ig_insights
                    is_reels = ig_insights.get("media_type") in ["REELS", "VIDEO"]

                    # Temel metrikler
                    analytics_data.update({
                        "ig_reach": ig_insights.get("reach", 0),
                        "ig_likes": ig_insights.get("likes", 0),
                        "ig_comments": ig_insights.get("comments", 0),
                        "ig_engagement_rate": ig_insights.get("engagement_rate", 0),
                        "ig_saves": ig_insights.get("saves", 0),
                        "ig_shares": ig_insights.get("shares", 0)
                    })

                    # Reels-specific metrikler
                    if is_reels:
                        analytics_data.update({
                            "ig_plays": ig_insights.get("plays", 0),
                            "ig_avg_watch_time": ig_insights.get("avg_watch_time_seconds", 0),
                            "ig_total_watch_time": ig_insights.get("total_watch_time_seconds", 0),
                            "ig_reach_followers": ig_insights.get("reach_followers", 0),
                            "ig_reach_non_followers": ig_insights.get("reach_non_followers", 0)
                        })
                        self.log(f"Instagram Reels: plays={ig_insights.get('plays')}, reach={ig_insights.get('reach')}, avg_watch={ig_insights.get('avg_watch_time_seconds')}s")
                    else:
                        self.log(f"Instagram Image: reach={ig_insights.get('reach')}, likes={ig_insights.get('likes')}")

            # DB'ye kaydet
            if post_id and analytics_data:
                update_post_analytics(post_id, analytics_data)
                self.log(f"Post {post_id} metrikleri DB'ye kaydedildi")

            log_agent_action(
                agent_name=self.name,
                action="fetch_metrics",
                input_data={"post_id": post_id, "ig_id": instagram_post_id},
                output_data=analytics_data,
                success=True
            )

            return result

        except Exception as e:
            self.log(f"Metrik çekme hatası: {e}")
            log_agent_action(
                agent_name=self.name,
                action="fetch_metrics",
                input_data=input_data,
                output_data={"error": str(e)},
                success=False
            )
            return {"success": False, "error": str(e)}
