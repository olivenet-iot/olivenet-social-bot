# Olivenet Social Bot

AI destekli Instagram icerik otomasyonu. Multi-agent mimari ile icerik planlama, olusturma ve yayinlama.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Instagram-E4405F)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Ozellikler

- **Multi-Agent Sistem** - 6 uzman agent ile orkestrasyon
- **Video Uretimi** - Sora 2, Veo 3.1, Kling AI entegrasyonu
- **Gorsel Uretimi** - FLUX.2 Pro, Gemini ile yuksek kalite
- **Sesli Reels** - ElevenLabs TTS ile Turkce seslendirme
- **Otomatik Altyazi** - Whisper ile word-level timing
- **Audio Sync** - Akilli ses/video senkronizasyonu
- **11 Infographic Template** - HTML tabanlı carousel sablonlari
- **Telegram Kontrol** - Onay akisi ve yonetim paneli
- **Performance Learning** - Hook ve konu performans takibi
- **A/B Testing** - Varyant karsilastirma ve ogrenme

---

## Hizli Baslangic

```bash
# Klonla
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
cd olivenet-social-bot

# Virtual environment
python -m venv venv
source venv/bin/activate

# Bagimliliklar
pip install -r requirements.txt

# Konfigurasyon
cp .env.example .env
nano .env  # API key'leri duzenle

# Veritabani
python -m app.database.models

# Calistir
python -m app.telegram_pipeline
```

Detayli kurulum: [QUICKSTART.md](QUICKSTART.md)

---

## Mimari

```
┌─────────────────────────────────────────────────────┐
│                  TELEGRAM BOT                        │
│           /start /manual /status /sync              │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │    PIPELINE     │
              │  Daily/Reels/   │
              │  Carousel/A-B   │
              └────────┬────────┘
                       │
    ┌──────────────────┼──────────────────┐
    │                  │                  │
┌───▼───┐         ┌────▼────┐        ┌────▼────┐
│PLANNER│────────▶│ CREATOR │───────▶│REVIEWER │
└───────┘         └────┬────┘        └────┬────┘
                       │                  │
              ┌────────▼────────┐         │
              │   AI Services   │         │
              │ Sora/Veo/FLUX   │         │
              │ ElevenLabs/CDN  │         │
              └─────────────────┘         │
                                          │
                       ┌──────────────────┘
                       │
              ┌────────▼────────┐
              │    PUBLISHER    │
              │  Instagram API  │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │    ANALYTICS    │
              │   Insights API  │
              └─────────────────┘
```

---

## Icerik Turleri

| Tur | Haftalik | Aciklama |
|-----|----------|----------|
| **Reels** | 7 (%58) | Video icerik, non-follower reach odakli |
| **Carousel** | 2 (%17) | Egitici, kaydet odakli |
| **Post** | 3 (%25) | Detayli bilgi, infographic |

---

## Video Modelleri

| Model | Sure | Kalite | Kullanim |
|-------|------|--------|----------|
| Sora 2 | 4-12s | En yuksek | Sinematik, voice reels |
| Veo 3.1 | 4-8s | Yuksek | Hizli uretim |
| Kling Pro | 5-10s | Iyi | Alternatif |
| Minimax | 5-6s | Iyi | Hizli uretim |
| Wan 2.6 | 5-15s | Iyi | Uzun icerik |

---

## Agent Sistemi

| Agent | Gorev | Metodlar |
|-------|-------|----------|
| **Orchestrator** | Haftalik plan, strateji | `plan_week()`, `daily_check()` |
| **Planner** | Konu secimi, hook onerisi | `suggest_topic()`, `get_top_topics()` |
| **Creator** | Icerik uretimi | `create_post()`, `create_reels_prompt()` |
| **Reviewer** | Kalite kontrol (0-10 puan) | `review_post()`, `final_approval()` |
| **Publisher** | Instagram yayinlama | `publish()`, `publish_carousel()` |
| **Analytics** | Metrik analizi, viral skor | `fetch_analytics()`, `calculate_viral_score()` |

---

## Telegram Komutlari

| Komut | Aciklama |
|-------|----------|
| `/start` | Bot'u baslat |
| `/manual` | Manuel icerik olustur |
| `/status` | Pipeline durumu |
| `/schedule` | Haftalik program |
| `/sync` | Metrikleri senkronize et |
| `/stats` | Istatistikler |

---

## API Entegrasyonlari

| API | Amac | Dosya |
|-----|------|-------|
| Instagram Graph | Post yayinlama, insights | `instagram_helper.py` |
| OpenAI Sora | Video uretimi | `sora_helper.py` |
| Google Veo | Video uretimi | `veo_helper.py` |
| fal.ai Kling | Video uretimi | `fal_helper.py` |
| FLUX.2 Pro | Gorsel uretimi | `flux_helper.py` |
| ElevenLabs | Turkce TTS | `elevenlabs_helper.py` |
| Cloudinary | Video CDN | `cloudinary_helper.py` |
| Meta Ads | Reklam metrikleri | `meta_ads_helper.py` |

---

## Dizin Yapisi

```
olivenet-social-bot/
├── app/
│   ├── agents/          # 6 AI agent
│   ├── database/        # SQLite models + CRUD
│   ├── scheduler/       # Pipeline ve zamanlama
│   └── *.py             # API helpers
├── context/             # AI context dosyalari
├── templates/           # 11 HTML template
├── data/                # SQLite veritabani
├── outputs/             # Uretilen icerikler
└── logs/                # Uygulama loglari
```

---

## Dokumantasyon

| Dosya | Icerik |
|-------|--------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Sistem mimarisi |
| [DATABASE.md](DATABASE.md) | Veritabani semasi |
| [API_INTEGRATIONS.md](API_INTEGRATIONS.md) | API detaylari |
| [CONFIGURATION.md](CONFIGURATION.md) | Konfigurasyon rehberi |
| [QUICKSTART.md](QUICKSTART.md) | Hizli baslangic |
| [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) | Kullanim ornekleri |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Sorun giderme |

---

## Gereksinimler

- Python 3.11+
- FFmpeg 6.0+ (video donusturme)
- Playwright (HTML render)
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

# Video (en az biri)
OPENAI_API_KEY=...      # Sora
GEMINI_API_KEY=...      # Veo
FAL_API_KEY=...         # Kling

# Gorsel
FLUX_API_KEY=...

# TTS
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...

# CDN
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

Detaylar: [CONFIGURATION.md](CONFIGURATION.md)

---

## Skills (Claude Code)

Proje `.claude/skills/` altinda 12 optimize edilmis skill icerir:

| Skill | Aciklama |
|-------|----------|
| `video-generation` | Sora/Veo/Kling model secimi |
| `instagram-api` | Graph API v21.0 referansi |
| `database-patterns` | SQLite CRUD ornekleri |
| `multi-agent-architecture` | Pipeline akislari |
| `olivenet-brand` | Marka sesi ve kurallar |
| `telegram-bot` | Komut ve handler referansi |
| `template-system` | 11 HTML template |
| `helper-reference` | Tum helper fonksiyonlari |
| `flux-image` | FLUX.2 Pro gorsel uretimi |
| `cloudinary-cdn` | Video CDN yonetimi |
| `error-handling` | Hata ayiklama rehberi |
| `recent-changes` | Son degisiklikler logu |

---

## Lisans

MIT License

---

## Gelistirici

**Olivenet Ltd.** - Industrial IoT & AI Solutions
