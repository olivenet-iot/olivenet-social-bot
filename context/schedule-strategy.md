# Olivenet Zamanlama Stratejisi (Iteration 2 - Organik Büyüme)

## Genel Bakış

| Platform | Haftalık | Oran |
|----------|----------|------|
| Instagram Reels | 7 | **58%** |
| Instagram Carousel | 2 | 17% |
| Instagram Post | 3 | 25% |
| Facebook | 3 | (Post'larla birlikte) |

**Neden %58 Reels?**
- Non-follower reach Reels'de 3x daha yüksek
- Explore page'de görünürlük
- Algoritma Reels'i önceliklendiriyor

---

## Haftalık Program

### Pazartesi - Hafta Başı Momentum
- 10:00 -> **Reels** (Instagram) - Hafta başı motivasyon
- 19:00 -> Post (Instagram + Facebook)

### Salı - Yoğun Gün
- 10:00 -> **Reels** (Instagram)
- 19:00 -> **Carousel** (Instagram) - Eğitici içerik

### Çarşamba - Orta Hafta
- 10:00 -> **Reels** (Instagram)
- 19:00 -> Post (Instagram + Facebook)

### Perşembe - Etkileşim Zirvesi
- 10:00 -> **Reels** (Instagram) - Teknik demo
- 19:00 -> **Reels** (Instagram) - Problem/Çözüm

### Cuma - Hafta Sonu Öncesi
- 10:00 -> **Reels** (Instagram)
- 19:00 -> Post (Instagram + Facebook)

### Cumartesi - Rahat İzleme
- 14:00 -> **Carousel** (Instagram) - Showcase

### Pazar - Hafta Özeti
- 14:00 -> **Reels** (Instagram) - Tips & Tricks

---

## Özet

- Toplam: 12 içerik/hafta
- **7 Reels (58%)** - Non-follower reach odaklı
- 2 Carousel (17%) - Eğitici/kaydet odaklı
- 3 Post (25%) - Detaylı bilgi

---

## Reels Konu Rotasyonu (7 Reels/hafta)

| Gün | Saat | Tarz | Örnek Konular |
|-----|------|------|---------------|
| Pazartesi | 10:00 | Motivasyon/Lifestyle | Hafta başı IoT, Smart farming |
| Salı | 10:00 | Teknik/Demo | LoRaWAN, Sensörler |
| Çarşamba | 10:00 | Eğitim | Edge AI, Veri yönetimi |
| Perşembe | 10:00 | Teknik Demo | Platform özellikleri |
| Perşembe | 19:00 | Problem/Çözüm | Enerji, Kestirimci Bakım |
| Cuma | 10:00 | Ürün Tanıtım | IoT çözümleri |
| Pazar | 14:00 | Hafta Özeti/Tips | Genel IoT, Tips |

---

## Carousel Konu Önerileri

| Gün | Tarz | Örnek Konular |
|-----|------|---------------|
| Salı | Eğitim | LoRaWAN 101, IoT Temelleri, Edge AI Başlangıç |
| Cumartesi | Showcase | Proje Örnekleri, Karşılaştırmalar, Faydalar |

---

## Carousel Kuralları

- Minimum 3, maksimum 7 slide
- Her slide max 30 kelime
- İlk slide dikkat çekici hook
- Son slide CTA içermeli ("Kaydet ve uygula!")
- Tutarlı görsel stili (aynı renk paleti)

---

## Konu Dağılımı (Haftalık Min)

| Kategori | Reels | Carousel | Post |
|----------|-------|----------|------|
| Tarım & Sera | 2 | 1/2 hafta | 1 |
| Enerji İzleme | 1 | - | 1/2 hafta |
| LoRaWAN | 2 | 1/2 hafta | 1 |
| Edge AI | 1 | 1/2 hafta | - |
| Kestirimci Bakım | 1 | - | 1/2 hafta |
| Endüstriyel IoT | 1 | - | 1/2 hafta |

---

## Teknik Notlar

### content_calendar Yapısı
- day_of_week: 0=Pazartesi, 6=Pazar
- visual_type_suggestion: "post" | "reels" | "carousel"
- platform: "instagram" | "facebook" | "both"

### OrchestratorAgent Haftalık Plan (Güncel)
```python
WEEKLY_SCHEDULE = [
    # Pazartesi - Hafta başı momentum
    {"day": 0, "time": "10:00", "type": "reels", "platform": "instagram"},
    {"day": 0, "time": "19:00", "type": "post", "platform": "both"},
    # Salı - Yoğun gün
    {"day": 1, "time": "10:00", "type": "reels", "platform": "instagram"},
    {"day": 1, "time": "19:00", "type": "carousel", "platform": "instagram"},
    # Çarşamba - Orta hafta
    {"day": 2, "time": "10:00", "type": "reels", "platform": "instagram"},
    {"day": 2, "time": "19:00", "type": "post", "platform": "both"},
    # Perşembe - Etkileşim zirvesi (çift Reels!)
    {"day": 3, "time": "10:00", "type": "reels", "platform": "instagram"},
    {"day": 3, "time": "19:00", "type": "reels", "platform": "instagram"},
    # Cuma - Hafta sonu öncesi
    {"day": 4, "time": "10:00", "type": "reels", "platform": "instagram"},
    {"day": 4, "time": "19:00", "type": "post", "platform": "both"},
    # Cumartesi - Rahat izleme
    {"day": 5, "time": "14:00", "type": "carousel", "platform": "instagram"},
    # Pazar - Hafta özeti
    {"day": 6, "time": "14:00", "type": "reels", "platform": "instagram"},
]
```

### İçerik Dağılımı
- Reels: 7 (%58) - Non-follower reach maksimizasyonu
- Carousel: 2 (%17) - Save rate artışı
- Post: 3 (%25) - Detaylı bilgi ve Facebook paylaşımı
