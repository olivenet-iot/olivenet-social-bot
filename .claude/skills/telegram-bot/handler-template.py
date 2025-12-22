# Telegram Bot Handler Template
# Based on app/telegram_pipeline.py patterns

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from app.config import settings


# ============ AUTHORIZATION ============

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in settings.admin_user_ids


async def check_authorization(update: Update) -> bool:
    """Check authorization and send error if not admin"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ *Yetkisiz Erisim*\n\n"
            f"Kullanici ID: `{user_id}`",
            parse_mode="Markdown"
        )
        return False
    return True


# ============ COMMAND HANDLERS ============

async def cmd_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Example command handler"""

    # Check authorization
    if not await check_authorization(update):
        return

    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("Option 1", callback_data="option_1"),
            InlineKeyboardButton("Option 2", callback_data="option_2")
        ],
        [InlineKeyboardButton("Cancel", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📋 *Example Command*\n\n"
        "Choose an option:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ============ CALLBACK HANDLERS ============

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries"""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback

    # Check authorization
    if not is_admin(query.from_user.id):
        await query.edit_message_text(
            "⛔ Yetkisiz erisim!",
            parse_mode="Markdown"
        )
        return

    data = query.data

    if data == "option_1":
        await handle_option_1(query)
    elif data == "option_2":
        await handle_option_2(query)
    elif data == "cancel":
        await query.edit_message_text("❌ Islem iptal edildi.")
    else:
        await query.edit_message_text(f"Unknown action: {data}")


async def handle_option_1(query):
    """Handle option 1 selection"""
    await query.edit_message_text(
        "✅ Option 1 selected!",
        parse_mode="Markdown"
    )


async def handle_option_2(query):
    """Handle option 2 selection"""
    await query.edit_message_text(
        "✅ Option 2 selected!",
        parse_mode="Markdown"
    )


# ============ MESSAGE HANDLERS ============

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages (for input collection)"""
    global pending_input

    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    # Check if we're waiting for input
    if user_id in pending_input:
        input_type = pending_input[user_id].get("type")
        collected_text = update.message.text

        if input_type == "topic":
            await handle_topic_input(update, collected_text)
        elif input_type == "feedback":
            await handle_feedback_input(update, collected_text)

        del pending_input[user_id]


async def handle_topic_input(update: Update, topic: str):
    """Handle topic input from user"""
    await update.message.reply_text(
        f"✅ Konu kaydedildi: {topic}",
        parse_mode="Markdown"
    )


async def handle_feedback_input(update: Update, feedback: str):
    """Handle feedback input from user"""
    await update.message.reply_text(
        f"✅ Geri bildirim alindi.",
        parse_mode="Markdown"
    )


# ============ PIPELINE NOTIFICATION ============

async def telegram_notify(message: str, data: dict = None, buttons: list = None):
    """Send notification to admin chat"""
    from telegram import Bot
    import os

    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    admin_chat_id = settings.admin_chat_id  # Set from /start

    # Build keyboard
    keyboard = []
    if buttons:
        for btn in buttons:
            keyboard.append([
                InlineKeyboardButton(btn["text"], callback_data=btn["callback"])
            ])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # Send photo if available
    if data and data.get("image_path"):
        with open(data["image_path"], "rb") as photo:
            await bot.send_photo(
                chat_id=admin_chat_id,
                photo=photo,
                caption=message[:1024],
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        return

    # Send video if available
    if data and data.get("video_path"):
        with open(data["video_path"], "rb") as video:
            await bot.send_video(
                chat_id=admin_chat_id,
                video=video,
                caption=message[:1024],
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        return

    # Send text message
    try:
        await bot.send_message(
            chat_id=admin_chat_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    except Exception:
        # Markdown error - send plain text
        clean_msg = message.replace("*", "").replace("_", "")
        await bot.send_message(
            chat_id=admin_chat_id,
            text=clean_msg,
            reply_markup=reply_markup
        )


# ============ APPLICATION SETUP ============

def create_application():
    """Create and configure the bot application"""
    import os

    app = Application.builder().token(
        os.getenv("TELEGRAM_BOT_TOKEN")
    ).build()

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("example", cmd_example))

    # Callback handler (for inline buttons)
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Message handler (for text input)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_message_handler
    ))

    return app


# ============ RUN ============

if __name__ == "__main__":
    app = create_application()
    app.run_polling()


# ============ APPROVAL FLOW EXAMPLE ============

# In pipeline:
# await telegram_notify(
#     message="📋 Konu onerisi hazir",
#     data={"topic": "IoT Teknolojisi"},
#     buttons=[
#         {"text": "✅ Onayla", "callback": "approve_topic"},
#         {"text": "❌ Iptal", "callback": "cancel"}
#     ]
# )

# In callback handler:
# if data == "approve_topic":
#     pipeline.set_approval({"action": "approve_topic"})
#     await query.edit_message_text("✅ Konu onaylandi!")
