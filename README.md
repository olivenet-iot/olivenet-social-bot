# 🤖 Olivenet AI Content System

**Multi-Agent AI ile Semi-Autonomous Sosyal Medya İçerik Sistemi**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)

---

## 🌟 Özellikler

### Multi-Agent Mimari
| Agent | Görev |
|-------|-------|
| 🎯 **Orchestrator** | Merkezi koordinatör, haftalık planlama, strateji güncelleme |
| 📋 **Planner** | Konu önerisi, trend analizi, içerik takvimi |
| ✍️ **Creator** | Post metni, görsel prompt üretimi |
| 🔍 **Reviewer** | Kalite kontrol, puanlama (1-10), onay/red |
| 📤 **Publisher** | Facebook/Instagram paylaşım |
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
| 🎬 AI Video | Google Veo 3 | Premium | Kullanım başı |

### Semi-Autonomous Mod
Her aşamada Telegram üzerinden onay bekler:

```
📋 Konu önerisi → Onay
✍️ Post metni → Onay
🎨 Görsel → Onay
🔍 Review → Final onay
🚀 Yayınla
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
│              📤 PUBLISHER → 📊 ANALYTICS                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Kurulum
```bash
# 1. Klonla
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
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

# 5. Çalıştır
python3 start_pipeline.py
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

# AI APIs
GEMINI_API_KEY=your_gemini_key
BFL_API_KEY=your_bfl_key  # FLUX.2 Pro için
```

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
│   │   ├── publisher.py         # Yayıncı
│   │   └── analytics.py         # Performans takip
│   │
│   ├── scheduler/               # ⏰ Zamanlayıcı
│   │   ├── pipeline.py          # 6 aşamalı içerik pipeline'ı
│   │   └── scheduler.py         # Cron-like görev yönetimi
│   │
│   ├── database/                # 💾 Veritabanı
│   │   ├── models.py            # SQLite şeması
│   │   └── crud.py              # CRUD operasyonları
│   │
│   ├── telegram_pipeline.py     # 📱 Telegram bot (yeni)
│   ├── claude_helper.py         # Claude Code CLI
│   ├── flux_helper.py           # FLUX.2 Pro API
│   ├── veo_helper.py            # Veo 3 Video API
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
│       ├── orchestrator.md
│       ├── planner.md
│       └── reviewer.md
│
├── data/
│   └── content.db               # SQLite veritabanı
│
├── start_pipeline.py            # 🚀 Ana başlatıcı
├── requirements.txt
└── .env.example
```

---

## 📊 Database Tabloları

| Tablo | Açıklama |
|-------|----------|
| `posts` | Tüm içerikler (metin, görsel, durum) |
| `analytics` | Performans metrikleri (views, likes, shares) |
| `content_calendar` | Haftalık içerik takvimi |
| `strategy` | AI'ın öğrendiği stratejiler |
| `agent_logs` | Agent aktivite logları |

---

## ⏰ Otomatik Görevler

| Zaman | Gün | Görev |
|-------|-----|-------|
| 08:00 | Pazartesi | 📅 Haftalık planlama |
| 09:00 | Pzt-Cum | 🚀 Günlük içerik pipeline |
| 20:00 | Her gün | 📊 Analytics raporu |
| 21:00 | Pazar | 🔄 Strateji güncelleme |

---

## 📱 Telegram Komutları

| Komut | Açıklama |
|-------|----------|
| `/start` | Ana menü |
| `/status` | Sistem durumu |
| `/manual` | Manuel içerik oluşturma |

### Ana Menü
- 🚀 Günlük İçerik Başlat
- 📅 Haftalık Plan
- 📊 Strateji Göster
- 📈 Analytics Raporu
- ⏰ Scheduler Durumu

---

## 🔄 Pipeline Akışı
```
IDLE
  ↓
PLANNING (AI konu önerir)
  ↓
AWAITING_TOPIC_APPROVAL ←── 📱 Telegram onay
  ↓
CREATING_CONTENT (AI post yazar)
  ↓
AWAITING_CONTENT_APPROVAL ←── 📱 Telegram onay
  ↓
CREATING_VISUAL (AI görsel üretir)
  ↓
AWAITING_VISUAL_APPROVAL ←── 📱 Telegram onay
  ↓
REVIEWING (AI kalite kontrol)
  ↓
AWAITING_FINAL_APPROVAL ←── 📱 Telegram onay
  ↓
PUBLISHING (Facebook'a gönder)
  ↓
COMPLETED ✅
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
- 🐙 GitHub: [github.com/olivenet-iot](https://github.com/olivenet-iot)

---

<p align="center">
  <b>Built with ❤️ by Olivenet IoT</b><br>
  <i>Smart Agriculture • Energy Monitoring • Industrial IoT</i>
</p>
