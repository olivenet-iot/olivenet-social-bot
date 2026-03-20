"""
Feed Aggregator - RSS feed'leri fetch, parse, normalize ve dedup
"""

import asyncio
import hashlib
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from email.utils import parsedate_to_datetime

import httpx
import feedparser

from app.utils.logger import get_logger
from app.database.crud import (
    create_opportunity, check_duplicate_opportunity,
    expire_old_opportunities, get_opportunity_stats
)
from app.sources.feed_config import FEEDS, MAX_ENTRIES_PER_FEED

logger = get_logger("feed_aggregator")


class FeedAggregator:
    """RSS feed fetch, parse, normalize, dedup."""

    def __init__(self):
        self.feed_health: Dict[str, Dict] = {}  # feed_name -> {last_fetch, error_count, last_error}
        self._running = False

    async def fetch_all_feeds(self) -> int:
        """Tüm feed'leri fetch et, parse et, DB'ye yaz. Toplam yeni entry sayısını döner."""
        total_new = 0

        for feed_config in FEEDS:
            try:
                entries = await self.fetch_single_feed(feed_config)
                new_count = await self.store_new_entries(entries, feed_config)
                total_new += new_count

                self.feed_health[feed_config["name"]] = {
                    "last_fetch": datetime.utcnow().isoformat(),
                    "entries_found": len(entries),
                    "new_stored": new_count,
                    "error_count": 0,
                    "last_error": None
                }

                logger.info(
                    f"[FEED] {feed_config['name']}: {len(entries)} entries, {new_count} new"
                )

            except Exception as e:
                health = self.feed_health.get(feed_config["name"], {"error_count": 0})
                self.feed_health[feed_config["name"]] = {
                    "last_fetch": datetime.utcnow().isoformat(),
                    "entries_found": 0,
                    "new_stored": 0,
                    "error_count": health.get("error_count", 0) + 1,
                    "last_error": str(e)
                }
                logger.error(f"[FEED] {feed_config['name']} fetch error: {e}")

        logger.info(f"[FEED] Total new opportunities: {total_new}")
        return total_new

    async def fetch_single_feed(self, feed_config: Dict) -> List[Dict]:
        """Tek bir feed'i fetch et ve normalize edilmiş entry listesi döner."""
        url = feed_config["url"]

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url, headers={
                "User-Agent": "OlivenetBot/2.0 (RSS Aggregator)"
            })
            response.raise_for_status()

        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Feed parse error: {feed.bozo_exception}")

        entries = []
        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            parsed = self.parse_rss_entry(entry, feed_config)
            if parsed:
                entries.append(parsed)

        return entries

    def parse_rss_entry(self, entry, feed_config: Dict) -> Optional[Dict]:
        """Tek bir RSS entry'sini normalize edilmiş dict'e çevir."""
        title = getattr(entry, "title", "").strip()
        if not title:
            return None

        # URL
        link = getattr(entry, "link", "") or ""

        # Summary / description
        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary
        elif hasattr(entry, "description"):
            summary = entry.description

        # HTML tag'lerini temizle (basit)
        if summary:
            import re
            summary = re.sub(r'<[^>]+>', '', summary).strip()
            summary = summary[:1000]  # Max 1000 karakter

        # Tarih
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                published = None
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                published = datetime(*entry.updated_parsed[:6])
            except Exception:
                published = None

        # Tags
        tags = list(feed_config.get("tags", []))
        if hasattr(entry, "tags"):
            for tag in entry.tags:
                term = getattr(tag, "term", "").lower().strip()
                if term and term not in tags:
                    tags.append(term)

        # Hash'ler
        title_hash, url_hash = self.generate_hashes(title, link)

        # Expire hesapla (haber bazlı: 72 saat)
        expires_at = None
        if published:
            expires_at = (published + timedelta(hours=72)).isoformat()
        else:
            expires_at = (datetime.utcnow() + timedelta(hours=72)).isoformat()

        return {
            "title": title,
            "source_url": link,
            "summary": summary,
            "published": published,
            "tags": tags,
            "title_hash": title_hash,
            "url_hash": url_hash,
            "expires_at": expires_at,
            "original_language": feed_config.get("language", "en"),
        }

    @staticmethod
    def generate_hashes(title: str, url: str) -> Tuple[str, str]:
        """Title ve URL için dedup hash'leri oluştur."""
        title_hash = hashlib.sha256(title.lower().strip().encode()).hexdigest()[:32]
        url_hash = hashlib.sha256(url.strip().encode()).hexdigest()[:32] if url else None
        return title_hash, url_hash

    async def store_new_entries(self, entries: List[Dict], feed_config: Dict) -> int:
        """Yeni entry'leri content_opportunities tablosuna yaz. Duplicate'leri atla."""
        new_count = 0

        for entry in entries:
            # Duplicate kontrolü
            if check_duplicate_opportunity(
                url_hash=entry.get("url_hash"),
                title_hash=entry.get("title_hash")
            ):
                continue

            opp_id = create_opportunity(
                source_type="rss",
                source_name=feed_config["name"],
                source_url=entry.get("source_url"),
                title=entry["title"],
                summary=entry.get("summary"),
                original_language=entry.get("original_language", "en"),
                tags=entry.get("tags", []),
                title_hash=entry.get("title_hash"),
                url_hash=entry.get("url_hash"),
                expires_at=entry.get("expires_at"),
            )

            if opp_id:
                new_count += 1

        return new_count

    async def run_feed_pipeline(self):
        """
        Tam feed pipeline: fetch -> enrich -> score -> summarize -> expire
        Her cycle'da çağrılır.
        """
        from app.sources.enricher import ArticleEnricher
        from app.sources.relevance_scorer import RelevanceScorer
        from app.sources.summarizer import ContentSummarizer
        from app.sources.calendar import EventCalendar
        from app.sources.evergreen import EvergreenPool

        # 1. Feed'leri fetch et
        new_count = await self.fetch_all_feeds()
        logger.info(f"[PIPELINE] Step 1/6: Fetched {new_count} new entries")

        # 2. Takvim etkinliklerini kontrol et
        try:
            calendar = EventCalendar()
            cal_count = calendar.inject_upcoming_as_opportunities(days_ahead=3)
            if cal_count:
                logger.info(f"[PIPELINE] Step 2/6: Injected {cal_count} calendar events")
        except Exception as e:
            logger.error(f"[PIPELINE] Calendar error: {e}")

        # 3. Evergreen dolgu (aktif fırsat az ise)
        try:
            stats = get_opportunity_stats()
            active = stats.get("active_count", 0)
            if active < 5:
                pool = EvergreenPool()
                eg_id = pool.inject_as_opportunity()
                if eg_id:
                    logger.info(f"[PIPELINE] Step 3/6: Injected evergreen topic (active pool low: {active})")
        except Exception as e:
            logger.error(f"[PIPELINE] Evergreen error: {e}")

        # 4. Enrich (discovered -> enriched)
        try:
            enricher = ArticleEnricher()
            enriched = await enricher.batch_enrich(limit=15)
            logger.info(f"[PIPELINE] Step 4/6: Enriched {enriched} opportunities")
        except Exception as e:
            logger.error(f"[PIPELINE] Enrich error: {e}")

        # 5. Score (enriched -> scored)
        try:
            scorer = RelevanceScorer()
            scored = await scorer.batch_score(limit=10)
            logger.info(f"[PIPELINE] Step 5/6: Scored {scored} opportunities")
        except Exception as e:
            logger.error(f"[PIPELINE] Score error: {e}")

        # 6. Summarize (scored high -> ready, scored low -> dropped)
        try:
            summarizer = ContentSummarizer()
            summarized = await summarizer.batch_summarize(limit=5)
            logger.info(f"[PIPELINE] Step 6/6: Summarized {summarized} opportunities")
        except Exception as e:
            logger.error(f"[PIPELINE] Summarize error: {e}")

        # Cleanup
        expired = expire_old_opportunities(max_age_hours=72)
        if expired:
            logger.info(f"[PIPELINE] Cleanup: Expired {expired} old opportunities")

    async def run_loop(self, interval_minutes: int = 30):
        """Feed aggregator döngüsü - belirtilen aralıkta tam pipeline çalıştırır."""
        self._running = True
        logger.info(f"[FEED] Feed aggregator started (interval: {interval_minutes}m)")

        while self._running:
            try:
                await self.run_feed_pipeline()
            except Exception as e:
                logger.error(f"[FEED] Loop error: {e}\n{traceback.format_exc()}")

            await asyncio.sleep(interval_minutes * 60)

    def stop(self):
        """Döngüyü durdur."""
        self._running = False

    def get_health_report(self) -> Dict:
        """Tüm feed'lerin sağlık durumunu döner."""
        return {
            "feeds": self.feed_health,
            "stats": get_opportunity_stats()
        }
