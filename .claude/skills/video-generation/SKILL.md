---
name: video-generation
description: AI video generation with Sora and Veo. Use when creating Reels, video prompts, or handling video generation workflows.
---

# AI Video Generation

## Quick Reference

| Model | Provider | Best For | Duration | Quality |
|-------|----------|----------|----------|---------|
| Veo 3.1 | Google | Simple scenes, products | 4-8s | High |
| Veo 3.1 Fast | Google | Quick generation | 4-8s | Medium |
| Sora 2 | OpenAI | Medium complexity | 4-12s | High |
| Sora 2 Pro | OpenAI | Complex scenes, humans | 4-12s | Premium |

## Model Selection Logic

```python
def analyze_prompt_complexity(prompt: str, topic: str = "") -> Dict:
    combined = f"{prompt.lower()} {topic.lower()}"

    # HIGH complexity → Sora 2 Pro
    high_keywords = ["transformation", "morphing", "cinematic", "epic", "dramatic"]
    for kw in high_keywords:
        if kw in combined:
            return {"complexity": "high", "model": "sora-2-pro", "duration": 8}

    # MEDIUM complexity → Sora 2
    medium_keywords = ["tracking", "dolly", "movement", "animation", "transition"]
    for kw in medium_keywords:
        if kw in combined:
            return {"complexity": "medium", "model": "sora-2", "duration": 8}

    # LOW complexity → Veo 3
    return {"complexity": "low", "model": "veo3", "duration": 6}
```

## Smart Generation with Fallback

```
1. Analyze prompt complexity
2. Select model (Sora or Veo)
3. If Sora fails → Fallback to Veo
4. Return video path
```

## Video Specifications

### Instagram Reels Requirements

| Spec | Value |
|------|-------|
| Aspect Ratio | 9:16 (vertical) |
| Resolution | 720x1280 or 1080x1920 |
| Duration | 5-8 seconds ideal |
| Format | MP4, H.264, AAC |

### Veo Parameters

```python
config = {
    "aspect_ratio": "9:16",      # or "16:9"
    "duration_seconds": 8,        # 4, 6, or 8
    "number_of_videos": 1,
    "person_generation": "allow_all"
}
```

### Sora Parameters

```python
params = {
    "model": "sora-2",           # or "sora-2-pro"
    "duration": 8,                # 4, 8, or 12
    "size": "720x1280"           # or "1280x720"
}
```

## Prompt Formula

**5-Part Formula:**
```
[CINEMATOGRAPHY] + [SUBJECT] + [ACTION] + [CONTEXT] + [STYLE]
```

**Example:**
```
"Slow dolly shot, IoT sensor device on greenhouse shelf, LED indicator
blinking green, morning sunlight through glass panels, professional
documentary style, shallow depth of field"
```

## Generation Flow

### Veo Generation

```python
from app.veo_helper import generate_video_veo3

result = await generate_video_veo3(
    prompt="Your detailed prompt here",
    aspect_ratio="9:16",
    duration_seconds=8
)

if result.get("success"):
    video_path = result["video_path"]
```

### Smart Generation (Sora + Veo Fallback)

```python
from app.sora_helper import generate_video_smart

result = await generate_video_smart(
    prompt="Your prompt",
    topic="Technology",
    duration=8
)

# Automatically falls back to Veo if Sora fails
video_path = result.get("video_path")
model_used = result.get("model_used")  # "sora-2" or "veo-3"
```

## Environment Variables

```bash
GEMINI_API_KEY=your_google_api_key    # For Veo
OPENAI_API_KEY=your_openai_api_key    # For Sora
```

## Timeouts and Limits

| Model | Max Wait | Polling Interval |
|-------|----------|------------------|
| Veo | 5 minutes | 5 seconds |
| Sora | 5 minutes | 10 seconds |

For more details, see [prompt-examples.md](prompt-examples.md) and [technical.md](technical.md).
