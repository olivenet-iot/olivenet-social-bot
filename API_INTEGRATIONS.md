# Olivenet Social Bot - API Entegrasyonları

## Özet Tablo

| API | Sağlayıcı | Dosya | Amaç |
|-----|-----------|-------|------|
| Instagram Graph | Meta | `instagram_helper.py` | Post yayınlama, insights |
| Instagram Insights | Meta | `insights_helper.py` | Metrik çekme |
| Meta Ads | Meta | `meta_ads_helper.py` | Reklam metrikleri |
| Sora | OpenAI | `sora_helper.py` | Video üretimi |
| Veo 3.1 | Google | `veo_helper.py` | Video üretimi |
| Kling AI | fal.ai | `fal_helper.py` | Video üretimi |
| FLUX.2 Pro | BFL/Replicate | `flux_helper.py` | Görsel üretimi |
| Gemini | Google | `gemini_helper.py` | Görsel üretimi |
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
# Hesap bilgisi
get_account_info() -> dict

# Fotoğraf paylaş
post_photo_to_instagram(image_url, caption) -> str  # post_id

# Video/Reels paylaş
post_video_to_instagram(video_url, caption) -> str  # post_id

# Carousel paylaş (2-10 görsel)
post_carousel_to_instagram(image_urls, caption) -> str  # post_id

# Lokal video yükle
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
# Reels metrikleri
get_instagram_reels_insights(media_id) -> dict

# Media tipi tespit
get_instagram_media_type(media_id) -> str  # VIDEO, IMAGE, CAROUSEL_ALBUM

# Son medyaları al
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

### Prompt Kuralları
- **NO TEXT** - Video içinde metin yok
- **NO DIALOGUE** - Konuşma yok (voice_mode=True ise)
- Sinematik ve görsel odaklı

---

## 4. Google Veo 3.1 (Video)

### Genel Bilgi
- **SDK:** google-generativeai
- **Dosya:** `app/veo_helper.py`
- **Modeller:** veo-3.1-generate-preview, veo-3.1-fast-generate-preview, veo-2

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

---

## 5. Kling AI via fal.ai (Video)

### Genel Bilgi
- **Endpoint:** `https://queue.fal.run/`
- **Dosya:** `app/fal_helper.py`

### Modeller

| Model ID | Model | Maks Süre | Audio |
|----------|-------|-----------|-------|
| `kling_standard` | Kling 2.5 Turbo Standard | 10s | - |
| `kling_pro` | Kling 2.5 Turbo Pro | 10s | - |
| `kling_master` | Kling 2.1 Master | 10s | - |
| `kling_26_pro` | Kling 2.6 Pro | 10s | ✓ |
| `wan_26` | Wan 2.6 | 15s | - |
| `hailuo_standard` | Hailuo 02 Standard | 6s | - |
| `hailuo_pro` | Hailuo 02 Pro | 6s | - |

### Fonksiyon

```python
FalVideoGenerator.generate_video(
    prompt: str,
    model: str = "kling_pro",
    duration: int = 5,
    aspect_ratio: str = "9:16",
    image_url: str = None,        # Image-to-video
    generate_audio: bool = None   # Sadece Kling 2.6
) -> dict
```

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

## 7. ElevenLabs TTS (Sesli Reels)

### Genel Bilgi
- **Endpoint:** `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
- **Dosya:** `app/elevenlabs_helper.py`
- **Model:** eleven_multilingual_v2

### Voice Settings

| Parametre | Aralık | Varsayılan |
|-----------|--------|------------|
| `stability` | 0-1 | 0.5 |
| `similarity_boost` | 0-1 | 0.75 |
| `style` | 0-1 | 0.0 |
| `speed` | 0.5-2.0 | 1.0 |

### Fonksiyon

```python
ElevenLabsHelper.generate_speech(
    text: str,
    voice_id: str = None,
    model_id: str = "eleven_multilingual_v2",
    voice_settings: dict = None,
    speed: float = 1.0
) -> dict
# Döner: {"success": bool, "audio_path": str, "duration_seconds": float}
```

### Türkçe Pronunciation Fixes
```python
PRONUNCIATION_FIXES = {
    "Olivenet": "Olivnet",
    "IoT": "ay o ti",
    "API": "ey pi ay",
    "vs.": "karşı",
    "vb.": "ve benzeri",
    # ...
}
```

---

## 8. Cloudinary (Video CDN)

### Genel Bilgi
- **Dosya:** `app/cloudinary_helper.py`
- **Amaç:** Video dosyalarını Instagram için CDN'e yükleme

### Fonksiyonlar

```python
# Video yükle
upload_video_to_cloudinary(
    video_path: str,
    folder: str = "olivenet-reels"
) -> dict
# Döner: {"success": bool, "url": str, "public_id": str, "duration": float}

# Video sil
delete_from_cloudinary(public_id: str) -> bool
```

### Workflow
```
Local Video → FFmpeg Convert → Cloudinary Upload → CDN URL → Instagram API
```

---

## 9. Meta Ads API

### Genel Bilgi
- **Versiyon:** v21.0
- **Endpoint:** `https://graph.facebook.com/v21.0/{ad_account_id}/insights`
- **Dosya:** `app/meta_ads_helper.py`

### Metrikler

| Kategori | Metrikler |
|----------|-----------|
| Temel | impressions, reach, clicks, spend |
| Maliyet | cpc, cpm, cost_per_follow, cost_per_save |
| Video | video_25_pct, video_50_pct, video_75_pct, video_100_pct |
| Aksiyonlar | likes, comments, saves, shares, follows |

### Fonksiyonlar

```python
# Hesap bilgisi
get_ad_account_info() -> dict

# Kampanya performansı
get_campaign_insights(
    date_start: str,
    date_stop: str,
    level: str = "campaign"  # campaign, adset, ad
) -> list
```

---

## 10. Telegram Bot API

### Genel Bilgi
- **Library:** python-telegram-bot
- **Dosya:** `app/telegram_pipeline.py`

### Komutlar

| Komut | Açıklama |
|-------|----------|
| `/start` | Bot başlat |
| `/status` | Pipeline durumu |
| `/next` | Sonraki içerik |
| `/schedule` | Haftalık program |
| `/sync` | Metrikleri senkronize et |
| `/stats` | İstatistikler |
| `/manual` | Manuel içerik oluştur |

### Callback Handlers

```python
# Onay butonları
handle_approval_callback(update, context)

# Konu seçimi
handle_topic_approval(update, context)

# İçerik onayı
handle_content_approval(update, context)

# Görsel onayı
handle_visual_approval(update, context)
```

---

## Rate Limits ve Timeouts

| API | Rate Limit | Timeout |
|-----|------------|---------|
| Instagram | 200/saat | 60s |
| Sora | - | 300s (5 dk) |
| Veo | - | 300s (5 dk) |
| Kling/fal.ai | - | 300s |
| ElevenLabs | - | 120s |
| FLUX | - | 120s |

---

## Fallback Stratejisi

Video üretiminde hata durumunda:

```
1. Sora 2 başarısız → Veo 3.1 dene
2. Veo 3.1 başarısız → Kling Pro dene
3. Hepsi başarısız → Hata bildir
```

---

## Environment Variables

Tüm API anahtarları için bkz: [CONFIGURATION.md](CONFIGURATION.md)
