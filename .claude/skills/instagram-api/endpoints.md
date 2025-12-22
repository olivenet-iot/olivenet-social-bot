# Instagram Graph API Endpoints

Base URL: `https://graph.instagram.com/v21.0`

## Account Endpoints

### Get Account Info
```http
GET /{user_id}?fields=id,username,media_count,followers_count&access_token={token}
```

**Response:**
```json
{
  "id": "17841400123456789",
  "username": "olivenet_tech",
  "media_count": 42,
  "followers_count": 1500
}
```

### Get Recent Media
```http
GET /{user_id}/media?fields=id,caption,timestamp,like_count,comments_count,media_type&limit=10&access_token={token}
```

## Media Container Endpoints

### Create Image Container
```http
POST /{user_id}/media
Content-Type: application/x-www-form-urlencoded

image_url={public_url}&caption={text}&access_token={token}
```

### Create Reels Container
```http
POST /{user_id}/media
Content-Type: application/x-www-form-urlencoded

video_url={public_url}&media_type=REELS&caption={text}&access_token={token}
```

### Create Carousel Item
```http
POST /{user_id}/media
Content-Type: application/x-www-form-urlencoded

image_url={public_url}&is_carousel_item=true&access_token={token}
```

### Create Carousel Container
```http
POST /{user_id}/media
Content-Type: application/x-www-form-urlencoded

media_type=CAROUSEL&children={id1},{id2},{id3}&caption={text}&access_token={token}
```

### Check Container Status
```http
GET /{container_id}?fields=status_code,status&access_token={token}
```

**Status Codes:**
| Code | Meaning |
|------|---------|
| `FINISHED` | Ready to publish |
| `IN_PROGRESS` | Still processing |
| `ERROR` | Processing failed |

## Publish Endpoint

### Publish Media
```http
POST /{user_id}/media_publish
Content-Type: application/x-www-form-urlencoded

creation_id={container_id}&access_token={token}
```

**Response:**
```json
{
  "id": "17901234567890123"
}
```

## Insights Endpoints

### Get Media Type
```http
GET /{media_id}?fields=media_type,media_product_type&access_token={token}
```

**Media Types:**
- `VIDEO` - Video content
- `IMAGE` - Single image
- `CAROUSEL_ALBUM` - Multiple images

**Product Types:**
- `REELS` - Instagram Reels
- `FEED` - Feed post
- `STORY` - Story (24h)

### Get Reels Insights
```http
GET /{media_id}/insights?metric=plays,reach,saved,shares,comments,likes,total_interactions&access_token={token}
```

**Response:**
```json
{
  "data": [
    {
      "name": "plays",
      "values": [{"value": 1234}]
    },
    {
      "name": "reach",
      "values": [{"value": 890}]
    }
  ]
}
```

### Get Image Insights
```http
GET /{media_id}/insights?metric=impressions,reach,saved&access_token={token}
```

### Get Basic Media Info
```http
GET /{media_id}?fields=like_count,comments_count,media_type,caption,timestamp&access_token={token}
```

## Error Response Format

```json
{
  "error": {
    "message": "Error description",
    "type": "OAuthException",
    "code": 190,
    "error_subcode": 460,
    "fbtrace_id": "A1B2C3..."
  }
}
```

## Common Error Codes

| Code | Type | Description |
|------|------|-------------|
| 190 | `OAuthException` | Invalid or expired token |
| 100 | `GraphMethodException` | Invalid parameter |
| 10 | `PermissionError` | Missing permission |
| 4 | `RateLimitError` | Too many calls |
