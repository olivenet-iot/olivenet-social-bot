# Olivenet Social Bot - Mimari Dokümantasyon (v2)

## Sistem Genel Bakış

Olivenet Social Bot v2, 3 katmanlı otonom içerik üretim sistemidir: Kaynaklar → Brain → Üretim.

```
┌──────────────────────────────────────────────────────────────────┐
│                     1. KAYNAKLAR (Sources)                        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  10 RSS Feed (IoT Now, RAKwireless, Hackaday, LoRa,     │    │
│  │  Embedded, TechCrunch AI, MIT Tech, CleanTechnica,       │    │
│  │  Renewable Energy, AgFunder)                              │    │
│  └────────────────────────┬─────────────────────────────────┘    │
│                           │                                       │
│  ┌────────────────────────▼─────────────────────────────────┐    │
│  │  FeedAggregator → enrich → score → content_opportunities │    │
│  │  (Her 30 dakikada bir, max 200 aktif fırsat)             │    │
│  └────────────────────────┬─────────────────────────────────┘    │
└───────────────────────────┼──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│                     2. BRAIN AGENT                                │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  BrainAgent.decide() — Her 2 saatte bir çalışır          │    │
│  │  1. SystemState'den durum topla                           │    │
│  │  2. Quick checks (gece, min interval, havuz)              │    │
│  │  3. Claude API ile karar: produce / wait                  │    │
│  │  4. Creative params: model, style, hook, carousel         │    │
│  └────────────────────────┬─────────────────────────────────┘    │
│                           │                                       │
│  ┌────────────────────────┤                                      │
│  │ V2Scheduler            │ EventBus (pub/sub)                   │
│  │ • feed_loop (30m)      │ SystemState (production tracking)    │
│  │ • brain_loop (120m)    │                                      │
│  │ • expiry_loop (6h)     │                                      │
│  │ • analytics_loop (24h) │                                      │
│  └────────────────────────┘                                      │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│                     3. PRODUCTION                                 │
│                                                                   │
│  ┌──────────┬──────────┬──────────┬───────────┬─────────────┐    │
│  │   post   │  reels   │ carousel │voice_reels│  long_video │    │
│  └──────────┴──────────┴──────────┴───────────┴─────────────┘    │
│  ┌──────────┬──────────────────┐                                 │
│  │news_reels│  conversational  │                                 │
│  └──────────┴──────────────────┘                                 │
│                           │                                       │
│  ┌────────────────────────┼─────────────────────────────────┐    │
│  │ Agents: Creator → Reviewer → Publisher → Analytics       │    │
│  └────────────────────────┼─────────────────────────────────┘    │
│                           │                                       │
│  ┌────────────────────────┼─────────────────────────────────┐    │
│  │ AI Services: Sora │ Veo │ Kling │ FLUX │ Nano Banana     │    │
│  │              OpenAI TTS │ Cloudinary │ Instagram API      │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT (14 komut)                        │
│  v1: /start /status /manual /stats /next /schedule /sync /prompts│
│  v2: /pool /brain /feeds /pause /resume /force                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Dizin Yapısı

```
/opt/olivenet-social-bot/
├── app/                              # Ana uygulama kodu
│   ├── agents/                       # 8 AI agent
│   │   ├── base_agent.py             # Temel agent sınıfı
│   │   ├── brain.py                  # Brain Agent (otonom karar motoru)
│   │   ├── orchestrator.py           # Koordinatör agent
│   │   ├── planner.py                # Planlama agent
│   │   ├── creator.py                # İçerik oluşturma agent
│   │   ├── reviewer.py               # Kalite kontrol agent
│   │   ├── publisher.py              # Yayınlama agent
│   │   └── analytics.py              # Analiz agent
│   │
│   ├── engine/                       # v2 Engine Layer
│   │   ├── scheduler.py              # V2Scheduler (feed + brain döngüleri)
│   │   ├── state.py                  # SystemState (production tracking)
│   │   └── event_bus.py              # EventBus (async pub/sub)
│   │
│   ├── production/                   # 7 Production Pipeline
│   │   ├── base_pipeline.py          # BasePipeline temel sınıf
│   │   ├── post_pipeline.py          # Tekli post
│   │   ├── reels_pipeline.py         # Video reels
│   │   ├── carousel_pipeline.py      # Çoklu görsel carousel
│   │   ├── voice_reels_pipeline.py   # Sesli reels (TTS)
│   │   ├── long_video_pipeline.py    # Uzun video
│   │   ├── news_reels_pipeline.py    # Haber reels
│   │   └── conversational_pipeline.py # Diyalog reels
│   │
│   ├── sources/                      # Feed System
│   │   ├── feed_aggregator.py        # RSS → enrich → score → pool
│   │   └── feed_config.py            # 10 RSS feed tanımları
│   │
│   ├── database/                     # Veritabanı katmanı
│   │   ├── models.py                 # SQLite şeması ve init (12 tablo)
│   │   └── crud.py                   # CRUD işlemleri
│   │
│   ├── scheduler/                    # v1 Pipeline (paralel çalışır)
│   │   ├── pipeline.py               # İçerik pipeline
│   │   └── scheduler.py              # Görev zamanlayıcı
│   │
│   ├── utils/                        # Yardımcı araçlar
│   │   └── logger.py                 # Loglama sistemi
│   │
│   ├── validators/                   # Doğrulama
│   │   └── text_validator.py         # Metin doğrulama
│   │
│   ├── main.py                       # v2 entry point
│   ├── config.py                     # Konfigürasyon yönetimi
│   ├── telegram_pipeline.py          # Telegram bot (14 komut)
│   ├── kling_helper.py               # Kling Direct API (JWT auth)
│   ├── nano_banana_helper.py         # fal.ai nano-banana-pro infographic
│   ├── video_models.py               # 4 video model konfigürasyonu
│   ├── video_styles.py               # 10 görsel stil
│   ├── sora_helper.py                # OpenAI Sora video
│   ├── veo_helper.py                 # Google Veo video
│   ├── flux_helper.py                # FLUX.2 Pro görsel
│   ├── openai_tts_helper.py          # OpenAI TTS
│   ├── cloudinary_helper.py          # Video CDN
│   ├── instagram_helper.py           # Instagram Graph API
│   ├── insights_helper.py            # Instagram Insights
│   ├── meta_ads_helper.py            # Meta Ads API
│   ├── claude_helper.py              # Claude Code CLI
│   └── renderer.py                   # HTML→PNG render (carousel slide)
│
├── context/                          # AI context dosyaları
│   ├── company-profile.md
│   ├── content-strategy.md
│   ├── topics.md
│   ├── schedule-strategy.md
│   ├── visual-guidelines.md
│   ├── reels-prompts.md
│   └── agent-personas/              # Agent kişilikleri
│
├── data/                             # Veritabanı
│   └── content.db                    # SQLite (12 tablo)
│
├── outputs/                          # Üretilen içerikler
│   ├── images/
│   ├── videos/
│   └── audio/
│
└── logs/                             # Uygulama logları
```

---

## v2 Engine Layer

### V2Scheduler

Feed ve Brain döngülerini yönetir. v1 scheduler ile paralel çalışır.

```
Feed Loop (30m):   RSS fetch → enrich → score → pool
Brain Loop (120m): SystemState → quick checks → Claude API → produce/wait
Expiry Loop (6h):  72 saatten eski fırsatları temizle
Analytics (24h):   Prediction accuracy kontrolü
```

### SystemState

```python
state.is_paused                    # Sistem duraklatılmış mı?
state.is_production_active()       # Aktif üretim var mı?
state.get_full_state()             # Tüm durum (Brain karar verisi)
state.register_production(key)     # Üretim başlat
state.complete_production(key, t)  # Üretim tamamla
```

### EventBus

Bileşenler arası loose coupling için async pub/sub.

```python
bus.subscribe("brain_decision", callback)
await bus.publish("feed_updated", data)
```

---

## Multi-Agent Sistemi (8 Agent)

### Agent Hiyerarşisi

```
                    ┌─────────────────────┐
                    │    BRAIN AGENT      │
                    │  (Otonom Karar)     │
                    └─────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐     ┌───────▼───────┐     ┌───────▼───────┐
│    PLANNER    │     │    CREATOR    │     │   REVIEWER    │
│  (Planlayıcı) │     │  (Oluşturucu) │     │   (Denetçi)   │
└───────────────┘     └───────┬───────┘     └───────────────┘
                              │
                      ┌───────▼───────┐
                      │   PUBLISHER   │
                      │   (Yayıncı)   │
                      └───────┬───────┘
                              │
                      ┌───────▼───────┐
                      │   ANALYTICS   │
                      │   (Analitik)  │
                      └───────────────┘
```

### Agent Detayları

| Agent | Dosya | Görev | Ana Metodlar |
|-------|-------|-------|--------------|
| **BrainAgent** | `brain.py` | Otonom karar, 2h döngü | `decide()`, `force_produce()`, `trigger_production()` |
| **Orchestrator** | `orchestrator.py` | Haftalık plan, strateji | `plan_week()`, `daily_check()` |
| **Planner** | `planner.py` | Konu seçimi, hook önerisi | `suggest_topic()`, `get_top_topics()` |
| **Creator** | `creator.py` | İçerik üretimi | `create_post()`, `create_reels_prompt()` |
| **Reviewer** | `reviewer.py` | Kalite kontrol | `review_post()`, `final_approval()` |
| **Publisher** | `publisher.py` | Yayınlama | `publish()`, `publish_carousel()` |
| **Analytics** | `analytics.py` | Metrik analizi | `fetch_analytics()`, `calculate_viral_score()` |

---

## Content Opportunity Lifecycle

```
RSS Feed → FeedAggregator
                │
          ┌─────▼─────┐
          │ discovered │ (ham haber)
          └─────┬─────┘
                │
          ┌─────▼─────┐
          │  enriched  │ (Olivenet angle, özet)
          └─────┬─────┘
                │
          ┌─────▼─────┐
          │   scored   │ (relevance + timeliness + virality)
          └─────┬─────┘
                │
          ┌─────▼─────┐
          │   ready    │ (Brain Agent havuzu)
          └─────┬─────┘
           │         │
     ┌─────▼──┐ ┌────▼────┐
     │selected│ │ expired │ (72h)
     └────┬───┘ └─────────┘
          │
     ┌────▼─────┐
     │producing │
     └────┬─────┘
          │
     ┌────▼─────┐
     │   used   │
     └──────────┘
```

---

## Production Pipelines (7 pipeline)

| Pipeline | Dosya | Default Model | Açıklama |
|----------|-------|---------------|----------|
| post | `post_pipeline.py` | - | Tekli post |
| reels | `reels_pipeline.py` | kling-3.0-pro | Video reels |
| carousel | `carousel_pipeline.py` | - | Nano Banana infographic |
| voice_reels | `voice_reels_pipeline.py` | sora-2-pro | TTS sesli video |
| long_video | `long_video_pipeline.py` | kling-3.0-pro | Uzun video |
| news_reels | `news_reels_pipeline.py` | kling-3.0-pro | Haber reels |
| conversational | `conversational_pipeline.py` | sora-2-pro | Diyalog reels |

---

## v1 Pipeline (paralel çalışır)

v1 pipeline hala aktiftir ve v2 ile paralel çalışır.

### Pipeline Türleri

| Pipeline | Fonksiyon | Açıklama |
|----------|-----------|----------|
| **Daily** | `run_daily_content()` | Telegram onaylı günlük içerik |
| **Autonomous** | `run_autonomous_content()` | Tam otomatik (skor >= 7) |
| **Reels** | `run_reels_content()` | Video içerik |
| **Voice Reels** | `run_reels_voice_content()` | Sesli video |
| **Carousel** | `run_carousel_pipeline()` | Çoklu görsel |

---

## API Entegrasyon Haritası

```
┌─────────────────────────────────────────────────────────────┐
│                     OLIVENET SOCIAL BOT v2                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────────┐
    │                         │                             │
┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│ SORA  │ │ VEO   │ │ KLING │ │ FLUX  │ │ NANO  │ │ELEVEN │
│ VIDEO │ │ VIDEO │ │DIRECT │ │ IMAGE │ │BANANA │ │  TTS  │
└───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘
    │         │         │         │         │         │
    └─────────┴─────────┴────┬────┴─────────┴─────────┘
                             │
                    ┌────────▼────────┐
                    │   CLOUDINARY    │
                    │   (Video CDN)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    INSTAGRAM    │
                    │   Graph API     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   META ADS      │
                    │   (Insights)    │
                    └─────────────────┘
```

---

## Veri Akışı

### İçerik Yaşam Döngüsü

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  DRAFT  │ ─► │SCHEDULED│ ─► │APPROVED │ ─► │PUBLISHED│
└─────────┘    └─────────┘    └─────────┘    └─────────┘
     │                             │
     └──────────┬──────────────────┘
                │
           ┌────▼────┐
           │REJECTED │
           └─────────┘
```

---

## System Startup

```python
# python3 app/main.py
async def main():
    # 1. Database init
    # 2. EventBus oluştur
    # 3. v2: FeedAggregator + BrainAgent + V2Scheduler
    # 4. v1: ContentPipeline + Scheduler (paralel)
    # 5. Telegram bot başlat (brain + aggregator global set)
    await asyncio.gather(telegram_main(), v2_scheduler.start())
```

**Not:** BrainAgent doğrudan `app/agents/brain.py`'den import edilir, `agents/__init__.py` üzerinden değil.

---

## Teknoloji Stack

| Kategori | Teknoloji |
|----------|-----------|
| **Dil** | Python 3.10+ |
| **Veritabanı** | SQLite (12 tablo) |
| **Bot** | python-telegram-bot |
| **HTTP** | httpx (async) |
| **AI** | Claude Code CLI, OpenAI, Google Gemini |
| **Video** | Sora 2/Pro, Veo 3.1, Kling 3.0 Pro (Direct API) |
| **Görsel** | FLUX.2 Pro, Nano Banana (fal-ai/nano-banana-pro) |
| **TTS** | OpenAI TTS (Türkçe, gpt-4o-mini-tts) |
| **CDN** | Cloudinary, imgbb |
| **Render** | Playwright (HTML→PNG, carousel slide) |

---

## İlgili Dokümantasyon

- [DATABASE.md](DATABASE.md) - Veritabanı şeması (12 tablo)
- [API_INTEGRATIONS.md](API_INTEGRATIONS.md) - API detayları
- [CONFIGURATION.md](CONFIGURATION.md) - Konfigürasyon rehberi
- [QUICKSTART.md](QUICKSTART.md) - Hızlı başlangıç
