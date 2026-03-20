# Olivenet Social Bot - Kullanım Örnekleri

## İçindekiler

1. [Telegram Komutları](#telegram-komutları)
2. [Manuel İçerik Oluşturma](#manuel-i̇çerik-oluşturma)
3. [Brain Agent & Feed System](#brain-agent--feed-system)
4. [Video Reels](#video-reels)
5. [Sesli Reels (Voice)](#sesli-reels-voice)
6. [Carousel Oluşturma](#carousel-oluşturma)
7. [Analytics Çekme](#analytics-çekme)
8. [Python API Kullanımı](#python-api-kullanımı)

---

## Telegram Komutları

### v1 Komutlar

```
/start          - Bot'u başlat
/status         - Mevcut pipeline durumu
/next           - Sıradaki planlanmış içerik
/schedule       - Haftalık program
/sync           - Instagram metriklerini senkronize et
/stats          - Performans istatistikleri
/manual         - Manuel içerik oluşturma başlat
/prompts        - Son video promptları
```

### v2 Komutlar

```
/pool           - İçerik fırsat havuzu durumu
/brain          - Brain Agent son kararları ve durumu
/feeds          - Feed aggregator durumu
/pause          - Sistemi duraklat (Brain + üretim)
/resume         - Sistemi devam ettir
/force          - Belirli fırsatı hemen üret
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
   Konu Önerisi:
   "Sera sıcaklık takibi ile %30 enerji tasarrufu"

   Kategori: tarim
   Görsel: infographic

   [Onayla] [Başka Öner] [Düzenle] [İptal]
   ```

2. **İçerik Onayı** — Post metni gösterilir
3. **Görsel Onayı** — Görsel önizleme
4. **Yayınlama** — Instagram'a paylaşılır

---

## Brain Agent & Feed System

### Feed Durumunu Kontrol Et

Telegram'da:
```
/feeds
```
Yanıt: aktif feed sayısı, son fetch zamanı, hata durumu

### İçerik Havuzunu Görüntüle

```
/pool
```
Yanıt: aktif fırsat sayısı, status dağılımı, en yüksek skorlu fırsatlar

### Brain Agent Kararlarını İzle

```
/brain
```
Yanıt: son 5 karar (produce/wait), seçilen fırsat, model ve stil bilgisi

### Sistemi Duraklat/Devam Ettir

```
/pause    — Brain Agent ve üretim duraklar
/resume   — Sistem devam eder
```

### Belirli Fırsatı Hemen Üret

```
/force
```
Bot fırsat listesi gösterir → Seçim yapılır → Üretim başlar

### Python ile Brain Agent

```python
from app.agents.brain import BrainAgent

brain = BrainAgent()

# Karar al
decision = await brain.decide()
# {"action": "produce", "reason": "...", "opportunity_id": 42,
#  "content_type": "reels", "model_id": "kling-3.0-pro",
#  "visual_style": "cinematic_4k", "hook_type": "question"}

# Son kararları al (Telegram /brain için)
decisions = brain.get_last_decisions(limit=5)

# Belirli fırsatı hemen üret
result = await brain.force_produce(opp_id=42, content_type="reels")
```

### Python ile Feed Aggregator

```python
from app.sources.feed_aggregator import FeedAggregator

aggregator = FeedAggregator()
result = await aggregator.run_feed_pipeline()
# RSS fetch → enrich → score → pool
```

---

## Video Reels

### Telegram'dan Reels Oluşturma

```
/manual
```
Konu seçiminde "Reels" tipinde konu seçin.

### Video Modelleri (4 model)

| Model | Süre | Özellik | Kullanım |
|-------|------|---------|----------|
| sora-2 | 4/8/12s | Yüksek kalite | Sinematik içerik |
| sora-2-pro | 4/8/12s | Native speech | Conversational reels |
| veo-3.1 | 4/6/8s | Native audio + lip-sync | Doğa sahneleri |
| kling-3.0-pro | 5/10/15s | Hızlı, fizik tabanlı | Endüstriyel, haber |

### Python ile Video Üretimi

```python
# Sora
from app.sora_helper import generate_video_sora
result = await generate_video_sora(
    prompt="A modern greenhouse with IoT sensors...",
    duration=8,
    model="sora-2"
)

# Veo
from app.veo_helper import generate_video_veo3
result = await generate_video_veo3(
    prompt="Smart farming technology...",
    duration_seconds=8
)

# Kling Direct API
from app.kling_helper import KlingHelper
kling = KlingHelper()
result = await kling.generate_video(
    prompt="Industrial IoT dashboard...",
    duration=10,
    model_name="kling-v3",
    generate_audio=True
)
```

### Model Yönetimi

```python
from app.video_models import get_model_config, validate_duration, get_available_models

models = get_available_models()
# ["sora-2", "sora-2-pro", "veo-3.1", "kling-3.0-pro"]

config = get_model_config("kling-3.0-pro")
# {name, provider, durations, max_duration, ...}

duration = validate_duration("kling-3.0-pro", 20)  # -> 15 (clamped)
```

---

## Sesli Reels (Voice)

### Özellikler

- ElevenLabs TTS ile Türkçe seslendirme
- Video ve ses senkronizasyonu
- Otomatik shot timing
- 5 farklı ses (erkek, kadın, narrator, cartoon erkek/kadın)

### Python ile Voice Reels

```python
# v2 Production Pipeline
from app.production.voice_reels_pipeline import VoiceReelsPipeline

pipeline = VoiceReelsPipeline()
result = await pipeline.run(
    topic="IoT ile enerji tasarrufu",
    model_id="sora-2-pro"
)
```

### TTS Kullanımı

```python
from app.elevenlabs_helper import ElevenLabsHelper

tts = ElevenLabsHelper()
result = await tts.generate_speech(
    text="Merhaba, bugün sera otomasyonundan bahsedeceğiz.",
    speed=1.0
)
# {"success": True, "audio_path": "...", "duration_seconds": 4.5}
```

---

## Carousel Oluşturma

### Carousel Akışı (v2)

1. Nano Banana (Gemini 3 Pro Image) slide görselleri üretir
2. imgbb'ye yüklenir
3. Instagram Carousel API ile paylaşılır

### Python ile Carousel

```python
# v2 Production Pipeline
from app.production.carousel_pipeline import CarouselPipeline

pipeline = CarouselPipeline()
result = await pipeline.run(
    topic="LoRaWAN Nedir? 5 Adımda Öğren",
    carousel_type="nano_banana",
    carousel_style="tech_blue",      # tech_blue, energy_green, warm_industrial, dark_premium, clean_minimal
    carousel_layout="storytelling",   # data_heavy, storytelling, comparison, step_by_step, tips_list
    slide_count=5
)
```

### Slide Kuralları

- Minimum 4, maksimum 8 slide
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
# {"plays": 1500, "reach": 1200, "saved": 45, "shares": 12}
```

---

## Python API Kullanımı

### v2 Production Pipeline'ları

```python
from app.production.reels_pipeline import ReelsPipeline
from app.production.news_reels_pipeline import NewsReelsPipeline
from app.production.post_pipeline import PostPipeline
from app.production.conversational_pipeline import ConversationalPipeline

# Reels
reels = ReelsPipeline()
result = await reels.run(topic="Sera otomasyonu", force_model="kling-3.0-pro")

# News Reels (opportunity bazlı)
news = NewsReelsPipeline()
result = await news.run(opportunity=opp_dict, autonomous=True, model_id="kling-3.0-pro")

# Post
post = PostPipeline()
result = await post.run(topic="IoT sensör teknolojileri")

# Conversational
conv = ConversationalPipeline()
result = await conv.run(topic="AI ve tarım", model_id="sora-2-pro")
```

### v1 Pipeline (hala aktif)

```python
from app.scheduler.pipeline import ContentPipeline

pipeline = ContentPipeline()

# Günlük içerik (Telegram onaylı)
await pipeline.run_daily_content()

# Otonom içerik (skor >= 7 ise otomatik yayın)
await pipeline.run_autonomous_content(min_score=7.0)
```

### Agent Kullanımı

```python
from app.agents.planner import PlannerAgent
from app.agents.creator import CreatorAgent
from app.agents.reviewer import ReviewerAgent

# Planner
planner = PlannerAgent()
topic = await planner.suggest_topic()
# {"topic": "Sera sıcaklık takibi", "category": "tarim", "visual_type": "reels"}

# Creator
creator = CreatorAgent()
post = await creator.create_post(topic="Sera sıcaklık takibi", category="tarim")

# Reviewer
reviewer = ReviewerAgent()
review = await reviewer.review_post(post["post_text"], topic)
# {"score": 7.5, "approved": True}
```

### Görsel Üretimi

```python
# FLUX (fotorealistik)
from app.flux_helper import generate_image_flux
image_path = generate_image_flux(
    prompt="Modern IoT dashboard with green theme...",
    width=1080,
    height=1080
)

# Nano Banana (infographic — Gemini 3 Pro Image)
from app.nano_banana_helper import generate_infographic
result = await generate_infographic(topic="IoT sensörler", post_text="...")
# {"success": True, "image_path": "..."}
```

---

## Scheduler Kullanımı

### v2 Scheduler

```python
from app.engine.scheduler import V2Scheduler

scheduler = V2Scheduler(brain_agent=brain, feed_aggregator=aggregator, event_bus=bus)
await scheduler.start()
# Feed loop (30m) + Brain loop (120m) + Expiry loop (6h) + Analytics (24h)
```

### v1 Scheduler

```python
from app.scheduler.scheduler import ContentScheduler, ScheduledTask

scheduler = ContentScheduler()
scheduler.add_task(
    ScheduledTask(
        name="morning_reels",
        hour=10,
        minute=0,
        days=[0, 1, 2, 3, 4],
        callback=pipeline.run_reels_content
    )
)
await scheduler.run_schedule_loop()
```

---

## Hook Performance Analizi

```python
from app.database.crud import get_hook_performance

hooks = get_hook_performance(platform="instagram", limit=5)
for hook in hooks:
    print(f"{hook['hook_type']}: viral_score={hook['viral_score']:.2f}")
```
