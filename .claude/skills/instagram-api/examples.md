# Instagram API Code Examples

Real code patterns from `instagram_helper.py` and `insights_helper.py`.

## Publishing Examples

### Post Single Image

```python
async def post_photo_to_instagram(image_url: str, caption: str = "") -> Dict[str, Any]:
    """Post a photo to Instagram"""

    # Step 1: Create container
    container_id = await create_media_container(
        image_url=image_url,
        caption=caption,
        media_type="IMAGE"
    )

    if not container_id:
        return {"success": False, "error": "Container creation failed"}

    await asyncio.sleep(2)  # Wait before publish

    # Step 2: Publish
    result = await publish_media(container_id)
    if result.get("success"):
        result["platform"] = "instagram"
    return result
```

### Post Reels with Video Processing

```python
async def post_video_to_instagram(video_url: str, caption: str = "") -> Dict[str, Any]:
    """Post a Reels video"""

    # Step 1: Create REELS container
    container_id = await create_media_container(
        video_url=video_url,
        caption=caption,
        media_type="REELS"
    )

    if not container_id:
        return {"success": False, "error": "Container creation failed"}

    # Step 2: Wait for video processing
    max_attempts = 30
    for attempt in range(max_attempts):
        await asyncio.sleep(10)

        status = await check_container_status(container_id)
        status_code = status.get("status_code")

        if status_code == "FINISHED":
            break
        elif status_code == "ERROR":
            return {"success": False, "error": status.get("status")}
        elif status_code == "IN_PROGRESS":
            print(f"Processing... ({attempt + 1}/{max_attempts})")
    else:
        return {"success": False, "error": "Video processing timeout"}

    # Step 3: Publish
    result = await publish_media(container_id)
    if result.get("success"):
        result["platform"] = "instagram_reels"
    return result
```

### Post Carousel

```python
async def post_carousel_to_instagram(image_urls: List[str], caption: str = "") -> Dict[str, Any]:
    """Post a carousel with 2-10 images"""

    if len(image_urls) < 2 or len(image_urls) > 10:
        return {"success": False, "error": "Carousel needs 2-10 images"}

    # Step 1: Create child containers
    children_ids = []
    for i, image_url in enumerate(image_urls):
        container_id = await create_media_container(
            image_url=image_url,
            media_type="IMAGE",
            is_carousel_item=True
        )

        if container_id:
            children_ids.append(container_id)
            await asyncio.sleep(2)  # Rate limit

    if len(children_ids) < 2:
        return {"success": False, "error": "Need at least 2 successful items"}

    # Step 2: Create carousel container
    carousel_container_id = await create_carousel_container(
        children_ids=children_ids,
        caption=caption
    )

    if not carousel_container_id:
        return {"success": False, "error": "Carousel container failed"}

    await asyncio.sleep(3)

    # Step 3: Publish
    result = await publish_media(carousel_container_id)
    if result.get("success"):
        result["platform"] = "instagram_carousel"
        result["slide_count"] = len(children_ids)
    return result
```

## Video Conversion Example

```python
async def convert_video_for_instagram(input_path: str) -> Dict[str, Any]:
    """Convert video to Instagram Reels format"""

    # Check if already compatible
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate",
        "-of", "csv=p=0",
        input_path
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)

    parts = probe_result.stdout.strip().split(",")
    if len(parts) >= 4:
        codec, width, height = parts[0], int(parts[1]), int(parts[2])

        is_compatible = (
            codec == "h264" and
            width == 720 and
            height == 1280
        )

        if is_compatible:
            return {"success": True, "output_path": input_path, "converted": False}

    # Convert video
    output_path = f"outputs/ig_ready_{datetime.now():%Y%m%d_%H%M%S}.mp4"

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r", "30",
        "-movflags", "+faststart",
        "-t", "90",
        output_path
    ]

    process = subprocess.run(ffmpeg_cmd, capture_output=True, timeout=300)

    if process.returncode != 0:
        return {"success": False, "error": process.stderr[:200]}

    return {
        "success": True,
        "output_path": output_path,
        "converted": True,
        "file_size_mb": os.path.getsize(output_path) / 1024 / 1024
    }
```

## Insights Examples

### Fetch Media Insights (Auto Type Detection)

```python
async def get_instagram_media_insights(media_id: str) -> Dict[str, Any]:
    """Fetch insights with automatic media type detection"""

    # Detect media type first
    type_info = await get_instagram_media_type(media_id)
    is_reels = type_info.get("is_reels", False)

    if is_reels:
        return await get_instagram_reels_insights(media_id)
    else:
        return await get_instagram_image_insights(media_id)
```

### Reels Insights

```python
async def get_instagram_reels_insights(media_id: str) -> Dict[str, Any]:
    """Fetch Reels-specific metrics"""

    async with httpx.AsyncClient(timeout=30) as client:
        result = {
            "success": True,
            "media_id": media_id,
            "media_type": "REELS",
            "plays": 0, "reach": 0, "saves": 0,
            "shares": 0, "comments": 0, "likes": 0,
            "total_interactions": 0, "engagement_rate": 0.0
        }

        # Fetch Reels metrics
        response = await client.get(
            f"{GRAPH_API_URL}/{media_id}/insights",
            params={
                "metric": "plays,reach,saved,shares,comments,likes,total_interactions",
                "access_token": INSTAGRAM_ACCESS_TOKEN
            }
        )

        if response.status_code == 200:
            for metric in response.json().get("data", []):
                name = metric.get("name")
                value = metric.get("values", [{}])[0].get("value", 0)

                if name == "saved":
                    result["saves"] = value
                else:
                    result[name] = value

        # Calculate engagement rate
        reach = result["reach"] if result["reach"] > 0 else 1
        total_engagement = result["likes"] + result["comments"] + result["saves"] + result["shares"]
        result["engagement_rate"] = round((total_engagement / reach) * 100, 2)

        return result
```

### Sync Insights to Database

```python
async def sync_insights_to_database() -> Dict[str, Any]:
    """Sync Instagram insights to local database"""
    from app.database import update_post_analytics, get_published_posts

    db_posts = get_published_posts(days=30)
    synced = 0

    for post in db_posts:
        ig_post_id = post.get("instagram_post_id")

        if ig_post_id:
            insights = await get_instagram_media_insights(ig_post_id)

            if insights.get("success"):
                update_post_analytics(post.get("id"), {
                    "ig_reach": insights.get("reach", 0),
                    "ig_likes": insights.get("likes", 0),
                    "ig_comments": insights.get("comments", 0),
                    "ig_saves": insights.get("saves", 0),
                    "ig_engagement_rate": insights.get("engagement_rate", 0)
                })
                synced += 1

            await asyncio.sleep(0.3)  # Rate limiting

    return {"success": True, "synced": synced}
```

## Helper Functions

### Create Media Container

```python
async def create_media_container(
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    caption: str = "",
    media_type: str = "IMAGE",
    is_carousel_item: bool = False
) -> Optional[str]:
    """Create an Instagram media container"""

    url = f"{GRAPH_API_URL}/{user_id}/media"

    data = {"access_token": access_token}

    if not is_carousel_item and caption:
        data["caption"] = caption

    if media_type == "IMAGE":
        data["image_url"] = image_url
    elif media_type == "REELS":
        data["video_url"] = video_url
        data["media_type"] = "REELS"

    if is_carousel_item:
        data["is_carousel_item"] = "true"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()
            return result.get("id")  # Returns container_id
```

### Publish Media

```python
async def publish_media(container_id: str) -> Dict[str, Any]:
    """Publish a media container"""

    url = f"{GRAPH_API_URL}/{user_id}/media_publish"
    data = {
        "creation_id": container_id,
        "access_token": access_token
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()

            if "error" in result:
                return {"success": False, "error": result["error"].get("message")}

            return {"success": True, "id": result.get("id")}
```
