"""
Hashtag validation and completion helper.
Ensures posts have required hashtags and minimum count.
"""

from typing import List
import random

# Zorunlu hashtagler - her postta olmalı
REQUIRED_HASHTAGS = ["#Olivenet", "#KKTC", "#IoT"]

# Yedek hashtag havuzu - eksik olduğunda buradan tamamlanır
FALLBACK_HASHTAGS = [
    # Sektörel - Tarım
    "#AkıllıTarım", "#SeraOtomasyonu", "#AkıllıSera", "#TarımTeknolojisi",
    # Sektörel - Enerji
    "#EnerjiYönetimi", "#EnerjiVerimliliği", "#EnerjiTasarrufu",
    # Sektörel - IoT
    "#EndüstriyelIoT", "#LoRaWAN", "#Sensör", "#Otomasyon",
    # Genel
    "#DijitalDönüşüm", "#Teknoloji", "#Verimlilik", "#Sürdürülebilirlik",
    "#Endüstri40", "#AkıllıSulama", "#SmartFarming"
]


def validate_and_complete_hashtags(
    hashtags: List[str],
    min_count: int = 8,
    max_count: int = 12
) -> List[str]:
    """
    Hashtag listesini doğrula ve eksikse tamamla.

    1. Zorunlu hashtagleri (#Olivenet, #KKTC, #IoT) kontrol et/ekle
    2. Minimum sayıya ulaşmamışsa fallback havuzundan rastgele ekle
    3. Maksimum sayıyı aşmışsa kırp

    Args:
        hashtags: LLM'den gelen hashtag listesi
        min_count: Minimum hashtag sayısı (default: 8)
        max_count: Maksimum hashtag sayısı (default: 12)

    Returns:
        Tamamlanmış hashtag listesi
    """
    if hashtags is None:
        hashtags = []

    # Normalize: # ekle, küçük harf karşılaştırma için kopyala
    normalized = []
    seen_lower = set()

    for tag in hashtags:
        # # ile başlamıyorsa ekle
        if not tag.startswith("#"):
            tag = f"#{tag}"

        # Duplicate kontrolü (case-insensitive)
        tag_lower = tag.lower()
        if tag_lower not in seen_lower:
            normalized.append(tag)
            seen_lower.add(tag_lower)

    # Zorunlu hashtagleri kontrol et ve ekle
    for required in REQUIRED_HASHTAGS:
        if required.lower() not in seen_lower:
            normalized.insert(0, required)  # Başa ekle
            seen_lower.add(required.lower())

    # Minimum sayıya ulaşmamışsa fallback'lerden ekle
    if len(normalized) < min_count:
        available_fallbacks = [
            tag for tag in FALLBACK_HASHTAGS
            if tag.lower() not in seen_lower
        ]
        random.shuffle(available_fallbacks)

        needed = min_count - len(normalized)
        for tag in available_fallbacks[:needed]:
            normalized.append(tag)
            seen_lower.add(tag.lower())

    # Maksimum sayıyı aşmışsa kırp (zorunlu hashtagleri koru)
    if len(normalized) > max_count:
        # İlk 3 zorunlu, geri kalanından rastgele seç
        required_part = normalized[:3]
        rest = normalized[3:]
        random.shuffle(rest)
        normalized = required_part + rest[:max_count - 3]

    return normalized


def format_hashtags_for_caption(hashtags: List[str]) -> str:
    """
    Hashtag listesini caption'a eklenecek formata çevir.

    Args:
        hashtags: Hashtag listesi

    Returns:
        Boşluklarla ayrılmış hashtag string'i
    """
    validated = validate_and_complete_hashtags(hashtags)
    return " ".join(validated)
