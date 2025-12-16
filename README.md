# Olivenet Social Media Bot

Telegram uzerinden Claude Code ile Facebook post otomasyonu.

## Ozellikler

- Claude Code ile akilli post metni uretimi
- Otomatik gorsel olusturma (Playwright)
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
- Telegram Bot Token (@BotFather'dan)
- Facebook Page Access Token

## Yapilandirma

`.env.example` dosyasini `.env` olarak kopyalayin ve doldurun:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id
FACEBOOK_PAGE_ID=your_page_id
FACEBOOK_ACCESS_TOKEN=your_access_token
```

## Telegram Komutlari

| Komut/Buton | Aciklama |
|-------------|----------|
| /start | Bot'u baslat |
| /help | Yardim menusu |
| Yeni Post Olustur | Konu gir, post uret |
| Onayla & Gorsel | HTML gorsel olustur |
| Facebook'a Gonder | Paylas |

## Dosya Yapisi

```
olivenet-social-bot/
├── app/
│   ├── telegram_bot.py   # Ana bot
│   ├── claude_helper.py  # Claude Code wrapper
│   ├── renderer.py       # HTML → PNG
│   ├── facebook_helper.py
│   └── config.py
├── context/              # Claude icin baglam dosyalari
│   ├── company-profile.md
│   ├── content-strategy.md
│   └── visual-guidelines.md
├── templates/
│   └── visual-template.html
├── outputs/              # Uretilen gorseller
├── setup.sh              # Kurulum script'i
├── requirements.txt
├── .env.example
└── olivenet-social.service  # Systemd servisi
```

## Systemd Servisi (Opsiyonel)

```bash
sudo cp olivenet-social.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable olivenet-social
sudo systemctl start olivenet-social
```

## Lisans

MIT License - Olivenet Ltd.
