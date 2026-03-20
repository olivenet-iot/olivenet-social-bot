---
name: video-generation
description: AI video generation with Sora, Veo, and Kling Direct API. Use when creating Reels, video prompts, or handling video generation workflows.
---

# AI Video Generation

## Quick Reference

| Model | Provider | Duration | Best For |
|-------|----------|----------|----------|
| sora-2 | OpenAI | 4/8/12s | Yüksek kalite, gerçekçi |
| sora-2-pro | OpenAI | 4/8/12s | Native speech, conversational only |
| veo-3.1 | Google | 4/6/8s | Native audio + lip-sync |
| kling-3.0-pro | Kling Direct API | 5/10/15s | Sinematik, fizik tabanlı, native audio |

## Model Selection (Brain Agent)

Brain Agent otomatik model secimi yapar. Manuel secim icin:

```python
from app.video_models import get_model_config, get_available_models, validate_duration

models = get_available_models()  # ["sora-2", "sora-2-pro", "veo-3.1", "kling-3.0-pro"]
config = get_model_config("kling-3.0-pro")
duration = validate_duration("kling-3.0-pro", 15)  # -> 15

# Model secim rehberi:
# Haber bazlı acil icerik → kling-3.0-pro (hızlı, 2-3 dk)
# Sinematik showcase → sora-2 veya veo-3.1
# Sesli anlatım → sora-2-pro
# Conversational diyalog → sora-2-pro
# Teknik demo → kling-3.0-pro veya veo-3.1
```

## Video Style System

```python
from app.video_styles import VIDEO_STYLES, get_style_config

# 10 görsel stil:
# cinematic_4k, anime, cartoon_3d, watercolor, 3d_render,
# pixel_art, comic_book, claymation, minimalist, neon_cyberpunk

style = get_style_config("cinematic_4k")
# -> character descriptions, scene settings, voice type mappings
```

## Generation Functions

```python
# Sora (OpenAI)
from app.sora_helper import generate_video_sora
result = await generate_video_sora(prompt, model="sora-2", size="720x1280", duration=12)

# Veo (Google)
from app.veo_helper import generate_video_veo3
result = await generate_video_veo3(prompt, aspect_ratio="9:16", duration_seconds=8)

# Kling (Direct API - api-singapore.klingai.com)
from app.kling_helper import KlingHelper
kling = KlingHelper()
result = await kling.generate_video(
    prompt=prompt,
    duration=10,          # 5/10/15s
    aspect_ratio="9:16",
    model_name="kling-v3",
    mode="pro",
    generate_audio=True   # Native audio
)
```

## Kling Direct API Details

- **Base URL:** `https://api-singapore.klingai.com`
- **Auth:** JWT (HS256) with `KLING_ACCESS_KEY` / `KLING_SECRET_KEY`
- **Model:** kling-v3 (Kling 3.0 Pro)
- **Durations:** 5s, 10s, 15s
- **Features:** Native audio, physics-based motion, cinematic quality
- Token auto-renewal: 30 min expiry, refreshed at 5 min remaining

## Instagram Specs

| Spec | Value |
|------|-------|
| Aspect | 9:16 vertical |
| Resolution | 720x1280 |
| Codec | H.264/AAC |
| Max Duration | 90s |

## Environment Variables

```bash
OPENAI_API_KEY=...          # Sora
GEMINI_API_KEY=...          # Veo
KLING_ACCESS_KEY=...        # Kling Direct API
KLING_SECRET_KEY=...        # Kling Direct API
```

## Return Format

```python
# Success
{"success": True, "video_path": "/path/to.mp4", "model_used": "kling-3.0-pro"}

# Error with fallback
{"success": False, "error": "...", "fallback": "veo3"}
```

## Best Practices

- Simple, comma-separated sentences
- Include camera movement + lighting
- Avoid complex physics (bouncing, running)
- Use: "cinematic", "professional", "documentary"
- Duration: 5-8s ideal for Reels
- Kling 3.0 Pro en hizli (2-3 dk), 15s destegi

## Production Pipelines

| Pipeline | Dosya | Default Model |
|----------|-------|---------------|
| reels | `app/production/reels_pipeline.py` | kling-3.0-pro |
| voice_reels | `app/production/voice_reels_pipeline.py` | sora-2-pro |
| news_reels | `app/production/news_reels_pipeline.py` | kling-3.0-pro |
| long_video | `app/production/long_video_pipeline.py` | kling-3.0-pro |
| conversational | `app/production/conversational_pipeline.py` | sora-2-pro |

## Deep Links

- `app/video_models.py` - Model configs (4 model)
- `app/video_styles.py` - 10 görsel stil
- `app/sora_helper.py` - Sora + smart selection
- `app/veo_helper.py` - Veo generation
- `app/kling_helper.py` - Kling Direct API (JWT auth)
- `context/reels-prompts.md` - Prompt examples
