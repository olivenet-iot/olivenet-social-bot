---
name: error-handling
description: Common errors and fixes. Use when debugging or troubleshooting.
---

# Error Handling

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Telegram Parse Error | Markdown chars | `escape_markdown()` veya `parse_mode=None` |
| Instagram Rate Limit | Too many calls | 0.3s delay ekle |
| Video Timeout | Sora/Veo slow | `generate_video_smart()` kullan |
| Container FINISHED timeout | IG processing | max_attempts=30, sleep=10s |
| None.upper() | Missing null check | `(value or "").upper()` |
| JSON decode error | Invalid response | `_clean_json_response()` |

## Retry Pattern

```python
from app.agents.base_agent import retry_with_backoff

@retry_with_backoff(max_retries=3, base_delay=2.0)
async def my_function():
    # Delays: 2s, 4s, 8s (exponential)
    pass
```

## Telegram Markdown Escape

```python
def escape_markdown(text: str) -> str:
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text
```

## Instagram Container Polling

```python
max_attempts = 30
for attempt in range(max_attempts):
    status = await check_container_status(container_id)
    if status["status_code"] == "FINISHED":
        break
    await asyncio.sleep(10)
else:
    raise TimeoutError("Container processing timeout")
```

## Video Generation Fallback

```python
# Sora fail → Veo fallback
result = await generate_video_smart(prompt, topic)
if not result["success"] and result.get("fallback"):
    result = await generate_video_veo3(prompt)
```

## JSON Cleanup

```python
def clean_json(text: str) -> str:
    # Remove markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    # Fix control characters
    text = text.replace('\n', '\\n').replace('\t', '\\t')
    return text.strip()
```

## Debug Commands

```bash
# Check logs
tail -f /opt/olivenet-social-bot/logs/app.log

# Test database
sqlite3 data/content.db ".schema posts"

# Check bot status
systemctl status olivenet-social

# Restart bot
sudo systemctl restart olivenet-social
```

## Deep Links

- `TROUBLESHOOTING.md` - Full troubleshooting guide
- `app/agents/base_agent.py` - Retry decorator
- `app/telegram_pipeline.py` - escape_markdown()
