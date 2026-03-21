# Olivenet Social Bot - API Entegrasyonları

## Özet Tablo

| API | Sağlayıcı | Dosya | Amaç |
|-----|-----------|-------|------|
| Instagram Graph | Meta | `instagram_helper.py` | Post yayınlama, insights |
| Instagram Insights | Meta | `insights_helper.py` | Metrik çekme |
| Meta Ads | Meta | `meta_ads_helper.py` | Reklam metrikleri |
| Sora | OpenAI | `sora_helper.py` | Video üretimi |
| Veo 3.1 | Google | `veo_helper.py` | Video üretimi |
| Kling 3.0 Pro | Kling Direct API | `kling_helper.py` | Video üretimi (JWT auth) |
| FLUX.2 Pro | BFL/Replicate | `flux_helper.py` | Görsel üretimi |
| Nano Banana | fal.ai (fal-ai/nano-banana-pro) | `nano_banana_helper.py` | İnfographic üretimi |
| ElevenLabs | ElevenLabs | `elevenlabs_helper.py` | Türkçe TTS |
| Cloudinary | Cloudinary | `cloudinary_helper.py` | Video CDN |
| Telegram | Telegram | `telegram_pipeline.py` | Bot arayüzü |

---

## 1. Instagram Graph API

### Genel Bilgi
- **Versiyon:** v21.0
- **Base URL:** `https://graph.instagram.com/v21.0`
- **Auth:** Long-lived Access Token
- **Dosya:** `app/instagram_helper.py`

### Endpoints

| Endpoint | Method | Amaç |
|----------|--------|------|
| `/{user_id}` | GET | Hesap bilgisi |
| `/{user_id}/media` | POST | Media container oluştur |
| `/{container_id}` | GET | Container durumu kontrol |
| `/{user_id}/media_publish` | POST | Media yayınla |
| `/{media_id}/insights` | GET | Post metrikleri |

### Fonksiyonlar

```python
get_account_info() -> dict
post_photo_to_instagram(image_url, caption) -> str  # post_id
post_video_to_instagram(video_url, caption) -> str  # post_id
post_carousel_to_instagram(image_urls, caption) -> str  # post_id
post_reels_to_instagram(video_path, caption) -> str  # post_id
```

### Video Gereksinimleri
- **Codec:** H.264 (video), AAC (audio)
- **Çözünürlük:** 720x1280 (9:16)
- **FPS:** 30
- **Maks Süre:** 90 saniye
- **Format:** MP4

---

## 2. Instagram Insights API

### Genel Bilgi
- **Dosya:** `app/insights_helper.py`
- **Rate Limit:** 200 istek/saat

### Metrikler

| Metrik | Reels | Image | Açıklama |
|--------|-------|-------|----------|
| `plays` | ✓ | - | Video oynatma |
| `reach` | ✓ | ✓ | Ulaşılan kişi |
| `saved` | ✓ | ✓ | Kaydetme |
| `shares` | ✓ | ✓ | Paylaşım |
| `comments` | ✓ | ✓ | Yorum |
| `likes` | ✓ | ✓ | Beğeni |
| `ig_reels_avg_watch_time` | ✓ | - | Ort. izleme süresi (ms) |

### Fonksiyonlar

```python
get_instagram_reels_insights(media_id) -> dict
get_instagram_media_type(media_id) -> str  # VIDEO, IMAGE, CAROUSEL_ALBUM
get_recent_media(limit=25) -> list
```

---

## 3. OpenAI Sora (Video)

### Genel Bilgi
- **Endpoint:** `https://api.openai.com/v1/videos`
- **Dosya:** `app/sora_helper.py`
- **Modeller:** sora-2, sora-2-pro

### Parametreler

| Parametre | Değerler | Varsayılan |
|-----------|----------|------------|
| `duration` | 4, 8, 12 saniye | 8 |
| `size` | 720x1280 | 720x1280 |
| `model` | sora-2, sora-2-pro | sora-2 |

### Fonksiyon

```python
generate_video_sora(
    prompt: str,
    duration: int = 8,
    size: str = "720x1280",
    model: str = "sora-2",
    voice_mode: bool = False
) -> dict
# Döner: {"success": bool, "video_path": str, "duration": int}
```

### Notlar
- sora-2-pro: Native speech destekli, conversational reels için ideal
- **NO TEXT** kuralı - video içinde metin yok
- Sinematik ve görsel odaklı promptlar

---

## 4. Google Veo 3.1 (Video)

### Genel Bilgi
- **SDK:** google-generativeai
- **Dosya:** `app/veo_helper.py`
- **Model:** veo-3.1-generate-preview

### Parametreler

| Parametre | Değerler | Varsayılan |
|-----------|----------|------------|
| `duration_seconds` | 4, 6, 8 | 8 |
| `aspect_ratio` | 9:16, 16:9, 1:1 | 9:16 |

### Fonksiyon

```python
generate_video_veo3(
    prompt: str,
    aspect_ratio: str = "9:16",
    duration_seconds: int = 8,
    model: str = "veo-3.1-generate-preview"
) -> dict
# Döner: {"success": bool, "video_path": str, "file_size_mb": float}
```

### Notlar
- Native audio + lip-sync destekli
- Doğa/açık alan sahneleri için güçlü

---

## 5. Kling 3.0 Pro (Direct API)

### Genel Bilgi
- **Base URL:** `https://api-singapore.klingai.com`
- **Auth:** JWT (HS256) — `KLING_ACCESS_KEY` / `KLING_SECRET_KEY`
- **Dosya:** `app/kling_helper.py`
- **Model:** kling-v3 (Kling 3.0 Pro)

### JWT Auth

```python
# Otomatik token yönetimi (30 dk expiry, 5 dk kala yenilenir)
headers = {"alg": "HS256", "typ": "JWT"}
payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
token = jwt.encode(payload, secret_key, algorithm="HS256", headers=headers)
```

### Parametreler

| Parametre | Değerler | Varsayılan |
|-----------|----------|------------|
| `duration` | 5, 10, 15 saniye | 5 |
| `aspect_ratio` | 9:16, 16:9, 1:1 | 9:16 |
| `model_name` | kling-v3 | kling-v3 |
| `mode` | pro | pro |
| `generate_audio` | true/false | None |
| `cfg_scale` | 0.0-1.0 | 0.5 |

### Fonksiyon

```python
from app.kling_helper import KlingHelper

kling = KlingHelper()
result = await kling.generate_video(
    prompt: str,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    model_name: str = "kling-v3",
    mode: str = "pro",
    negative_prompt: str = "blur, distort, low quality",
    cfg_scale: float = 0.5,
    generate_audio: Optional[bool] = None
) -> dict
# Döner: {"success": bool, "video_path": str, "video_id": str}
```

### Notlar
- Hızlı üretim (2-3 dakika)
- 15 saniyeye kadar video
- Native audio destekli (ambient ses)
- Fizik tabanlı hareket simülasyonu
- Endüstriyel ve gerçekçi sahneler için ideal
- `config.py`'de `fal_api_key` alanı hala mevcut (lip-sync için opsiyonel/legacy)

---

## 6. FLUX.2 Pro (Görsel)

### Genel Bilgi
- **Endpoint:** `https://api.bfl.ai/v1/flux-2-pro`
- **Dosya:** `app/flux_helper.py`

### Parametreler

| Parametre | Değerler | Varsayılan |
|-----------|----------|------------|
| `width` | 512-1024 | 1024 |
| `height` | 512-1024 | 1024 |
| `output_format` | png, jpeg | png |
| `safety_tolerance` | 0-3 | 2 |

### Fonksiyon

```python
generate_image_flux(
    prompt: str,
    output_path: str = None,
    width: int = 1024,
    height: int = 1024,
    output_format: str = "png"
) -> str  # image_path
```

---

## 7. Nano Banana (fal.ai — İnfographic)

### Genel Bilgi
- **Model:** fal-ai/nano-banana-pro (via fal.ai queue API)
- **HTTP Client:** httpx (async)
- **Dosya:** `app/nano_banana_helper.py`
- **Amaç:** HTML template'lerin yerini alan AI infographic üretimi
- **Text Accuracy:** %94

### Özellikler
- Olivenet marka renkleri ile infographic üretimi
- Carousel slide üretimi
- Logo overlay

### Fonksiyonlar

```python
# Tekli infographic
result = await generate_infographic(topic, post_text)
# Döner: {"success": bool, "image_path": str}

# Carousel slide'ları
slides = await generate_carousel_slides(topic, slide_data, count=5)
# Döner: [{"success": bool, "image_path": str}, ...]

# Logo overlay
add_logo_overlay(image_path, position="bottom_left", logo_scale=0.12)
```

---

## 8. OpenAI TTS (Sesli Reels)

### Genel Bilgi
- **Endpoint:** `POST https://api.openai.com/v1/audio/speech`
- **Dosya:** `app/openai_tts_helper.py`
- **Model:** gpt-4o-mini-tts (instructions parametresi ile ton kontrolü)
- **Maliyet:** $15/1M karakter (tts-1), $30/1M karakter (tts-1-hd)

### Sesler

| Voice | Adı | Kullanım |
|-------|-----|----------|
| `onyx` | Varsayılan/erkek | Standard voice reels, haber |
| `nova` | Kadın | Conversational reels |
| `fable` | Narrator | B-roll voiceover |
| `echo` | Cartoon erkek | Animasyon |
| `shimmer` | Cartoon kadın | Animasyon |

Tüm sesler: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse, marin, cedar

### Fonksiyon

```python
from app.openai_tts_helper import generate_speech_with_retry, generate_dialog_audio

# Tekli ses
result = await generate_speech_with_retry(
    text="Merhaba dünya",
    voice_id="onyx",       # opsiyonel, varsayılan: onyx
    max_retries=3
)
# Döner: {"success": bool, "audio_path": str, "duration_seconds": float}

# Diyalog (erkek/kadın)
result = await generate_dialog_audio(
    dialog_lines=[{"speaker": "male", "text": "..."}, {"speaker": "female", "text": "..."}],
    male_voice_id="onyx",
    female_voice_id="nova"
)
# Döner: {"success": bool, "audio_path": str, "total_duration": float, "audio_segments": list}
```

### ElevenLabs (Yedek)
- **Dosya:** `app/elevenlabs_helper.py` (backup olarak saklanıyor)
- **Model:** eleven_multilingual_v2

---

## 9. Cloudinary (Video CDN)

### Genel Bilgi
- **Dosya:** `app/cloudinary_helper.py`
- **Amaç:** Video dosyalarını Instagram için CDN'e yükleme

### Fonksiyonlar

```python
upload_video_to_cloudinary(video_path, folder="olivenet-reels") -> dict
# Döner: {"success": bool, "url": str, "public_id": str, "duration": float}

delete_from_cloudinary(public_id) -> bool
```

### Workflow
```
Local Video → FFmpeg Convert → Cloudinary Upload → CDN URL → Instagram API
```

---

## 10. Meta Ads API

### Genel Bilgi
- **Versiyon:** v21.0
- **Endpoint:** `https://graph.facebook.com/v21.0/{ad_account_id}/insights`
- **Dosya:** `app/meta_ads_helper.py`

### Fonksiyonlar

```python
get_ad_account_info() -> dict
get_campaign_insights(date_start, date_stop, level="campaign") -> list
```

---

## 11. Telegram Bot API

### Genel Bilgi
- **Library:** python-telegram-bot
- **Dosya:** `app/telegram_pipeline.py`

### Komutlar (14)

| Komut | Açıklama |
|-------|----------|
| `/start` | Bot başlat |
| `/status` | Pipeline durumu |
| `/manual` | Manuel içerik oluştur |
| `/stats` | İstatistikler |
| `/next` | Sonraki içerik |
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

## Rate Limits ve Timeouts

| API | Rate Limit | Timeout |
|-----|------------|---------|
| Instagram | 200/saat | 60s |
| Sora | - | 300s (5 dk) |
| Veo | - | 300s (5 dk) |
| Kling Direct | - | 300s |
| ElevenLabs | - | 120s |
| FLUX | - | 120s |

---

## Fallback Stratejisi

Video üretiminde hata durumunda:

```
1. Kling 3.0 Pro başarısız → Veo 3.1 dene
2. Veo 3.1 başarısız → Sora 2 dene
3. Hepsi başarısız → Hata bildir
```

---

## Environment Variables

Tüm API anahtarları için bkz: [CONFIGURATION.md](CONFIGURATION.md)
