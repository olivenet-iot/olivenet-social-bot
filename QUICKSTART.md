# Olivenet Social Bot - Hızlı Başlangıç

## Gereksinimler

- Python 3.10+
- FFmpeg (video dönüştürme için)
- Playwright (HTML render için)

---

## 1. Kurulum

### Repository'yi Klonla

```bash
git clone https://github.com/your-org/olivenet-social-bot.git
cd olivenet-social-bot
```

### Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# veya
.\venv\Scripts\activate   # Windows
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
OPENAI_API_KEY=your_key      # Sora için
GEMINI_API_KEY=your_key      # Veo için
FAL_API_KEY=your_key         # Kling için

# Görsel (En az biri)
FLUX_API_KEY=your_key

# CDN (Video için zorunlu)
CLOUDINARY_CLOUD_NAME=your_name
CLOUDINARY_API_KEY=your_key
CLOUDINARY_API_SECRET=your_secret
```

Detaylı ayarlar için: [CONFIGURATION.md](CONFIGURATION.md)

---

## 3. Veritabanı Başlatma

```bash
python -m app.database.models
```

Bu komut:
- SQLite veritabanını oluşturur
- Tabloları initialize eder
- Varsayılan stratejiyi ekler

---

## 4. Bot'u Çalıştır

### Foreground (Test için)

```bash
python -m app.telegram_pipeline
```

### Systemd Service (Production)

```bash
sudo nano /etc/systemd/system/olivenet-bot.service
```

```ini
[Unit]
Description=Olivenet Social Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/olivenet-social-bot
ExecStart=/opt/olivenet-social-bot/venv/bin/python -m app.telegram_pipeline
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable olivenet-bot
sudo systemctl start olivenet-bot
```

---

## 5. İlk İçerik Oluşturma

### Telegram'dan

1. Bot'a `/start` gönderin
2. `/manual` komutu ile manuel içerik başlatın
3. Adımları takip edin:
   - Konu onayı
   - İçerik onayı
   - Görsel onayı
   - Final onay

### Komutlar

| Komut | Açıklama |
|-------|----------|
| `/start` | Bot'u başlat |
| `/manual` | Manuel içerik oluştur |
| `/status` | Pipeline durumu |
| `/schedule` | Haftalık program |
| `/sync` | Metrikleri senkronize et |
| `/stats` | İstatistikler |

---

## 6. Doğrulama

### Logları Kontrol Et

```bash
tail -f /opt/olivenet-social-bot/logs/app.log
```

### Veritabanını Kontrol Et

```bash
sqlite3 /opt/olivenet-social-bot/data/content.db
sqlite> SELECT id, topic, status FROM posts ORDER BY id DESC LIMIT 5;
```

### Bot Durumunu Kontrol Et

```bash
sudo systemctl status olivenet-bot
```

---

## Hızlı Test

### 1. Bot Bağlantısı

Telegram'da bot'a `/start` gönderin. Yanıt gelirse bağlantı OK.

### 2. Instagram Bağlantısı

```python
from app.instagram_helper import get_account_info
info = get_account_info()
print(info)  # Hesap bilgileri görünmeli
```

### 3. Video Üretimi

```python
from app.sora_helper import generate_video_sora
result = generate_video_sora("A green field with wind turbines", duration=4)
print(result)  # {"success": True, "video_path": "..."}
```

---

## Sorun Giderme

Bot çalışmıyor mu?

1. `.env` dosyasını kontrol edin
2. Logları inceleyin: `tail -f logs/app.log`
3. Token'ların geçerli olduğunu doğrulayın

Detaylı sorun giderme: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Sonraki Adımlar

- [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) - Kullanım örnekleri
- [ARCHITECTURE.md](ARCHITECTURE.md) - Sistem mimarisi
- [API_INTEGRATIONS.md](API_INTEGRATIONS.md) - API detayları
