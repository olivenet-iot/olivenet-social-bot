"""
Relevance Scorer - İçerik fırsatlarını Claude API ile 5 boyutlu skorla
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.agents.base_agent import BaseAgent
from app.utils.logger import get_logger
from app.database.crud import (
    get_opportunities_by_status, update_opportunity, get_kktc_now
)
from app.sources.feed_config import CATEGORY_WEIGHTS, PRIORITY_BONUS

logger = get_logger("relevance_scorer")

# Saatlik max scoring limiti
MAX_SCORES_PER_HOUR = 20


class RelevanceScorer(BaseAgent):
    """Claude API ile içerik fırsatlarını 5 boyutlu skorla."""

    def __init__(self):
        super().__init__("scorer")
        self._scores_this_hour = 0
        self._hour_start = datetime.utcnow()

    async def execute(self, input_data: Dict) -> Dict:
        action = input_data.get("action", "batch_score")
        if action == "score_single":
            return await self.score_opportunity(input_data.get("opportunity", {}))
        elif action == "batch_score":
            count = await self.batch_score()
            return {"scored": count}
        return {"error": f"Unknown action: {action}"}

    async def score_opportunity(self, opportunity: Dict) -> Dict:
        """Tek bir fırsatı 5 boyutlu skorla. Claude API çağrısı yapar."""
        if not opportunity.get("title"):
            return {"error": "No title"}

        # Rate limit kontrolü
        if not self._check_rate_limit():
            return {"error": "Rate limit exceeded", "retry_after_minutes": 60}

        # Context dosyalarını yükle
        company_profile = self.load_context("company-profile.md")
        content_strategy = self.load_context("content-strategy.md")

        prompt = f"""Sen bir içerik fırsat değerlendirme uzmanısın. Olivenet, KKTC merkezli bir teknoloji şirketidir — IoT, Edge AI, enerji izleme ve yapay zeka çözümleri sunar. Instagram'da hem teknik hem popüler bilim içeriği üretir.

OLIVENET HAKKINDA:
{company_profile[:1500]}

İÇERİK STRATEJİSİ:
{content_strategy[:1000]}

DEĞERLENDİRİLECEK FIRSAT:
Başlık: {opportunity.get('title', '')}
Kaynak: {opportunity.get('source_name', '')}
Özet: {opportunity.get('summary', '')[:800]}
Dil: {opportunity.get('original_language', 'en')}
Etiketler: {json.dumps(opportunity.get('tags', []))}

Bu fırsatı aşağıdaki 5 boyutta 1-10 arası puanla:

1. **olivenet_relevance** (1-10): Bu konu Olivenet'in uzmanlık alanı ve Instagram içerik stratejisine ne kadar uygun?
   - Direkt IoT, LoRaWAN, akıllı sensör = 8-10
   - Edge AI, endüstriyel otomasyon, akıllı tarım = 7-9
   - Genel AI/ML, LLM, agentic AI = 5-7
   - Enerji, sürdürülebilirlik, akıllı şehir = 5-7
   - Genel teknoloji haberi = 3-5
   - Alakasız (politika, spor, magazin) = 1-2

2. **visual_potential** (1-10): Bu konu Instagram Reels/video olarak ne kadar görsel ve sinematik olabilir?
   - Robot, drone, fabrika, sensör görseli = 8-10
   - Veri dashboard, grafik, karşılaştırma = 6-8
   - Soyut konsept ama animasyonla anlatılabilir = 4-6
   - Sadece metin bazlı, görsel potansiyeli düşük = 1-3

3. **viral_potential** (1-10): Bu konu sosyal medyada ne kadar dikkat çekip paylaşılabilir?
   - "Bunu bilmiyordum!" etkisi yaratır = 8-10
   - Trend konu, herkesin konuştuğu = 7-9
   - Niş ama meraklısı için çok değerli = 5-7
   - Rutin haber, sürpriz yok = 3-5
   - Çok teknik, dar kitle = 1-3

4. **timeliness** (1-10): Bu konu ne kadar güncel ve zamanında?
   - Son 24 saat, breaking news = 9-10
   - Bu hafta trend = 7-8
   - Bu ay gündem = 5-6
   - Evergreen, her zaman geçerli = 4-5
   - Eski haber, geçmiş = 1-3

5. **originality** (1-10): Bu konu ne kadar özgün ve farklı?
   - Daha önce hiç görmediğimiz bir açı = 9-10
   - Bilinen konuya yeni bir bakış = 6-8
   - Herkesin paylaştığı standart haber = 3-5
   - Tekrar, zaten çok işlenmiş = 1-2

Ayrıca şunları da belirt:
- **reasoning**: Neden bu skorları verdin? (1-2 cümle, Türkçe)
- **olivenet_angle**: Bu haberi Olivenet perspektifinden nasıl anlatırız? (1-2 cümle, Türkçe)
- **content_type_suggestion**: En uygun format nedir? ("reels", "carousel", "post", "voice_reels")
- **hook_suggestion**: Önerilen hook/açılış cümlesi (Türkçe, max 15 kelime)

JSON formatında yanıt ver:
{{
    "olivenet_relevance": 7,
    "visual_potential": 8,
    "viral_potential": 6,
    "timeliness": 7,
    "originality": 5,
    "reasoning": "...",
    "olivenet_angle": "...",
    "content_type_suggestion": "reels",
    "hook_suggestion": "..."
}}"""

        try:
            response = await self.call_claude_with_retry(prompt, timeout=60, max_retries=2)
            result = json.loads(response)

            # Skor doğrulama (1-10 aralığında) — 5 boyut
            for key in ["olivenet_relevance", "visual_potential", "viral_potential", "timeliness", "originality"]:
                val = result.get(key, 0)
                if not isinstance(val, (int, float)):
                    val = 0
                result[key] = max(0, min(10, val))

            # Reasoning log
            if result.get("reasoning"):
                logger.info(f"Score reasoning [{opportunity.get('title', '')[:40]}]: {result['reasoning']}")

            # Backward-compat mapping (prompt key → DB column name)
            result["relevance_score"] = result["olivenet_relevance"]
            result["timeliness_score"] = result["timeliness"]
            result["virality_potential"] = result["viral_potential"]
            result["originality_score"] = result["originality"]

            # Combined score hesapla
            result["combined_score"] = self.calculate_combined_score(
                olivenet_relevance=result["olivenet_relevance"],
                visual_potential=result["visual_potential"],
                viral_potential=result["viral_potential"],
                timeliness=result["timeliness"],
                originality=result["originality"],
                source_type=opportunity.get("source_type", "rss"),
                source_name=opportunity.get("source_name", ""),
                priority=self._get_feed_priority(opportunity.get("source_name", "")),
                age_hours=self._calculate_age_hours(opportunity.get("created_at"))
            )

            self._scores_this_hour += 1
            return result

        except json.JSONDecodeError:
            logger.error(f"JSON parse error for opportunity: {opportunity.get('title', '')[:50]}")
            return {"error": "JSON parse error"}
        except Exception as e:
            logger.error(f"Scoring error: {e}")
            return {"error": str(e)}

    def calculate_combined_score(
        self,
        olivenet_relevance: float,
        visual_potential: float,
        viral_potential: float,
        timeliness: float,
        originality: float,
        source_type: str = "rss",
        source_name: str = "",
        priority: str = "normal",
        age_hours: float = 0
    ) -> float:
        """0-100 arası birleşik skor hesapla — 5 boyutlu ağırlıklı formül."""

        # Ağırlıklı ortalama (1-10 -> 0-100 normalize)
        base = (
            olivenet_relevance * 0.25 +
            visual_potential * 0.25 +
            viral_potential * 0.20 +
            timeliness * 0.15 +
            originality * 0.15
        ) * 10

        # Kaynak öncelik bonusu
        source_bonus = PRIORITY_BONUS.get(priority, 0)

        # Yaşlanma cezası (sadece RSS haberleri için)
        # Azaltıldı: timeliness zaten Claude tarafından skorlanıyor
        age_penalty = 0
        if source_type == "rss" and age_hours > 0:
            age_penalty = min(age_hours * 1, 20)

        score = base + source_bonus - age_penalty

        return round(max(0, min(100, score)), 1)

    async def batch_score(self, limit: int = 10) -> int:
        """Skorlanmamış fırsatları toplu skorla."""
        # enriched olanları al (enrichment'tan sonra skorla)
        opportunities = get_opportunities_by_status("enriched", limit=limit)

        # enriched yoksa discovered olanları da al (enrichment atlanmış olabilir)
        if not opportunities:
            opportunities = get_opportunities_by_status("discovered", limit=limit)

        scored_count = 0
        for opp in opportunities:
            if not self._check_rate_limit():
                logger.warning(f"Rate limit reached, scored {scored_count} opportunities")
                break

            result = await self.score_opportunity(opp)

            if "error" not in result:
                update_opportunity(opp["id"],
                    relevance_score=result["relevance_score"],
                    timeliness_score=result["timeliness_score"],
                    virality_potential=result["virality_potential"],
                    visual_potential=result.get("visual_potential", 0),
                    originality_score=result.get("originality", 0),
                    combined_score=result["combined_score"],
                    olivenet_angle=result.get("olivenet_angle", ""),
                    content_type_suggestion=result.get("content_type_suggestion", ""),
                    hook_suggestion=result.get("hook_suggestion", ""),
                    status="scored"
                )
                scored_count += 1
                logger.info(
                    f"Scored: {opp['title'][:50]}... -> {result['combined_score']}"
                )

        return scored_count

    def _check_rate_limit(self) -> bool:
        """Saatlik rate limit kontrolü."""
        now = datetime.utcnow()
        if (now - self._hour_start).total_seconds() > 3600:
            self._scores_this_hour = 0
            self._hour_start = now

        return self._scores_this_hour < MAX_SCORES_PER_HOUR

    def _get_feed_priority(self, source_name: str) -> str:
        """Feed adından öncelik bilgisini bul."""
        from app.sources.feed_config import FEEDS
        for feed in FEEDS:
            if feed["name"] == source_name:
                return feed.get("priority", "normal")
        return "normal"

    @staticmethod
    def _calculate_age_hours(created_at) -> float:
        """Fırsatın yaşını saat cinsinden hesapla."""
        if not created_at:
            return 0
        try:
            if isinstance(created_at, str):
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                created = created_at
            return (datetime.utcnow() - created.replace(tzinfo=None)).total_seconds() / 3600
        except Exception:
            return 0
