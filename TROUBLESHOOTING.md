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
   # Kling 3.0 Pro en hızlı (2-3 dk)
   result = await kling.generate_video(prompt="...", duration=5)
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

### 4. Kling API Authentication Failed

**Belirti:**
```
Error: JWT authentication failed
Error: KLING_ACCESS_KEY ve KLING_SECRET_KEY tanimli degil
```

**Çözüm:**

1. `.env` dosyasında key'lerin doğru olduğunu kontrol edin:
   ```bash
   KLING_ACCESS_KEY=your_access_key
   KLING_SECRET_KEY=your_secret_key
   ```

2. Key'lerin geçerli olduğunu doğrulayın (Kling AI dashboard'dan)

3. JWT token otomatik yenilenir (30 dk), manual müdahale gerekmez

4. API endpoint: `api-singapore.klingai.com` — ağ erişimini kontrol edin

---

### 5. Cloudinary Upload Failed

**Belirti:**
```
Error: Cloudinary upload failed - Invalid credentials
```

**Çözüm:**

1. `.env` dosyasındaki credentials'ları kontrol et
2. Cloudinary dashboard'dan credentials'ları doğrula
3. Video boyutunu kontrol et (max 100MB)

---

### 6. ElevenLabs Quota Exceeded

**Belirti:**
```
Error: QuotaExceededError - Monthly character limit reached
```

**Çözüm:**

1. [ElevenLabs Dashboard](https://elevenlabs.io/) → Usage kontrol et
2. Plan upgrade et veya
3. Kısa metinler kullan (max 500 karakter önerisi)

---

### 7. Bot Yanıt Vermiyor

**Belirti:**
- Telegram komutlarına yanıt yok
- `/start` çalışmıyor

**Çözüm:**

1. **Service durumunu kontrol et:**
   ```bash
   sudo systemctl status olivenet-bot-v2
   ```

2. **Logları incele:**
   ```bash
   tail -f /opt/olivenet-social-bot/logs/app.log
   ```

3. **Token'ı kontrol et:**
   - @BotFather'dan token'ın aktif olduğunu doğrula

4. **Manuel başlat:**
   ```bash
   cd /opt/olivenet-social-bot
   source venv/bin/activate
   python3 app/main.py
   ```

---

### 8. Database Locked

**Belirti:**
```
Error: database is locked
```

**Çözüm:**

1. **Bekleyen process'leri bul:**
   ```bash
   fuser /opt/olivenet-social-bot/data/content.db
   ```

2. **Tek instance çalıştığından emin ol:**
   ```bash
   ps aux | grep "app/main.py"
   ```

---

### 9. HTML Render Failed

**Belirti:**
```
Error: Playwright browser not found
```

**Çözüm:**

1. **Playwright'ı yeniden kur:**
   ```bash
   playwright install chromium
   playwright install-deps
   ```

**Not:** renderer.py carousel slide rendering için hala kullanılıyor (template dosyaları olmadan).

---

### 10. Instagram Container Processing Failed

**Belirti:**
```
Error: Container status: ERROR
```

**Çözüm:**

1. Video formatını kontrol et: H.264, AAC, 720x1280, 30fps, max 90s
2. Video'yu dönüştür:
   ```bash
   ffmpeg -i input.mp4 -c:v libx264 -c:a aac -r 30 -vf "scale=720:1280" output.mp4
   ```
3. Dosya boyutunu kontrol et: Maks 100MB

---

## Brain Agent Sorun Giderme

### Brain Karar Vermiyor

**Belirti:** `/brain` komutu hep "wait" gösteriyor

**Kontrol Listesi:**

1. **Havuzda fırsat var mı?**
   ```
   /pool
   ```
   Eğer boş ise → Feed'leri kontrol edin: `/feeds`

2. **Sistem duraklatılmış mı?**
   ```
   /resume  # Sistemi devam ettir
   ```

3. **Gece saati mi?** Brain 23:00-07:00 arası üretim yapmaz

4. **Min interval geçmiş mi?** Son paylaşımdan `BRAIN_MIN_POST_INTERVAL_HOURS` saat geçmeli

5. **Min skor sağlanıyor mu?** Fırsatın skoru `BRAIN_MIN_SCORE_PRODUCE` üstünde olmalı

6. **Dry-run aktif mi?**
   ```bash
   grep BRAIN_DRY_RUN .env
   # true ise kararlar loglanır ama üretim yapılmaz
   ```

### Brain Agent Logları

```bash
# Brain kararlarını izle
grep "Brain decision" logs/app.log | tail -10

# Dry-run kararlarını izle
grep "DRY-RUN" logs/app.log | tail -10

# Agent log'larını kontrol et
sqlite3 data/content.db "SELECT timestamp, json_extract(output_data, '$.action'), json_extract(output_data, '$.reason') FROM agent_logs WHERE agent_name='brain' ORDER BY timestamp DESC LIMIT 10;"
```

### Feed'ler Çalışmıyor

**Belirti:** `/feeds` boş veya hata gösteriyor

**Çözüm:**

1. İnternet bağlantısını kontrol edin
2. Feed URL'lerinin erişilebilir olduğunu kontrol edin:
   ```bash
   curl -s https://www.iot-now.com/feed/ | head -5
   ```
3. `FEED_POLL_MINUTES` değerini kontrol edin (varsayılan 30)
4. Logları inceleyin:
   ```bash
   grep "FEED" logs/app.log | tail -10
   ```

---

## v2 Service Yönetimi

### Yeniden Başlat

```bash
sudo systemctl restart olivenet-bot-v2
```

### Durdur

```bash
sudo systemctl stop olivenet-bot-v2
```

### Logları Görüntüle

```bash
sudo journalctl -u olivenet-bot-v2 -f
```

### Durumu Kontrol Et

```bash
sudo systemctl status olivenet-bot-v2
```

---

## Log Analizi

### Log Konumları

```
/opt/olivenet-social-bot/logs/
├── app.log           # Ana uygulama logu
├── agents.log        # Agent aktiviteleri
└── errors.log        # Sadece hatalar
```

### Log Filtreleme

```bash
# Sadece hatalar
grep "ERROR\|CRITICAL" logs/app.log

# Brain Agent kararları
grep "Brain decision\|DRY-RUN\|BRAIN" logs/app.log

# Feed aktivitesi
grep "FEED\|feed" logs/app.log

# Son 100 satır
tail -100 logs/app.log

# Canlı takip
tail -f logs/app.log
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

-- İçerik fırsatları durumu
SELECT status, COUNT(*) FROM content_opportunities GROUP BY status;

-- Hook performansı
SELECT hook_type, viral_score FROM hook_performance ORDER BY viral_score DESC;

-- Brain Agent son kararları
SELECT timestamp, json_extract(output_data, '$.action') as decision
FROM agent_logs WHERE agent_name = 'brain'
ORDER BY timestamp DESC LIMIT 5;
```

---

## API Bağlantı Testi

### Instagram

```python
from app.instagram_helper import get_account_info
info = get_account_info()
print(info)
```

### Kling Direct API

```python
from app.kling_helper import KlingHelper
kling = KlingHelper()
token = kling._generate_jwt()
print(f"JWT token generated: {token[:20]}...")
```

### ElevenLabs

```python
from app.elevenlabs_helper import ElevenLabsHelper
tts = ElevenLabsHelper()
result = await tts.generate_speech("Test")
print(result)
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
   sudo systemctl restart olivenet-bot-v2
   ```

3. Bekleyen içerikleri kontrol et:
   ```sql
   SELECT * FROM posts WHERE status = 'approved' AND published_at IS NULL;
   SELECT * FROM content_opportunities WHERE status = 'producing';
   ```

### Token Sızdıysa

1. Hemen yeni token oluştur
2. `.env` dosyasını güncelle
3. Eski token'ı iptal et
4. Service'i yeniden başlat

---

## Destek

Daha fazla yardım için:

- [ARCHITECTURE.md](ARCHITECTURE.md) - v2 sistem mimarisi
- [API_INTEGRATIONS.md](API_INTEGRATIONS.md) - API detayları
- [CONFIGURATION.md](CONFIGURATION.md) - Konfigürasyon
