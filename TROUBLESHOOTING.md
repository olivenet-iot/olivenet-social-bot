# Olivenet Social Bot - Sorun Giderme

## Sık Karşılaşılan Hatalar

### 1. Instagram Token Expired

**Belirti:**
```
Error: OAuthAccessTokenException - Access token has expired
```

**Çözüm:**
1. [Facebook Developer Console](https://developers.facebook.com/) → Graph API Explorer
2. Yeni access token oluştur
3. Token'ı long-lived'a çevir:
   ```bash
   curl -X GET "https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret={APP_SECRET}&access_token={SHORT_LIVED_TOKEN}"
   ```
4. `.env` dosyasındaki `INSTAGRAM_ACCESS_TOKEN`'ı güncelle
5. Bot'u yeniden başlat

**Önlem:** Token'ları 50 günde bir yenileyin (60 gün sonra expire olur)

---

### 2. Video Generation Timeout

**Belirti:**
```
Error: Video generation timed out after 300 seconds
```

**Çözüm:**

1. **Farklı model dene:**
   ```python
   # Sora yerine Veo
   await pipeline.run_reels_content(topic="...", force_model="veo")
   ```

2. **Daha kısa süre:**
   ```python
   generate_video_sora(prompt="...", duration=4)  # 8 yerine 4
   ```

3. **Prompt'u basitleştir:**
   - Karmaşık sahnelerden kaçın
   - Tek odak noktası
   - "NO TEXT" kuralına uy

---

### 3. Rate Limit Exceeded

**Belirti:**
```
Error: (#4) Application request limit reached
```

**Çözüm:**

1. **Bekle:** Instagram rate limit'i 200 istek/saat
2. **Delay artır:**
   ```bash
   # .env
   RATE_LIMIT_DELAY=1.0  # 0.3 yerine
   ```
3. **Batch işlemleri azalt**

---

### 4. Cloudinary Upload Failed

**Belirti:**
```
Error: Cloudinary upload failed - Invalid credentials
```

**Çözüm:**

1. `.env` dosyasındaki credentials'ları kontrol et:
   ```bash
   CLOUDINARY_CLOUD_NAME=your_cloud
   CLOUDINARY_API_KEY=your_key
   CLOUDINARY_API_SECRET=your_secret
   ```

2. Cloudinary dashboard'dan credentials'ları doğrula

3. Video boyutunu kontrol et (max 100MB)

---

### 5. ElevenLabs Quota Exceeded

**Belirti:**
```
Error: QuotaExceededError - Monthly character limit reached
```

**Çözüm:**

1. [ElevenLabs Dashboard](https://elevenlabs.io/) → Usage kontrol et
2. Plan upgrade et veya
3. Kısa metinler kullan:
   ```python
   # Max 500 karakter önerisi
   speech_script = speech_script[:500]
   ```

---

### 6. Bot Yanıt Vermiyor

**Belirti:**
- Telegram komutlarına yanıt yok
- `/start` çalışmıyor

**Çözüm:**

1. **Service durumunu kontrol et:**
   ```bash
   sudo systemctl status olivenet-bot
   ```

2. **Logları incele:**
   ```bash
   tail -f /opt/olivenet-social-bot/logs/app.log
   ```

3. **Token'ı kontrol et:**
   - @BotFather'dan token'ın aktif olduğunu doğrula
   - Token'ı yenile

4. **Manuel başlat:**
   ```bash
   cd /opt/olivenet-social-bot
   source venv/bin/activate
   python -m app.telegram_pipeline
   ```

---

### 7. Database Locked

**Belirti:**
```
Error: database is locked
```

**Çözüm:**

1. **Bekleyen process'leri bul:**
   ```bash
   fuser /opt/olivenet-social-bot/data/content.db
   ```

2. **Process'leri sonlandır:**
   ```bash
   kill -9 <pid>
   ```

3. **Tek instance çalıştığından emin ol:**
   ```bash
   ps aux | grep telegram_pipeline
   ```

---

### 8. HTML Render Failed

**Belirti:**
```
Error: Playwright browser not found
```

**Çözüm:**

1. **Playwright'ı yeniden kur:**
   ```bash
   playwright install chromium
   ```

2. **Sistem bağımlılıklarını kur:**
   ```bash
   playwright install-deps
   ```

---

### 9. FFmpeg Not Found

**Belirti:**
```
Error: ffmpeg not found in PATH
```

**Çözüm:**

1. **FFmpeg kur:**
   ```bash
   sudo apt update
   sudo apt install ffmpeg
   ```

2. **Kontrol et:**
   ```bash
   ffmpeg -version
   ```

---

### 10. Instagram Container Processing Failed

**Belirti:**
```
Error: Container status: ERROR
```

**Çözüm:**

1. **Video formatını kontrol et:**
   - Codec: H.264
   - Audio: AAC
   - Çözünürlük: 720x1280 (9:16)
   - FPS: 30
   - Maks süre: 90 saniye

2. **Video'yu dönüştür:**
   ```bash
   ffmpeg -i input.mp4 -c:v libx264 -c:a aac -r 30 -vf "scale=720:1280" output.mp4
   ```

3. **Dosya boyutunu kontrol et:** Maks 100MB

---

## Log Analizi

### Log Konumları

```
/opt/olivenet-social-bot/logs/
├── app.log           # Ana uygulama logu
├── agents.log        # Agent aktiviteleri
└── errors.log        # Sadece hatalar
```

### Log Seviyeleri

| Seviye | Açıklama |
|--------|----------|
| DEBUG | Detaylı bilgi |
| INFO | Normal işlem |
| WARNING | Potansiyel sorun |
| ERROR | Hata oluştu |
| CRITICAL | Kritik hata |

### Log Filtreleme

```bash
# Sadece hatalar
grep "ERROR\|CRITICAL" logs/app.log

# Son 100 satır
tail -100 logs/app.log

# Canlı takip
tail -f logs/app.log

# Belirli agent
grep "CreatorAgent" logs/agents.log
```

---

## Veritabanı Kontrolü

### Durumu Kontrol Et

```bash
sqlite3 /opt/olivenet-social-bot/data/content.db
```

```sql
-- Son postlar
SELECT id, topic, status, created_at FROM posts ORDER BY id DESC LIMIT 10;

-- Bekleyen onaylar
SELECT id, topic FROM posts WHERE status = 'approved' AND published_at IS NULL;

-- Hook performansı
SELECT hook_type, viral_score FROM hook_performance ORDER BY viral_score DESC;
```

### Veritabanı Boyutu

```bash
du -h /opt/olivenet-social-bot/data/content.db
```

---

## API Bağlantı Testi

### Instagram

```python
from app.instagram_helper import get_account_info
info = get_account_info()
print(info)
```

### OpenAI (Sora)

```python
import openai
openai.api_key = "your_key"
# Test API call
```

### ElevenLabs

```python
from app.elevenlabs_helper import ElevenLabsHelper
tts = ElevenLabsHelper()
result = await tts.generate_speech("Test")
print(result)
```

---

## Service Yönetimi

### Yeniden Başlat

```bash
sudo systemctl restart olivenet-bot
```

### Durdur

```bash
sudo systemctl stop olivenet-bot
```

### Logları Görüntüle

```bash
sudo journalctl -u olivenet-bot -f
```

### Durumu Kontrol Et

```bash
sudo systemctl status olivenet-bot
```

---

## Acil Durumlar

### Bot Çökerse

1. Logları kaydet:
   ```bash
   cp logs/app.log logs/app_$(date +%Y%m%d_%H%M%S).log
   ```

2. Service'i yeniden başlat:
   ```bash
   sudo systemctl restart olivenet-bot
   ```

3. Bekleyen içerikleri kontrol et:
   ```sql
   SELECT * FROM posts WHERE status = 'approved' AND published_at IS NULL;
   ```

### Token Sızdıysa

1. Hemen yeni token oluştur
2. `.env` dosyasını güncelle
3. Eski token'ı iptal et
4. Service'i yeniden başlat

---

## Destek

Daha fazla yardım için:

- [ARCHITECTURE.md](ARCHITECTURE.md) - Sistem mimarisi
- [API_INTEGRATIONS.md](API_INTEGRATIONS.md) - API detayları
- [CONFIGURATION.md](CONFIGURATION.md) - Konfigürasyon
