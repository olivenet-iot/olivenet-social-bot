# Olivenet Social Bot

Multi-agent AI sistemi ile Instagram icin otomatik icerik uretimi ve yayinlama.

## Ozellikler

- **6 AI Agent** - Orchestrator, Planner, Creator, Reviewer, Publisher, Analytics
- **11 Infographic Template** - Carousel ve post icin HTML sablonlar
- **Video Uretimi** - Sora 2 + Veo 3.1 (fallback)
- **Gorsel Uretimi** - FLUX.2 Pro
- **3 Icerik Turu** - Post, Carousel, Reels
- **Telegram Kontrol Paneli** - Onay akisi ve yonetim
- **Performance-Aware** - Performans verisine dayali icerik onerisi
- **A/B Testing** - Hook ve ton karsilastirmasi

---

## Mimari

```
                    ┌──────────────┐
                    │ Orchestrator │ Pipeline koordinasyonu
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Planner   │───▶│   Creator   │───▶│  Reviewer   │
│ Konu secimi │    │ Icerik uret │    │ Kalite ctrl │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                             │
                                             ▼
                   ┌─────────────┐    ┌─────────────┐
                   │  Analytics  │◀───│  Publisher  │
                   │ Perf. takip │    │ IG yayinla  │
                   └─────────────┘    └─────────────┘
```

---

## AI Agents

| Agent | Gorev | Dosya |
|-------|-------|-------|
| **Orchestrator** | Pipeline koordinasyonu, haftalik plan, strateji | `orchestrator.py` |
| **Planner** | Konu secimi, performans-aware oneri | `planner.py` |
| **Creator** | Caption + gorsel/video prompt uretimi | `creator.py` |
| **Reviewer** | Kalite kontrol (0-10 puan), A/B karsilastirma | `reviewer.py` |
| **Publisher** | Instagram yayinlama (post, carousel, reels) | `publisher.py` |
| **Analytics** | Performans takip, viral score hesaplama | `analytics.py` |

---

## Icerik Turleri

| Tur | Aciklama | Gorsel |
|-----|----------|--------|
| **Post** | Tek gorsel + caption | FLUX.2 Pro |
| **Carousel** | 5+ slide infographic | HTML template |
| **Reels** | 8s AI video | Sora 2 / Veo 3.1 |

---

## Template Sistemi

11 HTML infographic template (1080x1080px):

| Template | Kullanim Alani |
|----------|----------------|
| `dashboard-infographic` | Metrik/panel gorunumu |
| `feature-grid-infographic` | Ozellik grid layout |
| `timeline-infographic` | Zaman cizelgesi |
| `before-after-infographic` | Oncesi/sonrasi donusum |
| `comparison-infographic` | Yan yana karsilastirma |
| `quote-infographic` | Alinti/soz |
| `billboard-infographic` | Buyuk baslik, dikkat cekici |
| `big-number-infographic` | Buyuk istatistik (%75 gibi) |
| `process-infographic` | Adim adim surec |
| `checklist-infographic` | Kontrol listesi |
| `visual-template` | Genel amacli |

---

## Proje Yapisi

```
olivenet-social-bot/
├── app/
│   ├── agents/              # 6 AI Agent
│   │   ├── base_agent.py    # Temel agent sinifi
│   │   ├── orchestrator.py  # Pipeline koordinasyonu
│   │   ├── planner.py       # Konu secimi
│   │   ├── creator.py       # Icerik uretimi
│   │   ├── reviewer.py      # Kalite kontrol
│   │   ├── publisher.py     # Instagram yayinlama
│   │   └── analytics.py     # Performans takip
│   │
│   ├── scheduler/           # Zamanlama
│   │   └── pipeline.py      # ContentPipeline sinifi
│   │
│   ├── database/            # Veri katmani
│   │   ├── models.py        # SQLite tablo tanimlari
│   │   └── crud.py          # CRUD operasyonlari
│   │
│   ├── validators/          # Dogrulama
│   │   └── text_validator.py
│   │
│   ├── utils/               # Yardimci
│   │   └── logger.py
│   │
│   ├── claude_helper.py     # Claude CLI wrapper
│   ├── flux_helper.py       # FLUX.2 Pro API
│   ├── sora_helper.py       # OpenAI Sora API
│   ├── veo_helper.py        # Google Veo API
│   ├── instagram_helper.py  # Instagram Graph API
│   ├── insights_helper.py   # Instagram Analytics
│   ├── cloudinary_helper.py # Video CDN
│   ├── renderer.py          # HTML -> PNG (Playwright)
│   ├── telegram_pipeline.py # Telegram bot
│   └── config.py            # Konfigürasyon
│
├── context/                 # AI Context dosyalari
│   ├── company-profile.md   # Sirket bilgisi
│   ├── content-strategy.md  # Icerik stratejisi
│   ├── topics.md            # 10 kategori konu havuzu
│   ├── schedule-strategy.md # Zamanlama kurallari
│   ├── visual-guidelines.md # Tasarim rehberi
│   └── agent-personas/      # Agent kisilikleri
│
├── templates/               # 11 HTML template
│
├── .claude/skills/          # 11 Claude Code skill
│   ├── database-patterns/
│   ├── instagram-api/
│   ├── multi-agent-architecture/
│   ├── olivenet-brand/
│   ├── telegram-bot/
│   ├── video-generation/
│   ├── flux-image/
│   ├── cloudinary-cdn/
│   ├── template-system/
│   ├── helper-reference/
│   └── recent-changes/
│
├── data/
│   └── content.db           # SQLite veritabani
│
├── outputs/                 # Uretilen medya
├── logs/                    # Log dosyalari
├── main.py                  # Ana giris noktasi
└── requirements.txt         # Python bagimliliklari
```

---

## Kurulum

### Gereksinimler

- Python 3.10+
- ffmpeg (video donusumu)
- Playwright (HTML rendering)

### Adimlar

```bash
# Clone
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
cd olivenet-social-bot

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Playwright browser
playwright install chromium

# ffmpeg
sudo apt install ffmpeg

# Environment
cp .env.example .env
nano .env  # API key'leri ekle

# Run
python main.py
```

---

## Konfigürasyon

### Gerekli API Keys

| Servis | Env Degiskeni | Aciklama |
|--------|---------------|----------|
| **Telegram** | `TELEGRAM_BOT_TOKEN` | Bot API token |
| | `TELEGRAM_ADMIN_CHAT_ID` | Admin chat ID |
| **Instagram** | `INSTAGRAM_ACCESS_TOKEN` | Graph API token |
| | `INSTAGRAM_USER_ID` | IG User ID |
| **OpenAI** | `OPENAI_API_KEY` | Sora video icin |
| **Google** | `GEMINI_API_KEY` | Veo video icin |
| **FLUX** | `BFL_API_KEY` | Gorsel uretimi |
| **Cloudinary** | `CLOUDINARY_CLOUD_NAME` | Video CDN |
| | `CLOUDINARY_API_KEY` | |
| | `CLOUDINARY_API_SECRET` | |
| **imgbb** | `IMGBB_API_KEY` | Gorsel CDN |

---

## Telegram Komutlari

| Komut | Aciklama |
|-------|----------|
| `/start` | Ana menu |
| `/status` | Sistem durumu |
| `/manual` | Manuel icerik olustur |
| `/stats` | Analytics ozeti |
| `/next` | Siradaki planlanan icerik |
| `/schedule` | Haftalik takvim |
| `/sync` | Instagram insights senkronizasyonu |
| `/prompts` | Prompt performans raporu |

### Ana Menu Butonlari

```
[Gunluk Icerik] [Reels]
[Carousel] [Otonom]
[Icerik Plani] [Zamanlama]
[Siradaki] [Hizli Durum]
[Analytics] [Strateji]
[Sync] [Yardim]
```

---

## Pipeline Akisi

### Gunluk Icerik (Manuel Onay)

```
1. Planner     → Konu oner
   ↓ [Telegram: Onayla/Degistir]
2. Creator     → Caption + gorsel prompt
   ↓ [Telegram: Onayla/Yeniden Yaz]
3. FLUX/Veo    → Gorsel/video uret
   ↓ [Telegram: Onayla/Yeniden Uret]
4. Reviewer    → Kalite kontrol (min 7.0/10)
   ↓ [Telegram: Yayinla/Zamanla/Revize]
5. Publisher   → Instagram'a yayinla
```

### Otonom Mod

```
Planner → Creator → Visual → Reviewer → (score >= 7) → Publisher
```

### Carousel Pipeline

```
1. Konu sec
2. 5+ slide HTML uret
3. Her slide'i PNG'ye render et
4. CDN'e yukle
5. Instagram carousel olarak yayinla
```

---

## Icerik Kategorileri

| # | Kategori | Aciklama |
|---|----------|----------|
| 1 | Tarim & Sera Otomasyonu | Akilli tarim cozumleri |
| 2 | Enerji Izleme & Yonetim | Enerji verimliligi |
| 3 | Kestirimci Bakim | Predictive maintenance |
| 4 | LoRaWAN Teknolojisi | Uzun menzil IoT |
| 5 | Edge AI & Yapay Zeka | Ucta islem |
| 6 | Endustriyel IoT | Fabrika otomasyonu |
| 7 | Veri Yonetimi & Analitik | Data insights |
| 8 | IoT Platformlari | ThingsBoard vb. |
| 9 | IoT Guvenlik | Siber guvenlik |
| 10 | Surdurulebilirlik | Yesil teknoloji |

---

## Haftalik Program

```
Pazartesi:   10:00 (Post) + 19:00 (Post)
Sali:        10:00 (Post) + 19:00 (Reels)
Carsamba:    10:00 (Post) + 19:00 (Post)
Persembe:    10:00 (Post) + 19:00 (Reels)
Cuma:        10:00 (Post) + 19:00 (Post)
Cumartesi:   14:00 (Reels)
Pazar:       14:00 (Post)
```

**Haftalik:** 12 icerik (7 Reels + 2 Carousel + 3 Post)

---

## Veritabani

SQLite ile 9 tablo:

| Tablo | Amac |
|-------|------|
| `posts` | Tum icerikler |
| `analytics` | Post performans metrikleri |
| `content_calendar` | Planlanan icerikler |
| `strategy` | AI ogrenmis stratejiler |
| `agent_logs` | Agent aktiviteleri |
| `hook_performance` | Hook tipi performanslari |
| `ab_test_results` | A/B test sonuclari |
| `approval_logs` | Onay audit trail |
| `prompt_history` | Prompt performans takibi |

### Viral Score Formulu

```python
viral_score = (saves * 2) + (shares * 3) + engagement + (non_follower_reach * 0.015)
```

---

## Skills Sistemi

Claude Code icin 11 skill dosyasi (`.claude/skills/`):

| Skill | Aciklama |
|-------|----------|
| `database-patterns` | SQLite CRUD patterns |
| `instagram-api` | Graph API v21.0 |
| `multi-agent-architecture` | Agent ve pipeline yapisi |
| `olivenet-brand` | Marka sesi, hook'lar |
| `telegram-bot` | Bot komutlari |
| `video-generation` | Sora & Veo API |
| `flux-image` | FLUX.2 Pro gorsel |
| `cloudinary-cdn` | Video CDN |
| `template-system` | HTML template'ler |
| `helper-reference` | Tum helper fonksiyonlari |
| `recent-changes` | Son degisiklikler |

---

## Servis Yonetimi

```bash
# Systemd
sudo systemctl start olivenet-social
sudo systemctl stop olivenet-social
sudo systemctl restart olivenet-social
sudo systemctl status olivenet-social

# Loglar
sudo journalctl -u olivenet-social -f

# Manuel calistirma
cd /opt/olivenet-social-bot
source venv/bin/activate
python main.py
```

---

## Son Guncellemeler

| Tarih | Degisiklik |
|-------|------------|
| 2024-12 | Carousel iyilestirmeleri + 5 yeni template |
| 2024-12 | KAYDET sorunu fix (4 katmanli savunma) |
| 2024-12 | Prompt Tracking sistemi |
| 2024-12 | A/B Testing entegrasyonu |
| 2024-12 | Facebook devre disi birakildi |
| 2024-12 | Skills sistemi eklendi (11 skill) |

---

## Hakkinda

**Olivenet** - KKTC merkezli Endustriyel IoT sirketi

- Akilli Tarim & Sera Otomasyonu
- Enerji Izleme Sistemleri
- LoRaWAN Cozumleri
- Kestirimci Bakim

---

## Lisans

MIT License

---

Made with love by Olivenet
