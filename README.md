# Olivenet Social Media Bot

Telegram üzerinden Claude Code ile akıllı Facebook post otomasyonu.

## 🌟 Özellikler

### İçerik Üretimi
- 🤖 **Claude Code ile akıllı post üretimi** - Sosyal medya uzmanı gibi düşünür
- 💡 **Konu öneri sistemi** - Mevsim ve güne göre akıllı öneriler
- 📝 **Geri bildirim ile düzenleme** - "Daha kısa yap", "Emoji ekle" gibi

### Görsel Üretimi (3 Seçenek)
- 📊 **İnfografik (Statik)** - Dashboard tarzı PNG görseller
- 📸 **Gerçekçi AI Görsel** - Gemini 2.5 Flash ile fotoğraf üretimi
- 🎬 **AI Video (Veo 3)** - Google Veo 3 ile profesyonel video üretimi

### Entegrasyonlar
- 📱 Telegram bot ile kolay yönetim
- 📘 Facebook Graph API entegrasyonu (fotoğraf + video)
- 🎯 Olivenet marka kimliğine uygun içerik

## 🚀 Hızlı Kurulum
```bash
# 1. Repo'yu klonla
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
cd olivenet-social-bot

# 2. Kurulum script'ini çalıştır
chmod +x setup.sh
./setup.sh

# 3. Token'ları ayarla
nano .env

# 4. Bot'u başlat
python3 app/telegram_bot.py
```

## ⚙️ Gereksinimler

- Python 3.10+
- Claude Code CLI (kurulu ve çalışır durumda)
- Telegram Bot Token (@BotFather'dan)
- Facebook Page Access Token
- Gemini API Key (görsel + video için)

## 🔧 Yapılandırma

`.env.example` dosyasını `.env` olarak kopyalayın ve doldurun:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Facebook
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_ACCESS_TOKEN=your_access_token

# Gemini AI (görsel + Veo video)
GEMINI_API_KEY=your_gemini_api_key
```

## 📱 Telegram Komutları

| Komut/Buton | Açıklama |
|-------------|----------|
| /start | Ana menü |
| 📝 Yeni Post Oluştur | Konu gir, post üret |
| 💡 Konu Öner | Bugüne özel 3 konu önerisi |
| ✏️ Görseli Düzenle | Geri bildirim ile revize |
| ✅ Facebook'a Gönder | Paylaş |

## 📁 Dosya Yapısı
```
olivenet-social-bot/
├── app/
│   ├── telegram_bot.py      # Ana bot
│   ├── claude_helper.py     # Claude Code wrapper + prompt üretimi
│   ├── renderer.py          # HTML → PNG (infografik)
│   ├── gemini_helper.py     # Gemini AI görsel
│   ├── veo_helper.py        # Veo 3 video üretimi
│   ├── facebook_helper.py   # Facebook Graph API (foto + video)
│   └── config.py            # Ayarlar
├── context/                 # Claude için bağlam dosyaları
│   ├── company-profile.md   # Şirket bilgileri
│   ├── content-strategy.md  # İçerik stratejisi
│   ├── visual-guidelines.md # Görsel tasarım rehberi
│   └── social-media-expert.md # Sosyal medya uzmanlığı
├── outputs/                 # Üretilen görseller/videolar
├── setup.sh
├── requirements.txt
└── .env.example
```

## 🎨 Görsel Türleri

### 1. İnfografik (Statik)
- Glassmorphism dashboard tarzı
- Olivenet renk paleti (#4a7c4a, #0ea5e9)
- 1080x1080 PNG
- Playwright ile HTML → PNG render

### 2. Gerçekçi AI Görsel
- Gemini 2.5 Flash image generation
- Profesyonel fotoğraf tarzı
- IoT/teknoloji temalı
- 1024x1024 PNG

### 3. AI Video (Veo 3) 🆕
- Google Veo 3 video generation
- 5 saniyelik profesyonel video
- 1280x720 (16:9) MP4
- Claude Code ile optimize edilmiş prompt
- Konuya özel görsel temalar:
  - 🌱 Akıllı Tarım: Sera, sensörler, yeşil bitkiler
  - ⚡ Enerji İzleme: Sayaçlar, LED'ler, veri akışı
  - ⚙️ Kestirimci Bakım: Makineler, diagnostik
  - 🏢 Bina Otomasyonu: Modern ofis, akıllı kontrol

## 🎬 Veo 3 Video Üretimi

Bot, video prompt'u için Claude Code'u kullanır:

1. **Prompt Mühendisliği**: Claude Code, post metnini analiz eder ve Veo 3 için optimize edilmiş İngilizce prompt üretir
2. **Marka Uyumu**: Olivenet renk paleti (olive green, sky blue) ve profesyonel ton korunur
3. **Fallback Sistemi**: Veo 3 → Veo 3 Fast → Veo 2 sırasıyla denenir

Örnek Prompt (Claude Code tarafından üretilir):
```
"Slow cinematic tracking shot through a modern greenhouse,
rows of healthy green plants with small IoT sensors attached
to soil, morning sunlight streaming through glass panels,
olive green and sky blue color palette..."
```

## 🧠 Sosyal Medya Uzmanı Modu

Bot, içerik üretirken şunları analiz eder:
- Hook etkisi (ilk cümle dikkat çekiyor mu?)
- Duygusal tetikleyiciler (FOMO, merak, umut)
- KKTC pazarı uygunluğu
- Engagement tahmini

## 🔄 Sistemd Servisi (Opsiyonel)
```bash
sudo cp olivenet-social.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable olivenet-social
sudo systemctl start olivenet-social
```

## 📊 API Kullanımı

| API | Kullanım | Maliyet |
|-----|----------|---------|
| Claude Code CLI | Post metni, prompt üretimi | - |
| Gemini 2.5 Flash | AI görsel | Free tier |
| Veo 3 | AI video | Pay-per-use |
| Facebook Graph | Paylaşım | Free |

## 📄 Lisans

MIT License - Olivenet Ltd.

## 🔗 Bağlantılar

- Website: [olivenet.io](https://olivenet.io)
- GitHub: [github.com/olivenet-iot](https://github.com/olivenet-iot)
