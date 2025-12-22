# Video Generation Technical Reference

## API Endpoints

### Google Veo (via GenAI SDK)

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=GEMINI_API_KEY)

config = types.GenerateVideosConfig(
    aspect_ratio="9:16",
    duration_seconds=8,
    number_of_videos=1,
    person_generation="allow_all"
)

operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt=prompt,
    config=config
)

# Poll until done
while not operation.done:
    await asyncio.sleep(5)
    operation = client.operations.get(operation)

# Download
video = operation.response.generated_videos[0]
client.files.download(file=video.video)
video.video.save(output_path)
```

### OpenAI Sora

```python
# Step 1: Create job (multipart/form-data)
POST https://api.openai.com/v1/videos
Headers: Authorization: Bearer {OPENAI_API_KEY}
Body (multipart):
  - model: sora-2
  - prompt: {text}
  - seconds: 8
  - size: 720x1280

# Response
{"id": "video_abc123", "status": "pending"}

# Step 2: Poll status
GET https://api.openai.com/v1/videos/{video_id}
# Wait for status == "completed"

# Step 3: Download
GET https://api.openai.com/v1/videos/{video_id}/content
# Returns raw MP4 bytes
```

## Model Hierarchy

### Veo Models (Google)

```python
models_to_try = [
    ("veo-3.1-generate-preview", "Veo 3.1"),
    ("veo-3.1-fast-generate-preview", "Veo 3.1 Fast"),
    ("veo-2", "Veo 2")
]
```

### Sora Models (OpenAI)

| Model | Description | Best For |
|-------|-------------|----------|
| `sora-2` | Standard | General video generation |
| `sora-2-pro` | Premium | Complex scenes, humans |

## Duration Constraints

### Veo
- Valid: 4, 6, 8 seconds
- Auto-rounds to nearest valid value

### Sora
- Valid: 4, 8, 12 seconds
- Auto-rounds to nearest valid value

```python
valid_durations = [4, 8, 12]
duration = min(valid_durations, key=lambda x: abs(x - requested))
```

## Size/Aspect Ratio

### Veo
```python
aspect_ratio = "9:16"  # Vertical (Reels)
aspect_ratio = "16:9"  # Horizontal (YouTube)
```

### Sora
```python
size = "720x1280"   # 9:16 vertical
size = "1280x720"   # 16:9 horizontal
```

## Error Handling

### Veo Errors
```python
# 404 or model not found → try next model
if "404" in str(error) or "not found" in error.lower():
    continue

# Timeout after 5 minutes
if elapsed > 300:
    return {"success": False, "error": "Timeout"}
```

### Sora Errors
```python
# Returns fallback suggestion
return {
    "success": False,
    "error": error_message,
    "fallback": "veo3"  # Hint to try Veo
}
```

## Complete Flow Example

```python
async def generate_video_smart(prompt: str, topic: str = "") -> Dict:
    # 1. Analyze complexity
    complexity = analyze_prompt_complexity(prompt, topic)
    model = complexity.get("model", "veo3")

    # 2. Try Veo for low complexity
    if model == "veo3":
        from app.veo_helper import generate_video_veo3
        return await generate_video_veo3(prompt, aspect_ratio="9:16")

    # 3. Try Sora for medium/high
    sora_result = await generate_video_sora(
        prompt=prompt,
        model=model,
        size="720x1280"
    )

    if sora_result.get("success"):
        return sora_result

    # 4. Fallback to Veo if Sora fails
    if sora_result.get("fallback") == "veo3":
        from app.veo_helper import generate_video_veo3
        result = await generate_video_veo3(prompt, aspect_ratio="9:16")
        result["fallback_from"] = model
        return result

    return sora_result
```

## Output Format

```python
# Success
{
    "success": True,
    "video_path": "/path/to/output.mp4",
    "model": "veo-3.1",           # Actual model used
    "model_used": "veo-3.1",      # For consistency
    "duration": 8,
    "file_size_mb": 12.5,
    "video_id": "abc123"          # Sora only
}

# Failure
{
    "success": False,
    "error": "Description of what went wrong",
    "fallback": "veo3"            # Sora only - hint to try Veo
}
```

## Environment Configuration

```bash
# Google Veo
GEMINI_API_KEY=your_gemini_api_key

# OpenAI Sora
OPENAI_API_KEY=your_openai_api_key

# Output directory (from config)
OUTPUTS_DIR=/path/to/outputs
```

## Dependencies

```python
# Veo
pip install google-genai

# Sora
pip install httpx  # async HTTP client
```

## File Naming Convention

```python
# Veo output
f"outputs/veo_{datetime.now():%Y%m%d_%H%M%S}.mp4"
# Example: outputs/veo_20241215_143022.mp4

# Sora output
f"outputs/sora_{datetime.now():%Y%m%d_%H%M%S}.mp4"
# Example: outputs/sora_20241215_143022.mp4
```
