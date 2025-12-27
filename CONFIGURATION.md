# Olivenet Social Bot - Konfigürasyon Rehberi

## Environment Değişkenleri

Tüm ayarlar `.env` dosyasından okunur. Dosya konumu: `/opt/olivenet-social-bot/.env`

---

## Telegram

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | ✓ | Bot API token (@BotFather'dan) |
| `TELEGRAM_ADMIN_CHAT_ID` | ✓ | Admin chat ID (bildirimler için) |
| `TELEGRAM_ADMIN_USER_IDS` | - | Ek admin ID'leri (virgülle ayrılmış) |

### Telegram Bot Kurulumu

1. Telegram'da @BotFather'a gidin
2. `/newbot` komutu ile yeni bot oluşturun
3. Bot token'ı alın
4. Admin chat ID'yi bulmak için @userinfobot'a mesaj gönderin

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_admin_chat_id
```

---

## Instagram Graph API

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `INSTAGRAM_ACCESS_TOKEN` | ✓ | Long-lived access token |
| `INSTAGRAM_USER_ID` | ✓ | Instagram User ID |
| `INSTAGRAM_BUSINESS_ID` | - | Business Account ID |

### Instagram Token Alma

1. [Facebook Developer Console](https://developers.facebook.com/) → Uygulama oluştur
2. Instagram Graph API ekle
3. Graph API Explorer'da token oluştur
4. Token'ı long-lived'a çevir (60 gün)

```bash
INSTAGRAM_ACCESS_TOKEN=your_instagram_access_token
INSTAGRAM_USER_ID=your_instagram_user_id
INSTAGRAM_BUSINESS_ID=your_instagram_business_id
```

---

## Video Üretimi

### OpenAI Sora

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `OPENAI_API_KEY` | ✓ | OpenAI API key (Sora erişimi) |

```bash
OPENAI_API_KEY=your_openai_api_key
```

### Google Veo (Gemini)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `GEMINI_API_KEY` | ✓ | Google AI Studio API key |

```bash
GEMINI_API_KEY=your_gemini_api_key
```

### fal.ai (Kling AI)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `FAL_API_KEY` | ✓ | fal.ai API key |

```bash
FAL_API_KEY=your_fal_api_key
```

---

## Görsel Üretimi

### FLUX.2 Pro

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `FLUX_API_KEY` | ✓ | BFL API key |

```bash
FLUX_API_KEY=your_flux_api_key
```

### Gemini Image

Aynı `GEMINI_API_KEY` kullanılır.

---

## TTS (Sesli Reels)

### ElevenLabs

| Değişken | Zorunlu | Varsayılan | Açıklama |
|----------|---------|------------|----------|
| `ELEVENLABS_API_KEY` | ✓ | - | API key |
| `ELEVENLABS_VOICE_ID` | ✓ | - | Türkçe voice ID |
| `ELEVENLABS_MODEL` | - | `eleven_multilingual_v2` | Model |

```bash
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_voice_id
ELEVENLABS_MODEL=eleven_multilingual_v2
```

---

## CDN

### Cloudinary (Video)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `CLOUDINARY_CLOUD_NAME` | ✓ | Cloud name |
| `CLOUDINARY_API_KEY` | ✓ | API key |
| `CLOUDINARY_API_SECRET` | ✓ | API secret |

```bash
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
```

### imgbb (Görsel)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `IMGBB_API_KEY` | ✓ | imgbb API key |

```bash
IMGBB_API_KEY=your_imgbb_api_key
```

---

## Meta Ads (Opsiyonel)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `META_AD_ACCOUNT_ID` | - | Ad account ID (act_xxx) |
| `META_BUSINESS_ID` | - | Business Manager ID |

```bash
META_AD_ACCOUNT_ID=act_your_ad_account_id
```

---

## Uygulama Ayarları

### Timeouts (Saniye)

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `CLAUDE_TIMEOUT_POST` | 60 | Post üretimi timeout |
| `CLAUDE_TIMEOUT_VISUAL` | 90 | Görsel prompt timeout |
| `CLAUDE_TIMEOUT_VIDEO` | 120 | Video prompt timeout |
| `API_TIMEOUT_DEFAULT` | 30 | Genel API timeout |
| `API_TIMEOUT_VIDEO` | 300 | Video API timeout |
| `API_TIMEOUT_INSIGHTS` | 60 | Insights timeout |

### Rate Limiting

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `RATE_LIMIT_DELAY` | 0.3 | API çağrıları arası bekleme |
| `RATE_LIMIT_CAROUSEL` | 2.0 | Carousel item arası bekleme |

### İçerik Ayarları

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `MAX_INSTAGRAM_WORDS` | 120 | Maks post kelime sayısı |

### Scoring Thresholds

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `MIN_REVIEW_SCORE` | 7.0 | Onay için min skor |
| `MIN_REVIEW_SCORE_REVISE` | 5.0 | Revizyon için min skor |
| `MIN_REVIEW_SCORE_AUTONOMOUS` | 7.0 | Otonom yayın için min skor |
| `MIN_VIRAL_SCORE` | 10.0 | Viral içerik eşiği |
| `HOOK_UNDERPERFORMANCE_THRESHOLD` | 5.0 | Hook düşük performans eşiği |

### Haftalık Hedefler

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `REELS_WEEKLY_TARGET` | 7 | Haftalık Reels hedefi |
| `CAROUSEL_WEEKLY_TARGET` | 2 | Haftalık Carousel hedefi |
| `POST_WEEKLY_TARGET` | 3 | Haftalık Post hedefi |

### TTS Ayarları

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `TTS_STABILITY` | 0.5 | Ses stabilitesi (0-1) |
| `TTS_SIMILARITY_BOOST` | 0.75 | Ses benzerliği (0-1) |
| `TTS_SPEED` | 1.0 | Konuşma hızı (0.5-2.0) |

---

## Dizin Yapısı

| Path | Açıklama |
|------|----------|
| `BASE_DIR` | `/opt/olivenet-social-bot` |
| `context/` | AI context dosyaları |
| `templates/` | HTML şablonları |
| `outputs/` | Üretilen içerikler |
| `logs/` | Uygulama logları |
| `data/` | SQLite veritabanı |

`OLIVENET_BASE_DIR` env var ile base dizin override edilebilir.

---

## Örnek .env Dosyası

```bash
# ============ TELEGRAM ============
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# ============ INSTAGRAM ============
INSTAGRAM_ACCESS_TOKEN=your_ig_token
INSTAGRAM_USER_ID=your_user_id
INSTAGRAM_BUSINESS_ID=your_business_id

# ============ VIDEO GENERATION ============
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
FAL_API_KEY=your_fal_key

# ============ IMAGE GENERATION ============
FLUX_API_KEY=your_flux_key

# ============ TTS ============
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=your_voice_id

# ============ CDN ============
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_cloud_key
CLOUDINARY_API_SECRET=your_cloud_secret
IMGBB_API_KEY=your_imgbb_key

# ============ META ADS (Opsiyonel) ============
META_AD_ACCOUNT_ID=act_xxxxx
```

---

## Güvenlik Notları

- `.env` dosyasını **asla** git'e commit etmeyin
- `.gitignore`'a `.env` ekli olduğundan emin olun
- Production'da dosya izinlerini kısıtlayın: `chmod 600 .env`
- Token'ları düzenli olarak yenileyin
