"""
Article Enricher - Kısa özetli haberlerin tam metnini scrape eder
"""

import re
import traceback
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from app.utils.logger import get_logger
from app.database.crud import get_opportunities_by_status, update_opportunity

logger = get_logger("enricher")

# Minimum özet uzunluğu (bundan kısa ise scrape yap)
MIN_SUMMARY_LENGTH = 300

# Scrape edilen metnin max uzunluğu
MAX_ARTICLE_LENGTH = 5000

# Scrape timeout
SCRAPE_TIMEOUT = 15


class ArticleEnricher:
    """RSS feed özetleri kısa olan haberlerin tam metnini scrape eder."""

    async def enrich_opportunity(self, opportunity: Dict) -> Optional[str]:
        """
        Tek bir fırsatı zenginleştir.
        Summary yeterli uzunluktaysa scrape atlar.
        Returns: enriched full_text or None if skipped/failed
        """
        summary = opportunity.get("summary", "") or ""
        source_url = opportunity.get("source_url", "")

        # Yeterli summary varsa atlaTürkçe
        if len(summary) >= MIN_SUMMARY_LENGTH:
            return summary

        # URL yoksa atlaTürkçe
        if not source_url:
            return None

        try:
            full_text = await self._scrape_article(source_url)
            if full_text and len(full_text) > len(summary):
                return full_text[:MAX_ARTICLE_LENGTH]
        except Exception as e:
            logger.warning(f"Scrape failed for {source_url[:60]}: {e}")

        return None

    async def _scrape_article(self, url: str) -> Optional[str]:
        """URL'den makale metnini çek."""
        async with httpx.AsyncClient(
            timeout=SCRAPE_TIMEOUT,
            follow_redirects=True
        ) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; OlivenetBot/2.0)"
            })
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Gereksiz elementleri temizle
        for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                                   "aside", "form", "iframe", "noscript"]):
            tag.decompose()

        # Article veya main tag'i bul
        article = (
            soup.find("article") or
            soup.find("main") or
            soup.find("div", class_=re.compile(r"(article|post|content|entry)", re.I))
        )

        if article:
            text = article.get_text(separator=" ", strip=True)
        else:
            # Fallback: body'den tüm paragraph'ları al
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text(strip=True) for p in paragraphs)

        # Temizlik
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 50:
            return None

        return text

    async def batch_enrich(self, limit: int = 20) -> int:
        """Discovered durumundaki fırsatları toplu zenginleştir."""
        opportunities = get_opportunities_by_status("discovered", limit=limit)

        enriched_count = 0
        for opp in opportunities:
            try:
                full_text = await self.enrich_opportunity(opp)

                updates = {"status": "enriched"}
                if full_text:
                    updates["full_text"] = full_text
                    # Summary kısa ise full_text'ten güncelle
                    if len(opp.get("summary", "") or "") < MIN_SUMMARY_LENGTH:
                        updates["summary"] = full_text[:500]

                update_opportunity(opp["id"], **updates)
                enriched_count += 1

            except Exception as e:
                logger.warning(f"Enrich error for opp {opp['id']}: {e}")
                # Enrichment başarısız olsa bile status'u güncelle (scorer'ın işleyebilmesi için)
                update_opportunity(opp["id"], status="enriched")
                enriched_count += 1

        logger.info(f"Enriched {enriched_count} opportunities")
        return enriched_count
