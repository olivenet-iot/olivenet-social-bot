# Olivenet Social Bot 🤖

Multi-agent AI sistemi ile otomatik sosyal medya içerik üretimi ve paylaşımı.

## 🎯 Özellikler

### 🎬 Video Üretimi (Reels)
| Model | Kullanım | Süre |
|-------|----------|------|
| **Sora 2** | Premium kalite (öncelikli) | ~2 dk |
| **Veo 3.1** | Fallback | ~1 dk |

- Otomatik format dönüşümü (H.264 + AAC)
- Cloudinary CDN entegrasyonu
- Instagram Reels + Facebook Video

### 🤖 AI Agents
| Agent | Görev |
|-------|-------|
| **Planner** | Konu seçimi, haftalık planlama |
| **Creator** | İçerik üretimi (caption + video prompt) |
| **Reviewer** | Kalite kontrolü (1-10 puan) |
| **Publisher** | Çoklu platform yayınlama |

### 📱 Platformlar
- **Instagram**: Post + Reels (12/hafta)
- **Facebook**: Video + Post (3/hafta)
- **Telegram**: Kontrol paneli

## 📊 İçerik Kategorileri (10 adet)

| # | Emoji | Kategori |
|---|-------|----------|
| 1 | 🌾 | Tarım & Sera Otomasyonu |
| 2 | ⚡ | Enerji İzleme & Yönetim |
| 3 | 🔧 | Kestirimci Bakım |
| 4 | 📡 | LoRaWAN Teknolojisi |
| 5 | 🤖 | Edge AI & Yapay Zeka |
| 6 | 🏭 | Endüstriyel IoT |
| 7 | 📊 | Veri Yönetimi & Analitik |
| 8 | 📱 | IoT Platformları (ThingsBoard) |
| 9 | 🔐 | IoT Güvenlik |
| 10 | 🌍 | Sürdürülebilirlik |

## 📅 Haftalık Program
```
Pazartesi:   10:00 (IG+FB) + 19:00 (IG)
Salı:        10:00 (IG)    + 19:00 (IG) 🎬 REELS
Çarşamba:    10:00 (IG+FB) + 19:00 (IG)
Perşembe:    10:00 (IG)    + 19:00 (IG) 🎬 REELS
Cuma:        10:00 (IG+FB) + 19:00 (IG)
Cumartesi:   14:00 (IG) 🎬 REELS
Pazar:       14:00 (IG)
```

**Özet:** 12 içerik/hafta (9 post + 3 reels)

## 🔧 Teknoloji Stack

### Backend
- Python 3.10+
- SQLite (içerik veritabanı)
- APScheduler (zamanlama)

### AI & Video
- **Claude AI** (Anthropic) - İçerik üretimi
- **Sora 2** (OpenAI) - Video üretimi
- **Veo 3.1** (Google) - Video fallback
- **FLUX** - Görsel üretimi

### Entegrasyonlar
- Facebook Graph API
- Instagram Graph API
- Telegram Bot API
- Cloudinary (Video CDN)

## 🚀 Kurulum
```bash
# Clone
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
cd olivenet-social-bot

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# ffmpeg (video dönüşümü için)
sudo apt install ffmpeg

# Environment
cp .env.example .env
nano .env  # API key'leri ekle

# Run
python main.py
```

## 📁 Proje Yapısı
```
olivenet-social-bot/
├── app/
│   ├── agents/              # AI Agents
│   │   ├── planner.py       # Konu planlama
│   │   ├── creator.py       # İçerik üretimi
│   │   ├── reviewer.py      # Kalite kontrol
│   │   └── publisher.py     # Yayınlama
│   ├── scheduler/           # Zamanlama
│   │   └── pipeline.py      # İçerik pipeline
│   ├── sora_helper.py       # OpenAI Sora API
│   ├── veo_helper.py        # Google Veo API
│   ├── cloudinary_helper.py # Video CDN
│   ├── instagram_helper.py  # IG Reels API
│   ├── facebook_helper.py   # FB Video API
│   └── telegram_pipeline.py # Telegram kontrol
├── context/                 # AI Context dosyaları
│   ├── company-profile.md   # Şirket bilgisi
│   ├── content-strategy.md  # İçerik stratejisi
│   ├── topics.md            # Konu havuzu (10 kategori)
│   ├── schedule-strategy.md # Zamanlama kuralları
│   └── reels-prompts.md     # Video prompt şablonları
├── data/
│   └── content.db           # SQLite veritabanı
├── outputs/                 # Üretilen videolar
├── main.py                  # Ana giriş noktası
└── requirements.txt
```

## 🎬 Reels Pipeline
```
┌─────────────┐
│  Planner    │ Konu seç (topics.md'den)
└──────┬──────┘
       ▼
┌─────────────┐
│  Creator    │ Caption + Video prompt üret
└──────┬──────┘
       ▼
┌─────────────┐
│  Sora 2     │ Video üret (~2 dk)
└──────┬──────┘
       │ ❌ Fail?
       ▼
┌─────────────┐
│  Veo 3.1    │ Fallback video (~1 dk)
└──────┬──────┘
       ▼
┌─────────────┐
│  Reviewer   │ Kalite kontrol (min 6.0/10)
└──────┬──────┘
       ▼
┌─────────────┐
│  Cloudinary │ CDN'e yükle
└──────┬──────┘
       ▼
┌─────────────┐
│  Publisher  │ FB + IG Reels yayınla
└─────────────┘
```

## ⚙️ Servis Yönetimi
```bash
# Systemd service
sudo systemctl start olivenet-social
sudo systemctl stop olivenet-social
sudo systemctl restart olivenet-social
sudo systemctl status olivenet-social

# Logları izle
sudo journalctl -u olivenet-social -f
```

## 📊 Performans Metrikleri

| Metrik | Değer |
|--------|-------|
| Sora video üretimi | ~2 dakika |
| Veo video üretimi | ~1 dakika |
| Instagram upload | ~30 saniye |
| Tam pipeline | ~4-5 dakika |
| Haftalık içerik | 12 adet |
| Reels/hafta | 3 adet |

## 🔐 Gerekli API Keys
```env
# AI
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-proj-xxx
GEMINI_API_KEY=xxx

# Social Media
FACEBOOK_ACCESS_TOKEN=xxx
FACEBOOK_PAGE_ID=xxx
INSTAGRAM_ACCOUNT_ID=xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_ADMIN_CHAT_ID=xxx

# CDN
CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_API_KEY=xxx
CLOUDINARY_API_SECRET=xxx

# Image
IMGBB_API_KEY=xxx
FLUX_API_KEY=xxx
```

## 📝 Telegram Komutları

- `/start` - Ana menü
- `📝 Post Oluştur` - Manuel post
- `🎬 Reels Oluştur` - Manuel reels
- `📊 Durum` - Sistem durumu
- `📅 Haftalık Plan` - Program görüntüle

## 🏢 Hakkında

**Olivenet** - KKTC merkezli Endüstriyel IoT şirketi

- 🌾 Tarım & Sera Otomasyonu
- ⚡ Enerji İzleme Sistemleri
- 📡 LoRaWAN Çözümleri
- 🔧 Kestirimci Bakım

## 📄 Lisans

MIT License

---

Made with ❤️ by Olivenet
