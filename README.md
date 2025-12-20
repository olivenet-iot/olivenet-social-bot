# 🤖 Olivenet AI Content System

**Multi-Agent AI ile Full-Autonomous Sosyal Medya İçerik Sistemi**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)

---

## 🌟 Özellikler

### Multi-Agent Mimari
| Agent | Görev |
|-------|-------|
| 🎯 **Orchestrator** | Merkezi koordinatör, haftalık planlama, strateji güncelleme |
| 📋 **Planner** | Konu önerisi, trend analizi, içerik takvimi |
| ✍️ **Creator** | Post metni, görsel prompt üretimi (Claude AI) |
| 🔍 **Reviewer** | Kalite kontrol, puanlama (1-10), onay/red |
| 📤 **Publisher** | Dual-platform paylaşım (Facebook + Instagram) |
| 📊 **Analytics** | Performans takip, raporlama |

### Self-Learning Strateji
- 📈 AI performans verilerini analiz eder
- 📅 En iyi günleri ve saatleri öğrenir
- 🎨 İçerik ve görsel mix'ini optimize eder
- 🔄 Haftalık strateji günceller

### Görsel Üretimi (4 Seçenek)
| Seçenek | Teknoloji | Kalite | Maliyet |
|---------|-----------|--------|---------|
| 📊 İnfografik | HTML → PNG | İyi | Ücretsiz |
| 📸 Gerçekçi AI | Gemini 2.5 Flash | İyi | Ücretsiz |
| 🎨 FLUX.2 Pro | Black Forest Labs | Premium | ~$0.03/görsel |
| 🎬 AI Video | Sora 2 / Veo 3.1 | Premium | Kullanım başı |

### 🎬 Video/Reels Üretimi (YENİ!)
| Model | Özellik | Süre |
|-------|---------|------|
| **Sora 2** | OpenAI - Yüksek kalite | 4-12 saniye |
| **Veo 3.1** | Google - Hızlı fallback | 4-8 saniye |
| **Cloudinary** | Video CDN | - |
| **ffmpeg** | Instagram format dönüşümü | - |

### 🚀 Full-Autonomous Mod (YENİ!)
Sıfır manuel müdahale ile çalışır:

```
📅 Content Calendar taranır (her 5 dk)
     ↓
⏰ Zamanı gelen içerik tespit edilir (±5 dk tolerans)
     ↓
✍️ AI içerik üretir (Claude)
     ↓
🎨 AI görsel üretir (FLUX.2 Pro)
     ↓
🔍 AI kalite kontrolü yapar (min 7/10)
     ↓
📤 Facebook + Instagram'a paylaşır
     ↓
📱 Telegram'a bildirim gönderir
```

### 📱 Dual-Platform Publishing
- **Facebook**: Graph API ile direkt paylaşım (Photo + Video)
- **Instagram**: ImgBB CDN üzerinden görsel yükleme → Instagram API
- **Instagram Reels**: Cloudinary CDN üzerinden video → Reels API

### 🎬 Reels Pipeline
```
Planner → Konu seç
Creator → Caption + Video prompt
Sora 2 → Video üret (fallback: Veo 3.1)
ffmpeg → Instagram formatına dönüştür (H.264/AAC)
Cloudinary → CDN'e yükle
Publisher → Facebook Video + Instagram Reels
```

---

## 🏗️ Sistem Mimarisi
```
┌─────────────────────────────────────────────────────────────┐
│                   🧠 ORCHESTRATOR AGENT                      │
│                  (Merkezi Karar Verici)                      │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ 📋 PLANNER      │ │ ✍️ CREATOR      │ │ 🎨 VISUAL       │
│    AGENT        │ │    AGENT        │ │    DIRECTOR     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   🔍 REVIEWER AGENT                          │
│                  (Kalite Kontrol)                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│       📤 PUBLISHER (FB + IG) → 📊 ANALYTICS                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Kurulum
```bash
# 1. Klonla
git clone https://github.com/seyidmemmedli/olivenet-social-bot.git
cd olivenet-social-bot

# 2. Virtual environment (önerilen)
python3 -m venv venv
source venv/bin/activate

# 3. Bağımlılıkları kur
pip install -r requirements.txt
playwright install chromium

# 4. .env ayarla
cp .env.example .env
nano .env  # API key'leri gir

# 5. Systemd servisi kur (Production)
sudo cp olivenet-social-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable olivenet-social-bot
sudo systemctl start olivenet-social-bot
```

---

## ⚙️ Yapılandırma

### .env Dosyası
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Facebook
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_ACCESS_TOKEN=your_access_token

# Instagram
INSTAGRAM_ACCOUNT_ID=your_instagram_business_account_id

# AI APIs
GEMINI_API_KEY=your_gemini_key
BFL_API_KEY=your_bfl_key           # FLUX.2 Pro için
REPLICATE_API_TOKEN=your_replicate_key

# CDN (Instagram için gerekli)
IMGBB_API_KEY=your_imgbb_key       # https://api.imgbb.com
```

### Gerekli API Anahtarları

| Servis | Amaç | Zorunlu |
|--------|------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot kontrolü | ✅ |
| `TELEGRAM_ADMIN_CHAT_ID` | Admin bildirim chat ID | ✅ |
| `FACEBOOK_PAGE_ID` | Facebook sayfa ID | ✅ |
| `FACEBOOK_ACCESS_TOKEN` | Facebook Graph API token | ✅ |
| `INSTAGRAM_ACCOUNT_ID` | Instagram Business Account ID | ✅ |
| `GEMINI_API_KEY` | Google Gemini AI (içerik + video) | ✅ |
| `BFL_API_KEY` | Black Forest Labs FLUX.2 Pro | ✅ |
| `IMGBB_API_KEY` | ImgBB CDN (Instagram için) | ✅ |
| `REPLICATE_API_TOKEN` | Replicate API (alternatif) | ⚪ |

---

## 📁 Proje Yapısı
```
olivenet-social-bot/
├── app/
│   ├── agents/                  # 🤖 AI Agent'lar
│   │   ├── base_agent.py        # Temel agent sınıfı
│   │   ├── orchestrator.py      # Merkezi koordinatör
│   │   ├── planner.py           # İçerik planlayıcı
│   │   ├── creator.py           # İçerik üretici
│   │   ├── reviewer.py          # Kalite kontrol
│   │   ├── publisher.py         # Dual-platform yayıncı
│   │   └── analytics.py         # Performans takip
│   │
│   ├── scheduler/               # ⏰ Zamanlayıcı
│   │   ├── pipeline.py          # 6 aşamalı içerik pipeline'ı
│   │   └── scheduler.py         # Full-autonomous scheduler
│   │
│   ├── database/                # 💾 Veritabanı
│   │   ├── models.py            # SQLite şeması
│   │   └── crud.py              # CRUD operasyonları
│   │
│   ├── telegram_pipeline.py     # 📱 Telegram bot (ana giriş)
│   ├── instagram_helper.py      # Instagram + CDN yardımcıları
│   ├── claude_helper.py         # Claude Code CLI
│   ├── flux_helper.py           # FLUX.2 Pro API
│   ├── sora_helper.py           # OpenAI Sora 2 Video API
│   ├── veo_helper.py            # Google Veo 3.1 Video API
│   ├── cloudinary_helper.py     # Video CDN upload
│   ├── gemini_helper.py         # Gemini API
│   ├── facebook_helper.py       # Facebook Graph API
│   └── renderer.py              # HTML → PNG
│
├── context/                     # 📚 AI Context
│   ├── company-profile.md       # Şirket bilgileri
│   ├── content-strategy.md      # İçerik stratejisi
│   ├── visual-guidelines.md     # Görsel kuralları
│   ├── flux-prompting-guide.md  # FLUX prompt rehberi
│   └── agent-personas/          # Agent kişilikleri
│
├── data/
│   └── content.db               # SQLite veritabanı
│
├── generated_images/            # Üretilen görseller
├── start_bot.sh                 # 🚀 Başlatma scripti
├── olivenet-social-bot.service  # Systemd servisi
├── requirements.txt
└── .env.example
```

---

## 📊 Database Tabloları

| Tablo | Açıklama |
|-------|----------|
| `posts` | Tüm içerikler (metin, görsel, durum, platform ID'leri) |
| `analytics` | Performans metrikleri (views, likes, shares) |
| `content_calendar` | Haftalık içerik takvimi |
| `strategy` | AI'ın öğrendiği stratejiler |
| `agent_logs` | Agent aktivite logları |

### Content Calendar Şeması
| Alan | Açıklama |
|------|----------|
| `week_start` | Haftanın başlangıç tarihi |
| `day_of_week` | Gün (0=Pazartesi, 6=Pazar) |
| `scheduled_time` | Yayınlama saati (HH:MM) |
| `topic_category` | Konu kategorisi |
| `topic_suggestion` | Önerilen konu |
| `visual_type_suggestion` | Görsel tipi (flux/infographic/video) |
| `status` | Durum (pending/in_progress/published) |

---

## ⏰ Otomatik Görevler

| Zaman (KKTC/UTC+2) | Gün | Görev |
|-------------------|-----|-------|
| 08:00 | Pazartesi | 📅 Haftalık planlama |
| Her 5 dk | Her gün | 🔍 Calendar kontrol + paylaşım |
| 20:00 | Her gün | 📊 Analytics raporu |
| 21:00 | Pazar | 🔄 Strateji güncelleme |

### Timezone
- **KKTC**: UTC+2 (Kuzey Kıbrıs Türk Cumhuriyeti)
- Tüm zamanlamalar KKTC saatine göredir

---

## 📱 Telegram Komutları

| Komut | Açıklama |
|-------|----------|
| `/start` | Ana menü |
| `/status` | Sistem durumu |
| `/calendar` | Bu haftanın takvimi |
| `/generate` | Manuel içerik oluşturma |
| `/plan` | Haftalık plan oluştur |

### Ana Menü
- 🚀 Günlük İçerik Başlat
- 📅 Haftalık Plan
- 📊 Strateji Göster
- 📈 Analytics Raporu
- ⏰ Scheduler Durumu

---

## 🔄 Full-Autonomous Pipeline

```
CONTENT CALENDAR
       │
       ▼
┌──────────────────────────────────┐
│  check_calendar_and_publish()    │  ← Her 5 dakikada çalışır
│  (scheduler.py)                  │
└──────────────────────────────────┘
       │
       ▼ Zamanı gelen içerik varsa
┌──────────────────────────────────┐
│  run_autonomous_content_with_plan│
│  (pipeline.py)                   │
└──────────────────────────────────┘
       │
       ├──► Creator Agent: İçerik üret
       ├──► Visual Generator: Görsel üret (FLUX.2 Pro)
       ├──► Reviewer Agent: Kalite kontrol (min 7/10)
       └──► Publisher Agent: FB + IG'ye paylaş
               │
               ├──► Facebook: Graph API
               └──► Instagram: ImgBB CDN → IG API
```

---

## 🧠 Self-Learning

AI şunları öğrenir ve stratejisini günceller:
```json
{
  "posts_per_week": 5,
  "best_days": ["tuesday", "thursday"],
  "best_hours": ["10:00", "14:00"],
  "content_mix": {
    "egitici": 35,
    "tanitim": 25,
    "ipucu": 20,
    "haber": 10,
    "basari_hikayesi": 10
  },
  "visual_mix": {
    "flux": 35,
    "infographic": 30,
    "gemini": 25,
    "video": 10
  }
}
```

---

## 🔧 Servis Yönetimi

```bash
# Servisi başlat
sudo systemctl start olivenet-social-bot

# Servisi durdur
sudo systemctl stop olivenet-social-bot

# Servisi yeniden başlat
sudo systemctl restart olivenet-social-bot

# Logları izle (canlı)
sudo journalctl -u olivenet-social-bot -f

# Son 100 log satırı
sudo journalctl -u olivenet-social-bot -n 100

# Durumu kontrol et
sudo systemctl status olivenet-social-bot
```

---

## 🔧 Özelleştirme

### Yeni Agent Ekleme
```python
from app.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__("my_agent")

    async def execute(self, input_data: dict) -> dict:
        # Agent mantığı
        result = await self.call_claude("prompt...")
        return {"success": True, "data": result}
```

### Yeni Zamanlanmış Görev
```python
from app.scheduler import ScheduledTask

task = ScheduledTask(
    name="my_task",
    callback=my_async_function,
    hour=10,
    minute=30,
    days=["monday", "wednesday", "friday"]
)
scheduler.add_task(task)
```

---

## 📄 Lisans

MIT License - [Olivenet Ltd.](https://olivenet.io)

---

## 🔗 Bağlantılar

- 🌐 Website: [olivenet.io](https://olivenet.io)
- 📧 Email: info@olivenet.io
- 📘 Facebook: [Olivenet](https://facebook.com/672821805923920)
- 📷 Instagram: [@olivenet.io](https://instagram.com/olivenet.io)

---

<p align="center">
  <b>Built with ❤️ by Olivenet IoT</b><br>
  <i>Smart Agriculture • Energy Monitoring • Industrial IoT</i>
</p>
