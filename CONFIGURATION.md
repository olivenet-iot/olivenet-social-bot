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
| `OPENAI_API_KEY` | ✓ | OpenAI API key (Sora 2 / Sora 2 Pro) |

```bash
OPENAI_API_KEY=your_openai_api_key
```

### Google Veo (Gemini)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `GEMINI_API_KEY` | ✓ | Google AI Studio API key (Veo) |

```bash
GEMINI_API_KEY=your_gemini_api_key
```

### Kling Direct API

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `KLING_ACCESS_KEY` | ✓ | Kling AI API access key |
| `KLING_SECRET_KEY` | ✓ | Kling AI API secret key |

```bash
KLING_ACCESS_KEY=your_kling_access_key
KLING_SECRET_KEY=your_kling_secret_key
```

**Not:** JWT auth ile `api-singapore.klingai.com`'a bağlanır. Token 30 dk geçerli, otomatik yenilenir.

### FAL.ai (Infographic + Lip-sync)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `FAL_API_KEY` | ✓ | fal.ai API key (Nano Banana infographic üretimi + opsiyonel lip-sync) |

```bash
FAL_API_KEY=your_fal_api_key  # Nano Banana infographic + lip-sync
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

### Nano Banana (fal-ai/nano-banana-pro)

`FAL_API_KEY` kullanılır. İnfographic ve carousel slide üretimi için fal.ai queue API ile httpx.

---

## TTS (Sesli Reels)

### OpenAI TTS (Aktif)

| Değişken | Zorunlu | Varsayılan | Açıklama |
|----------|---------|------------|----------|
| `OPENAI_API_KEY` | ✓ | - | OpenAI API key (Sora ile paylaşımlı) |
| `OPENAI_TTS_MODEL` | - | `gpt-4o-mini-tts` | TTS modeli |
| `OPENAI_TTS_VOICE_MALE` | - | `onyx` | Varsayılan/erkek ses |
| `OPENAI_TTS_VOICE_FEMALE` | - | `nova` | Kadın ses (conversational) |
| `OPENAI_TTS_VOICE_NARRATOR` | - | `fable` | Narrator ses (B-roll) |
| `OPENAI_TTS_VOICE_CARTOON_MALE` | - | `echo` | Cartoon erkek |
| `OPENAI_TTS_VOICE_CARTOON_FEMALE` | - | `shimmer` | Cartoon kadın |
| `OPENAI_TTS_SPEED` | - | `1.0` | Konuşma hızı (0.25-4.0) |

Mevcut sesler: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse, marin, cedar

### ElevenLabs (Yedek/Backup)

| Değişken | Zorunlu | Varsayılan | Açıklama |
|----------|---------|------------|----------|
| `ELEVENLABS_API_KEY` | - | - | API key |
| `ELEVENLABS_VOICE_ID` | - | - | Varsayılan Türkçe voice ID |
| `ELEVENLABS_MODEL` | - | `eleven_multilingual_v2` | Model |

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

## Brain Agent (v2)

| Değişken | Zorunlu | Varsayılan | Açıklama |
|----------|---------|------------|----------|
| `BRAIN_DRY_RUN` | - | `true` | `true` = kararlar loglanır, üretim yapılmaz |
| `BRAIN_CYCLE_MINUTES` | - | `120` | Brain karar döngüsü aralığı (dakika) |
| `BRAIN_MAX_DAILY_POSTS` | - | `2` | Günlük max paylaşım sayısı |
| `BRAIN_MIN_POST_INTERVAL_HOURS` | - | `4` | Paylaşımlar arası min süre (saat) |
| `BRAIN_MIN_SCORE_PRODUCE` | - | `60` | Üretim için min fırsat skoru |

```bash
BRAIN_DRY_RUN=true
BRAIN_CYCLE_MINUTES=120
BRAIN_MAX_DAILY_POSTS=2
BRAIN_MIN_POST_INTERVAL_HOURS=4
BRAIN_MIN_SCORE_PRODUCE=60
```

---

## Feed System (v2)

| Değişken | Zorunlu | Varsayılan | Açıklama |
|----------|---------|------------|----------|
| `FEED_POLL_MINUTES` | - | `30` | Feed çekme aralığı (dakika) |
| `EXPIRY_CHECK_HOURS` | - | `6` | Eski fırsat temizleme aralığı (saat) |

```bash
FEED_POLL_MINUTES=30
EXPIRY_CHECK_HOURS=6
```

---

## Subtitle Ayarları

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `SUBTITLE_ENABLED` | `false` | Otomatik altyazı üretimi |
| `WHISPER_MODEL_SIZE` | `small` | Whisper model: tiny, base, small, medium, large |
| `SUBTITLE_FONT` | `DejaVu Sans` | Altyazı fontu |
| `SUBTITLE_FONT_SIZE` | `48` | Altyazı font boyutu (px) |
| `SUBTITLE_MAX_CHARS` | `35` | Satır başına max karakter |
| `SUBTITLE_MAX_LINES` | `2` | Max altyazı satırı |

---

## Story Boost Ayarları

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `STORY_BOOST_ENABLED` | `true` | Post sonrası otomatik Story boost |
| `STORY_BOOST_REMINDER_DELAY` | `15` | Reminder story gecikmesi (dakika) |
| `STORY_BOOST_TELEGRAM_FALLBACK` | `true` | API başarısız olursa Telegram bildirimi |

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
KLING_ACCESS_KEY=your_kling_access_key
KLING_SECRET_KEY=your_kling_secret_key

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

# ============ BRAIN AGENT (v2) ============
BRAIN_DRY_RUN=true
BRAIN_CYCLE_MINUTES=120
BRAIN_MAX_DAILY_POSTS=2
BRAIN_MIN_POST_INTERVAL_HOURS=4
BRAIN_MIN_SCORE_PRODUCE=60

# ============ FEED SYSTEM (v2) ============
FEED_POLL_MINUTES=30
EXPIRY_CHECK_HOURS=6

# ============ OPSIYONEL ============
FAL_API_KEY=your_fal_key  # Sadece lip-sync için
```

---

## Güvenlik Notları

- `.env` dosyasını **asla** git'e commit etmeyin
- `.gitignore`'a `.env` ekli olduğundan emin olun
- Production'da dosya izinlerini kısıtlayın: `chmod 600 .env`
- Token'ları düzenli olarak yenileyin
- Kling JWT token'ları otomatik yenilenir (30 dk)
