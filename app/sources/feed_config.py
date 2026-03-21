"""
Feed Configuration - RSS feed tanımları ve kategori ağırlıkları
"""

# Her feed'in name, url, category, language, priority ve tags alanları var
FEEDS = [
    # ========== Tier 1: IoT / Endüstri (Çekirdek Alan) ==========
    {
        "name": "IoT Now",
        "url": "https://www.iot-now.com/feed/",
        "category": "iot",
        "language": "en",
        "priority": "high",
        "tags": ["iot", "industrial", "smart-factory"]
    },
    {
        "name": "RAKwireless News",
        "url": "https://news.rakwireless.com/rss/",
        "category": "lorawan",
        "language": "en",
        "priority": "high",
        "tags": ["lorawan", "iot", "connectivity"]
    },
    {
        "name": "Hackaday",
        "url": "https://hackaday.com/feed/",
        "category": "maker",
        "language": "en",
        "priority": "normal",
        "tags": ["maker", "electronics", "iot", "embedded"]
    },
    {
        "name": "LoRa Alliance Blog",
        "url": "https://lora-alliance.org/feed/",
        "category": "lorawan",
        "language": "en",
        "priority": "high",
        "tags": ["lorawan", "iot", "standard"]
    },
    {
        "name": "Embedded Computing Design",
        "url": "https://embeddedcomputing.com/feed",
        "category": "embedded",
        "language": "en",
        "priority": "normal",
        "tags": ["embedded", "edge", "computing"]
    },

    # ========== Tier 1.5: AI / ML ==========
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "category": "ai",
        "language": "en",
        "priority": "high",
        "tags": ["ai", "llm", "research"]
    },
    {
        "name": "Google DeepMind Blog",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "ai",
        "language": "en",
        "priority": "high",
        "tags": ["ai", "research", "deeplearning"]
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "ai",
        "language": "en",
        "priority": "normal",
        "tags": ["ai", "llm", "open-source"]
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "category": "ai",
        "language": "en",
        "priority": "normal",
        "tags": ["ai", "tech", "news"]
    },
    {
        "name": "Ars Technica AI",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "category": "ai",
        "language": "en",
        "priority": "normal",
        "tags": ["ai", "tech", "science"]
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "category": "ai",
        "language": "en",
        "priority": "normal",
        "tags": ["ai", "enterprise", "startup"]
    },
    {
        "name": "NVIDIA AI Blog",
        "url": "https://blogs.nvidia.com/feed/",
        "category": "ai",
        "language": "en",
        "priority": "normal",
        "tags": ["ai", "edge-ai", "gpu", "embedded"]
    },

    # ========== Tier 2: Genel Teknoloji ==========
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "category": "tech",
        "language": "en",
        "priority": "normal",
        "tags": ["ai", "tech", "startup"]
    },
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "category": "research",
        "language": "en",
        "priority": "normal",
        "tags": ["research", "ai", "tech"]
    },

    # ========== Tier 2: Enerji & Sürdürülebilirlik ==========
    {
        "name": "CleanTechnica",
        "url": "https://cleantechnica.com/feed/",
        "category": "energy",
        "language": "en",
        "priority": "normal",
        "tags": ["energy", "renewable", "cleantech"]
    },
    {
        "name": "Renewable Energy World",
        "url": "https://www.renewableenergyworld.com/feed/",
        "category": "energy",
        "language": "en",
        "priority": "normal",
        "tags": ["energy", "solar", "wind"]
    },

    # ========== Tier 2: Tarım Teknolojisi ==========
    {
        "name": "AgFunder News",
        "url": "https://agfundernews.com/feed",
        "category": "agriculture",
        "language": "en",
        "priority": "normal",
        "tags": ["agriculture", "agtech", "smart-farming"]
    },
]

# Kategori ağırlıkları - Olivenet'in çekirdek alanlarına yakınlık
CATEGORY_WEIGHTS = {
    "iot": 1.0,
    "lorawan": 1.0,
    "embedded": 0.9,
    "agriculture": 0.9,
    "energy": 0.8,
    "industrial": 0.8,
    "maker": 0.7,
    "ai": 0.8,
    "tech": 0.6,
    "research": 0.6,
}

# Öncelik bazlı bonus skorlar
PRIORITY_BONUS = {
    "high": 15,
    "normal": 5,
    "low": 0,
}

# Feed başına max entry sayısı (her fetch'te)
MAX_ENTRIES_PER_FEED = 20

# Toplam aktif fırsat limiti (DB'de biriken)
MAX_ACTIVE_OPPORTUNITIES = 200
