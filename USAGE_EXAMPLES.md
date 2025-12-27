# Olivenet Social Bot - Kullanım Örnekleri

## İçindekiler

1. [Telegram Komutları](#telegram-komutları)
2. [Manuel İçerik Oluşturma](#manuel-i̇çerik-oluşturma)
3. [Video Reels](#video-reels)
4. [Sesli Reels (Voice)](#sesli-reels-voice)
5. [Carousel Oluşturma](#carousel-oluşturma)
6. [Analytics Çekme](#analytics-çekme)
7. [Python API Kullanımı](#python-api-kullanımı)

---

## Telegram Komutları

### Temel Komutlar

```
/start          - Bot'u başlat
/status         - Mevcut pipeline durumu
/next           - Sıradaki planlanmış içerik
/schedule       - Haftalık program
/sync           - Instagram metriklerini senkronize et
/stats          - Performans istatistikleri
/manual         - Manuel içerik oluşturma başlat
```

### Admin Komutları

```
/prompts        - Son video promptları
```

---

## Manuel İçerik Oluşturma

### Telegram'dan Adım Adım

1. **Konu Önerisi**
   ```
   /manual
   ```
   Bot konu önerir:
   ```
   📝 Konu Önerisi:
   "Sera sıcaklık takibi ile %30 enerji tasarrufu"

   Kategori: tarim
   Görsel: infographic

   [Onayla] [Başka Öner] [Düzenle] [İptal]
   ```

2. **İçerik Onayı**
   ```
   ✍️ Post Metni:

   Sera sıcaklığını sürekli izlemek neden önemli?

   🌡️ Akıllı sensörler ile:
   • Gerçek zamanlı sıcaklık takibi
   • Otomatik alarm sistemi
   • %30'a varan enerji tasarrufu

   Olivenet ile seranızı akıllandırın.

   [Onayla] [Yeniden Yaz] [Düzenle] [İptal]
   ```

3. **Görsel Onayı**
   ```
   🎨 Görsel hazır!

   [Görsel önizleme]

   [Yayınla] [Görsel Değiştir] [İptal]
   ```

4. **Yayınlama**
   ```
   ✅ Post yayınlandı!
   https://instagram.com/p/xxxxx
   ```

---

## Video Reels

### Telegram'dan Reels Oluşturma

```
/manual
```

Konu seçiminde "Reels" tipinde konu seçin. Sistem otomatik olarak:
1. Video prompt oluşturur
2. Sora/Veo ile video üretir
3. Cloudinary'ye yükler
4. Instagram'a Reels olarak paylaşır

### Python ile Reels

```python
from app.scheduler.pipeline import ContentPipeline

pipeline = ContentPipeline()

# Reels oluştur
await pipeline.run_reels_content(
    topic="Sera otomasyonu nasıl çalışır?",
    force_model="sora"  # veya "veo", "kling"
)
```

### Model Seçimi

| Model | Süre | Kalite | Kullanım |
|-------|------|--------|----------|
| Sora 2 | 4-12s | En yüksek | Sinematik içerik |
| Veo 3.1 | 4-8s | Yüksek | Hızlı üretim |
| Kling Pro | 5-10s | İyi | Alternatif |

---

## Sesli Reels (Voice)

### Özellikler

- ElevenLabs TTS ile Türkçe seslendirme
- Video ve ses senkronizasyonu
- Otomatik shot timing

### Python ile Voice Reels

```python
from app.scheduler.pipeline import ContentPipeline

pipeline = ContentPipeline()

# Sesli Reels oluştur
await pipeline.run_reels_voice_content(
    topic="IoT ile enerji tasarrufu",
    duration=12  # saniye
)
```

### Workflow

1. **Speech Script Üretimi**
   ```
   Creator: create_speech_script()
   → Türkçe voiceover metni
   ```

2. **Audio Üretimi**
   ```
   ElevenLabs: generate_speech()
   → MP3 dosyası
   ```

3. **Video Üretimi**
   ```
   Sora/Veo: generate_video()
   → Audio süresine sync edilmiş video
   ```

4. **Birleştirme**
   ```
   FFmpeg: merge_audio_video()
   → Final video
   ```

---

## Carousel Oluşturma

### Carousel Akışı

1. Claude Code slide HTML'leri oluşturur
2. Playwright her slide'ı PNG'ye render eder
3. imgbb'ye yüklenir
4. Instagram Carousel API ile paylaşılır

### Python ile Carousel

```python
from app.scheduler.pipeline import ContentPipeline

pipeline = ContentPipeline()

# Carousel oluştur
await pipeline.run_carousel_pipeline(
    topic="LoRaWAN Nedir? 5 Adımda Öğren",
    slide_count=6
)
```

### Slide Kuralları

- Minimum 3, maksimum 7 slide
- Her slide max 30 kelime
- İlk slide: Dikkat çekici hook
- Son slide: CTA ("Kaydet ve uygula!")

---

## Analytics Çekme

### Telegram'dan

```
/sync
```

Bot Instagram'dan metrikleri çeker ve veritabanını günceller.

### Python ile

```python
from app.agents.analytics import AnalyticsAgent
from app.insights_helper import get_instagram_reels_insights

# Agent ile
analytics = AnalyticsAgent()
await analytics.execute(action="fetch_analytics")

# Direkt API ile
insights = get_instagram_reels_insights(media_id="12345678")
print(insights)
# {
#     "plays": 1500,
#     "reach": 1200,
#     "saved": 45,
#     "shares": 12,
#     "likes": 89,
#     "comments": 5
# }
```

### Viral Skor Hesaplama

```python
from app.database.crud import calculate_viral_score

score = calculate_viral_score(
    saves=45,
    shares=12,
    engagement_rate=0.074,
    non_follower_pct=0.65
)
# score = (45/reach * 2) + (12/reach * 3) + 0.074 + (0.65 * 0.015)
```

---

## Python API Kullanımı

### Pipeline Oluşturma

```python
from app.scheduler.pipeline import ContentPipeline

# Pipeline instance
pipeline = ContentPipeline()

# Günlük içerik (Telegram onaylı)
await pipeline.run_daily_content()

# Otonom içerik (skor >= 7 ise otomatik yayın)
await pipeline.run_autonomous_content(min_score=7.0)

# A/B Test
await pipeline.run_ab_content(
    topic="Enerji tasarrufu",
    enable_ab=True
)
```

### Agent Kullanımı

```python
from app.agents.planner import PlannerAgent
from app.agents.creator import CreatorAgent
from app.agents.reviewer import ReviewerAgent

# Planner
planner = PlannerAgent()
topic = await planner.suggest_topic()
print(topic)
# {
#     "topic": "Sera sıcaklık takibi",
#     "category": "tarim",
#     "visual_type": "reels",
#     "suggested_hooks": ["question", "statistic"]
# }

# Creator
creator = CreatorAgent()
post = await creator.create_post(
    topic="Sera sıcaklık takibi",
    category="tarim",
    hooks=["question"]
)
print(post["post_text"])

# Reviewer
reviewer = ReviewerAgent()
review = await reviewer.review_post(post["post_text"], topic)
print(review["score"])  # 7.5
print(review["approved"])  # True
```

### Video Üretimi

```python
from app.sora_helper import generate_video_sora
from app.veo_helper import generate_video_veo3
from app.fal_helper import FalVideoGenerator

# Sora
result = generate_video_sora(
    prompt="A modern greenhouse with IoT sensors...",
    duration=8,
    model="sora-2"
)

# Veo
result = generate_video_veo3(
    prompt="Smart farming technology...",
    duration_seconds=8
)

# Kling (fal.ai)
generator = FalVideoGenerator()
result = await generator.generate_video(
    prompt="Industrial IoT dashboard...",
    model="kling_pro",
    duration=5
)
```

### TTS (Sesli İçerik)

```python
from app.elevenlabs_helper import ElevenLabsHelper

tts = ElevenLabsHelper()

result = await tts.generate_speech(
    text="Merhaba, bugün sera otomasyonundan bahsedeceğiz.",
    speed=1.0
)

print(result)
# {
#     "success": True,
#     "audio_path": "/opt/olivenet-social-bot/outputs/audio/speech_123.mp3",
#     "duration_seconds": 4.5
# }
```

### Görsel Üretimi

```python
from app.flux_helper import generate_image_flux
from app.gemini_helper import generate_realistic_image

# FLUX
image_path = generate_image_flux(
    prompt="Modern IoT dashboard with green theme...",
    width=1080,
    height=1080
)

# Gemini
image_path = await generate_realistic_image(
    topic="Sera otomasyonu",
    post_text="Akıllı sera sistemleri..."
)
```

---

## Scheduler Kullanımı

### Zamanlanmış Görevler

```python
from app.scheduler.scheduler import ContentScheduler, ScheduledTask

scheduler = ContentScheduler()

# Günlük görev ekle
scheduler.add_task(
    ScheduledTask(
        name="morning_reels",
        hour=10,
        minute=0,
        days=[0, 1, 2, 3, 4],  # Pazartesi-Cuma
        callback=pipeline.run_reels_content
    )
)

# Scheduler'ı başlat
await scheduler.run_schedule_loop()
```

### Calendar-Based Publishing

```python
from app.scheduler.scheduler import check_calendar_and_publish

# Takvimden yayınla
await check_calendar_and_publish()
```

---

## Hook Performance Analizi

```python
from app.database.crud import get_hook_performance

# En iyi hookları al
hooks = get_hook_performance(platform="instagram", limit=5)
for hook in hooks:
    print(f"{hook['hook_type']}: viral_score={hook['viral_score']:.2f}")

# Örnek çıktı:
# question: viral_score=12.45
# statistic: viral_score=11.23
# bold_claim: viral_score=10.87
```

---

## Hata Yönetimi

```python
from app.scheduler.pipeline import ContentPipeline

pipeline = ContentPipeline()

try:
    await pipeline.run_reels_content(topic="Test")
except Exception as e:
    print(f"Hata: {e}")
    # Fallback: Farklı model dene
    await pipeline.run_reels_content(topic="Test", force_model="veo")
```
