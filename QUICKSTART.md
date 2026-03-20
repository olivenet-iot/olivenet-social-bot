# Olivenet Social Bot - Hızlı Başlangıç

## Gereksinimler

- Python 3.10+
- FFmpeg (video dönüştürme için)
- Playwright (carousel slide render için)

---

## 1. Kurulum

### Repository'yi Klonla

```bash
git clone https://github.com/olivenet-iot/olivenet-social-bot.git
cd olivenet-social-bot
```

### Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Bağımlılıkları Yükle

```bash
pip install -r requirements.txt
```

### Playwright Kurulumu

```bash
playwright install chromium
```

---

## 2. Konfigürasyon

### .env Dosyası Oluştur

```bash
cp .env.example .env
nano .env  # veya tercih ettiğiniz editör
```

### Minimum Gerekli Ayarlar

```bash
# Telegram (Zorunlu)
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Instagram (Zorunlu)
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_USER_ID=your_user_id

# Video (En az biri)
OPENAI_API_KEY=your_key          # Sora
GEMINI_API_KEY=your_key          # Veo + Nano Banana
KLING_ACCESS_KEY=your_key        # Kling Direct API
KLING_SECRET_KEY=your_key        # Kling Direct API

# Görsel
FLUX_API_KEY=your_key

# CDN (Video için zorunlu)
CLOUDINARY_CLOUD_NAME=your_name
CLOUDINARY_API_KEY=your_key
CLOUDINARY_API_SECRET=your_secret

# Brain Agent (v2)
BRAIN_DRY_RUN=true               # Başlangıçta true önerilir
```

Detaylı ayarlar için: [CONFIGURATION.md](CONFIGURATION.md)

---

## 3. Kling Direct API Kurulumu

1. [Kling AI Platform](https://klingai.com) hesabı oluşturun
2. API erişimi talep edin
3. Access Key ve Secret Key alın
4. `.env`'e ekleyin:

```bash
KLING_ACCESS_KEY=your_access_key
KLING_SECRET_KEY=your_secret_key
```

API JWT auth kullanır, token otomatik yenilenir. Endpoint: `api-singapore.klingai.com`

---

## 4. Veritabanı Başlatma

```bash
python3 -m app.database.models
```

Bu komut:
- SQLite veritabanını oluşturur (12 tablo)
- Migration'ları çalıştırır
- Varsayılan stratejiyi ekler

---

## 5. Bot'u Çalıştır

### v2 Mode (Brain + Feed + Telegram — Önerilen)

```bash
python3 app/main.py
```

Bu mod:
- v2 Engine başlatır (FeedAggregator, BrainAgent, V2Scheduler)
- v1 Pipeline'ı paralel çalıştırır
- Telegram bot'u başlatır (14 komut aktif)

### Systemd Service (Production)

```bash
sudo nano /etc/systemd/system/olivenet-bot-v2.service
```

```ini
[Unit]
Description=Olivenet Social Bot v2
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/olivenet-social-bot
ExecStart=/opt/olivenet-social-bot/venv/bin/python3 app/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable olivenet-bot-v2
sudo systemctl start olivenet-bot-v2
```

---

## 6. Brain Agent Dry-Run Test

Brain Agent varsayılan olarak `BRAIN_DRY_RUN=true` ile başlar — kararlar loglanır ama üretim yapılmaz.

### Doğrulama Adımları

1. **Bot'u başlat:**
   ```bash
   python3 app/main.py
   ```

2. **Feed'leri kontrol et:**
   Telegram'da `/feeds` komutu gönderin → Feed durumunu gösterir

3. **Havuzu kontrol et:**
   Telegram'da `/pool` komutu → İçerik fırsatları listesi

4. **Brain kararlarını izle:**
   Telegram'da `/brain` komutu → Son kararlar (produce/wait)

5. **Üretimi aktifleştir (hazır olduğunuzda):**
   ```bash
   # .env'de değiştir:
   BRAIN_DRY_RUN=false
   ```
   ```bash
   sudo systemctl restart olivenet-bot-v2
   ```

---

## 7. İlk İçerik Oluşturma

### Telegram'dan

1. Bot'a `/start` gönderin
2. `/manual` komutu ile manuel içerik başlatın
3. Adımları takip edin:
   - Konu onayı
   - İçerik onayı
   - Görsel onayı
   - Final onay

### v2 ile Otonom Üretim

Brain Agent `BRAIN_DRY_RUN=false` olduğunda otomatik olarak:
1. Feed'lerden en uygun fırsatı seçer
2. Creative parametreleri belirler (model, stil, hook)
3. Uygun production pipeline'ı tetikler
4. İçerik üretir ve yayınlar

### Telegram Komutları (14)

| Komut | Açıklama |
|-------|----------|
| `/start` | Bot'u başlat |
| `/status` | Pipeline durumu |
| `/manual` | Manuel içerik oluştur |
| `/stats` | İstatistikler |
| `/next` | Sıradaki içerik |
| `/schedule` | Haftalık program |
| `/sync` | Metrikleri senkronize et |
| `/prompts` | Prompt istatistikleri |
| `/pool` | İçerik fırsat havuzu |
| `/brain` | Brain Agent kararları |
| `/feeds` | Feed aggregator durumu |
| `/pause` | Sistemi duraklat |
| `/resume` | Sistemi devam ettir |
| `/force` | Fırsatı hemen üret |

---

## 8. Doğrulama

### Logları Kontrol Et

```bash
tail -f /opt/olivenet-social-bot/logs/app.log
```

### Veritabanını Kontrol Et

```bash
sqlite3 /opt/olivenet-social-bot/data/content.db
sqlite> SELECT id, topic, status FROM posts ORDER BY id DESC LIMIT 5;
sqlite> SELECT COUNT(*), status FROM content_opportunities GROUP BY status;
```

### Bot Durumunu Kontrol Et

```bash
sudo systemctl status olivenet-bot-v2
```

### Brain Agent Logları

```bash
grep "BRAIN" /opt/olivenet-social-bot/logs/app.log | tail -20
```

---

## Sorun Giderme

Bot çalışmıyor mu?

1. `.env` dosyasını kontrol edin
2. Logları inceleyin: `tail -f logs/app.log`
3. Token'ların geçerli olduğunu doğrulayın
4. Kling API: `KLING_ACCESS_KEY` ve `KLING_SECRET_KEY` doğru mu?

Detaylı sorun giderme: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Sonraki Adımlar

- [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) - Kullanım örnekleri
- [ARCHITECTURE.md](ARCHITECTURE.md) - v2 sistem mimarisi
- [API_INTEGRATIONS.md](API_INTEGRATIONS.md) - API detayları
