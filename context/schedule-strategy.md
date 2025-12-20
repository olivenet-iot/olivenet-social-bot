# Olivenet Zamanlama Stratejisi (Güncel)

## Genel Bakış

| Platform | Haftalık | Oran |
|----------|----------|------|
| Instagram Post | 5 | 42% |
| Instagram Reels | 5 | 42% |
| Instagram Carousel | 2 | 16% |
| Facebook | 3 | (Post'larla birlikte) |

---

## Haftalık Program

### Pazartesi
- 10:00 -> Post (Instagram + Facebook)
- 19:00 -> **Reels** (Instagram)

### Salı
- 10:00 -> **Reels** (Instagram)
- 19:00 -> Post (Instagram)

### Çarşamba
- 10:00 -> **Carousel** (Instagram)
- 19:00 -> Post (Instagram + Facebook)

### Perşembe
- 10:00 -> Post (Instagram)
- 19:00 -> **Reels** (Instagram)

### Cuma
- 10:00 -> **Reels** (Instagram)
- 19:00 -> Post (Instagram + Facebook)

### Cumartesi
- 14:00 -> **Carousel** (Instagram)

### Pazar
- 14:00 -> **Reels** (Instagram)

---

## Özet

- Toplam: 12 içerik/hafta
- 5 Reels (42%)
- 2 Carousel (17%)
- 5 Post (42%)

---

## Reels Konu Rotasyonu

| Gün | Saat | Tarz | Örnek Konular |
|-----|------|------|---------------|
| Pazartesi | 19:00 | Demo/Lifestyle | Tarım, Sera Otomasyonu |
| Salı | 10:00 | Teknik/Eğitim | LoRaWAN, Edge AI |
| Perşembe | 19:00 | Problem/Çözüm | Enerji, Kestirimci Bakım |
| Cuma | 10:00 | Ürün Tanıtım | IoT Platformları, Sensörler |
| Pazar | 14:00 | Hafta Özeti/Tips | Genel IoT, Sürdürülebilirlik |

---

## Carousel Konu Önerileri

| Gün | Tarz | Örnek Konular |
|-----|------|---------------|
| Çarşamba | Eğitim | LoRaWAN 101, IoT Temelleri, Edge AI Başlangıç |
| Cumartesi | Showcase | Proje Örnekleri, Karşılaştırmalar, Faydalar |

---

## Carousel Kuralları

- Minimum 3, maksimum 7 slide
- Her slide max 30 kelime
- İlk slide dikkat çekici hook
- Son slide CTA içermeli
- Tutarlı görsel stili (aynı renk paleti)

---

## Konu Dağılımı (Haftalık Min)

| Kategori | Min Post | Reels | Carousel |
|----------|----------|-------|----------|
| Tarım & Sera | 2 | 1/hafta | 1/2 hafta |
| Enerji İzleme | 1 | 1/2 hafta | - |
| LoRaWAN | 2 | 1/hafta | 1/2 hafta |
| Edge AI | 1 | 1/2 hafta | - |
| Kestirimci Bakım | 1 | 1/2 hafta | - |
| Endüstriyel IoT | 1 | 1/2 hafta | - |
| Veri Yönetimi | 1 | - | - |
| IoT Platformları | 1 | 1/3 hafta | - |
| IoT Güvenlik | 1 | - | - |
| Sürdürülebilirlik | 1 | 1/3 hafta | - |

---

## Teknik Notlar

### content_calendar Yapısı
- day_of_week: 0=Pazartesi, 6=Pazar
- visual_type_suggestion: "post" | "reels" | "carousel"
- platform: "instagram" | "facebook" | "both"

### OrchestratorAgent Haftalık Plan
```python
WEEKLY_SCHEDULE = [
    {"day": 0, "time": "10:00", "type": "post", "platform": "both"},
    {"day": 0, "time": "19:00", "type": "reels", "platform": "instagram"},
    {"day": 1, "time": "10:00", "type": "reels", "platform": "instagram"},
    {"day": 1, "time": "19:00", "type": "post", "platform": "instagram"},
    {"day": 2, "time": "10:00", "type": "carousel", "platform": "instagram"},
    {"day": 2, "time": "19:00", "type": "post", "platform": "both"},
    {"day": 3, "time": "10:00", "type": "post", "platform": "instagram"},
    {"day": 3, "time": "19:00", "type": "reels", "platform": "instagram"},
    {"day": 4, "time": "10:00", "type": "reels", "platform": "instagram"},
    {"day": 4, "time": "19:00", "type": "post", "platform": "both"},
    {"day": 5, "time": "14:00", "type": "carousel", "platform": "instagram"},
    {"day": 6, "time": "14:00", "type": "reels", "platform": "instagram"},
]
```
