---
name: instagram-api
description: Instagram Graph API entegrasyonu. Use when publishing content, fetching insights, or working with Instagram media.
---

# Instagram Graph API Integration

## Quick Reference

| Feature | Endpoint | Method |
|---------|----------|--------|
| Account Info | `/{user_id}` | GET |
| Create Container | `/{user_id}/media` | POST |
| Publish | `/{user_id}/media_publish` | POST |
| Container Status | `/{container_id}` | GET |
| Media Insights | `/{media_id}/insights` | GET |
| Recent Media | `/{user_id}/media` | GET |

**API Version:** v21.0
**Base URL:** `https://graph.instagram.com/v21.0`

## Two-Phase Publish Flow

Instagram requires a 2-step process to publish content:

```
1. Create Container → Get container_id
2. Wait (if video) → Check status
3. Publish Container → Get post_id
```

### Image Publishing

```python
# Step 1: Create container
POST /{user_id}/media
{
    "image_url": "https://...",  # PUBLIC URL required
    "caption": "...",
    "access_token": "..."
}
# Returns: {"id": "container_id"}

# Step 2: Publish
POST /{user_id}/media_publish
{
    "creation_id": "container_id",
    "access_token": "..."
}
# Returns: {"id": "post_id"}
```

### Video/Reels Publishing

```python
# Step 1: Create REELS container
POST /{user_id}/media
{
    "video_url": "https://...",  # PUBLIC URL required
    "media_type": "REELS",
    "caption": "...",
    "access_token": "..."
}

# Step 2: Wait for processing (poll every 10s)
GET /{container_id}?fields=status_code,status
# Wait until status_code == "FINISHED"

# Step 3: Publish
POST /{user_id}/media_publish
```

### Carousel Publishing

```python
# Step 1: Create child containers (no caption)
POST /{user_id}/media
{
    "image_url": "https://...",
    "is_carousel_item": "true",
    "access_token": "..."
}
# Repeat for each image (2-10 images)

# Step 2: Create carousel container
POST /{user_id}/media
{
    "media_type": "CAROUSEL",
    "children": "id1,id2,id3,...",
    "caption": "...",
    "access_token": "..."
}

# Step 3: Publish
POST /{user_id}/media_publish
```

## Video Requirements

Instagram Reels have strict format requirements:

| Spec | Requirement |
|------|-------------|
| Codec | H.264 (video), AAC (audio) |
| Resolution | 720x1280 (9:16) |
| FPS | 30 |
| Max Duration | 90 seconds |
| Format | MP4 |

### FFmpeg Conversion Command

```bash
ffmpeg -y -i input.mp4 \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 128k -ar 44100 \
  -vf "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1" \
  -r 30 -movflags +faststart -t 90 \
  output.mp4
```

## Insights API

### Available Metrics by Media Type

**Reels/Video:**
- `plays` - Video plays
- `reach` - Unique accounts reached
- `saved` - Saves
- `shares` - Shares
- `comments` - Comments
- `likes` - Likes
- `total_interactions` - All interactions

**Image/Carousel:**
- `impressions` - Total views
- `reach` - Unique accounts reached
- `saved` - Saves

### Fetching Insights

```python
GET /{media_id}/insights?metric=plays,reach,saved,shares,comments,likes
```

### Engagement Rate Formula

```python
engagement_rate = (likes + comments + saves + shares) / reach * 100
```

## Error Handling

Common error codes:
- `OAuthAccessTokenException` - Token expired/invalid
- `MediaTypeNotSupported` - Wrong media format
- `MediaUploadError` - Upload failed
- `RateLimitError` - Too many requests

## Rate Limiting

- Wait 2 seconds between container creation
- Wait 10 seconds between video status checks
- Max 30 attempts for video processing (5 minutes)
- 0.3 second delay between insight fetches

## Environment Variables

```bash
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_USER_ID=your_user_id
INSTAGRAM_BUSINESS_ID=your_business_id  # Optional
```

For more details, see [endpoints.md](endpoints.md) and [examples.md](examples.md).
