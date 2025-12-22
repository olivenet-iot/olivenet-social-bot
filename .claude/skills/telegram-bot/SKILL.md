---
name: telegram-bot
description: Telegram bot komutlari ve handler referansi. Use when working with Telegram bot commands, callbacks, or approval workflows.
---

# Telegram Bot Reference

## Quick Reference

| Command | Description |
|---------|-------------|
| /start | Ana menu |
| /status | Sistem durumu |
| /manual | Manuel icerik olustur |
| /stats | Analytics ozeti |
| /next | Siradaki icerik |
| /schedule | Haftalik takvim |
| /sync | Insights senkronizasyonu |
| /prompts | Prompt tracking |

## Admin Authorization

Only admin users can use the bot:

```python
def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_user_ids
```

```python
# In .env
ADMIN_USER_IDS=123456789,987654321
```

## Main Menu Layout

```
[Gunluk Icerik] [Reels]
[Carousel] [Otonom]
[Icerik Plani] [Zamanlama]
[Siradaki] [Hizli Durum]
[Analytics] [Strateji]
[Sync] [Yardim]
```

## Callback Data Pattern

| Callback | Action |
|----------|--------|
| start_daily | Gunluk icerik pipeline |
| create_reels | Reels pipeline |
| create_carousel | Carousel pipeline |
| start_autonomous | Otonom mod |
| approve_topic | Konu onayla |
| new_topic | Yeni konu oner |
| edit_topic | Konuyu duzenle |
| approve_content | Icerik onayla |
| regenerate_content | Icerigi yeniden yaz |
| approve_visual | Gorsel onayla |
| regenerate_visual | Gorsel yeniden uret |
| publish_now | Hemen yayinla |
| schedule | Zamanla |
| cancel | Iptal |

## Approval Workflow

Pipeline notifies Telegram at each stage:

```
1. Topic Suggestion
   [Onayla] [Baska Oner] [Duzenle] [Iptal]

2. Content Ready
   [Onayla] [Yeniden Yaz] [Duzenle] [Iptal]

3. Visual Ready
   [Onayla] [Yeniden Uret] [Tip Degistir] [Iptal]

4. Final Review
   [YAYINLA] [Zamanla] [Revize Et] [Iptal]
```

## Pipeline Integration

```python
from app.scheduler import ContentPipeline

async def telegram_notify(message, data=None, buttons=None):
    # Send notification to admin chat
    pass

pipeline = ContentPipeline(telegram_callback=telegram_notify)
result = await pipeline.run_daily_content()
```

## Setting Approval Response

```python
# Called when user clicks a button
pipeline.set_approval({
    "action": "approve_topic",
    "edited_topic": "New topic text",  # optional
    "feedback": "Make it shorter"       # optional
})
```

## Sending Messages

### Text Message
```python
await update.message.reply_text(
    "*Bold* and _italic_",
    parse_mode="Markdown"
)
```

### With Inline Keyboard
```python
keyboard = [
    [InlineKeyboardButton("Option 1", callback_data="opt1")],
    [InlineKeyboardButton("Option 2", callback_data="opt2")]
]
reply_markup = InlineKeyboardMarkup(keyboard)

await update.message.reply_text(
    "Choose an option:",
    reply_markup=reply_markup
)
```

### Photo with Caption
```python
with open(image_path, "rb") as photo:
    await bot.send_photo(
        chat_id=admin_chat_id,
        photo=photo,
        caption="Caption text",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
```

### Video with Caption
```python
with open(video_path, "rb") as video:
    await bot.send_video(
        chat_id=admin_chat_id,
        video=video,
        caption="Caption text",
        parse_mode="Markdown"
    )
```

## Error Handling

Markdown parse errors fallback to plain text:

```python
try:
    await bot.send_message(
        chat_id=admin_chat_id,
        text=message,
        parse_mode="Markdown"
    )
except Exception:
    clean_msg = message.replace("*", "").replace("_", "")
    await bot.send_message(
        chat_id=admin_chat_id,
        text=clean_msg
    )
```

## Retry Logic

Network errors use exponential backoff:

```python
max_retries = 3
retry_delay = 5  # seconds

for attempt in range(max_retries):
    try:
        await bot.send_message(...)
        return
    except (NetworkError, TimedOut) as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay * (attempt + 1))
```

## Environment Variables

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_USER_IDS=123456789,987654321
```

For more details, see [handler-template.py](handler-template.py).
