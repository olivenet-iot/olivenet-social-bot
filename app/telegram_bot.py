#!/usr/bin/env python3
"""
Olivenet Social Media Bot - Telegram Bot
Main bot application with conversation handling.
"""
import asyncio
import json
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
from app.claude_helper import generate_post_text, generate_visual_html, improve_post_text, suggest_topics
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
    CHOOSING_VISUAL_TYPE = auto()
    SHOWING_VISUAL = auto()
    CONFIRMING_PUBLISH = auto()
    WAITING_FEEDBACK = auto()
    EDITING_VISUAL = auto()


class SessionData:
    """Session data for a user."""

    def __init__(self):
        self.state: BotState = BotState.IDLE
        self.topic: Optional[str] = None
        self.post_text: Optional[str] = None
        self.html_content: Optional[str] = None
        self.image_path: Optional[str] = None
        self.html_path: Optional[str] = None
        self.visual_type: Optional[str] = None  # 'infographic' or 'realistic'

    def reset(self):
        """Reset session to initial state."""
        self.state = BotState.IDLE
        self.topic = None
        self.post_text = None
        self.html_content = None
        self.image_path = None
        self.html_path = None
        self.visual_type = None


# Global session storage (in production, use Redis or database)
sessions: Dict[int, SessionData] = {}

# Session file path for persistence
SESSION_FILE = Path("/opt/olivenet-social/session_state.json")


def save_sessions():
    """Save sessions to disk."""
    try:
        data = {}
        for user_id, session in sessions.items():
            data[str(user_id)] = {
                "state": session.state.name,
                "topic": session.topic,
                "post_text": session.post_text,
                "image_path": session.image_path,
                "html_path": session.html_path
            }
        SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning(f"Failed to save sessions: {e}")


def load_sessions():
    """Load sessions from disk."""
    if not SESSION_FILE.exists():
        return
    try:
        data = json.loads(SESSION_FILE.read_text())
        for user_id_str, session_data in data.items():
            user_id = int(user_id_str)
            session = SessionData()
            session.state = BotState[session_data.get("state", "IDLE")]
            session.topic = session_data.get("topic")
            session.post_text = session_data.get("post_text")
            session.image_path = session_data.get("image_path")
            session.html_path = session_data.get("html_path")
            sessions[user_id] = session
        logger.info(f"Loaded {len(sessions)} sessions from disk")
    except Exception as e:
        logger.warning(f"Failed to load sessions: {e}")


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
        [InlineKeyboardButton("Konu Oner", callback_data="suggest_topic")],
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


def get_visual_type_keyboard() -> InlineKeyboardMarkup:
    """Visual type selection keyboard."""
    keyboard = [
        [InlineKeyboardButton("Infografik (Statik)", callback_data="visual_infographic")],
        [InlineKeyboardButton("Animasyonlu Video", callback_data="visual_animated")],
        [InlineKeyboardButton("Gercekci AI Gorsel", callback_data="visual_realistic")],
        [InlineKeyboardButton("Iptal", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_visual_review_keyboard() -> InlineKeyboardMarkup:
    """Visual review keyboard."""
    keyboard = [
        [InlineKeyboardButton("Facebook'a Gonder", callback_data="publish_facebook")],
        [InlineKeyboardButton("Gorseli Duzenle", callback_data="edit_visual")],
        [
            InlineKeyboardButton("Yeniden Uret", callback_data="regenerate_visual"),
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
        "- Sosyal medya uzmani gibi konu onerileri alabilir\n"
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
    elif action == "suggest_topic":
        await handle_suggest_topic(query, session)
    elif action == "status":
        await handle_status(query, session)
    elif action == "approve_post":
        await handle_approve_post(query, session)
    elif action == "visual_infographic":
        await handle_visual_infographic(query, session)
    elif action == "visual_animated":
        await handle_visual_animated(query, session)
    elif action == "visual_realistic":
        await handle_visual_realistic(query, session)
    elif action == "regenerate_post":
        await handle_regenerate_post(query, session)
    elif action == "edit_post":
        await handle_edit_post(query, session)
    elif action == "edit_visual":
        await handle_edit_visual(query, session)
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
    elif action == "main_menu":
        await handle_main_menu(query, session)


async def handle_new_post(query, session: SessionData):
    """Handle new post request."""
    session.reset()
    session.state = BotState.WAITING_TOPIC
    save_sessions()

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


async def handle_suggest_topic(query, session: SessionData):
    """Handle topic suggestion request - social media expert style."""
    await query.edit_message_text(
        "Konu onerileri hazirlaniyor...\n\n"
        "Mevsim, gun ve KKTC pazarina uygun oneriler olusturuluyor."
    )

    try:
        suggestions = await suggest_topics()

        # Create keyboard with main menu option
        keyboard = [
            [InlineKeyboardButton("Yeni Post Olustur", callback_data="new_post")],
            [InlineKeyboardButton("Ana Menu", callback_data="main_menu")]
        ]

        await query.message.reply_text(
            f"*Bugun Icin Konu Onerileri:*\n\n{suggestions}\n\n"
            "_Bir konu secip 'Yeni Post Olustur' ile devam edebilirsiniz._",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Failed to suggest topics: {e}")
        await query.message.reply_text(
            f"Konu onerileri olusturulurken hata olustu:\n{str(e)[:200]}",
            reply_markup=get_main_keyboard()
        )


async def handle_approve_post(query, session: SessionData):
    """Handle post approval - show visual type selection."""
    if not session.post_text or not session.topic:
        await query.edit_message_text(
            "Hata: Post metni bulunamadi.",
            reply_markup=get_main_keyboard()
        )
        return

    session.state = BotState.CHOOSING_VISUAL_TYPE
    save_sessions()

    # Show visual type selection
    post_preview = session.post_text[:400] + "..." if len(session.post_text) > 400 else session.post_text

    await query.edit_message_text(
        f"*Post metni onaylandi!*\n\n{post_preview}\n\n*Gorsel turunu secin:*",
        parse_mode='Markdown',
        reply_markup=get_visual_type_keyboard()
    )


async def handle_visual_infographic(query, session: SessionData):
    """Handle infographic visual generation (existing HTML/Dashboard system)."""
    await query.edit_message_text(
        "Infografik gorsel olusturuluyor... Bu islem 1-2 dakika surebilir."
    )

    try:
        # Generate visual HTML
        html_content = await generate_visual_html(session.post_text, session.topic)
        session.html_content = html_content
        session.visual_type = "infographic"

        # Render to PNG
        html_path, image_path = await save_html_and_render(html_content)
        session.html_path = html_path
        session.image_path = image_path
        session.state = BotState.SHOWING_VISUAL
        save_sessions()

        # Send the image
        await query.message.reply_photo(
            photo=open(image_path, 'rb'),
            caption=f"*Infografik gorsel olusturuldu!*\n\nKonu: {session.topic}\n\nAsagidaki seceneklerden birini secin:",
            parse_mode='Markdown',
            reply_markup=get_visual_review_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to generate infographic visual: {e}")
        await query.message.reply_text(
            f"Gorsel olusturulurken hata olustu:\n{str(e)}\n\nTekrar denemek ister misiniz?",
            reply_markup=get_visual_type_keyboard()
        )


async def handle_visual_realistic(query, session: SessionData):
    """Handle realistic AI visual generation using Gemini."""
    await query.edit_message_text(
        "Gercekci AI gorsel olusturuluyor (Gemini)...\n\nBu islem 30-60 saniye surebilir..."
    )

    try:
        from app.gemini_helper import generate_realistic_image

        image_path = await generate_realistic_image(
            topic=session.topic,
            post_text=session.post_text
        )

        session.image_path = image_path
        session.visual_type = "realistic"
        session.state = BotState.SHOWING_VISUAL
        save_sessions()

        # Send the image
        await query.message.reply_photo(
            photo=open(image_path, 'rb'),
            caption=f"*Gercekci AI gorsel olusturuldu!*\n\nKonu: {session.topic}\n\nAsagidaki seceneklerden birini secin:",
            parse_mode='Markdown',
            reply_markup=get_visual_review_keyboard()
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Gemini error: {error_detail}")
        print(f"Gemini hatasi: {error_detail}")
        await query.message.reply_text(
            f"AI gorsel olusturma hatasi:\n{str(e)[:300]}\n\nBaska bir gorsel turu denemek ister misiniz?",
            reply_markup=get_visual_type_keyboard()
        )


async def handle_visual_animated(query, session: SessionData):
    """Handle animated MP4 visual generation."""
    await query.edit_message_text(
        "Animasyonlu video olusturuluyor...\n\n"
        "Bu islem 1-2 dakika surebilir (frame'ler render ediliyor)."
    )

    try:
        from app.claude_helper import generate_animated_visual_html
        from app.animated_renderer import render_animated_html_to_video
        from datetime import datetime

        # Generate animated HTML
        html_content = await generate_animated_visual_html(session.post_text, session.topic)
        session.html_content = html_content
        session.visual_type = "animated"

        # Render to video
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/opt/olivenet-social/outputs/animated_{timestamp}.mp4"

        await render_animated_html_to_video(html_content, output_path, duration=4, fps=30)

        session.image_path = output_path
        session.state = BotState.SHOWING_VISUAL
        save_sessions()

        # Send video
        with open(output_path, 'rb') as video_file:
            await query.message.reply_video(
                video=video_file,
                caption=f"*Animasyonlu gorsel olusturuldu!*\n\nKonu: {session.topic}\n\nAsagidaki seceneklerden birini secin:",
                parse_mode='Markdown',
                reply_markup=get_visual_review_keyboard()
            )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Animation error: {error_detail}")
        print(f"Animasyon hatasi: {error_detail}")
        await query.message.reply_text(
            f"Animasyon olusturma hatasi:\n{str(e)[:300]}\n\nBaska bir gorsel turu denemek ister misiniz?",
            reply_markup=get_visual_type_keyboard()
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
    """Handle visual regeneration request - show visual type selection again."""
    session.state = BotState.CHOOSING_VISUAL_TYPE
    save_sessions()

    # Fotoğraflı mesajlar için caption, text mesajlar için text kullan
    try:
        await query.edit_message_caption(
            caption="*Gorsel turunu secin:*",
            parse_mode='Markdown',
            reply_markup=get_visual_type_keyboard()
        )
    except Exception:
        await query.edit_message_text(
            "*Gorsel turunu secin:*",
            parse_mode='Markdown',
            reply_markup=get_visual_type_keyboard()
        )


async def handle_edit_visual(query, session: SessionData):
    """Handle visual edit request - ask for feedback."""
    session.state = BotState.EDITING_VISUAL
    save_sessions()

    await query.message.reply_text(
        "Gorsel icin geri bildiriminizi yazin:\n\n"
        "*Ornekler:*\n"
        "- 'Arka plani daha acik yap'\n"
        "- 'Daha az metin olsun'\n"
        "- 'Istatistikleri buyut'\n"
        "- 'Daha minimalist bir tasarim'\n"
        "- 'Turuncu yerine mavi kullan'\n"
        "- 'Daha fazla yesil ton kullan'",
        parse_mode='Markdown'
    )


async def handle_publish_facebook(query, session: SessionData):
    """Handle Facebook publish request - ask for confirmation."""
    session.state = BotState.CONFIRMING_PUBLISH
    save_sessions()

    confirmation_text = (
        "*Facebook'a Paylasim*\n\n"
        f"Konu: {session.topic}\n\n"
        "Bu postu Facebook sayfanizda paylasmak istediginizden emin misiniz?"
    )

    # Fotoğraflı mesajlar için caption, text mesajlar için text kullan
    try:
        await query.edit_message_caption(
            caption=confirmation_text,
            parse_mode='Markdown',
            reply_markup=get_confirm_publish_keyboard()
        )
    except Exception:
        # Fallback: eğer text message ise
        await query.edit_message_text(
            confirmation_text,
            parse_mode='Markdown',
            reply_markup=get_confirm_publish_keyboard()
        )


async def handle_confirm_publish(query, session: SessionData):
    """Handle confirmed Facebook publish."""
    if not session.post_text:
        try:
            await query.edit_message_text(
                "Hata: Post metni bulunamadi.",
                reply_markup=get_main_keyboard()
            )
        except Exception:
            await query.edit_message_caption(
                caption="Hata: Post metni bulunamadi.",
                reply_markup=get_main_keyboard()
            )
        return

    # Fotoğraflı mesajlar için caption, text mesajlar için text kullan
    try:
        await query.edit_message_text("Facebook'a gonderiliyor...")
    except Exception:
        await query.edit_message_caption(caption="Facebook'a gonderiliyor...")

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
        save_sessions()

    except FacebookError as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Facebook error: {e.message}\n{error_detail}")
        await query.message.reply_text(
            f"Facebook hatasi:\n{e.message}\n\n"
            f"Detay: {str(e)[:300]}\n\n"
            "Facebook ayarlarinizi kontrol edin.",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"Failed to publish: {e}\n{error_detail}")
        print(f"Facebook paylaşım hatası: {error_detail}")
        await query.message.reply_text(
            f"Paylasim sirasinda hata olustu:\n{str(e)[:500]}\n\n"
            f"Image path: {session.image_path}",
            reply_markup=get_visual_review_keyboard()
        )


async def handle_cancel_publish(query, session: SessionData):
    """Handle publish cancellation."""
    session.state = BotState.SHOWING_VISUAL
    save_sessions()

    cancel_text = "Paylasim iptal edildi.\n\nNe yapmak istersiniz?"

    # Fotoğraflı mesajlar için caption, text mesajlar için text kullan
    try:
        await query.edit_message_caption(
            caption=cancel_text,
            reply_markup=get_visual_review_keyboard()
        )
    except Exception:
        await query.edit_message_text(
            cancel_text,
            reply_markup=get_visual_review_keyboard()
        )


async def handle_cancel(query, session: SessionData):
    """Handle general cancellation."""
    session.reset()
    save_sessions()

    await query.edit_message_text(
        "Islem iptal edildi.",
        reply_markup=get_main_keyboard()
    )


async def handle_main_menu(query, session: SessionData):
    """Handle main menu request."""
    await query.edit_message_text(
        "Ana menu:\n\nNe yapmak istersiniz?",
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
    elif session.state == BotState.EDITING_VISUAL:
        await handle_visual_feedback_input(update, context, session, text)
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
        save_sessions()

        await update.message.reply_text(
            f"*Olusturulan Post:*\n\n{post_text}",
            parse_mode='Markdown',
            reply_markup=get_post_review_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to generate post: {e}")
        session.state = BotState.IDLE
        save_sessions()
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
        save_sessions()

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


async def handle_visual_feedback_input(update: Update, context: ContextTypes.DEFAULT_TYPE, session: SessionData, feedback: str):
    """Handle feedback for visual improvement."""
    if not session.post_text or not session.topic:
        await update.message.reply_text(
            "Hata: Post bilgisi bulunamadi.",
            reply_markup=get_main_keyboard()
        )
        session.state = BotState.IDLE
        save_sessions()
        return

    visual_type = session.visual_type or "infographic"

    await update.message.reply_text(
        f"Gorsel geri bildirime gore yeniden olusturuluyor...\n"
        f"Geri bildirim: {feedback}"
    )

    try:
        if visual_type == "infographic":
            from app.claude_helper import generate_visual_html_with_feedback
            from app.renderer import save_html_and_render

            html_content = await generate_visual_html_with_feedback(
                session.post_text,
                session.topic,
                feedback
            )
            session.html_content = html_content

            html_path, image_path = await save_html_and_render(html_content)
            session.html_path = html_path
            session.image_path = image_path

        else:  # realistic
            from app.gemini_helper import generate_realistic_image_with_feedback

            image_path = await generate_realistic_image_with_feedback(
                session.topic,
                session.post_text,
                feedback
            )
            session.image_path = image_path

        session.state = BotState.SHOWING_VISUAL
        save_sessions()

        # Send the updated image
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=open(session.image_path, 'rb'),
            caption=f"*Duzenlenmis gorsel hazir!*\n\nGeri bildirim: {feedback[:100]}",
            parse_mode='Markdown',
            reply_markup=get_visual_review_keyboard()
        )

    except Exception as e:
        logger.error(f"Failed to regenerate visual with feedback: {e}")
        session.state = BotState.SHOWING_VISUAL
        save_sessions()
        await update.message.reply_text(
            f"Gorsel duzenlenirken hata olustu:\n{str(e)[:200]}",
            reply_markup=get_visual_review_keyboard()
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

    # Load saved sessions
    load_sessions()

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
