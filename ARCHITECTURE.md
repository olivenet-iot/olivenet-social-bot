# Olivenet Social Bot - Mimari Dokümantasyon

## Sistem Genel Bakış

Olivenet Social Bot, yapay zeka destekli sosyal medya içerik otomasyonu sistemidir. Multi-agent mimarisi ile içerik planlama, oluşturma, inceleme ve yayınlama süreçlerini yönetir.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT ARAYÜZÜ                          │
│  Komutlar: /start, /next, /status, /schedule, /sync, /stats     │
└──────────────────────┬──────────────────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
    [Onay Butonları]          [Komut İşleyiciler]
         │                            │
┌────────▼────────────────────────────▼────────────────────────────┐
│                    CONTENT PIPELINE                               │
│  Durumlar: IDLE → PLANNING → CREATING → REVIEWING → PUBLISHING   │
└──────────────────────┬───────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────────────┐
        │                                     │
┌───────▼──────────┐              ┌──────────▼─────────┐
│   AGENT KATMANI  │              │   HELPER KATMANI   │
│                  │              │                    │
│ • Orchestrator   │              │ • Claude Helper    │
│ • Planner        │──────────────│ • Instagram API    │
│ • Creator        │              │ • Sora/Veo/Kling   │
│ • Reviewer       │              │ • FLUX/Gemini      │
│ • Publisher      │              │ • ElevenLabs       │
│ • Analytics      │              │ • Cloudinary       │
│                  │              │ • Meta Ads         │
└──────────────────┘              └────────┬───────────┘
        │                                  │
        └──────────────────┬───────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼────┐      ┌──────▼──────┐   ┌──────▼──────┐
│  SCHEDULER │      │  DATABASE   │   │ EXTERNAL API│
│            │      │             │   │             │
│ • Tasks    │      │ • SQLite    │   │ • OpenAI    │
│ • Timing   │      │ • Posts     │   │ • Google    │
│ • Calendar │      │ • Analytics │   │ • Meta      │
│            │      │ • Strategy  │   │ • ElevenLabs│
└────────────┘      │ • Hooks     │   └─────────────┘
                    │ • Prompts   │
                    └─────────────┘
```

---

## Dizin Yapısı

```
/opt/olivenet-social-bot/
├── app/                          # Ana uygulama kodu
│   ├── agents/                   # Multi-agent sistemi
│   │   ├── base_agent.py         # Temel agent sınıfı
│   │   ├── orchestrator.py       # Koordinatör agent
│   │   ├── planner.py            # Planlama agent
│   │   ├── creator.py            # İçerik oluşturma agent
│   │   ├── reviewer.py           # Kalite kontrol agent
│   │   ├── publisher.py          # Yayınlama agent
│   │   └── analytics.py          # Analiz agent
│   │
│   ├── database/                 # Veritabanı katmanı
│   │   ├── models.py             # SQLite şeması ve init
│   │   └── crud.py               # CRUD işlemleri
│   │
│   ├── scheduler/                # Zamanlama ve pipeline
│   │   ├── pipeline.py           # İçerik pipeline (2200+ satır)
│   │   └── scheduler.py          # Görev zamanlayıcı
│   │
│   ├── utils/                    # Yardımcı araçlar
│   │   └── logger.py             # Loglama sistemi
│   │
│   ├── validators/               # Doğrulama
│   │   └── text_validator.py     # Metin doğrulama
│   │
│   ├── config.py                 # Konfigürasyon yönetimi
│   ├── claude_helper.py          # Claude Code CLI entegrasyonu
│   ├── instagram_helper.py       # Instagram Graph API
│   ├── sora_helper.py            # OpenAI Sora video
│   ├── veo_helper.py             # Google Veo video
│   ├── fal_helper.py             # Kling AI video (fal.ai)
│   ├── flux_helper.py            # FLUX.2 Pro görsel
│   ├── gemini_helper.py          # Gemini görsel
│   ├── elevenlabs_helper.py      # ElevenLabs TTS
│   ├── cloudinary_helper.py      # Video CDN
│   ├── insights_helper.py        # Instagram Insights
│   ├── meta_ads_helper.py        # Meta Ads API
│   ├── telegram_pipeline.py      # Telegram bot
│   └── renderer.py               # HTML→PNG render
│
├── context/                      # AI context dosyaları
│   ├── company-profile.md        # Şirket bilgisi
│   ├── content-strategy.md       # İçerik stratejisi
│   ├── topics.md                 # Konu havuzu
│   ├── schedule-strategy.md      # Zamanlama stratejisi
│   ├── visual-guidelines.md      # Görsel rehber
│   ├── reels-prompts.md          # Video prompt rehberi
│   └── agent-personas/           # Agent kişilikleri
│
├── templates/                    # HTML şablonları
│   ├── dashboard-infographic.html
│   ├── big-number-infographic.html
│   └── ... (11 şablon)
│
├── data/                         # Veritabanı
│   └── content.db                # SQLite veritabanı
│
├── outputs/                      # Üretilen içerikler
│   ├── images/
│   ├── videos/
│   └── audio/
│
└── logs/                         # Uygulama logları
```

---

## Multi-Agent Sistemi

### Agent Hiyerarşisi

```
                    ┌─────────────────────┐
                    │   ORCHESTRATOR      │
                    │   (Koordinatör)     │
                    └─────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐     ┌───────▼───────┐     ┌───────▼───────┐
│    PLANNER    │     │    CREATOR    │     │   REVIEWER    │
│  (Planlayıcı) │     │  (Oluşturucu) │     │   (Denetçi)   │
└───────────────┘     └───────────────┘     └───────────────┘
                              │
                      ┌───────▼───────┐
                      │   PUBLISHER   │
                      │   (Yayıncı)   │
                      └───────────────┘
                              │
                      ┌───────▼───────┐
                      │   ANALYTICS   │
                      │   (Analitik)  │
                      └───────────────┘
```

### Agent Detayları

| Agent | Dosya | Görev | Ana Metodlar |
|-------|-------|-------|--------------|
| **Orchestrator** | `orchestrator.py` | Haftalık plan, strateji | `plan_week()`, `daily_check()` |
| **Planner** | `planner.py` | Konu seçimi, hook önerisi | `suggest_topic()`, `get_top_topics()` |
| **Creator** | `creator.py` | İçerik üretimi | `create_post()`, `create_reels_prompt()` |
| **Reviewer** | `reviewer.py` | Kalite kontrol | `review_post()`, `final_approval()` |
| **Publisher** | `publisher.py` | Yayınlama | `publish()`, `publish_carousel()` |
| **Analytics** | `analytics.py` | Metrik analizi | `fetch_analytics()`, `calculate_viral_score()` |

---

## Content Pipeline

### Pipeline Durumları

```
IDLE → PLANNING → CREATING_CONTENT → CREATING_VISUAL →
AWAITING_REVIEW → AWAITING_APPROVAL → PUBLISHING → COMPLETED
```

### Pipeline Türleri

| Pipeline | Fonksiyon | Açıklama |
|----------|-----------|----------|
| **Daily** | `run_daily_content()` | Telegram onaylı günlük içerik |
| **Autonomous** | `run_autonomous_content()` | Tam otomatik (skor >= 7) |
| **Reels** | `run_reels_content()` | Video içerik |
| **Voice Reels** | `run_reels_voice_content()` | Sesli video (ElevenLabs TTS) |
| **Carousel** | `run_carousel_pipeline()` | Çoklu görsel |
| **A/B Test** | `run_ab_content()` | Varyant karşılaştırma |

### Daily Pipeline Akışı

```
1. TOPIC SUGGESTION (Planner)
   └─ Telegram: [Onayla] [Başka Öner] [Düzenle]

2. CONTENT CREATION (Creator)
   └─ Telegram: [Onayla] [Yeniden Yaz] [Düzenle]

3. VISUAL PROMPT (Creator)
   └─ Prompt oluşturma

4. VISUAL GENERATION
   ├─ Infographic → HTML Template + Playwright
   ├─ FLUX → Replicate API
   ├─ Gemini → Google API
   ├─ Reels → Sora/Veo/Kling
   └─ Carousel → Multi-slide HTML

5. REVIEW (Reviewer)
   └─ Skor >= 7.0 → Onay
   └─ Skor < 5.0 → Red
   └─ Arada → Revizyon

6. FINAL APPROVAL
   └─ Telegram: [Yayınla] [Değiştir] [İptal]

7. PUBLISHING (Publisher)
   └─ Instagram Graph API
```

---

## API Entegrasyon Haritası

```
┌─────────────────────────────────────────────────────────────┐
│                     OLIVENET SOCIAL BOT                      │
└─────────────────────────────┬───────────────────────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────────┐
    │                         │                             │
┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│ SORA  │ │ VEO   │ │ KLING │ │ FLUX  │ │GEMINI │ │ELEVEN │
│ VIDEO │ │ VIDEO │ │ VIDEO │ │ IMAGE │ │ IMAGE │ │  TTS  │
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

### Metrik Sync Döngüsü

```
Instagram API ─► insights_helper ─► posts tablosu ─► Analytics Agent
                                          │
                                          ▼
                              hook_performance tablosu
                                          │
                                          ▼
                              strategy tablosu (öğrenme)
```

---

## Dosya Büyüklükleri (Satır)

| Dosya | Satır | Açıklama |
|-------|-------|----------|
| `scheduler/pipeline.py` | 2.205 | Ana pipeline motoru |
| `claude_helper.py` | 2.031 | Prompt mühendisliği |
| `database/crud.py` | 1.699 | Veritabanı işlemleri |
| `telegram_pipeline.py` | 1.375 | Telegram bot |
| `agents/creator.py` | 1.316 | İçerik oluşturma |
| `instagram_helper.py` | 1.010 | Instagram API |
| **Toplam** | **34.774** | Tüm proje |

---

## Teknoloji Stack

| Kategori | Teknoloji |
|----------|-----------|
| **Dil** | Python 3.10+ |
| **Veritabanı** | SQLite |
| **Bot** | python-telegram-bot |
| **HTTP** | httpx (async) |
| **AI** | Claude Code CLI, OpenAI, Google Gemini |
| **Video** | Sora, Veo 3.1, Kling (fal.ai) |
| **Görsel** | FLUX.2 Pro, Gemini |
| **TTS** | ElevenLabs (Türkçe) |
| **CDN** | Cloudinary, imgbb |
| **Render** | Playwright (HTML→PNG) |

---

## İlgili Dokümantasyon

- [DATABASE.md](DATABASE.md) - Veritabanı şeması
- [API_INTEGRATIONS.md](API_INTEGRATIONS.md) - API detayları
- [CONFIGURATION.md](CONFIGURATION.md) - Konfigürasyon rehberi
- [QUICKSTART.md](QUICKSTART.md) - Hızlı başlangıç
