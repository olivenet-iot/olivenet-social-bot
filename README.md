# Olivenet Social Media Bot

Telegram uzerinden Claude Code ile akilli Facebook post otomasyonu.

## Ozellikler

### Icerik Uretimi
- **Claude Code ile akilli post uretimi** - Sosyal medya uzmani gibi dusunur
- **Konu oneri sistemi** - Mevsim ve gune gore akilli oneriler
- **Geri bildirim ile duzenleme** - "Daha kisa yap", "Emoji ekle" gibi

### Gorsel Uretimi (3 Secenek)
- **Infografik (Statik)** - Dashboard tarzi PNG gorseller
- **Animasyonlu Video** - Olivenet website tarzi MP4 (pulse, fade-in efektleri)
- **Gercekci AI Gorsel** - Gemini 2.5 Flash ile fotograf uretimi

### Entegrasyonlar
- Telegram bot ile kolay yonetim
- Facebook Graph API entegrasyonu
- Olivenet marka kimligine uygun icerik

## Hizli Kurulum

```bash
# 1. Repo'yu klonla
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
cd olivenet-social-bot

# 2. Kurulum script'ini calistir
chmod +x setup.sh
./setup.sh

# 3. Token'lari ayarla
nano .env

# 4. Bot'u baslat
python3 app/telegram_bot.py
```

## Gereksinimler

- Python 3.10+
- Claude Code CLI (kurulu ve calisir durumda)
- ffmpeg (animasyonlu video icin)
- Telegram Bot Token (@BotFather'dan)
- Facebook Page Access Token
- Gemini API Key (opsiyonel, AI gorsel icin)

## Yapilandirma

`.env.example` dosyasini `.env` olarak kopyalayin ve doldurun:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Facebook
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_ACCESS_TOKEN=your_access_token

# Gemini AI (opsiyonel)
GEMINI_API_KEY=your_gemini_api_key
```

## Telegram Komutlari

| Komut/Buton | Aciklama |
|-------------|----------|
| /start | Ana menu |
| Yeni Post Olustur | Konu gir, post uret |
| Konu Oner | Bugune ozel 3 konu onerisi |
| Gorseli Duzenle | Geri bildirim ile revize |
| Facebook'a Gonder | Paylas |

## Dosya Yapisi

```
olivenet-social-bot/
├── app/
│   ├── telegram_bot.py      # Ana bot
│   ├── claude_helper.py     # Claude Code wrapper + post uretimi
│   ├── renderer.py          # HTML -> PNG (statik)
│   ├── animated_renderer.py # HTML -> MP4 (animasyonlu)
│   ├── gemini_helper.py     # Gemini AI gorsel
│   ├── facebook_helper.py   # Facebook Graph API
│   └── config.py            # Ayarlar
├── context/                 # Claude icin baglam dosyalari
│   ├── company-profile.md   # Sirket bilgileri
│   ├── content-strategy.md  # Icerik stratejisi
│   ├── visual-guidelines.md # Gorsel tasarim rehberi
│   └── social-media-expert.md # Sosyal medya uzmanligi
├── templates/
│   └── visual-template.html
├── outputs/                 # Uretilen gorseller/videolar
├── assets/                  # Logo vb.
├── setup.sh
├── requirements.txt
├── .env.example
└── olivenet-social.service
```

## Gorsel Turleri

### 1. Infografik (Statik)
- Glassmorphism dashboard tarzi
- Olive renk paleti (#4a7c4a, #0ea5e9)
- 1080x1080 PNG

### 2. Animasyonlu Video
- Pulse ring efektleri
- Fade-in metin animasyonlari
- SVG SMIL animasyonlari
- 4 saniye MP4

### 3. Gercekci AI Gorsel
- Gemini 2.5 Flash
- Profesyonel fotograf tarzi
- IoT/teknoloji temali

## Sosyal Medya Uzmani Modu

Bot, icerik uretirken sunlari analiz eder:
- Hook etkisi (ilk cumle dikkat cekiyor mu?)
- Duygusal tetikleyiciler (FOMO, merak, umut)
- KKTC pazari uygunlugu
- Engagement tahmini

## Systemd Servisi

```bash
sudo cp olivenet-social.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable olivenet-social
sudo systemctl start olivenet-social
```

## Lisans

MIT License - Olivenet Ltd.

## Baglantilar

- Website: https://olivenet.io
- GitHub: https://github.com/olivenet-iot
