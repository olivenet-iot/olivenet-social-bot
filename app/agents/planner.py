"""
Planner Agent - İçerik planlayıcı
Konu seçimi, zamanlama ve içerik mix'i yönetir
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from .base_agent import BaseAgent
from app.database import (
    get_current_strategy, get_published_posts,
    log_agent_action
)

class PlannerAgent(BaseAgent):
    """İçerik planlayıcı - konu ve zamanlama belirler"""

    def __init__(self):
        super().__init__("planner")

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

    async def suggest_topic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Tek bir konu öner"""
        self.log("Konu önerisi oluşturuluyor...")

        # Parametreler
        category = input_data.get("category")  # Belirli kategori istendi mi?
        exclude_topics = input_data.get("exclude", [])  # Hariç tutulacak konular

        # Context yükle
        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")
        topics_pool = self.load_context("topics.md")
        strategy = get_current_strategy()

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

Mevsimselliği düşün:
- Kış: Enerji tasarrufu, ısıtma maliyetleri
- Yaz: Serinletme, sulama sistemleri
- Genel: IoT faydaları, teknoloji trendleri

ÇIKTI FORMATI (JSON):
```json
{{
  "topic": "Konu başlığı (Türkçe)",
  "category": "egitici|tanitim|ipucu|haber|basari_hikayesi",
  "description": "Kısa açıklama",
  "reasoning": "Neden bu konu ve neden bugün?",
  "suggested_visual": "flux|infographic|gemini|video",
  "suggested_hooks": [
    "Hook önerisi 1",
    "Hook önerisi 2",
    "Hook önerisi 3"
  ],
  "hashtags": ["#hashtag1", "#hashtag2"],
  "best_time": "HH:MM",
  "urgency": "high|medium|low"
}}
```

Sadece JSON döndür.
"""

        response = await self.call_claude(prompt, timeout=90)

        try:
            result = json.loads(self._clean_json_response(response))

            log_agent_action(
                agent_name=self.name,
                action="suggest_topic",
                input_data={"category": category, "exclude": exclude_topics},
                output_data=result,
                success=True
            )

            self.log(f"Konu önerildi: {result.get('topic', 'N/A')}")
            return result

        except json.JSONDecodeError:
            log_agent_action(
                agent_name=self.name,
                action="suggest_topic",
                success=False,
                error_message="JSON parse error"
            )
            return {"error": "JSON parse error", "raw_response": response}

    async def suggest_week_topics(self) -> Dict[str, Any]:
        """Haftalık konu planı oluştur"""
        self.log("Haftalık konu planı oluşturuluyor...")

        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")
        topics_pool = self.load_context("topics.md")
        schedule_strategy = self.load_context("schedule-strategy.md")
        strategy = get_current_strategy()

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
            result = json.loads(self._clean_json_response(response))

            log_agent_action(
                agent_name=self.name,
                action="suggest_week_topics",
                output_data=result,
                success=True
            )

            self.log(f"Haftalık plan oluşturuldu: {len(result.get('week_topics', []))} konu")
            return result

        except json.JSONDecodeError:
            return {"error": "JSON parse error", "raw_response": response}

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
            return json.loads(self._clean_json_response(response))
        except json.JSONDecodeError:
            return {"error": "JSON parse error", "raw_response": response}
