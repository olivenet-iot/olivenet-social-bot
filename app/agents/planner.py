"""
Planner Agent - İçerik planlayıcı
Konu seçimi, zamanlama ve içerik mix'i yönetir

Performance-aware topic selection:
- En iyi performans gösteren konuları önceliklendirir
- Hook type performance tracking
- Trend context entegrasyonu
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent
from app.database import (
    get_current_strategy, get_published_posts,
    log_agent_action, get_connection, get_strategy_version,
    get_best_performing_hooks, get_hook_recommendations
)


def get_top_performing_topics(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Son 90 günün en iyi performans gösteren konularını getir.
    Engagement rate, save rate ve share rate'e göre sıralar.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            topic,
            visual_type,
            ig_reach,
            ig_likes,
            ig_comments,
            ig_saves,
            ig_shares,
            ig_engagement_rate,
            ig_reach_non_followers,
            published_at
        FROM posts
        WHERE status = 'published'
          AND published_at > datetime('now', '-90 days')
          AND ig_reach > 0
        ORDER BY ig_engagement_rate DESC
        LIMIT ?
    ''', (limit,))

    results = []
    for row in cursor.fetchall():
        # Calculate viral score: saves + shares weighted higher
        save_rate = (row['ig_saves'] / row['ig_reach'] * 100) if row['ig_reach'] else 0
        share_rate = (row['ig_shares'] / row['ig_reach'] * 100) if row['ig_reach'] else 0
        non_follower_rate = (row['ig_reach_non_followers'] / row['ig_reach'] * 100) if row['ig_reach'] else 0

        results.append({
            'topic': row['topic'],
            'visual_type': row['visual_type'],
            'engagement_rate': row['ig_engagement_rate'],
            'save_rate': round(save_rate, 2),
            'share_rate': round(share_rate, 2),
            'non_follower_reach_pct': round(non_follower_rate, 2),
            'reach': row['ig_reach'],
            'viral_score': round(save_rate * 2 + share_rate * 3 + row['ig_engagement_rate'], 2)
        })

    conn.close()
    return results


def get_underperforming_topics(limit: int = 5) -> List[str]:
    """Son 90 günde düşük performans gösteren konuları getir."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT topic
        FROM posts
        WHERE status = 'published'
          AND published_at > datetime('now', '-90 days')
          AND ig_engagement_rate < 3
          AND ig_reach > 0
        ORDER BY ig_engagement_rate ASC
        LIMIT ?
    ''', (limit,))

    results = [row['topic'] for row in cursor.fetchall()]
    conn.close()
    return results


def get_hook_performance_summary() -> Dict[str, Any]:
    """Hook type'ların performansını özetle - Gerçek verilerden."""
    try:
        # Database'den en iyi hook'ları al
        best_hooks = get_best_performing_hooks(limit=5)

        if not best_hooks:
            return {
                "best_performing": "question",
                "top_hooks": ["question", "statistic", "problem"],
                "avoid": [],
                "note": "Henüz yeterli veri yok, default öneriler kullanılıyor"
            }

        # En iyi performans gösteren hook'ları listele
        top_hooks = [h['hook_type'] for h in best_hooks]

        # En düşük performans gösterenler için underperforming query
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT hook_type
            FROM hook_performance
            WHERE usage_count >= 3 AND viral_score < 5
            ORDER BY viral_score ASC
            LIMIT 3
        ''')
        avoid_hooks = [row['hook_type'] for row in cursor.fetchall()]
        conn.close()

        return {
            "best_performing": top_hooks[0] if top_hooks else "question",
            "top_hooks": top_hooks,
            "avoid": avoid_hooks,
            "data_based": True
        }

    except Exception as e:
        return {
            "best_performing": "question",
            "top_hooks": ["question", "statistic", "problem"],
            "avoid": [],
            "note": f"Hook data error: {str(e)}"
        }


class PlannerAgent(BaseAgent):
    """İçerik planlayıcı - konu ve zamanlama belirler"""

    def __init__(self):
        super().__init__("planner")
        self.performance_context_enabled = True
        # Strategy caching for feedback loop
        self._cached_strategy = None
        self._cached_strategy_version = 0

    def _get_strategy_with_cache(self) -> Dict[str, Any]:
        """
        Strategy'yi cache'den veya database'den al.
        Version değişmişse otomatik refresh yapar (feedback loop).
        """
        current_version = get_strategy_version()

        if self._cached_strategy is None or current_version != self._cached_strategy_version:
            if self._cached_strategy_version > 0:
                self.log(f"Strategy güncellendi (v{self._cached_strategy_version} → v{current_version}), refreshing...")
            self._cached_strategy = get_current_strategy()
            self._cached_strategy_version = current_version

        return self._cached_strategy

    def refresh_strategy(self) -> Dict[str, Any]:
        """
        Strategy'yi zorla yenile (Orchestrator update sonrası çağrılır).
        Feedback loop için kritik.
        """
        self._cached_strategy = None
        self._cached_strategy_version = 0
        strategy = self._get_strategy_with_cache()
        self.log(f"Strategy refreshed: v{self._cached_strategy_version}")
        return strategy

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Ana yürütme metodu"""
        action = input_data.get("action", "suggest_topic")

        if action == "suggest_topic":
            return await self.suggest_topic(input_data)
        elif action == "suggest_week_topics":
            return await self.suggest_week_topics()
        elif action == "analyze_trends":
            return await self.analyze_trends()
        else:
            return {"error": f"Unknown action: {action}"}

    def _get_performance_context(self) -> str:
        """Performance data'yı prompt context'i olarak formatla"""
        if not self.performance_context_enabled:
            return ""

        try:
            top_topics = get_top_performing_topics(limit=10)
            underperforming = get_underperforming_topics(limit=5)
            hook_summary = get_hook_performance_summary()

            if not top_topics:
                return "\n### Performance Data\nHenüz yeterli veri yok.\n"

            context = "\n### PERFORMANCE DATA (BUNU DİKKATE AL!)\n\n"
            context += "**En İyi Performans Gösteren Konular (son 90 gün):**\n"

            for i, topic in enumerate(top_topics[:5], 1):
                context += f"{i}. **{topic['topic']}**\n"
                context += f"   - Engagement: {topic['engagement_rate']}%\n"
                context += f"   - Save Rate: {topic['save_rate']}%\n"
                context += f"   - Non-follower reach: {topic['non_follower_reach_pct']}%\n"
                context += f"   - Viral Score: {topic['viral_score']}\n"

            if underperforming:
                context += "\n**Kaçınılması Gereken Konular (düşük performans):**\n"
                for topic in underperforming:
                    context += f"- {topic}\n"

            context += f"\n**Hook Önerisi:** {hook_summary.get('best_performing', 'question')} tipi hook'lar daha iyi performans gösteriyor.\n"

            return context

        except Exception as e:
            self.log(f"Performance context hatası: {e}", level="warning")
            return ""

    def _get_trend_context(self) -> str:
        """Weekly trends context'ini yükle"""
        try:
            trends = self.load_context("weekly-trends.md")
            if trends:
                return f"\n### GÜNCEL TRENDLER\n{trends[:2000]}\n"
            return ""
        except Exception:
            return ""

    async def suggest_topic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tek bir konu öner - Performance-aware"""
        self.log("Konu önerisi oluşturuluyor...")

        # Parametreler
        category = input_data.get("category")  # Belirli kategori istendi mi?
        exclude_topics = input_data.get("exclude", [])  # Hariç tutulacak konular

        # Context yükle
        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")
        topics_pool = self.load_context("topics.md")
        strategy = self._get_strategy_with_cache()  # Feedback loop: cache'li version kullan

        # Performance ve trend context
        performance_context = self._get_performance_context()
        trend_context = self._get_trend_context()

        # Son postları al (tekrar önleme)
        recent_posts = get_published_posts(days=14)
        recent_topics = [p.get('topic', '') for p in recent_posts]

        # Bugünün bilgisi
        today = datetime.now()
        day_name = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"][today.weekday()]
        month_name = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                      "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"][today.month - 1]

        prompt = f"""
## GÖREV: İçerik Konusu Öner

### Şirket Profili
{company_profile}

### Konu Havuzu (BU HAVUZDAN SEÇ!)
{topics_pool}

### İçerik Stratejisi
{content_strategy}
{performance_context}
{trend_context}

### Mevcut Strateji
- İçerik mix: {strategy.get('content_mix', {})}
- Görsel mix: {strategy.get('visual_mix', {})}

### Bugün
- Tarih: {today.strftime('%d %B %Y')}
- Gün: {day_name}
- Ay: {month_name}

### Son 14 Günde Paylaşılan Konular (TEKRAR ETME!)
{json.dumps(recent_topics, ensure_ascii=False)}

### Hariç Tutulacak Konular
{json.dumps(exclude_topics, ensure_ascii=False)}

{"### İstenen Kategori: " + category if category else ""}

---

Yukarıdaki bilgilere dayanarak bugün için EN UYGUN tek bir konu öner.

**ÖNCELİKLER:**
1. Performance data'daki başarılı konulara benzer konuları tercih et
2. Trend context'teki güncel konuları değerlendir
3. Düşük performanslı konulardan kaçın
4. Mevsimselliği düşün (Kış: Enerji, Yaz: Su/Sulama)
5. **NON-FOLLOWER REACH OPTİMİZASYONU:** Takipçi olmayanlar tarafından keşfedilebilir konular seç

**DISCOVERY-FOCUSED İÇERİK (Non-Follower Reach Artışı İçin):**
- Reels için: Genel IoT/teknoloji trendleri, problem-çözüm formatı, "X'in Y'si" karşılaştırmaları
- Hashtag stratejisi: Niche (#SmartFarming) + Broad (#Technology) mix
- Hook: Merak uyandıran sorular veya şok istatistikler
- Konu: Endüstri genelinde ilgi çekici, spesifik değil evrensel problemler

ÇIKTI FORMATI (JSON):
```json
{{
  "topic": "Konu başlığı (Türkçe)",
  "category": "egitici|tanitim|ipucu|haber|basari_hikayesi",
  "description": "Kısa açıklama",
  "reasoning": "Neden bu konu ve neden bugün? (performance data referansı ver)",
  "suggested_visual": "flux|infographic|gemini|video",
  "suggested_hook_type": "question|statistic|bold_claim|problem|value|fear|before_after|list|comparison|local",
  "suggested_hooks": [
    "Hook önerisi 1",
    "Hook önerisi 2",
    "Hook önerisi 3"
  ],
  "hashtags": ["#hashtag1", "#hashtag2"],
  "discovery_hashtags": ["#broad_hashtag1", "#trend_hashtag2"],
  "best_time": "HH:MM",
  "urgency": "high|medium|low",
  "expected_engagement": "low|medium|high",
  "discovery_potential": "low|medium|high",
  "performance_based": true
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=90)

        try:
            # call_claude zaten _clean_json_response çağırıyor, tekrar çağırmaya gerek yok
            result = json.loads(response)

            log_agent_action(
                agent_name=self.name,
                action="suggest_topic",
                input_data={"category": category, "exclude": exclude_topics},
                output_data=result,
                success=True
            )

            self.log(f"Konu önerildi: {result.get('topic', 'N/A')}")
            return result

        except json.JSONDecodeError as e:
            # Debug: Raw response'u logla
            self.log(f"JSON parse error: {str(e)}", level="error")
            self.log(f"Raw response (first 500 chars): {response[:500]}", level="error")

            # Son şans: Belki hala code block var, tekrar temizle
            cleaned = self._clean_json_response(response)
            try:
                result = json.loads(cleaned)
                self.log("JSON recovered after second cleaning")
                return result
            except json.JSONDecodeError:
                pass

            log_agent_action(
                agent_name=self.name,
                action="suggest_topic",
                success=False,
                error_message=f"JSON parse error: {str(e)}"
            )
            return {"error": "JSON parse error", "raw_response": response[:1000], "parse_error": str(e)}

    async def suggest_week_topics(self) -> Dict[str, Any]:
        """Haftalık konu planı oluştur"""
        self.log("Haftalık konu planı oluşturuluyor...")

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")
        topics_pool = self.load_context("topics.md")
        schedule_strategy = self.load_context("schedule-strategy.md")
        strategy = self._get_strategy_with_cache()  # Feedback loop: cache'li version kullan

        posts_per_week = strategy.get('posts_per_week', 5)
        best_days = strategy.get('best_days', ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])
        best_hours = strategy.get('best_hours', ['10:00', '14:00', '18:00'])
        content_mix = strategy.get('content_mix', {})

        recent_posts = get_published_posts(days=30)
        recent_topics = [p.get('topic', '') for p in recent_posts]

        prompt = f"""
## GÖREV: Haftalık İçerik Planı Oluştur

### Şirket Profili
{company_profile}

### Konu Havuzu (BU HAVUZDAN SEÇ!)
{topics_pool}

### Zamanlama Stratejisi
{schedule_strategy}

### İçerik Stratejisi
{content_strategy}

### Son 30 Günde Paylaşılan Konular (TEKRAR ETME!)
{json.dumps(recent_topics, ensure_ascii=False)}

---

## KRİTİK KURALLAR:
1. Haftada 12 içerik: 9 post + 3 reels
2. Reels günleri: Salı 19:00, Perşembe 19:00, Cumartesi 14:00
3. Facebook: Sadece Pzt/Çar/Cuma 10:00 (platform: "both")
4. Her içerik FARKLI kategoriden olmalı
5. Konu havuzundaki kategorilerden dengeli seç

ÇIKTI FORMATI (JSON):
```json
{{
  "week_topics": [
    {{
      "day": "monday",
      "day_of_week": 0,
      "time": "10:00",
      "topic": "Konu başlığı",
      "category": "Tarım & Sera",
      "content_type": "post",
      "platform": "both",
      "visual_type": "flux",
      "brief": "Kısa açıklama"
    }},
    {{
      "day": "tuesday",
      "day_of_week": 1,
      "time": "19:00",
      "topic": "Reels konusu",
      "category": "LoRaWAN",
      "content_type": "reels",
      "platform": "instagram",
      "visual_type": "reels",
      "brief": "Reels açıklama"
    }}
  ],
  "summary": {{
    "total": 12,
    "posts": 9,
    "reels": 3,
    "facebook": 3
  }},
  "notes": "Plan hakkında notlar"
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=120)

        try:
            result = json.loads(response)

            log_agent_action(
                agent_name=self.name,
                action="suggest_week_topics",
                output_data=result,
                success=True
            )

            self.log(f"Haftalık plan oluşturuldu: {len(result.get('week_topics', []))} konu")
            return result

        except json.JSONDecodeError as e:
            self.log(f"JSON parse error (week_topics): {str(e)}", level="error")
            self.log(f"Raw response (first 500 chars): {response[:500]}", level="error")

            # Son şans: tekrar temizle
            cleaned = self._clean_json_response(response)
            try:
                result = json.loads(cleaned)
                self.log("JSON recovered after second cleaning")
                return result
            except json.JSONDecodeError:
                pass

            return {"error": "JSON parse error", "raw_response": response[:1000], "parse_error": str(e)}

    async def analyze_trends(self) -> Dict[str, Any]:
        """Sektör trendlerini analiz et"""
        self.log("Trend analizi yapılıyor...")

        company_profile = self.load_context("company-profile.md")

        prompt = f"""
## GÖREV: Sektör Trend Analizi

### Şirket Profili
{company_profile}

---

Bu şirketin sektöründeki güncel trendleri analiz et.
Sosyal medya içeriğine dönüştürülebilecek konuları belirle.

ÇIKTI FORMATI (JSON):
```json
{{
  "current_trends": [
    {{
      "trend": "Trend adı",
      "relevance": "high|medium|low",
      "content_angle": "Nasıl içeriğe dönüştürülür?"
    }}
  ],
  "seasonal_opportunities": [
    {{
      "opportunity": "Fırsat",
      "timing": "Ne zaman?",
      "content_idea": "İçerik fikri"
    }}
  ],
  "competitor_gaps": ["Rakiplerin kaçırdığı konular"],
  "recommended_focus": "Öncelikli odak alanı"
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=90)

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            self.log(f"JSON parse error (analyze_trends): {str(e)}", level="error")
            self.log(f"Raw response (first 500 chars): {response[:500]}", level="error")

            # Son şans: tekrar temizle
            cleaned = self._clean_json_response(response)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            return {"error": "JSON parse error", "raw_response": response[:1000], "parse_error": str(e)}
