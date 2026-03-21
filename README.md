# Olivenet Social Bot

AI destekli Instagram icerik otomasyonu. v2 mimaride Brain Agent, Feed System ve 7 modular production pipeline ile otonom icerik planlama, olusturma ve yayinlama.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Instagram-E4405F)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Ozellikler

- **Brain Agent** - Otonom karar motoru, 2 saatlik dongulerle icerik uretim kararlari
- **Feed System** - 10 RSS feed ile icerik firsati toplama, skorlama ve havuz yonetimi
- **Multi-Agent Sistem** - 8 uzman agent (Brain, Orchestrator, Planner, Creator, Reviewer, Publisher, Analytics + BaseAgent)
- **7 Production Pipeline** - post, reels, carousel, voice_reels, long_video, news_reels, conversational
- **Video Uretimi** - Sora 2, Sora 2 Pro, Kling 3.0 Pro (fal.ai)
- **Gorsel Uretimi** - FLUX.2 Pro (fotorealistik), Nano Banana (fal-ai/nano-banana-pro infographic)
- **Sesli Reels** - OpenAI TTS (gpt-4o-mini-tts) ile Turkce seslendirme
- **Otomatik Altyazi** - Whisper ile word-level timing
- **Telegram Kontrol** - 14 komut ile yonetim paneli
- **Performance Learning** - Hook ve konu performans takibi, A/B testing

---

## Hizli Baslangic

```bash
# Klonla
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
cd olivenet-social-bot

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Bagimliliklar
pip install -r requirements.txt

# Konfigurasyon
cp .env.example .env
nano .env  # API key'leri duzenle

# Veritabani
python3 -m app.database.models

# Calistir (v2 - Brain + Feed + Telegram)
python3 app/main.py
```

Detayli kurulum: [QUICKSTART.md](QUICKSTART.md)

---

## Mimari (v2)

```
┌──────────────────────────────────────────────────────────────────┐
│                        KAYNAKLAR (Sources)                        │
│  10 RSS Feed → FeedAggregator → content_opportunities havuzu      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │      BRAIN AGENT        │
              │  (Otonom Karar Motoru)   │
              │  2h dongu, Claude API    │
              └────────────┬────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                   PRODUCTION PIPELINES                             │
│  post │ reels │ carousel │ voice_reels │ long_video │ news_reels  │
│                        │ conversational                           │
└──────────────────────────┬───────────────────────────────────────┘
                           │
    ┌──────────────────────┼──────────────────┐
    │                      │                  │
┌───▼────┐          ┌──────▼──────┐    ┌──────▼──────┐
│ AGENTS │          │ AI SERVICES │    │   PUBLISH   │
│ Creator│          │ Sora/Kling/ │    │ Instagram   │
│Reviewer│          │ FLUX/TTS    │    │  Graph API  │
│Planner │          │ OpenAI TTS  │    └─────────────┘
└────────┘          └─────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT (14 komut)                       │
│  /start /status /manual /stats /next /schedule /sync /prompts     │
│  /pool /brain /feeds /pause /resume /force                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Icerik Turleri

| Tur | Haftalik | Aciklama |
|-----|----------|----------|
| **Reels** | 7 (%58) | Video icerik, non-follower reach odakli |
| **Carousel** | 2 (%17) | Egitici, kaydet odakli |
| **Post** | 3 (%25) | Detayli bilgi, infographic |

---

## Video Modelleri (3 model)

| Model | Provider | Sure | Ozellikler |
|-------|----------|------|------------|
| sora-2 | OpenAI | 4/8/12s | En yuksek kalite, gercekci |
| sora-2-pro | OpenAI | 4/8/12s | Native speech, conversational only |
| kling-3.0-pro | fal.ai | 5/10/15s | Sinematik, fizik tabanli, native audio |

---

## Agent Sistemi (8 agent)

| Agent | Gorev | Dosya |
|-------|-------|-------|
| **BrainAgent** | Otonom karar motoru, 2h dongu | `agents/brain.py` |
| **Orchestrator** | Haftalik plan, strateji | `agents/orchestrator.py` |
| **Planner** | Konu secimi, hook onerisi | `agents/planner.py` |
| **Creator** | Icerik uretimi | `agents/creator.py` |
| **Reviewer** | Kalite kontrol (0-10 puan) | `agents/reviewer.py` |
| **Publisher** | Instagram yayinlama | `agents/publisher.py` |
| **Analytics** | Metrik analizi, viral skor | `agents/analytics.py` |
| **BaseAgent** | Temel sinif, retry logic | `agents/base_agent.py` |

---

## RSS Feed'ler (10 feed)

| Feed | Kategori |
|------|----------|
| IoT Now | iot |
| RAKwireless News | lorawan |
| Hackaday | maker |
| LoRa Alliance Blog | lorawan |
| Embedded Computing Design | embedded |
| TechCrunch AI | tech |
| MIT Technology Review | research |
| CleanTechnica | energy |
| Renewable Energy World | energy |
| AgFunder News | agriculture |

---

## Telegram Komutlari (14 komut)

### v1 Komutlar

| Komut | Aciklama |
|-------|----------|
| `/start` | Bot'u baslat |
| `/status` | Pipeline durumu |
| `/manual` | Manuel icerik olustur |
| `/stats` | Istatistikler |
| `/next` | Siradaki icerik |
| `/schedule` | Haftalik program |
| `/sync` | Metrikleri senkronize et |
| `/prompts` | Prompt istatistikleri |

### v2 Komutlar

| Komut | Aciklama |
|-------|----------|
| `/pool` | Icerik firsati havuzu |
| `/brain` | Brain Agent kararlari |
| `/feeds` | Feed aggregator durumu |
| `/pause` | Sistemi duraklat |
| `/resume` | Sistemi devam ettir |
| `/force` | Firsati hemen uret |

---

## API Entegrasyonlari

| API | Amac | Dosya |
|-----|------|-------|
| Instagram Graph | Post yayinlama, insights | `instagram_helper.py` |
| OpenAI Sora | Video uretimi | `sora_helper.py` |
| Kling (fal.ai) | Video uretimi | `kling_helper.py` |
| FLUX.2 Pro | Gorsel uretimi | `flux_helper.py` |
| Nano Banana | Infographic uretimi (fal-ai/nano-banana-pro) | `nano_banana_helper.py` |
| OpenAI TTS | Turkce TTS (gpt-4o-mini-tts) | `openai_tts_helper.py` |
| Cloudinary | Video CDN | `cloudinary_helper.py` |
| Meta Ads | Reklam metrikleri | `meta_ads_helper.py` |

---

## Dizin Yapisi

```
olivenet-social-bot/
├── app/
│   ├── agents/          # 8 AI agent (brain, orchestrator, planner, ...)
│   ├── database/        # SQLite models + CRUD (12 tablo)
│   ├── engine/          # v2: scheduler, state, event_bus
│   ├── production/      # 7 production pipeline
│   ├── sources/         # Feed aggregator + config (10 RSS)
│   ├── scheduler/       # v1 pipeline ve zamanlama
│   ├── utils/           # Logger
│   ├── validators/      # Text validation
│   └── *.py             # API helpers
├── context/             # AI context dosyalari + agent personas
├── data/                # SQLite veritabani (12 tablo)
├── outputs/             # Uretilen icerikler
└── logs/                # Uygulama loglari
```

---

## Dokumantasyon

| Dosya | Icerik |
|-------|--------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Sistem mimarisi |
| [DATABASE.md](DATABASE.md) | Veritabani semasi (12 tablo) |
| [API_INTEGRATIONS.md](API_INTEGRATIONS.md) | API detaylari |
| [CONFIGURATION.md](CONFIGURATION.md) | Konfigurasyon rehberi |
| [QUICKSTART.md](QUICKSTART.md) | Hizli baslangic |
| [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) | Kullanim ornekleri |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Sorun giderme |

---

## Gereksinimler

- Python 3.10+
- FFmpeg 6.0+ (video donusturme)
- Playwright (carousel slide render)
- SQLite

---

## Konfigurasyon

Gerekli API anahtarlari (`.env`):

```bash
# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_CHAT_ID=...

# Instagram
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_USER_ID=...

# Video
OPENAI_API_KEY=...          # Sora

# Gorsel
FLUX_API_KEY=...
FAL_API_KEY=...             # Nano Banana infographic

# TTS (OPENAI_API_KEY yukarıda zaten tanımlı - ek ayar gerekmez)

# CDN
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...

# Brain Agent (v2)
BRAIN_DRY_RUN=true          # true=logla, false=uret
BRAIN_CYCLE_MINUTES=120
BRAIN_MAX_DAILY_POSTS=2
BRAIN_MIN_POST_INTERVAL_HOURS=4
BRAIN_MIN_SCORE_PRODUCE=60

# Feed System (v2)
FEED_POLL_MINUTES=30
EXPIRY_CHECK_HOURS=6
```

Detaylar: [CONFIGURATION.md](CONFIGURATION.md)

---

## Skills (Claude Code)

Proje `.claude/skills/` altinda 11 optimize edilmis skill icerir:

| Skill | Aciklama |
|-------|----------|
| `video-generation` | Sora/Kling model secimi |
| `instagram-api` | Graph API v21.0 referansi |
| `database-patterns` | SQLite CRUD ornekleri (12 tablo) |
| `multi-agent-architecture` | v2 mimari, Brain Agent, pipeline akislari |
| `olivenet-brand` | Marka sesi ve kurallar |
| `telegram-bot` | 14 komut ve handler referansi |
| `helper-reference` | Tum helper fonksiyonlari |
| `flux-image` | FLUX.2 Pro gorsel uretimi |
| `cloudinary-cdn` | Video CDN yonetimi |
| `error-handling` | Hata ayiklama rehberi |
| `recent-changes` | v2 migrasyon degisiklik logu |

---

## Lisans

MIT License

---

## Gelistirici

**Olivenet Ltd.** - Industrial IoT & AI Solutions
