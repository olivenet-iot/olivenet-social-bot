# Pipeline Flow Reference

## ContentPipeline Class

Location: `app/scheduler/pipeline.py`

```python
from app.scheduler.pipeline import ContentPipeline

pipeline = ContentPipeline(telegram_callback=my_callback)
result = await pipeline.run_daily_content()
```

## Daily Content Flow (Semi-Autonomous)

Each stage requires Telegram approval:

```
┌────────────────────────────────────────────────────────────┐
│ STAGE 1: PLANNING                                          │
├────────────────────────────────────────────────────────────┤
│ Planner.execute({"action": "suggest_topic"})               │
│ → topic, category, reasoning, suggested_hooks              │
│                                                            │
│ Telegram: "Bugünün Konu Önerisi"                          │
│ Buttons: [Onayla] [Başka Öner] [Düzenle] [İptal]          │
│ → await approval                                           │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│ STAGE 2: CONTENT CREATION                                  │
├────────────────────────────────────────────────────────────┤
│ Creator.execute({                                          │
│     "action": "create_post",                               │
│     "topic": topic,                                        │
│     "category": category,                                  │
│     "suggested_hooks": hooks,                              │
│     "visual_type": "flux"                                  │
│ })                                                         │
│ → post_text, word_count, emoji_count, hook_used            │
│                                                            │
│ Telegram: "Post Metni Hazır"                              │
│ Buttons: [Onayla] [Yeniden Yaz] [Düzenle] [İptal]         │
│ → await approval                                           │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│ STAGE 3: VISUAL GENERATION                                 │
├────────────────────────────────────────────────────────────┤
│ Creator.execute({                                          │
│     "action": "create_visual_prompt",                      │
│     "post_text": text,                                     │
│     "topic": topic,                                        │
│     "visual_type": "flux"                                  │
│ })                                                         │
│ → visual_prompt                                            │
│                                                            │
│ if visual_type == "flux":                                  │
│     flux_helper.generate_image_flux()                      │
│ elif visual_type == "video":                               │
│     veo_helper.generate_video_with_retry()                 │
│                                                            │
│ Telegram: "Görsel Hazır" + image/video                    │
│ Buttons: [Onayla] [Yeniden Üret] [Tip Değiştir] [İptal]   │
│ → await approval                                           │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│ STAGE 4: REVIEW                                            │
├────────────────────────────────────────────────────────────┤
│ Reviewer.execute({                                         │
│     "action": "review_post",                               │
│     "post_text": text,                                     │
│     "topic": topic,                                        │
│     "post_id": id                                          │
│ })                                                         │
│ → total_score, decision, scores, strengths, feedback       │
│                                                            │
│ Telegram: "Final Onay" + review scores                    │
│ Buttons: [YAYINLA] [Zamanla] [Revize Et] [İptal]          │
│ → await approval                                           │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│ STAGE 5: PUBLISH                                           │
├────────────────────────────────────────────────────────────┤
│ Publisher.execute({                                        │
│     "action": "publish",                                   │
│     "post_id": id,                                         │
│     "post_text": text,                                     │
│     "image_path": path,                                    │
│     "platform": "instagram"                                │
│ })                                                         │
│ → success, instagram_post_id                               │
│                                                            │
│ Telegram: "YAYINLANDI!"                                   │
└────────────────────────────────────────────────────────────┘
```

## Autonomous Content Flow

No approval required - just notifications:

```python
result = await pipeline.run_autonomous_content(min_score=7)
```

```
Planner → suggest_topic
    │
    ▼ (no approval)
Creator → create_post
    │
    ▼ (no approval)
Creator → create_visual_prompt
    │
    ▼
Visual Generation (Flux/Veo)
    │
    ▼ (no approval)
Reviewer → review_post
    │
    ├── IF score >= min_score (7):
    │       Publisher → publish
    │
    └── IF score < min_score:
            Skip publish (log only)
```

## Reels Pipeline Flow

Video-focused pipeline:

```python
result = await pipeline.run_reels_content()
```

Key differences:
- Uses `create_reels_prompt` action
- Generates video via Veo/Sora
- Converts video for Instagram (FFmpeg)
- Uploads to Cloudinary for CDN

## Carousel Pipeline Flow

Multi-image pipeline:

```python
result = await pipeline.run_carousel_pipeline()
```

Key differences:
- Creates 3-7 slide prompts
- Generates images for each slide
- Uses carousel publishing API

## Pipeline Result Format

```python
{
    "success": True,
    "stages_completed": [
        "planning",
        "content_creation",
        "visual_prompt",
        "visual_generation",
        "review",
        "published"
    ],
    "final_state": "completed",
    "topic": "Topic title",
    "post_id": 123,
    "instagram_post_id": "17901234567890123",
    "autonomous": False
}
```

## Error Handling

Pipeline catches all errors and returns:

```python
{
    "success": False,
    "error": "Error message",
    "stages_completed": ["planning", "content_creation"],
    "final_state": "error",
    "retry_available": True
}
```

## Approval Response Format

From Telegram callback:

```python
pipeline.set_approval({
    "action": "approve_topic",    # or cancel, new_topic, edit_topic
    "edited_topic": "New topic",  # optional
    "feedback": "Make it shorter" # optional
})
```

## Visual Types

| Type | Generator | Output |
|------|-----------|--------|
| flux | FLUX.2 Pro | 1024x1024 image |
| video | Veo/Sora | 720x1280 MP4 |
| infographic | Claude HTML | Rendered PNG |
| gemini | Disabled | Falls back to flux |
