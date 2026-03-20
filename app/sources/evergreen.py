"""
Evergreen Pool - Statik konu havuzu arayüzü (topics.md v2)
"""

import re
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.config import settings
from app.utils.logger import get_logger
from app.database.crud import (
    create_opportunity, get_kktc_now,
    get_opportunities_by_status
)

logger = get_logger("evergreen")

# Kategori eşlemeleri (topics.md başlıkları -> db tags)
CATEGORY_MAP = {
    "TARIM & SERA OTOMASYONU": {
        "category": "agriculture",
        "tags": ["agriculture", "sera", "smart-farming"],
        "cooldown_days": 14
    },
    "ENERJİ İZLEME & YÖNETİM": {
        "category": "energy",
        "tags": ["energy", "monitoring", "efficiency"],
        "cooldown_days": 14
    },
    "KESİTİRİMCİ BAKIM": {
        "category": "predictive_maintenance",
        "tags": ["predictive-maintenance", "industrial", "ai"],
        "cooldown_days": 14
    },
    "LoRaWAN TEKNOLOJİSİ": {
        "category": "lorawan",
        "tags": ["lorawan", "iot", "connectivity"],
        "cooldown_days": 21
    },
    "EDGE AI & GÖRÜNTÜ İŞLEME": {
        "category": "edge_ai",
        "tags": ["edge-ai", "computer-vision", "ai"],
        "cooldown_days": 21
    },
    "ENDÜSTRİYEL IoT": {
        "category": "industrial_iot",
        "tags": ["iiot", "industrial", "iot"],
        "cooldown_days": 14
    },
    "GÖMÜLÜ SİSTEMLER": {
        "category": "embedded",
        "tags": ["embedded", "firmware", "hardware"],
        "cooldown_days": 21
    },
    "KKTC & BÖLGESEL": {
        "category": "kktc",
        "tags": ["kktc", "local", "solution"],
        "cooldown_days": 30
    },
}


class EvergreenPool:
    """Statik konu havuzunu yönetir. Fallback ve dolgu kaynağı olarak kullanılır."""

    def __init__(self):
        self.topics_path = settings.get_context_file("topics.md")
        self._topics_cache = None

    def _load_topics(self) -> Dict[str, List[str]]:
        """topics.md'den kategorileri ve konuları parse et."""
        if self._topics_cache:
            return self._topics_cache

        if not self.topics_path.exists():
            logger.warning(f"Topics file not found: {self.topics_path}")
            return {}

        content = self.topics_path.read_text()
        categories = {}
        current_category = None

        for line in content.split("\n"):
            line = line.strip()

            # Kategori başlığı (## ile başlayan)
            if line.startswith("## "):
                # Emoji ve ekstra karakterleri temizle
                cat_name = re.sub(r'[^\w\s&]', '', line.replace("## ", "")).strip()
                for key in CATEGORY_MAP:
                    if key in cat_name.upper():
                        current_category = key
                        categories[current_category] = []
                        break

            # Konu (- ile başlayan)
            elif line.startswith("- ") and current_category:
                topic = line[2:].strip()
                if topic and len(topic) > 5:
                    categories[current_category].append(topic)

        self._topics_cache = categories
        return categories

    def get_random_topic(self, category: str = None) -> Optional[Dict]:
        """Rastgele bir evergreen konu seç."""
        topics = self._load_topics()

        if not topics:
            return None

        if category:
            # Belirli kategoriden seç
            for cat_key, cat_info in CATEGORY_MAP.items():
                if cat_info["category"] == category and cat_key in topics:
                    topic_list = topics[cat_key]
                    if topic_list:
                        selected = random.choice(topic_list)
                        return {
                            "title": selected,
                            "category": cat_info["category"],
                            "tags": cat_info["tags"],
                            "cooldown_days": cat_info["cooldown_days"]
                        }
            return None

        # Tüm kategorilerden rastgele seç
        all_categories = list(topics.keys())
        if not all_categories:
            return None

        cat_key = random.choice(all_categories)
        cat_info = CATEGORY_MAP.get(cat_key, {})
        topic_list = topics[cat_key]

        if not topic_list:
            return None

        selected = random.choice(topic_list)
        return {
            "title": selected,
            "category": cat_info.get("category", "general"),
            "tags": cat_info.get("tags", []),
            "cooldown_days": cat_info.get("cooldown_days", 14)
        }

    def inject_as_opportunity(self, topic: Dict = None) -> Optional[int]:
        """Evergreen konuyu content_opportunity olarak DB'ye ekle."""
        if topic is None:
            topic = self.get_random_topic()

        if not topic:
            return None

        opp_id = create_opportunity(
            source_type="evergreen",
            source_name=f"topics.md/{topic['category']}",
            title=topic["title"],
            summary=topic["title"],
            original_language="tr",
            tags=topic.get("tags", []),
        )

        if opp_id:
            logger.info(f"Injected evergreen topic: {topic['title']}")

        return opp_id

    def get_all_categories(self) -> List[str]:
        """Tüm mevcut kategorileri listele."""
        topics = self._load_topics()
        result = []
        for cat_key in topics:
            info = CATEGORY_MAP.get(cat_key, {})
            result.append({
                "name": cat_key,
                "category_id": info.get("category", "unknown"),
                "topic_count": len(topics[cat_key]),
                "cooldown_days": info.get("cooldown_days", 14)
            })
        return result
