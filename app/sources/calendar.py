"""
Event Calendar - Endüstri etkinlikleri ve sezonsal içerik takvimi
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.utils.logger import get_logger
from app.database.crud import create_opportunity, check_duplicate_opportunity

logger = get_logger("calendar")

# Sabit takvim etkinlikleri (MM-DD formatında)
CALENDAR_EVENTS = [
    # Teknoloji & Mühendislik
    {"date": "03-14", "title": "Pi Günü — Mühendislikte π'nin Rolü", "tags": ["math", "engineering"], "content_type": "reels"},
    {"date": "04-22", "title": "Dünya Günü — Yeşil IoT ve Sürdürülebilirlik", "tags": ["sustainability", "energy"], "content_type": "carousel"},
    {"date": "05-17", "title": "Dünya Telekomünikasyon Günü — IoT Bağlantısı", "tags": ["iot", "connectivity"], "content_type": "reels"},
    {"date": "06-05", "title": "Dünya Çevre Günü — Akıllı Enerji Yönetimi", "tags": ["energy", "environment"], "content_type": "carousel"},
    {"date": "10-01", "title": "Enerji Verimliliği Haftası — IoT ile Tasarruf", "tags": ["energy", "efficiency"], "content_type": "carousel"},
    {"date": "11-30", "title": "Endüstri 4.0 Günü — Geleceğin Fabrikası", "tags": ["industry4", "smart-factory"], "content_type": "reels"},

    # Tarım sezonu
    {"date": "03-20", "title": "İlkbahar Ekinoksu — Sera Sezonu Başlıyor", "tags": ["agriculture", "sera"], "content_type": "reels"},
    {"date": "06-21", "title": "Yaz Gündönümü — Sera Sıcaklık Yönetimi", "tags": ["agriculture", "monitoring"], "content_type": "post"},
    {"date": "09-22", "title": "Sonbahar Ekinoksu — Hasat ve IoT Veri Analizi", "tags": ["agriculture", "data"], "content_type": "carousel"},

    # KKTC özel
    {"date": "07-20", "title": "KKTC Barış Harekatı — Teknoloji ile Gelişim", "tags": ["kktc", "local"], "content_type": "post"},
    {"date": "11-15", "title": "KKTC Cumhuriyet Bayramı — Dijital Dönüşüm", "tags": ["kktc", "digital"], "content_type": "post"},
]


class EventCalendar:
    """Takvim bazlı içerik fırsatları üretir."""

    def get_upcoming_events(self, days_ahead: int = 7) -> List[Dict]:
        """Önümüzdeki N gün içindeki etkinlikleri getir."""
        now = datetime.utcnow()
        upcoming = []

        for event in CALENDAR_EVENTS:
            month, day = map(int, event["date"].split("-"))
            event_date = datetime(now.year, month, day)

            # Geçmiş etkinlikleri gelecek yıla al
            if event_date < now - timedelta(days=1):
                event_date = datetime(now.year + 1, month, day)

            days_until = (event_date - now).days

            if 0 <= days_until <= days_ahead:
                upcoming.append({
                    **event,
                    "event_date": event_date.strftime("%Y-%m-%d"),
                    "days_until": days_until
                })

        # Yakınlık sırasına göre sırala
        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming

    def inject_upcoming_as_opportunities(self, days_ahead: int = 3) -> int:
        """Yaklaşan etkinlikleri content_opportunity olarak DB'ye ekle."""
        events = self.get_upcoming_events(days_ahead=days_ahead)
        injected = 0

        for event in events:
            # Duplicate kontrolü (title hash ile)
            import hashlib
            title_hash = hashlib.sha256(
                f"{event['title']}_{event['event_date']}".encode()
            ).hexdigest()[:32]

            if check_duplicate_opportunity(title_hash=title_hash):
                continue

            opp_id = create_opportunity(
                source_type="calendar",
                source_name="event_calendar",
                title=event["title"],
                summary=f"Takvim etkinliği: {event['title']} ({event['event_date']})",
                original_language="tr",
                tags=event.get("tags", []),
                title_hash=title_hash,
            )

            if opp_id:
                # Takvim etkinlikleri yüksek öncelikli
                from app.database.crud import update_opportunity
                update_opportunity(opp_id,
                    relevance_score=8,
                    timeliness_score=9,
                    virality_potential=6,
                    combined_score=75.0,
                    content_type_suggestion=event.get("content_type", "reels"),
                    status="ready"
                )
                injected += 1
                logger.info(f"Injected calendar event: {event['title']}")

        return injected
