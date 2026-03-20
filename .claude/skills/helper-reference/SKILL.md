---
name: helper-reference
description: Tum helper fonksiyonlari referansi. Use for quick lookup of available functions.
---

# Helper Reference

Tum helper dosyalari ve public fonksiyonlari.

## kling_helper.py
Kling AI Direct API video uretimi (fal.ai yerine dogrudan API).

```python
from app.kling_helper import KlingHelper

kling = KlingHelper()

# Video uret (Kling 3.0 Pro)
result = await kling.generate_video(
    prompt="...",
    duration=10,              # 5, 10, 15 saniye
    aspect_ratio="9:16",
    model_name="kling-v3",
    mode="pro",
    negative_prompt="blur, distort, low quality",
    cfg_scale=0.5,
    generate_audio=True       # Native audio
)
# Returns: {success, video_path, video_id, duration, model}

# Base URL: https://api-singapore.klingai.com
# Auth: JWT (HS256) with KLING_ACCESS_KEY / KLING_SECRET_KEY
```

## nano_banana_helper.py
Gemini 3 Pro Image ile infographic/carousel uretimi (HTML template'lerin yerini aldi).

```python
from app.nano_banana_helper import (
    generate_infographic,
    generate_carousel_slides,
    add_logo_overlay
)

# Tek infographic
result = await generate_infographic(topic, post_text)
# Returns: {success, image_path}

# Carousel slide'lari
slides = await generate_carousel_slides(topic, slide_data, count=5)
# Returns: [{success, image_path}, ...]

# Logo overlay
add_logo_overlay(image_path, position="bottom_left", logo_scale=0.12)
```

## video_models.py
Video model konfigurasyonlari (4 model).

```python
from app.video_models import (
    get_model_config, get_available_models,
    get_model_durations, get_max_duration,
    validate_duration, should_disable_audio
)

models = get_available_models()
# ["sora-2", "sora-2-pro", "veo-3.1", "kling-3.0-pro"]

config = get_model_config("kling-3.0-pro")
# {name, provider, durations, default_duration, max_duration, ...}

duration = validate_duration("veo-3.1", 10)  # -> 8 (clamped)
disable = should_disable_audio("kling-3.0-pro", voice_mode=True)  # -> True
```

## video_styles.py
Gorsel stil sistemi (10 stil).

```python
from app.video_styles import VIDEO_STYLES, get_style_config

# 10 stil: cinematic_4k, anime, cartoon_3d, watercolor, 3d_render,
#          pixel_art, comic_book, claymation, minimalist, neon_cyberpunk

style = get_style_config("cinematic_4k")
# -> {character_descriptions, scene_settings, voice_type}
```

## flux_helper.py
FLUX.2 Pro gorsel uretimi.

```python
generate_image_flux(prompt, width=1024, height=1024, output_format="png") -> Dict
# Returns: {success, image_path, duration, cost}

get_credits() -> Dict
# Returns: {success, credits}
```

## cloudinary_helper.py
Video CDN yonetimi.

```python
configure_cloudinary() -> bool
upload_video_to_cloudinary(video_path, folder="olivenet-reels") -> Dict
# Returns: {success, url, public_id, duration}

delete_from_cloudinary(public_id) -> Dict
# Returns: {success}
```

## instagram_helper.py
Instagram Graph API v21.0.

```python
get_account_info() -> Dict
post_photo_to_instagram(image_url, caption) -> str  # post_id
post_video_to_instagram(video_url, caption) -> str  # post_id
post_carousel_to_instagram(image_urls, caption) -> str  # post_id
post_reels_to_instagram(video_path, caption) -> Dict
convert_video_for_instagram(video_path) -> Dict
get_media_insights(media_id) -> Dict
get_recent_media(limit=10) -> List
upload_image_to_cdn(image_path) -> str  # public URL
```

## insights_helper.py
Instagram Analytics.

```python
get_instagram_account_info() -> Dict
get_instagram_media_type(media_id) -> Dict
get_instagram_reels_insights(media_id) -> Dict
get_instagram_image_insights(media_id) -> Dict
get_instagram_insights() -> List  # Son 10 post
get_best_performing_content() -> List  # Top 20
sync_insights_to_database() -> int  # Guncellenen post sayisi
```

## sora_helper.py
OpenAI Sora video uretimi.

```python
generate_video_sora(prompt, duration=8, size="720x1280", model="sora-2") -> Dict
# Returns: {success, video_path, video_id, model, file_size_mb}

analyze_prompt_complexity(prompt, topic="") -> Dict
# Returns: {complexity, model, duration}

generate_video_smart(prompt, topic="", force_model=None, duration=8) -> Dict
# Otomatik model secimi + fallback
# Returns: {success, video_path, model_used}
```

## veo_helper.py
Google Veo video uretimi.

```python
generate_video_veo3(prompt, aspect_ratio="9:16", duration_seconds=8) -> Dict
# Returns: {success, video_path, file_size_mb, model, duration}

generate_video_with_retry(prompt, max_retries=2) -> Dict
```

## elevenlabs_helper.py
ElevenLabs TTS (Turkce seslendirme).

```python
ElevenLabsHelper.generate_speech(text, voice_id=None, speed=1.0) -> Dict
# Returns: {success, audio_path, duration_seconds}
```

## claude_helper.py
Claude CLI wrapper.

```python
run_claude_code(prompt, timeout=60) -> str
generate_post_text(topic) -> str
```

## renderer.py
HTML -> PNG rendering (carousel slide'lari icin hala kullaniliyor).

```python
render_html_to_png(html_content, output_path=None, width=1080, height=1080) -> str
save_html_and_render(html_content, base_name=None) -> Tuple[str, str]
get_browser() -> Browser
close_browser() -> None
```

## config.py
Konfigürasyon ve ayarlar.

```python
settings.telegram_bot_token
settings.telegram_admin_chat_id
settings.instagram_access_token
settings.instagram_user_id
settings.gemini_api_key
settings.flux_api_key
settings.openai_api_key
settings.kling_access_key       # Kling Direct API
settings.kling_secret_key       # Kling Direct API
settings.cloudinary_cloud_name

# Paths
settings.base_dir
settings.context_dir
settings.templates_dir
settings.outputs_dir
settings.database_path
```

## Dosya Konumlari

| Helper | Konum |
|--------|-------|
| kling_helper.py | app/kling_helper.py |
| nano_banana_helper.py | app/nano_banana_helper.py |
| video_models.py | app/video_models.py |
| video_styles.py | app/video_styles.py |
| flux_helper.py | app/flux_helper.py |
| cloudinary_helper.py | app/cloudinary_helper.py |
| instagram_helper.py | app/instagram_helper.py |
| insights_helper.py | app/insights_helper.py |
| sora_helper.py | app/sora_helper.py |
| veo_helper.py | app/veo_helper.py |
| elevenlabs_helper.py | app/elevenlabs_helper.py |
| claude_helper.py | app/claude_helper.py |
| renderer.py | app/renderer.py |
| config.py | app/config.py |

## Silinen Helper'lar (v2'de yok)

- ~~fal_helper.py~~ → Kling: `kling_helper.py` (Direct API)
- ~~gemini_helper.py~~ → Gorsel: `nano_banana_helper.py` (Gemini 3 Pro Image)
