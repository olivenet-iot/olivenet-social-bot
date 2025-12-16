#!/usr/bin/env python3
"""
Olivenet Social Media Bot - Telegram Bot
Main bot application with conversation handling.
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum, auto

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.claude_helper import generate_post_text, generate_visual_html, improve_post_text
from app.renderer import save_html_and_render, cleanup
from app.facebook_helper import post_with_photo_to_facebook, post_text_to_facebook, FacebookError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BotState(Enum):
    """Bot conversation states."""
    IDLE = auto()
    WAITING_TOPIC = auto()
    SHOWING_POST = auto()
    SHOWING_VISUAL = auto()
    CONFIRMING_PUBLISH = auto()
    WAITING_FEEDBACK = auto()


class SessionData:
    """Session data for a user."""

    def __init__(self):
        self.state: BotState = BotState.IDLE
        self.topic: Optional[str] = None
        self.post_text: Optional[str] = None
        self.html_content: Optional[str] = None
        self.image_path: Optional[str] = None
        self.html_path: Optional[str] = None

    def reset(self):
        """Reset session to initial state."""
        self.state = BotState.IDLE
        self.topic = None
        self.post_text = None
        self.html_content = None
        self.image_path = None
        self.html_path = None


# Global session storage (in production, use Redis or database)
sessions: Dict[int, SessionData] = {}


def get_session(user_id: int) -> SessionData:
    """Get or create session for user."""
    if user_id not in sessions:
        sessions[user_id] = SessionData()
    return sessions[user_id]


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == settings.telegram_admin_chat_id


# Keyboard builders
def get_main_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("Yeni Post Olustur", callback_data="new_post")],
        [InlineKeyboardButton("Durum", callback_data="status")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_post_review_keyboard() -> InlineKeyboardMarkup:
    """Post review keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Onayla & Gorsel Olustur", callback_data="approve_post"),
            InlineKeyboardButton("Yeniden Uret", callback_data="regenerate_post")
        ],
        [
            InlineKeyboardButton("Duzenle", callback_data="edit_post"),
            InlineKeyboardButton("Iptal", callback_data="cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_visual_review_keyboard() -> InlineKeyboardMarkup:
    """Visual review keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Facebook'a Gonder", callback_data="publish_facebook"),
        ],
        [
            InlineKeyboardButton("Gorseli Yeniden Uret", callback_data="regenerate_visual"),
            InlineKeyboardButton("Metni Duzenle", callback_data="edit_post")
        ],
        [InlineKeyboardButton("Iptal", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_publish_keyboard() -> InlineKeyboardMarkup:
    """Confirm publish keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Evet, Paylas", callback_data="confirm_publish"),
            InlineKeyboardButton("Hayir, Vazgec", callback_data="cancel_publish")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text(
            "Bu bot sadece yetkili kullanicilar tarafindan kullanilabilir."
        )
        return

    session = get_session(user_id)
    session.reset()

    await update.message.reply_text(
        "Merhaba! Olivenet Sosyal Medya Bot'una hosgeldiniz.\n\n"
        "Bu bot ile:\n"
        "- AI destekli sosyal medya postlari olusturabilir\n"
        "- Otomatik gorseller uretebilir\n"
        "- Facebook'a direkt paylasabilirsiniz\n\n"
        "Baslamak icin asagidaki menuyu kullanin:",
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
*Olivenet Sosyal Medya Bot*

*Komutlar:*
/start - Botu baslat
/help - Yardim
/cancel - Mevcut islemi iptal et
/status - Bot durumu

*Kullanim:*
1. "Yeni Post Olustur" butonuna tiklayin
2. Konu girin (ornek: "akilli tarim", "enerji tasarrufu")
3. Olusturulan metni inceleyin
4. Onaylayin veya yeniden uretim isteyin
5. Gorsel olusturulunca Facebook'a paylasin

*Ipuclari:*
- Konu ne kadar spesifik olursa post o kadar iyi olur
- "KKTC'de sera sulama" gibi konular deneyin
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command."""
    user_id = update.effective_user.id
    session = get_session(user_id)
    session.reset()

    await update.message.reply_text(
        "Islem iptal edildi.",
        reply_markup=get_main_keyboard()
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    session = get_session(user_id)

    status_text = f"""
*Bot Durumu*
- State: {session.state.name}
- Topic: {session.topic or 'Yok'}
- Post: {'Var' if session.post_text else 'Yok'}
- Gorsel: {'Var' if session.image_path else 'Yok'}
"""
    await update.message.reply_text(status_text, parse_mode='Markdown')


# Callback handlers
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await query.edit_message_text("Yetkisiz erisim.")
        return

    session = get_session(user_id)
    action = query.data

    if action == "new_post":
        await handle_new_post(query, session)
    elif action == "status":
        await handle_status(query, session)
    elif action == "approve_post":
        await handle_approve_post(query, session)
    elif action == "regenerate_post":
        await handle_regenerate_post(query, session)
    elif action == "edit_post":
        await handle_edit_post(query, session)
    elif action == "regenerate_visual":
        await handle_regenerate_visual(query, session)
    elif action == "publish_facebook":
        await handle_publish_facebook(query, session)
    elif action == "confirm_publish":
        await handle_confirm_publish(query, session)
    elif action == "cancel_publish":
        await handle_cancel_publish(query, session)
    elif action == "cancel":
        await handle_cancel(query, session)


async def handle_new_post(query, session: SessionData):
    """Handle new post request."""
    session.reset()
    session.state = BotState.WAITING_TOPIC

    await query.edit_message_text(
        "Yeni post olusturmak icin bir konu girin.\n\n"
        "*Ornek konular:*\n"
        "- KKTC'de akilli tarim\n"
        "- Sera sulama sistemleri\n"
        "- Enerji izleme faydlari\n"
        "- IoT ile maliyet dusurme\n"
        "- Kestirimci bakim avantajlari\n\n"
        "Konunuzu yazin:",
        parse_mode='Markdown'
    )


async def handle_status(query, session: SessionData):
    """Handle status request."""
    status_text = f"""
*Bot Durumu*
- Durum: {session.state.name}
- Konu: {session.topic or 'Belirlenmedi'}
- Post Metni: {'Mevcut' if session.post_text else 'Yok'}
- Gorsel: {'Mevcut' if session.image_path else 'Yok'}
"""
    await query.edit_message_text(
        status_text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard()
    )


async def handle_approve_post(query, session: SessionData):
    """Handle post approval - generate visual."""
    if not session.post_text or not session.topic:
        await query.edit_message_text(
            "Hata: Post metni bulunamadi.",
            reply_markup=get_main_keyboard()
        )
        return

    await query.edit_message_text(
        "Gorsel olusturuluyor... Bu islem 1-2 dakika surebilir."
    )

    try:
        # Generate visual HTML
        html_content = await generate_visual_html(session.post_text, session.topic)
        session.html_content = html_content

        # Render to PNG
        html_path, image_path = await save_html_and_render(html_content)
        session.html_path = html_path
        session.image_path = image_path
        session.state = BotState.SHOWING_VISUAL

        # Send the image
        await query.message.reply_photo(
            photo=open(image_path, 'rb'),
            caption=f"*Gorsel olusturuldu!*\n\nKonu: {session.topic}\n\nAsagidaki seceneklerden birini secin:",
            parse_mode='Markdown',
            reply_markup=get_visual_review_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to generate visual: {e}")
        await query.message.reply_text(
            f"Gorsel olusturulurken hata olustu:\n{str(e)}\n\nTekrar denemek ister misiniz?",
            reply_markup=get_post_review_keyboard()
        )


async def handle_regenerate_post(query, session: SessionData):
    """Handle post regeneration request."""
    if not session.topic:
        await query.edit_message_text(
            "Hata: Konu bulunamadi.",
            reply_markup=get_main_keyboard()
        )
        return

    await query.edit_message_text(
        f"Post yeniden olusturuluyor...\nKonu: {session.topic}"
    )

    try:
        post_text = await generate_post_text(session.topic)
        session.post_text = post_text
        session.state = BotState.SHOWING_POST

        await query.message.reply_text(
            f"*Yeni Post Metni:*\n\n{post_text}",
            parse_mode='Markdown',
            reply_markup=get_post_review_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to regenerate post: {e}")
        await query.message.reply_text(
            f"Post olusturulurken hata olustu:\n{str(e)}",
            reply_markup=get_main_keyboard()
        )


async def handle_edit_post(query, session: SessionData):
    """Handle post edit request."""
    session.state = BotState.WAITING_FEEDBACK

    await query.edit_message_text(
        "Post metnini nasil degistirmemi istersiniz?\n\n"
        "Geri bildiriminizi yazin (ornek: 'daha kisa yap', 'emoji azalt', 'enerji tasarrufunu vurgula'):"
    )


async def handle_regenerate_visual(query, session: SessionData):
    """Handle visual regeneration request."""
    # Same as approve_post but regenerates
    await handle_approve_post(query, session)


async def handle_publish_facebook(query, session: SessionData):
    """Handle Facebook publish request - ask for confirmation."""
    session.state = BotState.CONFIRMING_PUBLISH

    await query.edit_message_text(
        "*Facebook'a Paylasim*\n\n"
        f"Konu: {session.topic}\n\n"
        "Bu postu Facebook sayfanizda paylasmak istediginizden emin misiniz?",
        parse_mode='Markdown',
        reply_markup=get_confirm_publish_keyboard()
    )


async def handle_confirm_publish(query, session: SessionData):
    """Handle confirmed Facebook publish."""
    if not session.post_text:
        await query.edit_message_text(
            "Hata: Post metni bulunamadi.",
            reply_markup=get_main_keyboard()
        )
        return

    await query.edit_message_text("Facebook'a gonderiliyor...")

    try:
        if session.image_path:
            result = await post_with_photo_to_facebook(
                message=session.post_text,
                image_path=session.image_path
            )
        else:
            result = await post_text_to_facebook(message=session.post_text)

        post_id = result.get('id', 'Bilinmiyor')

        await query.message.reply_text(
            f"Basariyla Facebook'a paylasild!\n\n"
            f"Post ID: {post_id}\n"
            f"Konu: {session.topic}",
            reply_markup=get_main_keyboard()
        )

        # Reset session after successful publish
        session.reset()

    except FacebookError as e:
        logger.error(f"Facebook error: {e.message}")
        await query.message.reply_text(
            f"Facebook hatasi:\n{e.message}\n\n"
            "Facebook ayarlarinizi kontrol edin.",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Failed to publish: {e}")
        await query.message.reply_text(
            f"Paylasim sirasinda hata olustu:\n{str(e)}",
            reply_markup=get_visual_review_keyboard()
        )


async def handle_cancel_publish(query, session: SessionData):
    """Handle publish cancellation."""
    session.state = BotState.SHOWING_VISUAL

    await query.edit_message_text(
        "Paylasim iptal edildi.\n\nNe yapmak istersiniz?",
        reply_markup=get_visual_review_keyboard()
    )


async def handle_cancel(query, session: SessionData):
    """Handle general cancellation."""
    session.reset()

    await query.edit_message_text(
        "Islem iptal edildi.",
        reply_markup=get_main_keyboard()
    )


# Message handler for text input
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages based on current state."""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    session = get_session(user_id)
    text = update.message.text.strip()

    if session.state == BotState.WAITING_TOPIC:
        await handle_topic_input(update, session, text)
    elif session.state == BotState.WAITING_FEEDBACK:
        await handle_feedback_input(update, session, text)
    else:
        # Check for natural language commands
        lower_text = text.lower()
        if any(word in lower_text for word in ['yeni post', 'post olustur', 'yeni icerik']):
            session.reset()
            session.state = BotState.WAITING_TOPIC
            await update.message.reply_text(
                "Yeni post icin konu girin:\n\n"
                "Ornek: 'KKTC akilli tarim', 'sera otomasyonu', 'enerji izleme'"
            )
        elif 'hakkinda post' in lower_text or 'konusunda post' in lower_text:
            # Extract topic from message
            topic = text.replace('hakkinda post', '').replace('konusunda post', '').strip()
            if topic:
                session.reset()
                session.topic = topic
                await generate_and_show_post(update, session)
            else:
                await update.message.reply_text(
                    "Konu belirtmediniz. Ornek: 'akilli tarim hakkinda post'",
                    reply_markup=get_main_keyboard()
                )
        else:
            await update.message.reply_text(
                "Anlamadim. Asagidaki menuyu kullanabilirsiniz:",
                reply_markup=get_main_keyboard()
            )


async def handle_topic_input(update: Update, session: SessionData, topic: str):
    """Handle topic input for new post."""
    if len(topic) < 3:
        await update.message.reply_text(
            "Konu cok kisa. En az 3 karakter olmali.\nLutfen tekrar deneyin:"
        )
        return

    session.topic = topic
    await generate_and_show_post(update, session)


async def generate_and_show_post(update: Update, session: SessionData):
    """Generate post and show to user."""
    await update.message.reply_text(
        f"Post olusturuluyor...\nKonu: {session.topic}\n\n"
        "Bu islem 30-60 saniye surebilir."
    )

    try:
        post_text = await generate_post_text(session.topic)
        session.post_text = post_text
        session.state = BotState.SHOWING_POST

        await update.message.reply_text(
            f"*Olusturulan Post:*\n\n{post_text}",
            parse_mode='Markdown',
            reply_markup=get_post_review_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to generate post: {e}")
        session.state = BotState.IDLE
        await update.message.reply_text(
            f"Post olusturulurken hata olustu:\n{str(e)}\n\n"
            "Lutfen tekrar deneyin.",
            reply_markup=get_main_keyboard()
        )


async def handle_feedback_input(update: Update, session: SessionData, feedback: str):
    """Handle feedback for post improvement."""
    if not session.post_text:
        await update.message.reply_text(
            "Hata: Duzenlencek post bulunamadi.",
            reply_markup=get_main_keyboard()
        )
        session.state = BotState.IDLE
        return

    await update.message.reply_text(
        f"Post geri bildirime gore duzenleniyor...\n"
        f"Geri bildirim: {feedback}"
    )

    try:
        improved_post = await improve_post_text(session.post_text, feedback)
        session.post_text = improved_post
        session.state = BotState.SHOWING_POST
        # Reset visual since post changed
        session.html_content = None
        session.image_path = None

        await update.message.reply_text(
            f"*Duzenlenmis Post:*\n\n{improved_post}",
            parse_mode='Markdown',
            reply_markup=get_post_review_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to improve post: {e}")
        await update.message.reply_text(
            f"Post duzenlenirken hata olustu:\n{str(e)}",
            reply_markup=get_post_review_keyboard()
        )


# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.effective_user:
        user_id = update.effective_user.id
        session = get_session(user_id)
        session.reset()

    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Bir hata olustu. Islem iptal edildi.\n"
                "/start komutuyla tekrar baslayabilirsiniz."
            )
    except Exception:
        pass


def main():
    """Main function to run the bot."""
    logger.info("Starting Olivenet Social Media Bot...")

    # Ensure directories exist
    settings.ensure_directories()

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Run the bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
