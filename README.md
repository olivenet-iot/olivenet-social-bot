# Olivenet Social Media Bot

Telegram üzerinden Claude Code ile akıllı Facebook post otomasyonu.

## Özellikler

### İçerik Üretimi
- **Claude Code ile akıllı post üretimi** - Sosyal medya uzmanı gibi düşünür
- **Konu öneri sistemi** - Mevsim ve güne göre akıllı öneriler
- **Geri bildirim ile düzenleme** - "Daha kısa yap", "Emoji ekle" gibi

### Görsel Üretimi (4 Seçenek)
- **İnfografik (Statik)** - Dashboard tarzı PNG görseller
- **Gerçekçi AI Görsel** - Gemini 2.5 Flash ile fotoğraf üretimi
- **FLUX.2 Pro (Premium)** - Black Forest Labs premium görsel üretimi
- **AI Video (Veo 3)** - Google Veo 3 ile profesyonel video üretimi

### Entegrasyonlar
- Telegram bot ile kolay yönetim
- Facebook Graph API entegrasyonu (fotoğraf + video)
- Olivenet marka kimliğine uygun içerik

## Hızlı Kurulum
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

## Gereksinimler

- Python 3.10+
- Claude Code CLI (kurulu ve çalışır durumda)
- Telegram Bot Token (@BotFather'dan)
- Facebook Page Access Token
- Gemini API Key (görsel + video için)
- BFL API Key (FLUX.2 Pro için - opsiyonel)

## Yapılandırma

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

# Black Forest Labs FLUX API (premium görsel - opsiyonel)
BFL_API_KEY=your_bfl_api_key
```

## Telegram Komutları

| Komut/Buton | Açıklama |
|-------------|----------|
| /start | Ana menü |
| Yeni Post Oluştur | Konu gir, post üret |
| Konu Öner | Bugüne özel 3 konu önerisi |
| Görseli Düzenle | Geri bildirim ile revize |
| Facebook'a Gönder | Paylaş |

## Dosya Yapısı
```
olivenet-social-bot/
├── app/
│   ├── telegram_bot.py      # Ana bot
│   ├── claude_helper.py     # Claude Code wrapper + prompt üretimi
│   ├── renderer.py          # HTML → PNG (infografik)
│   ├── gemini_helper.py     # Gemini AI görsel
│   ├── flux_helper.py       # FLUX.2 Pro API client
│   ├── veo_helper.py        # Veo 3 video üretimi
│   ├── facebook_helper.py   # Facebook Graph API (foto + video)
│   └── config.py            # Ayarlar
├── context/                 # Claude için bağlam dosyaları
│   ├── company-profile.md   # Şirket bilgileri
│   ├── content-strategy.md  # İçerik stratejisi
│   ├── visual-guidelines.md # Görsel tasarım rehberi
│   ├── social-media-expert.md # Sosyal medya uzmanlığı
│   └── flux-prompting-guide.md # FLUX prompt rehberi
├── outputs/                 # Üretilen görseller/videolar
├── setup.sh
├── requirements.txt
└── .env.example
```

## Görsel Türleri

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

### 3. FLUX.2 Pro (Premium)
- Black Forest Labs FLUX.2 Pro API
- En yüksek kalite AI görsel üretimi
- HEX renk kodu desteği (#4a7c4a, #38bdf8)
- Claude Code ile optimize edilmiş prompt
- 1024x1024 PNG
- Maliyet: ~$0.03/görsel

### 4. AI Video (Veo 3)
- Google Veo 3 video generation
- 5 saniyelik profesyonel video
- 1280x720 (16:9) MP4
- Claude Code ile optimize edilmiş prompt
- Konuya özel görsel temalar:
  - Akıllı Tarım: Sera, sensörler, yeşil bitkiler
  - Enerji İzleme: Sayaçlar, LED'ler, veri akışı
  - Kestirimci Bakım: Makineler, diagnostik
  - Bina Otomasyonu: Modern ofis, akıllı kontrol

## FLUX.2 Pro Prompting

Bot, FLUX prompt'u için Claude Code'u kullanır:

1. **Prompt Framework**: Subject + Action + Style + Context
2. **Renk Kontrolü**: HEX kod desteği (#4a7c4a olive green, #38bdf8 sky blue)
3. **Optimal Uzunluk**: 40-80 kelime arası
4. **Marka Uyumu**: Olivenet kimliği korunur

Örnek Prompt (Claude Code tarafından üretilir):
```
"Modern greenhouse interior with rows of healthy tomato plants,
small IoT soil moisture sensors embedded in rich dark soil,
soft natural morning sunlight filtering through glass panels,
olive green (#4a7c4a) and sky blue (#38bdf8) accent colors,
commercial agriculture photography style, f/2.8 shallow depth
of field, clean minimal composition, professional and modern"
```

## Sosyal Medya Uzmanı Modu

Bot, içerik üretirken şunları analiz eder:
- Hook etkisi (ilk cümle dikkat çekiyor mu?)
- Duygusal tetikleyiciler (FOMO, merak, umut)
- KKTC pazarı uygunluğu
- Engagement tahmini

## API Maliyetleri

| API | Kullanım | Maliyet |
|-----|----------|---------|
| Claude Code CLI | Post + prompt | Free |
| Gemini 2.5 Flash | AI görsel | Free tier |
| FLUX.2 Pro | Premium görsel | ~$0.03/görsel |
| Veo 3 | AI video | ~$0.10/video |
| Facebook Graph | Paylaşım | Free |

## Systemd Servisi
```bash
# Servis dosyasını kopyala
sudo cp olivenet-social.service /etc/systemd/system/

# Servisi etkinleştir
sudo systemctl daemon-reload
sudo systemctl enable olivenet-social
sudo systemctl start olivenet-social

# Durum kontrolü
sudo systemctl status olivenet-social
```

## Sorun Giderme

### Bot çalışmıyor
```bash
# Log kontrol
tail -f /tmp/bot.log

# Manuel başlat
cd /opt/olivenet-social
source venv/bin/activate
python3 app/telegram_bot.py
```

### API key hatası
```bash
# .env kontrolü
cat .env | grep -E "(TELEGRAM|GEMINI|BFL|FACEBOOK)"

# Test
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('BFL_API_KEY'))"
```

### FLUX kredi kontrolü
```bash
source venv/bin/activate
python3 -c "
import asyncio
from app.flux_helper import get_credits
result = asyncio.run(get_credits())
print(f'Krediler: {result}')
"
```

## Lisans

MIT License - Olivenet Ltd.

## Bağlantılar

- **Website:** [olivenet.io](https://olivenet.io)
- **GitHub:** [github.com/olivenet-iot](https://github.com/olivenet-iot)
- **FLUX API:** [bfl.ai](https://bfl.ai)
- **Gemini API:** [ai.google.dev](https://ai.google.dev)
