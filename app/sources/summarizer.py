"""
Content Summarizer - Skorlanmış fırsatlar için yapılandırılmış özet üretir
"""

import json
from typing import Dict, List

from app.agents.base_agent import BaseAgent
from app.utils.logger import get_logger
from app.database.crud import get_opportunities_by_status, update_opportunity

logger = get_logger("summarizer")

# Minimum combined_score (bunun üstündeki fırsatlar özetlenir)
MIN_SCORE_FOR_SUMMARY = 50.0


class ContentSummarizer(BaseAgent):
    """Yüksek skorlu fırsatlar için yapılandırılmış özet üretir."""

    def __init__(self):
        super().__init__("summarizer")

    async def execute(self, input_data: Dict) -> Dict:
        action = input_data.get("action", "batch_summarize")
        if action == "summarize_single":
            return await self.summarize(input_data.get("opportunity", {}))
        elif action == "batch_summarize":
            count = await self.batch_summarize()
            return {"summarized": count}
        return {"error": f"Unknown action: {action}"}

    async def summarize(self, opportunity: Dict) -> Dict:
        """
        Tek bir fırsat için yapılandırılmış özet üret.
        Returns: {what_happened, why_important, olivenet_angle, key_facts, suggested_hook}
        """
        title = opportunity.get("title", "")
        summary = opportunity.get("summary", "")
        full_text = opportunity.get("full_text", "")
        source_name = opportunity.get("source_name", "")
        tags = opportunity.get("tags", [])

        # En iyi mevcut metni kullan
        content = full_text if full_text else summary

        if not content:
            return {"error": "No content to summarize"}

        prompt = f"""Sen Olivenet için içerik hazırlayan bir editörsün. Olivenet, KKTC merkezli Endüstriyel IoT şirketidir.

Aşağıdaki haberi/makaleyi analiz et ve Türkçe yapılandırılmış bir özet oluştur:

KAYNAK: {source_name}
BAŞLIK: {title}
ETİKETLER: {json.dumps(tags) if isinstance(tags, list) else tags}
İÇERİK:
{content[:3000]}

JSON formatında yanıt ver:
{{
    "what_happened": "Ne oldu? (2-3 cümle, Türkçe)",
    "why_important": "Neden önemli? (1-2 cümle, Türkçe)",
    "olivenet_angle": "Olivenet perspektifinden nasıl anlatılır? (1-2 cümle, Türkçe)",
    "key_facts": ["Anahtar bilgi 1", "Anahtar bilgi 2", "Anahtar bilgi 3"],
    "suggested_hook": "Instagram hook önerisi (max 15 kelime, Türkçe, dikkat çekici)"
}}"""

        try:
            response = await self.call_claude_with_retry(prompt, timeout=60, max_retries=2)
            result = json.loads(response)

            # Doğrulama
            required = ["what_happened", "why_important", "olivenet_angle"]
            for field in required:
                if field not in result:
                    result[field] = ""

            if "key_facts" not in result:
                result["key_facts"] = []
            if "suggested_hook" not in result:
                result["suggested_hook"] = ""

            return result

        except json.JSONDecodeError:
            logger.error(f"JSON parse error for: {title[:50]}")
            return {"error": "JSON parse error"}
        except Exception as e:
            logger.error(f"Summarize error: {e}")
            return {"error": str(e)}

    async def batch_summarize(self, limit: int = 10) -> int:
        """Yüksek skorlu scored fırsatları toplu özetle."""
        opportunities = get_opportunities_by_status("scored", limit=limit)

        # Sadece yüksek skorluları özetle
        high_score = [o for o in opportunities if o.get("combined_score", 0) >= MIN_SCORE_FOR_SUMMARY]

        summarized_count = 0
        for opp in high_score:
            result = await self.summarize(opp)

            if "error" not in result:
                # Özet bilgilerini DB'ye yaz
                update_data = {
                    "status": "ready",
                    "olivenet_angle": result.get("olivenet_angle", ""),
                    "hook_suggestion": result.get("suggested_hook", ""),
                }

                # Summary'yi zenginleştir
                structured_summary = (
                    f"{result.get('what_happened', '')}\n\n"
                    f"Neden önemli: {result.get('why_important', '')}\n\n"
                    f"Olivenet açısı: {result.get('olivenet_angle', '')}"
                )
                update_data["summary"] = structured_summary

                update_opportunity(opp["id"], **update_data)
                summarized_count += 1
                logger.info(f"Summarized: {opp['title'][:50]}...")

        # Düşük skorluları da durumunu güncelle (ready yapmadan)
        low_score = [o for o in opportunities if o.get("combined_score", 0) < MIN_SCORE_FOR_SUMMARY]
        for opp in low_score:
            update_opportunity(opp["id"], status="dropped")

        logger.info(f"Summarized {summarized_count}, dropped {len(low_score)} low-score")
        return summarized_count
