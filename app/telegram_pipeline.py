"""
Telegram Bot - Pipeline Entegrasyonu
Semi-autonomous mod için onay akışı

Authorization: Sadece admin kullanıcılar işlem yapabilir.
"""

import asyncio
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut, RetryAfter
from telegram.helpers import escape_markdown
from app.scheduler import ContentPipeline, ContentScheduler, create_default_scheduler
from app.database import (
    get_current_strategy, get_analytics_summary, log_approval_decision,
    get_week_calendar, get_published_posts,
    get_todays_summary, get_weekly_progress, get_next_scheduled,
    get_best_performing_content, get_next_schedule_slot,
    get_recent_prompts, get_top_performing_prompts, get_prompt_style_stats
)
from app.config import settings
from app.video_models import VIDEO_MODELS, get_model_config, get_model_durations, get_max_duration
from app.video_styles import VIDEO_STYLES, STYLE_CATEGORIES, get_style_config, get_styles_by_category
from app.database.crud import (
    get_top_opportunities, get_opportunity, get_opportunity_stats,
    get_agent_logs, update_opportunity, get_weekly_content_breakdown
)
from app.engine.scheduler import BRAIN_CYCLE_MINUTES

# Global değişkenler
pipeline: ContentPipeline = None
scheduler: ContentScheduler = None
admin_chat_id: int = None
pending_input: dict = {}  # Kullanıcıdan beklenen input
brain_agent = None  # Set by main.py, used by /pause /resume /force
feed_aggregator = None  # Set by main.py, used by /feeds


# ============ AUTHORIZATION ============

def is_admin(user_id: int) -> bool:
    """
    Kullanıcının admin olup olmadığını kontrol et.
    Admin listesi: settings.admin_user_ids
    """
    return user_id in settings.admin_user_ids


async def send_unauthorized_message(query):
    """Yetkisiz kullanıcıya mesaj gönder."""
    await query.answer("⛔ Bu işlem için yetkiniz yok!", show_alert=True)
    await query.edit_message_text(
        "⛔ *Yetkisiz Erişim*\n\n"
        "Bu bot sadece yetkili kullanıcılar tarafından kullanılabilir.\n"
        f"Kullanıcı ID'niz: `{query.from_user.id}`\n\n"
        "Erişim için sistem yöneticisiyle iletişime geçin.",
        parse_mode="Markdown"
    )

async def telegram_notify(message: str, data: dict = None, buttons: list = None):
    """Pipeline'dan Telegram'a bildirim - retry mekanizması ile"""
    global admin_chat_id

    if not admin_chat_id:
        print("[TELEGRAM] Admin chat ID not set!")
        return

    from telegram import Bot
    import os

    # Retry ayarları
    max_retries = 3
    retry_delay = 5  # saniye

    request = HTTPXRequest(
        connection_pool_size=4,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
    )
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"), request=request)

    # Keyboard oluştur
    keyboard = []
    if buttons:
        for btn in buttons:
            keyboard.append([InlineKeyboardButton(btn["text"], callback_data=btn["callback"])])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # Görsel varsa gönder
    if data and data.get("image_path"):
        try:
            with open(data["image_path"], "rb") as photo:
                try:
                    await bot.send_photo(
                        chat_id=admin_chat_id,
                        photo=photo,
                        caption=message[:1024],
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                except Exception:
                    # Markdown hatası - tekrar dene
                    photo.seek(0)
                    clean_msg = message.replace("*", "").replace("_", "").replace("`", "")
                    await bot.send_photo(
                        chat_id=admin_chat_id,
                        photo=photo,
                        caption=clean_msg[:1024],
                        reply_markup=reply_markup
                    )
                return
        except Exception as e:
            print(f"[TELEGRAM] Photo send error: {e}")

    # Video varsa gönder
    if data and data.get("video_path"):
        try:
            with open(data["video_path"], "rb") as video:
                try:
                    await bot.send_video(
                        chat_id=admin_chat_id,
                        video=video,
                        caption=message[:1024],
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                except Exception:
                    video.seek(0)
                    clean_msg = message.replace("*", "").replace("_", "").replace("`", "")
                    await bot.send_video(
                        chat_id=admin_chat_id,
                        video=video,
                        caption=clean_msg[:1024],
                        reply_markup=reply_markup
                    )
                return
        except Exception as e:
            print(f"[TELEGRAM] Video send error: {e}")

    # Normal mesaj gönder - retry ile
    for attempt in range(max_retries):
        try:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=message,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            return
        except (NetworkError, TimedOut) as e:
            if attempt < max_retries - 1:
                print(f"[TELEGRAM] Retry {attempt + 1}/{max_retries} - {e}")
                await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                print(f"[TELEGRAM] Mesaj gönderilemedi: {e}")
        except Exception as e:
            # Markdown parse hatası - düz metin gönder
            clean_message = message.replace("*", "").replace("_", "").replace("`", "")
            try:
                await bot.send_message(
                    chat_id=admin_chat_id,
                    text=clean_message,
                    reply_markup=reply_markup
                )
                return
            except (NetworkError, TimedOut) as ne:
                if attempt < max_retries - 1:
                    print(f"[TELEGRAM] Retry {attempt + 1}/{max_retries} - {ne}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
            except Exception as inner_e:
                print(f"[TELEGRAM] Mesaj gönderilemedi: {inner_e}")
                return


# ============ KOMUTLAR ============

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ana menü"""
    global admin_chat_id
    admin_chat_id = update.effective_chat.id

    keyboard = [
        # İçerik Oluşturma
        [
            InlineKeyboardButton("📝 Günlük İçerik", callback_data="start_daily"),
            InlineKeyboardButton("🎬 Reels", callback_data="create_reels")
        ],
        [
            InlineKeyboardButton("🎠 Carousel", callback_data="create_carousel"),
            InlineKeyboardButton("🎥 Uzun Video", callback_data="create_long_video")
        ],
        [
            InlineKeyboardButton("🎭 Conversational", callback_data="create_conversational"),
            InlineKeyboardButton("🤖 Otonom", callback_data="start_autonomous")
        ],
        # Planlama
        [
            InlineKeyboardButton("📋 İçerik Planı", callback_data="weekly_plan"),
            InlineKeyboardButton("📆 Zamanlama", callback_data="weekly_schedule")
        ],
        [
            InlineKeyboardButton("⏭️ Sıradaki", callback_data="next_content"),
            InlineKeyboardButton("📊 Hızlı Durum", callback_data="quick_status")
        ],
        # Analytics & Ayarlar
        [
            InlineKeyboardButton("📈 Analytics", callback_data="analytics_report"),
            InlineKeyboardButton("⚙️ Strateji", callback_data="show_strategy")
        ],
        [
            InlineKeyboardButton("🔄 Sync", callback_data="sync_metrics"),
            InlineKeyboardButton("❓ Yardım", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🤖 *Olivenet AI Content System*\n\n"
        "*İçerik:* 📝 Günlük | 🎬 Reels | 🎠 Carousel | 🤖 Otonom\n"
        "*Planlama:* 📋 İçerik | 📆 Zamanlama | ⏭️ Sıradaki | 📊 Durum\n"
        "*Analytics:* 📈 Rapor | ⚙️ Strateji | 🔄 Sync\n\n"
        "Ne yapmak istersiniz?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sistem durumu"""
    global pipeline, scheduler

    pipeline_state = pipeline.state.value if pipeline else "not_initialized"
    scheduler_status = scheduler.get_status() if scheduler else {"running": False}

    await update.message.reply_text(
        f"📊 *Sistem Durumu*\n\n"
        f"*Pipeline:* {pipeline_state}\n"
        f"*Scheduler:* {'Çalışıyor' if scheduler_status.get('running') else 'Durdu'}\n"
        f"*Aktif Görevler:* {len(scheduler_status.get('tasks', []))}\n",
        parse_mode="Markdown"
    )


async def cmd_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manuel içerik oluştur"""
    keyboard = [
        [InlineKeyboardButton("📝 Konu Belirle", callback_data="manual_topic")],
        [InlineKeyboardButton("💡 AI Konu Öner", callback_data="ai_suggest_topic")],
        [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📝 *Manuel İçerik Oluşturma*\n\n"
        "Kendi konunuzu belirleyebilir veya AI'dan öneri alabilirsiniz.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hızlı durum - /stats"""
    global admin_chat_id
    admin_chat_id = update.effective_chat.id

    summary = get_todays_summary()
    weekly = get_weekly_progress()

    text = "📊 *BUGÜNÜN DURUMU*\n━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"✅ Yayınlanan: {summary.get('published', 0)}\n"
    text += f"⏳ Bekleyen: {summary.get('scheduled', 0)}\n"
    text += f"❌ Başarısız: {summary.get('failed', 0)}\n\n"

    text += "📈 *BU HAFTA:*\n"
    text += f"Toplam: {weekly.get('total', 0)} içerik\n"
    text += f"🎬 Reels: {weekly.get('reels', 0)}\n"
    text += f"🎠 Carousel: {weekly.get('carousel', 0)}\n"
    text += f"📝 Post: {weekly.get('post', 0)}\n"

    keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sıradaki içerik - /next"""
    global admin_chat_id
    admin_chat_id = update.effective_chat.id

    from datetime import datetime
    next_post = get_next_scheduled()

    type_icons = {"reels": "🎬", "carousel": "🎠", "post": "📝", "flux": "📝"}

    if next_post:
        scheduled_str = next_post.get('scheduled_at')
        if scheduled_str:
            try:
                scheduled_at = datetime.fromisoformat(str(scheduled_str).replace('Z', '+00:00'))
                remaining = scheduled_at - datetime.now()
                total_seconds = int(remaining.total_seconds())
                if total_seconds > 0:
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes = remainder // 60
                    time_left = f"{hours}s {minutes}dk"
                else:
                    time_left = "Şimdi!"
            except:
                time_left = "N/A"
                scheduled_at = None
        else:
            time_left = "N/A"
            scheduled_at = None

        vtype = (next_post.get('visual_type') or 'post').lower()
        icon = type_icons.get(vtype, '📌')

        text = f"⏭️ *Sıradaki:* {icon} {vtype.capitalize()}\n"
        if scheduled_at:
            text += f"⏰ {scheduled_at.strftime('%H:%M')} ({time_left})\n"
        if next_post.get('topic'):
            text += f"📋 {next_post['topic'][:40]}..."
    else:
        # Slot bilgisini göster
        next_slot = get_next_schedule_slot()
        if next_slot:
            icon = type_icons.get(next_slot['type'], '📌')
            mins = next_slot['minutes_until']
            if mins < 60:
                time_left = f"{mins}dk"
            elif mins < 1440:
                time_left = f"{mins // 60}s {mins % 60}dk"
            else:
                time_left = f"{mins // 1440}g {(mins % 1440) // 60}s"

            text = f"⏭️ *Slot:* {icon} {next_slot['type'].capitalize()}\n"
            text += f"📅 {next_slot['day']} {next_slot['time']} ({time_left})\n"
            text += "⚠️ İçerik henüz oluşturulmadı"
        else:
            text = "📭 Zamanlama bulunamadı."

    keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Haftalık program - /schedule"""
    global admin_chat_id
    admin_chat_id = update.effective_chat.id

    from app.agents.orchestrator import OrchestratorAgent
    schedule = OrchestratorAgent.WEEKLY_SCHEDULE

    day_names = {0: "Pzt", 1: "Sal", 2: "Çar", 3: "Per", 4: "Cum", 5: "Cmt", 6: "Paz"}
    type_icons = {"reels": "🎬", "carousel": "🎠", "post": "📝"}

    text = "📆 *HAFTALIK PROGRAM*\n━━━━━━━━━━━━━━━━━━━\n"

    current_day = -1
    for item in schedule:
        if item['day'] != current_day:
            current_day = item['day']
            text += f"\n*{day_names[current_day]}:* "
            first = True
        else:
            first = False

        icon = type_icons.get(item['type'], '📌')
        if first:
            text += f"{icon}{item['time']}"
        else:
            text += f", {icon}{item['time']}"

    text += "\n\n🎬7 🎠2 📝3 = 12/hafta"

    keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Metrics sync - /sync"""
    global admin_chat_id
    admin_chat_id = update.effective_chat.id

    await update.message.reply_text("🔄 *Metrikler senkronize ediliyor...*", parse_mode="Markdown")

    try:
        from app.insights_helper import sync_insights_to_database
        result = await sync_insights_to_database()

        if result.get('success'):
            text = f"✅ Sync tamamlandı! ({result.get('updated', 0)} post güncellendi)"
        else:
            text = f"❌ Hata: {result.get('error', 'Bilinmeyen')}"
    except ImportError:
        text = "⚠️ Sync fonksiyonu bulunamadı."
    except Exception as e:
        text = f"❌ Hata: {str(e)}"

    keyboard = [[InlineKeyboardButton("📈 Analytics", callback_data="analytics_report")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_prompts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt istatistikleri - /prompts"""
    global admin_chat_id
    admin_chat_id = update.effective_chat.id

    # Son 7 günün prompt'ları
    recent = get_recent_prompts(days=7)

    # Top performers
    top = get_top_performing_prompts(limit=3)

    # Stil istatistikleri
    stats = get_prompt_style_stats(days=30)

    message = "📝 *PROMPT İSTATİSTİKLERİ*\n"
    message += "━━━━━━━━━━━━━━━━━━━\n\n"

    # Özet
    message += f"📊 *Son 7 gün:* {len(recent)} prompt\n"

    # Tip dağılımı
    by_type = stats.get('by_type', {})
    if by_type:
        type_str = ", ".join([f"{k}: {v}" for k, v in by_type.items()])
        message += f"📌 *Tip dağılımı:* {type_str}\n"

    # Stil dağılımı
    by_style = stats.get('by_style', {})
    if by_style:
        top_styles = list(by_style.items())[:3]
        style_str = ", ".join([f"{k}: {v}" for k, v in top_styles])
        message += f"🎨 *En çok kullanılan stiller:* {style_str}\n"

    message += "\n"

    # Top performers
    if top:
        message += "🏆 *En İyi Performans:*\n"
        for i, p in enumerate(top, 1):
            style = p.get('prompt_style') or 'N/A'
            ptype = p.get('prompt_type', 'N/A')
            reach = p.get('reach', 0)
            eng = p.get('engagement_rate', 0)
            saves = p.get('saves', 0)

            message += f"{i}. \\[{ptype}/{style}\\]\n"
            message += f"   📊 reach:{reach} eng:{eng:.1f}% saves:{saves}\n"

            # Prompt metninin kısa versiyonu
            prompt_text = p.get('prompt_text', '')
            if prompt_text:
                short_text = prompt_text[:50].replace('_', '\\_').replace('*', '\\*')
                message += f"   _{short_text}..._\n"
            message += "\n"
    else:
        message += "⏳ *Henüz performans verisi yok*\n"
        message += "_Metrikler çekildikçe burada görünecek._\n"

    await update.message.reply_text(message, parse_mode="Markdown")


# ============ CALLBACK HANDLER'LAR ============

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm callback'leri yönet - Authorization kontrolü ile"""
    global pipeline, scheduler, pending_input

    query = update.callback_query
    user_id = query.from_user.id

    # ===== AUTHORIZATION CHECK =====
    if not is_admin(user_id):
        await send_unauthorized_message(query)
        return

    await query.answer()
    action = query.data

    # ===== ANA MENÜ =====
    if action == "main_menu":
        keyboard = [
            # İçerik Oluşturma
            [
                InlineKeyboardButton("📝 Günlük İçerik", callback_data="start_daily"),
                InlineKeyboardButton("🎬 Reels", callback_data="create_reels")
            ],
            [
                InlineKeyboardButton("🎠 Carousel", callback_data="create_carousel"),
                InlineKeyboardButton("🎥 Uzun Video", callback_data="create_long_video")
            ],
            [
                InlineKeyboardButton("🎭 Conversational", callback_data="create_conversational"),
                InlineKeyboardButton("🤖 Otonom", callback_data="start_autonomous")
            ],
            # Planlama
            [
                InlineKeyboardButton("📅 Haftalık Plan", callback_data="weekly_plan"),
                InlineKeyboardButton("📆 Program", callback_data="weekly_schedule")
            ],
            [
                InlineKeyboardButton("⏭️ Sıradaki", callback_data="next_content"),
                InlineKeyboardButton("📊 Hızlı Durum", callback_data="quick_status")
            ],
            # Analytics & Ayarlar
            [
                InlineKeyboardButton("📈 Analytics", callback_data="analytics_report"),
                InlineKeyboardButton("⚙️ Strateji", callback_data="show_strategy")
            ],
            [
                InlineKeyboardButton("🔄 Sync", callback_data="sync_metrics"),
                InlineKeyboardButton("❓ Yardım", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🤖 *Olivenet AI Content System*\n\nNe yapmak istersiniz?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    # ===== GÜNLÜK İÇERİK - KONU SEÇİM MENÜSÜ =====
    elif action == "start_daily":
        keyboard = [
            [InlineKeyboardButton("🤖 Otomatik Konu", callback_data="daily_auto"),
             InlineKeyboardButton("✏️ Manuel Konu", callback_data="daily_manual")],
            [InlineKeyboardButton("❌ İptal", callback_data="cancel")]
        ]
        await query.edit_message_text(
            "📋 *Günlük İçerik*\n\n"
            "Konu seçimi:\n"
            "• *Otomatik*: AI en uygun konuyu seçer\n"
            "• *Manuel*: Kendi konunu yaz",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== GÜNLÜK İÇERİK - OTOMATİK KONU =====
    elif action == "daily_auto":
        await query.edit_message_text("🚀 *Günlük içerik pipeline'ı başlatılıyor...*", parse_mode="Markdown")
        asyncio.create_task(pipeline.run_daily_content())

    # ===== GÜNLÜK İÇERİK - MANUEL KONU =====
    elif action == "daily_manual":
        pending_input["type"] = "daily_manual_topic"
        pending_input["user_id"] = query.from_user.id
        await query.edit_message_text(
            "✏️ *Manuel Konu Girişi*\n\n"
            "Günlük içerik için konu yazın:\n\n"
            "Örnek:\n"
            "• `Jetson Nano ile fabrikada hata tespiti`\n"
            "• `Antalya seralarında akıllı sulama`",
            parse_mode="Markdown"
        )

    # ===== GÜNLÜK İÇERİK - GÖRSEL TİPİ SEÇİMİ =====
    elif action.startswith("daily_visual:"):
        visual_type = action.replace("daily_visual:", "")
        topic = pending_input.get("topic")
        pending_input.clear()

        if not topic:
            await query.edit_message_text("❌ Konu bulunamadı, tekrar deneyin.")
            return

        visual_names = {
            "infographic": "Infographic (HTML)",
            "nano_banana": "AI Infographic (Nano Banana)",
            "carousel": "Carousel (Flux AI)",
            "single": "Tek Görsel (Flux AI)"
        }

        await query.edit_message_text(
            f"🚀 *Günlük içerik başlatılıyor...*\n\n"
            f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n"
            f"🖼️ *Görsel:* {visual_names.get(visual_type, visual_type)}",
            parse_mode="Markdown"
        )

        asyncio.create_task(pipeline.run_daily_content(
            topic=topic,
            manual_topic_mode=True,
            visual_type=visual_type
        ))

    # ===== OTONOM İÇERİK BAŞLAT =====
    elif action == "start_autonomous":
        await query.edit_message_text(
            "🤖 *OTONOM MOD* baslatiliyor...\n\n"
            "Icerik otomatik olusturulacak.\n"
            "Kalite puani 7/10 uzerindeyse otomatik yayinlanacak.\n"
            "Sadece sonuc bildirilecek."
        )

        # Otonom pipeline'ı arka planda çalıştır
        asyncio.create_task(pipeline.run_autonomous_content(min_score=7))

    # ===== CONVERSATIONAL REELS - MODEL SEÇİM MENÜSÜ =====
    elif action == "create_conversational":
        # Model seçim menüsü göster
        conv_models = {
            "sora-2-pro": {"name": "Sora 2 Pro", "emoji": "⭐", "desc": "Yüksek kalite (12s) ⭐"},
            "sora-2": {"name": "Sora 2", "emoji": "🌟", "desc": "Native speech (12s max)"},
        }

        keyboard = []
        for model_id, info in conv_models.items():
            keyboard.append([InlineKeyboardButton(
                f"{info['emoji']} {info['name']} - {info['desc']}",
                callback_data=f"conv_model:{model_id}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data="main_menu")])

        await query.edit_message_text(
            "🎭 *CONVERSATIONAL REELS*\n\n"
            "İki karakter arasında dialog video:\n"
            "• 👨 ERKEK: Problem/soru sorar\n"
            "• 👩 KADIN: Çözüm sunar\n\n"
            "📹 *Model Seç:*\n\n"
            "🌟 *Sora 2 / Sora 2 Pro*: Native speech\n"
            "⚡ *Kling*: TTS + Lipsync API",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== CONVERSATIONAL REELS - MODEL SEÇİLDİ =====
    elif action.startswith("conv_model:"):
        model_id = action.replace("conv_model:", "")
        config = get_model_config(model_id)

        keyboard = []
        for cat_id, cat_info in STYLE_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(
                cat_info["name"],
                callback_data=f"style_cat:{model_id}:{cat_id}:conv"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data="create_conversational")])

        native_speech_models = ["sora-2", "sora-2-pro"]
        speech_info = "🗣️ Native Turkish speech" if model_id in native_speech_models else "🗣️ TTS + Lipsync API"

        await query.edit_message_text(
            f"🎭 *Conversational Reels*\n\n"
            f"📹 *Model:* {config.get('emoji', '🎬')} {config.get('name', model_id)}\n"
            f"{speech_info}\n\n"
            "🎨 *Görsel stil kategorisi seç:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== CONVERSATIONAL REELS - OTOMATİK KONU (backward compat) =====
    elif action == "conv_auto":
        # Default stil ile başlat (geriye uyumluluk)
        await query.edit_message_text(
            "🎭 *CONVERSATIONAL REELS* başlatılıyor...\n\n"
            "🎨 Stil: 🎬 Sinematik 4K (default)\n\n"
            "Pipeline aşamaları:\n"
            "1️⃣ Konu seçimi (AI)\n"
            "2️⃣ Dialog içeriği\n"
            "3️⃣ Multi-voice TTS\n"
            "4️⃣ Avatar video\n"
            "5️⃣ Lip-sync\n"
            "6️⃣ B-roll video\n"
            "7️⃣ Video birleştirme\n"
            "8️⃣ Instagram yayını\n\n"
            "⏳ Bu işlem 8-12 dakika sürebilir...",
            parse_mode="Markdown"
        )
        asyncio.create_task(pipeline.run_conversational_reels(visual_style="cinematic_4k"))

    # ===== CONVERSATIONAL REELS - MANUEL KONU (backward compat) =====
    elif action == "conv_manual":
        pending_input["type"] = "conv_topic"
        pending_input["visual_style"] = "cinematic_4k"  # Default stil
        pending_input["user_id"] = query.from_user.id
        await query.edit_message_text(
            "✏️ *MANUEL KONU GİRİŞİ*\n\n"
            "🎨 Stil: 🎬 Sinematik 4K (default)\n\n"
            "Conversational Reels için konu yazın:\n\n"
            "📌 *Örnekler:*\n"
            "• Serada nem kontrolü\n"
            "• Fabrikada enerji izleme\n"
            "• LoRaWAN ile uzaktan takip\n"
            "• Akıllı sulama otomasyonu\n\n"
            "💬 Konunuzu yazın:",
            parse_mode="Markdown"
        )

    # ===== CONVERSATIONAL REELS - ONAYLA =====
    elif action.startswith("conv_approve:"):
        post_id = action.replace("conv_approve:", "")
        # Video mesajları için caption düzenle, text mesajları için text düzenle
        if query.message.video:
            await query.edit_message_caption(
                caption=f"✅ *CONVERSATIONAL REELS* yayınlanıyor...\n\nPost ID: {post_id}",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"✅ *CONVERSATIONAL REELS* yayınlanıyor...\n\nPost ID: {post_id}",
                parse_mode="Markdown"
            )
        asyncio.create_task(pipeline.publish_conversational_reels(int(post_id)))

    # ===== CONVERSATIONAL REELS - YENİDEN ÜRET =====
    elif action.startswith("conv_regenerate:"):
        post_id = action.replace("conv_regenerate:", "")
        # Video mesajları için caption düzenle, text mesajları için text düzenle
        if query.message.video:
            await query.edit_message_caption(
                caption=f"🔄 *CONVERSATIONAL REELS* yeniden üretiliyor...\n\nPost ID: {post_id}",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"🔄 *CONVERSATIONAL REELS* yeniden üretiliyor...\n\nPost ID: {post_id}",
                parse_mode="Markdown"
            )
        asyncio.create_task(pipeline.run_conversational_reels())

    # ===== CONVERSATIONAL REELS - İPTAL =====
    elif action.startswith("conv_cancel:"):
        post_id = action.replace("conv_cancel:", "")
        # Video mesajları için caption düzenle, text mesajları için text düzenle
        if query.message.video:
            await query.edit_message_caption(
                caption=f"❌ *CONVERSATIONAL REELS* iptal edildi.\n\nPost ID: {post_id}",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"❌ *CONVERSATIONAL REELS* iptal edildi.\n\nPost ID: {post_id}",
                parse_mode="Markdown"
            )

    # ===== REELS OLUŞTUR - MODEL SEÇİM MENÜSÜ =====
    elif action == "create_reels":
        # Video model seçim menüsü göster
        video_model_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎥 Sora 2", callback_data="video_model:sora2"),
                InlineKeyboardButton("🔮 Kling 3.0 Pro", callback_data="video_model:kling_v3_pro"),
            ],
            [
                InlineKeyboardButton("🎙️ Sesli Reels (TTS)", callback_data="voice_reels_menu"),
            ],
            [
                InlineKeyboardButton("❌ İptal", callback_data="main_menu"),
            ]
        ])
        await query.edit_message_text(
            "🎬 *Video Modeli Seçin*\n\n"
            "• *Sora 2*: OpenAI, 12s, sinematik kalite\n"
            "• *Kling 3.0 Pro*: Kling API, 15s, 🔮 sinematik yönetmenlik\n\n"
            "🎙️ *Sesli Reels*: Türkçe voiceover + video\n\n"
            "💡 Tüm modeller 9:16 dikey format kullanır.",
            parse_mode="Markdown",
            reply_markup=video_model_keyboard
        )

    # ===== VIDEO MODEL SEÇİMİ - STİL KATEGORİSİ MENÜSÜ =====
    elif action.startswith("video_model:"):
        model = action.replace("video_model:", "")

        model_names = {
            "sora2": "Sora 2 (OpenAI)",
            "kling_v3_pro": "Kling 3.0 Pro",
        }
        model_name = model_names.get(model, model)

        # Stil kategorisi seçim menüsü göster
        keyboard = []
        for cat_id, cat_info in STYLE_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(
                cat_info["name"],
                callback_data=f"style_cat:{model}:{cat_id}:silent"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data="create_reels")])

        await query.edit_message_text(
            f"🎬 *Sessiz Reels - {model_name}*\n\n"
            "🎨 *Görsel stil kategorisi seç:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== STİL KATEGORİSİ SEÇİLDİ - STİL MENÜSÜ =====
    elif action.startswith("style_cat:"):
        parts = action.replace("style_cat:", "").split(":")
        model = parts[0]
        category = parts[1]
        video_type = parts[2]  # silent, voice, long, conv

        cat_info = STYLE_CATEGORIES.get(category, {})
        cat_name = cat_info.get("name", category)

        keyboard = []
        for style_id in get_styles_by_category(category):
            config = VIDEO_STYLES[style_id]
            keyboard.append([InlineKeyboardButton(
                f"{config['emoji']} {config['name']}",
                callback_data=f"style_sel:{model}:{style_id}:{video_type}"
            )])

        # Geri butonu - video tipine göre
        if video_type == "silent":
            back_data = f"video_model:{model}"
        elif video_type == "voice":
            back_data = f"voice_model:{model}"
        elif video_type == "long":
            back_data = f"long_model:{model}"
        elif video_type == "conv":
            back_data = f"conv_model:{model}"
        else:
            back_data = "create_conversational"

        keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data=back_data)])

        await query.edit_message_text(
            f"🎨 *{cat_name}* stilleri:\n\n"
            "Bir stil seç:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== STİL SEÇİLDİ - SONRAKİ ADIM =====
    elif action.startswith("style_sel:"):
        parts = action.replace("style_sel:", "").split(":")
        model = parts[0]
        style_id = parts[1]
        video_type = parts[2]

        style_config = get_style_config(style_id)
        style_name = f"{style_config['emoji']} {style_config['name']}"

        if video_type == "silent":
            # Sessiz reels: Konu seçim menüsü
            model_names = {
                "sora2": "Sora 2",
                "kling_v3_pro": "Kling 3.0 Pro",
            }
            model_name = model_names.get(model, model)

            keyboard = [
                [InlineKeyboardButton("🤖 Otomatik Konu", callback_data=f"reels_auto:{model}:{style_id}"),
                 InlineKeyboardButton("✏️ Manuel Konu", callback_data=f"reels_manual:{model}:{style_id}")],
                [InlineKeyboardButton("◀️ Geri", callback_data=f"video_model:{model}")]
            ]
            await query.edit_message_text(
                f"🎬 *Sessiz Reels*\n\n"
                f"📹 Model: {model_name}\n"
                f"🎨 Stil: {style_name}\n\n"
                "📝 Konu seçimi:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif video_type == "voice":
            # Sesli reels: Süre seçim menüsü
            config = get_model_config(model)
            durations = get_model_durations(model)

            keyboard = []
            for duration in durations:
                is_default = duration == config.get("default_duration")
                emoji = "⭐" if is_default else "⏱️"
                suffix = " (önerilen)" if is_default else ""
                button_text = f"{emoji} {duration} saniye{suffix}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"voice_duration:{model}:{style_id}:{duration}")])

            keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data=f"voice_model:{model}")])

            await query.edit_message_text(
                f"🎙️ *Sesli Reels*\n\n"
                f"📹 Model: {config.get('name', model)}\n"
                f"🎨 Stil: {style_name}\n\n"
                "⏱️ Video süresini seç:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif video_type == "long":
            # Uzun video: model parametresinde segment_seg_model formatı var
            long_parts = model.split("_seg_")
            if len(long_parts) == 2:
                segment_count = int(long_parts[0])
                model_id = long_parts[1]
            else:
                segment_count = 2
                model_id = model

            config = get_model_config(model_id)
            max_duration = get_max_duration(model_id)
            total_duration = segment_count * max_duration

            keyboard = [
                [InlineKeyboardButton("🎲 Otomatik Konu", callback_data=f"long_topic:{segment_count}:{model_id}:{style_id}:auto")],
                [InlineKeyboardButton("✏️ Manuel Konu", callback_data=f"long_topic:{segment_count}:{model_id}:{style_id}:manual")],
                [InlineKeyboardButton("◀️ Geri", callback_data=f"long_model:{segment_count}:{model_id}")]
            ]
            await query.edit_message_text(
                f"🎥 *Uzun Video*\n\n"
                f"🎬 Segment: {segment_count}x{max_duration}s = {total_duration}s\n"
                f"📹 Model: {config.get('name', model_id)}\n"
                f"🎨 Stil: {style_name}\n\n"
                "📝 Konu seçimi:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif video_type == "conv":
            # Conversational: Konu girişi bekle
            pending_input["type"] = "conv_topic"
            pending_input["visual_style"] = style_id
            pending_input["model_id"] = model  # Model bilgisi
            pending_input["user_id"] = query.from_user.id
            pending_input["username"] = query.from_user.username or query.from_user.first_name

            model_config = get_model_config(model)
            model_name = f"{model_config.get('emoji', '🎬')} {model_config.get('name', model)}"
            native_speech_models = ["sora-2", "sora-2-pro"]
            speech_mode = "Native Turkish speech" if model in native_speech_models else "TTS + Lipsync API"

            keyboard = [[InlineKeyboardButton("❌ İptal", callback_data=f"conv_model:{model}")]]
            await query.edit_message_text(
                f"🎭 *Conversational Reels*\n\n"
                f"📹 Model: {model_name}\n"
                f"🎨 Stil: {style_name}\n"
                f"🗣️ Konuşma: {speech_mode}\n\n"
                "✏️ Şimdi video konusunu yaz:\n"
                "_Örnek: Serada sıcaklık takibi nasıl yapılır?_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    # ===== REELS - OTOMATİK KONU =====
    elif action.startswith("reels_auto:"):
        parts = action.replace("reels_auto:", "").split(":")
        model = parts[0]
        style_id = parts[1] if len(parts) > 1 else "cinematic_4k"

        model_names = {
            "sora2": "Sora 2 (OpenAI)",
            "kling_v3_pro": "Kling 3.0 Pro",
        }
        model_name = model_names.get(model, model)
        style_config = get_style_config(style_id)
        style_name = f"{style_config['emoji']} {style_config['name']}"

        await query.edit_message_text(
            f"🎬 *REELS MOD* başlatılıyor...\n\n"
            f"🎯 *Model:* {model_name}\n"
            f"🎨 *Stil:* {style_name}\n\n"
            "Video içeriği oluşturulacak:\n"
            "• Konu seçimi (AI)\n"
            "• Caption üretimi (IG+FB)\n"
            "• Video prompt\n"
            f"• Video üretimi ({model_name})\n"
            "• Instagram Reels + Facebook Video\n\n"
            "⏳ Bu işlem 5-10 dakika sürebilir...",
            parse_mode="Markdown"
        )
        asyncio.create_task(pipeline.run_reels_content(force_model=model, visual_style=style_id))

    # ===== REELS - MANUEL KONU =====
    elif action.startswith("reels_manual:"):
        parts = action.replace("reels_manual:", "").split(":")
        model = parts[0]
        style_id = parts[1] if len(parts) > 1 else "cinematic_4k"

        model_names = {
            "sora2": "Sora 2 (OpenAI)",
            "kling_v3_pro": "Kling 3.0 Pro",
        }
        model_name = model_names.get(model, model)
        style_config = get_style_config(style_id)
        style_name = f"{style_config['emoji']} {style_config['name']}"

        pending_input["type"] = "reels_manual_topic"
        pending_input["model"] = model
        pending_input["visual_style"] = style_id
        pending_input["user_id"] = query.from_user.id
        await query.edit_message_text(
            f"✏️ *Manuel Konu Girişi*\n\n"
            f"🎬 Model: {model_name}\n"
            f"🎨 Stil: {style_name}\n\n"
            "Reels için konu yazın:\n\n"
            "Örnek:\n"
            "• `YOLOv8 ile kalite kontrol`\n"
            "• `LoRaWAN gateway kurulumu`",
            parse_mode="Markdown"
        )

    # ===== SESLİ REELS MENÜSÜ - MODEL SEÇİMİ =====
    elif action == "voice_reels_menu":
        # Model seçim menüsü
        keyboard = []
        for model_id, config in VIDEO_MODELS.items():
            emoji = config["emoji"]
            name = config["name"]
            max_dur = config["max_duration"]
            desc = config["description"]
            button_text = f"{emoji} {name} (max {max_dur}s)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"voice_model:{model_id}")])

        keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="create_reels")])

        await query.edit_message_text(
            "🎬 *SESLİ REELS* - Model Seç\n\n"
            "Hangi AI modeli ile video oluşturmak istersin?\n\n"
            "🌟 *Sora 2* - Sinematik kalite (max 12s)\n"
            "⭐ *Sora 2 Pro* - Premium, native speech (max 12s)\n"
            "🔮 *Kling 3.0 Pro* - Sinematik yönetmenlik (max 15s)\n\n"
            "🔊 Tüm modellerde Türkçe AI voiceover eklenir.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SESLİ REELS - MODEL SEÇİLDİ → STİL KATEGORİSİ =====
    elif action.startswith("voice_model:"):
        model_id = action.replace("voice_model:", "")
        config = get_model_config(model_id)

        # Stil kategorisi seçim menüsü göster
        keyboard = []
        for cat_id, cat_info in STYLE_CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(
                cat_info["name"],
                callback_data=f"style_cat:{model_id}:{cat_id}:voice"
            )])
        keyboard.append([InlineKeyboardButton("⬅️ Geri", callback_data="voice_reels_menu")])

        await query.edit_message_text(
            f"🎙️ *Sesli Reels - {config['emoji']} {config['name']}*\n\n"
            "🎨 *Görsel stil kategorisi seç:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SESLİ REELS - SÜRE SEÇİLDİ → KONU MENÜSÜ =====
    elif action.startswith("voice_duration:"):
        parts = action.split(":")
        model_id = parts[1]
        # Yeni format: voice_duration:{model_id}:{style_id}:{duration}
        # Eski format: voice_duration:{model_id}:{duration} (backward compat)
        if len(parts) >= 4:
            style_id = parts[2]
            duration = int(parts[3])
        else:
            style_id = "cinematic_4k"
            duration = int(parts[2])

        config = get_model_config(model_id)
        style_config = get_style_config(style_id)
        style_name = f"{style_config['emoji']} {style_config['name']}"

        keyboard = [
            [InlineKeyboardButton("🎲 Otomatik Konu", callback_data=f"voice_topic:{model_id}:{style_id}:{duration}:auto")],
            [InlineKeyboardButton("✏️ Manuel Konu", callback_data=f"voice_topic:{model_id}:{style_id}:{duration}:manual")],
            [InlineKeyboardButton("⬅️ Geri", callback_data=f"voice_model:{model_id}")]
        ]

        await query.edit_message_text(
            f"📝 *Konu Seç*\n\n"
            f"🎬 Model: {config['emoji']} {config['name']}\n"
            f"🎨 Stil: {style_name}\n"
            f"⏱️ Süre: {duration} saniye\n\n"
            "Konu nasıl belirlensin?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SESLİ REELS - KONU SEÇİLDİ =====
    elif action.startswith("voice_topic:") and ":" in action[12:]:
        # Yeni format: voice_topic:{model_id}:{style_id}:{duration}:{auto|manual}
        # Eski format: voice_topic:{model}:{duration}:{auto|manual}
        parts = action.split(":")
        model_id = parts[1]

        # Format kontrolü
        if len(parts) >= 5:
            # Yeni format
            style_id = parts[2]
            duration = int(parts[3])
            topic_mode = parts[4]
        else:
            # Eski format (backward compat)
            style_id = "cinematic_4k"
            duration = int(parts[2])
            topic_mode = parts[3]

        config = get_model_config(model_id)
        style_config = get_style_config(style_id)
        style_name = f"{style_config['emoji']} {style_config['name']}"

        if topic_mode == "auto":
            # Otomatik konu ile pipeline başlat
            await query.edit_message_text(
                f"🎙️ *SESLİ REELS* başlatılıyor...\n\n"
                f"🎬 *Model:* {config['emoji']} {config['name']}\n"
                f"🎨 *Stil:* {style_name}\n"
                f"⏱️ *Süre:* {duration} saniye\n"
                f"🔊 *Ses:* Türkçe AI voiceover\n\n"
                "Pipeline aşamaları:\n"
                "1️⃣ Konu seçimi (AI)\n"
                "2️⃣ Caption üretimi\n"
                "3️⃣ Voiceover scripti\n"
                "4️⃣ TTS ses üretimi\n"
                "5️⃣ Video prompt\n"
                f"6️⃣ Video üretimi ({config['name']})\n"
                "7️⃣ Audio-video birleştirme\n"
                "8️⃣ Instagram Reels yayını\n\n"
                "⏳ Bu işlem 5-10 dakika sürebilir...",
                parse_mode="Markdown"
            )
            # Pipeline başlat
            asyncio.create_task(pipeline.run_reels_voice_content(
                target_duration=duration,
                model_id=model_id,
                visual_style=style_id
            ))
        else:
            # Manuel konu girişi bekle
            pending_input["type"] = "voice_topic_manual"
            pending_input["model_id"] = model_id
            pending_input["duration"] = duration
            pending_input["visual_style"] = style_id
            pending_input["user_id"] = query.from_user.id
            pending_input["username"] = query.from_user.username or query.from_user.first_name

            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ İptal", callback_data="voice_reels_menu")]
            ])

            await query.edit_message_text(
                f"✏️ *MANUEL KONU GİRİŞİ*\n\n"
                f"🎬 Model: {config['emoji']} {config['name']}\n"
                f"🎨 Stil: {style_name}\n"
                f"⏱️ Süre: {duration}s\n\n"
                "Sesli Reels için konu veya anahtar kelimeler yaz:\n\n"
                "💡 *Örnekler:*\n"
                "• Sera sulama otomasyonu\n"
                "• Akıllı tarım solenoid vana kontrolü\n"
                "• Fabrikada enerji izleme sistemi\n\n"
                "📝 Konunuzu yazın (en az 5 karakter):",
                parse_mode="Markdown",
                reply_markup=cancel_keyboard
            )

    # ===== ESKİ CALLBACK'LER - BACKWARD COMPATIBILITY =====
    # Eski: voice_topic:auto (model bilgisi yok, Sora 2 default)
    elif action == "voice_topic:auto":
        # Eski format - Sora 2 ile süre seçimi
        voice_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎙️ 8s Kısa", callback_data="voice_reels:8"),
                InlineKeyboardButton("🎙️ 12s Standart ⭐", callback_data="voice_reels:12"),
            ],
            [
                InlineKeyboardButton("⬅️ Geri", callback_data="voice_reels_menu"),
            ]
        ])

        await query.edit_message_text(
            "🎙️ *SESLİ REELS* - Süre Seçin\n\n"
            "• *8 saniye*: Kısa hook + tek mesaj\n"
            "• *12 saniye*: Standart (önerilen) ⭐\n\n"
            "🎯 Konu: AI tarafından seçilecek\n"
            "💡 Script otomatik oluşturulur.\n"
            "🎥 Video: Sora 2",
            parse_mode="Markdown",
            reply_markup=voice_keyboard
        )

    # Eski: voice_topic:manual (model bilgisi yok, Sora 2 default)
    elif action == "voice_topic:manual":
        pending_input["type"] = "voice_topic_manual"
        pending_input["model_id"] = "sora-2"  # Default model
        pending_input["duration"] = None  # Sonra seçilecek
        pending_input["user_id"] = query.from_user.id
        pending_input["username"] = query.from_user.username or query.from_user.first_name

        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ İptal", callback_data="voice_reels_menu")]
        ])

        await query.edit_message_text(
            "✏️ *MANUEL KONU GİRİŞİ*\n\n"
            "Sesli Reels için konu yazın:\n\n"
            "💡 *Örnekler:*\n"
            "• Sera sulama otomasyonu\n"
            "• Akıllı tarım solenoid vana kontrolü\n"
            "• Fabrikada enerji izleme sistemi\n"
            "• LoRaWAN ile uzaktan sensör takibi\n\n"
            "📝 Konunuzu yazın (en az 5 karakter):",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard
        )

    # ===== SESLİ REELS BAŞLAT =====
    elif action.startswith("voice_reels:"):
        duration = int(action.replace("voice_reels:", ""))

        await query.edit_message_text(
            f"🎙️ *SESLİ REELS* başlatılıyor...\n\n"
            f"⏱️ *Süre:* {duration} saniye\n"
            f"🔊 *Ses:* Türkçe AI voiceover\n"
            f"🎥 *Video:* Sora 2 (sinematik)\n\n"
            "Pipeline aşamaları:\n"
            "1️⃣ Konu seçimi (AI)\n"
            "2️⃣ Caption üretimi\n"
            "3️⃣ Voiceover scripti\n"
            "4️⃣ TTS ses üretimi\n"
            "5️⃣ Video prompt\n"
            "6️⃣ Video üretimi (Sora 2)\n"
            "7️⃣ Audio-video birleştirme\n"
            "8️⃣ Instagram Reels yayını\n\n"
            "⏳ Bu işlem 5-10 dakika sürebilir...",
            parse_mode="Markdown"
        )

        # Sesli reels pipeline'ı arka planda çalıştır (otomatik konu, Sora 2 default)
        asyncio.create_task(pipeline.run_reels_voice_content(
            target_duration=duration,
            model_id="sora-2"  # Backward compatibility
        ))

    # ===== SESLİ REELS - MANUEL KONU İLE BAŞLAT =====
    elif action.startswith("voice_reels_manual:"):
        duration = int(action.replace("voice_reels_manual:", ""))

        # Saklanan manuel konuyu al
        topic = pending_input.get("manual_topic", "")
        pending_input.clear()  # State'i temizle

        if not topic:
            await query.edit_message_text(
                "⚠️ Konu bulunamadı. Lütfen tekrar deneyin.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar Dene", callback_data="voice_reels_menu")]
                ])
            )
            return

        await query.edit_message_text(
            f"🎙️ *SESLİ REELS* başlatılıyor...\n\n"
            f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n"
            f"⏱️ *Süre:* {duration} saniye\n"
            f"🔊 *Ses:* Türkçe AI voiceover\n"
            f"🎥 *Video:* Sora 2 (sinematik)\n\n"
            "Pipeline aşamaları:\n"
            "1️⃣ Konu işleme (AI)\n"
            "2️⃣ Caption üretimi\n"
            "3️⃣ Voiceover scripti\n"
            "4️⃣ TTS ses üretimi\n"
            "5️⃣ Video prompt\n"
            "6️⃣ Video üretimi (Sora 2)\n"
            "7️⃣ Audio-video birleştirme\n"
            "8️⃣ Instagram Reels yayını\n\n"
            "⏳ Bu işlem 5-10 dakika sürebilir...",
            parse_mode="Markdown"
        )

        # Manuel konu ile sesli reels pipeline'ı başlat (Sora 2 default)
        asyncio.create_task(pipeline.run_reels_voice_content(
            topic=topic,
            target_duration=duration,
            model_id="sora-2",  # Backward compatibility
            manual_topic_mode=True
        ))

    # ===== UZUN VIDEO (MULTI-SEGMENT) =====
    elif action == "create_long_video":
        keyboard = [
            [
                InlineKeyboardButton("2️⃣ 2 Segment", callback_data="long_segments:2"),
                InlineKeyboardButton("3️⃣ 3 Segment", callback_data="long_segments:3")
            ],
            [InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            "🎥 *UZUN VIDEO*\n\n"
            "Multi-segment video pipeline.\n"
            "Segmentler paralel üretilip birleştirilir.\n\n"
            "📊 *Segment süreleri modele göre değişir:*\n"
            "• Sora 2/Pro: 12s/segment\n"
            "• Kling 3.0 Pro: 15s/segment (sinematik)\n\n"
            "🎬 *Segment sayısı seçin:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action.startswith("long_segments:"):
        segment_count = int(action.split(":")[1])
        # Model butonlarında süre bilgisi göster
        keyboard = [
            [
                InlineKeyboardButton(f"⭐ Sora 2 Pro ({segment_count}x12s={segment_count*12}s)", callback_data=f"long_model:{segment_count}:sora-2-pro"),
                InlineKeyboardButton(f"🌟 Sora 2 ({segment_count}x12s={segment_count*12}s)", callback_data=f"long_model:{segment_count}:sora-2")
            ],
            [
                InlineKeyboardButton(f"🔮 Kling 3.0 Pro ({segment_count}x15s={segment_count*15}s)", callback_data=f"long_model:{segment_count}:kling-3.0-pro"),
            ],
            [InlineKeyboardButton("◀️ Geri", callback_data="create_long_video")]
        ]
        await query.edit_message_text(
            f"🎥 *UZUN VIDEO* - {segment_count} Segment\n\n"
            "🎬 *Model seçin:*\n\n"
            "• *⭐ Sora 2 Pro:* Premium kalite (~$0.60/segment) ⭐\n"
            "• *Sora 2:* Yüksek kalite (~$0.50/segment)\n"
            "• *Kling 3.0 Pro:* Sinematik yönetmenlik (~$0.35/segment)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action.startswith("long_model:"):
        parts = action.split(":")
        segment_count = int(parts[1])
        model_id = parts[2]
        model_config = get_model_config(model_id)
        model_name = model_config.get("name", model_id)
        max_duration = get_max_duration(model_id)
        total_duration = segment_count * max_duration

        # Stil kategorisi seçim menüsü göster
        keyboard = []
        for cat_id, cat_info in STYLE_CATEGORIES.items():
            # Model parametresinde segment_seg_model formatı kullan
            keyboard.append([InlineKeyboardButton(
                cat_info["name"],
                callback_data=f"style_cat:{segment_count}_seg_{model_id}:{cat_id}:long"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data=f"long_segments:{segment_count}")])

        await query.edit_message_text(
            f"🎥 *Uzun Video*\n\n"
            f"🎬 Segment: {segment_count}x{max_duration}s = {total_duration}s\n"
            f"📹 Model: {model_name}\n\n"
            "🎨 *Görsel stil kategorisi seç:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action.startswith("long_topic:"):
        parts = action.split(":")
        segment_count = int(parts[1])
        model_id = parts[2]

        # Format kontrolü
        if len(parts) >= 5:
            # Yeni format: long_topic:{segment_count}:{model_id}:{style_id}:{auto|manual}
            style_id = parts[3]
            topic_mode = parts[4]
        else:
            # Eski format: long_topic:{segment_count}:{model_id}:{auto|manual}
            style_id = "cinematic_4k"
            topic_mode = parts[3]

        max_duration = get_max_duration(model_id)
        total_duration = segment_count * max_duration
        style_config = get_style_config(style_id)
        style_name = f"{style_config['emoji']} {style_config['name']}"

        if topic_mode == "auto":
            await query.edit_message_text(
                f"🎥 *UZUN VIDEO* başlatılıyor...\n\n"
                f"🎬 *Segment:* {segment_count}x{max_duration}s = {total_duration}s\n"
                f"📹 *Model:* {model_id}\n"
                f"🎨 *Stil:* {style_name}\n"
                f"📝 *Konu:* Otomatik\n\n"
                "Pipeline aşamaları:\n"
                "1️⃣ Konu seçimi\n"
                "2️⃣ Caption üretimi\n"
                "3️⃣ Voiceover scripti\n"
                "4️⃣ TTS ses üretimi\n"
                "5️⃣ Multi-scene prompt üretimi\n"
                f"6️⃣ Paralel video üretimi ({segment_count}x)\n"
                "7️⃣ Video birleştirme (crossfade)\n"
                "8️⃣ Audio-video merge\n"
                "9️⃣ Instagram Reels yayını\n\n"
                "⏳ Bu işlem 4-5 dakika sürebilir...",
                parse_mode="Markdown"
            )
            asyncio.create_task(pipeline.run_long_video_pipeline(
                segment_count=segment_count,
                model_id=model_id,
                visual_style=style_id
            ))
        else:
            pending_input["type"] = "long_video_manual"
            pending_input["segment_count"] = segment_count
            pending_input["model_id"] = model_id
            pending_input["visual_style"] = style_id
            pending_input["user_id"] = query.from_user.id

            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ İptal", callback_data="create_long_video")]
            ])

            style_text = f"🎨 Stil: {style_name}\n"
            await query.edit_message_text(
                f"✏️ *MANUEL KONU GİRİŞİ*\n\n"
                f"{style_text}\n"
                "Uzun video için konu yazın:\n\n"
                "💡 *Örnekler:*\n"
                "• Kestirimci bakım ile makine arızalarını önleyin\n"
                "• IoT sensörlerle sera otomasyonu\n"
                "• Akıllı fabrika enerji yönetimi\n\n"
                "📝 Konunuzu yazın (en az 5 karakter):",
                parse_mode="Markdown",
                reply_markup=cancel_keyboard
            )

    # ===== HAFTALIK PLAN =====
    elif action == "weekly_plan":
        # Mevcut haftalık planı kontrol et
        from datetime import datetime, timedelta
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())

        existing_calendar = get_week_calendar(week_start.date())

        if existing_calendar:
            # Mevcut planı göster
            day_names = ['Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt', 'Paz']
            plan_text = "📋 *Bu Haftanın İçerik Planı*\n"
            plan_text += f"_{week_start.strftime('%d/%m')} - {(week_start + timedelta(days=6)).strftime('%d/%m/%Y')}_\n"
            plan_text += "━━━━━━━━━━━━━━━━━━━\n\n"

            for entry in existing_calendar:
                day_idx = entry.get('day_of_week', 0)
                day = day_names[day_idx] if day_idx < len(day_names) else 'N/A'
                time = entry.get('scheduled_time', '') or ''
                topic = (entry.get('topic_suggestion') or 'Konu belirlenmedi')[:40]
                vtype = (entry.get('visual_type_suggestion') or 'post').lower()

                type_icons = {"reels": "🎬", "carousel": "🎠", "post": "📝", "flux": "📝"}
                icon = type_icons.get(vtype, '📌')

                plan_text += f"• *{day}* {time} {icon}\n  _{topic}_\n"

                # Engagement bilgileri (varsa)
                viral_format = entry.get('viral_format')
                hook_type = entry.get('hook_type')
                if viral_format or hook_type:
                    engagement_info = []
                    if viral_format:
                        engagement_info.append(f"🎯{viral_format}")
                    if hook_type:
                        engagement_info.append(f"🪝{hook_type}")
                    plan_text += f"  `{' '.join(engagement_info)}`\n"

            keyboard = [
                [InlineKeyboardButton("🔄 Yeni Plan Oluştur", callback_data="create_new_plan")],
                [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
            ]
            await query.edit_message_text(
                plan_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Yeni plan oluştur
            await query.edit_message_text("📅 *Haftalık plan oluşturuluyor...*", parse_mode="Markdown")

            from app.agents import OrchestratorAgent
            orchestrator = OrchestratorAgent()
            result = await orchestrator.execute({"action": "plan_week"})

            if "error" not in result:
                plan_text = "📋 *Yeni İçerik Planı Oluşturuldu*\n━━━━━━━━━━━━━━━━━━━\n\n"
                for item in result.get("week_plan", [])[:12]:
                    plan_text += f"• *{item.get('day', 'N/A').title()}* {item.get('time', '')}: {item.get('topic', 'N/A')[:30]}\n"

                keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
                await query.edit_message_text(
                    plan_text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(f"❌ Hata: {result.get('error')}")

    # ===== YENİ PLAN OLUŞTUR =====
    elif action == "create_new_plan":
        await query.edit_message_text("📅 *Yeni haftalık plan oluşturuluyor...*", parse_mode="Markdown")

        from app.agents import OrchestratorAgent
        orchestrator = OrchestratorAgent()
        result = await orchestrator.execute({"action": "plan_week"})

        if "error" not in result:
            plan_text = "📋 *Yeni İçerik Planı*\n━━━━━━━━━━━━━━━━━━━\n\n"
            for item in result.get("week_plan", [])[:12]:
                plan_text += f"• *{item.get('day', 'N/A').title()}* {item.get('time', '')}: {item.get('topic', 'N/A')[:30]}\n"

            keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
            await query.edit_message_text(
                plan_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(f"❌ Hata: {result.get('error')}")

    # ===== STRATEJİ GÖSTER =====
    elif action == "show_strategy":
        # Config hedefleri
        text = "⚙️ *İÇERİK STRATEJİSİ*\n━━━━━━━━━━━━━━━━━━━\n\n"

        text += "📊 *Haftalık Hedefler:*\n"
        text += f"  🎬 Reels: {settings.reels_weekly_target}/hafta (58%)\n"
        text += f"  🎠 Carousel: {settings.carousel_weekly_target}/hafta (17%)\n"
        text += f"  📝 Post: {settings.post_weekly_target}/hafta (25%)\n"
        text += f"  📌 *Toplam:* 12 içerik/hafta\n\n"

        text += "⏰ *Paylaşım Saatleri:*\n"
        text += "  • Sabah: 10:00 (6x/hafta)\n"
        text += "  • Akşam: 19:00 (4x/hafta)\n"
        text += "  • Hafta sonu: 14:00 (2x/hafta)\n\n"

        text += "🎯 *Kalite Eşikleri:*\n"
        text += f"  • Onay: {settings.min_review_score}/10\n"
        text += f"  • Otonom: {settings.min_review_score_autonomous}/10\n"
        text += f"  • Revizyon: {settings.min_review_score_revise}/10\n\n"

        # Analytics'ten öğrenilen veriler
        strategy = get_current_strategy() or {}
        if strategy.get('avg_engagement_rate') or strategy.get('avg_reach'):
            text += "━━━━━━━━━━━━━━━━━━━\n"
            text += "📈 *Öğrenilen (30 gün):*\n"
            if strategy.get('avg_engagement_rate'):
                text += f"  • Ort. Engagement: {strategy.get('avg_engagement_rate', 0):.2f}%\n"
            if strategy.get('avg_reach'):
                text += f"  • Ort. Reach: {strategy.get('avg_reach', 0):.0f}\n"
            if strategy.get('best_days'):
                best_days = strategy.get('best_days', [])[:3]
                if best_days:
                    text += f"  • En iyi günler: {', '.join(best_days)}\n"
            if strategy.get('best_hours'):
                best_hours = strategy.get('best_hours', [])[:3]
                if best_hours:
                    text += f"  • En iyi saatler: {', '.join(best_hours)}\n"

        keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== ANALYTICS RAPORU =====
    elif action == "analytics_report":
        summary = get_analytics_summary(days=7) or {}
        published = get_published_posts(days=7) or []

        text = "📈 *SON 7 GÜN PERFORMANSI*\n━━━━━━━━━━━━━━━━━━━\n\n"

        if published:
            text += f"📊 Yayınlanan Post: {len(published)}\n\n"

            # Metrikler varsa göster
            has_metrics = (summary.get('total_views') or 0) > 0 or (summary.get('total_likes') or 0) > 0
            if has_metrics:
                text += "*Platform Metrikleri:*\n"
                text += f"  👁️ Görüntüleme: {(summary.get('total_views') or 0):,}\n"
                text += f"  👍 Beğeni: {(summary.get('total_likes') or 0):,}\n"
                text += f"  💬 Yorum: {(summary.get('total_comments') or 0):,}\n"
                text += f"  🔄 Paylaşım: {(summary.get('total_shares') or 0):,}\n\n"
                text += f"📈 Ort. Engagement: {(summary.get('avg_engagement_rate') or 0):.2f}%\n"
                text += f"👥 Ort. Reach: {(summary.get('avg_reach') or 0):,.0f}\n"
            else:
                text += "⚠️ *Metrikler henüz senkronize edilmedi.*\n"
                text += "Insights'ları güncellemek için 🔄 butonuna basın.\n"

            # En iyi performans
            best = get_best_performing_content(days=7)
            if best:
                text += "\n━━━━━━━━━━━━━━━━━━━\n"
                text += "🔥 *En İyi Performans:*\n"
                topic = (best.get('topic') or 'N/A')[:35]
                text += f"  \"{topic}...\"\n"
                if best.get('ig_reach'):
                    text += f"  → {best.get('ig_reach', 0):,} reach"
                    if best.get('ig_engagement_rate'):
                        text += f", {best.get('ig_engagement_rate', 0):.1f}% eng."
                    text += "\n"
        else:
            text += "📭 Henüz yayınlanmış içerik yok.\n\n"
            text += "İçerik oluşturmak için ana menüden başlayın."

        keyboard = [
            [InlineKeyboardButton("🔄 Metrics Sync", callback_data="sync_metrics")],
            [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== SCHEDULER DURUMU =====
    elif action == "scheduler_status":
        status = scheduler.get_status() if scheduler else {"running": False, "tasks": []}

        text = "⏰ Scheduler Durumu\n\n"
        text += f"Durum: {'🟢 Çalışıyor' if status.get('running') else '🔴 Durdu'}\n\n"
        text += "Görevler:\n"

        for task in status.get("tasks", []):
            text += f"• {task.get('name', 'N/A')}: "
            if task.get('hour') is not None:
                text += f"{task['hour']:02d}:{task.get('minute', 0):02d}"
            text += f" ({'Aktif' if task.get('enabled') else 'Pasif'})\n"

        keyboard = [
            [InlineKeyboardButton("▶️ Başlat" if not status.get('running') else "⏹️ Durdur",
                                  callback_data="toggle_scheduler")],
            [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== HAFTALIK PROGRAM =====
    elif action == "weekly_schedule":
        from app.agents.orchestrator import OrchestratorAgent
        schedule = OrchestratorAgent.WEEKLY_SCHEDULE

        day_names = {
            0: "Pazartesi", 1: "Salı", 2: "Çarşamba",
            3: "Perşembe", 4: "Cuma", 5: "Cumartesi", 6: "Pazar"
        }
        type_icons = {"reels": "🎬", "carousel": "🎠", "post": "📝"}

        text = "📆 *HAFTALIK PROGRAM*\n━━━━━━━━━━━━━━━━━━━\n\n"

        current_day = -1
        for item in schedule:
            if item['day'] != current_day:
                if current_day != -1:
                    text += "\n"
                current_day = item['day']
                text += f"*{day_names[current_day]}:*\n"

            icon = type_icons.get(item['type'], '📌')
            platform = f"({item['platform']})" if item['platform'] != 'instagram' else ""
            text += f"  {icon} {item['time']} - {item['type'].capitalize()} {platform}\n"

        text += "\n━━━━━━━━━━━━━━━━━━━\n"
        text += "*Toplam:* 12 içerik/hafta\n"
        text += "🎬 7 Reels (58%)\n"
        text += "🎠 2 Carousel (17%)\n"
        text += "📝 3 Post (25%)\n"

        keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== SIRADAKİ İÇERİK =====
    elif action == "next_content":
        from datetime import datetime
        next_post = get_next_scheduled()

        type_icons = {"reels": "🎬", "carousel": "🎠", "post": "📝", "flux": "📝"}

        if next_post:
            # DB'de hazır içerik var
            scheduled_str = next_post.get('scheduled_at')
            if scheduled_str:
                try:
                    scheduled_at = datetime.fromisoformat(str(scheduled_str).replace('Z', '+00:00'))
                    remaining = scheduled_at - datetime.now()
                    total_seconds = int(remaining.total_seconds())

                    if total_seconds > 0:
                        hours, remainder = divmod(total_seconds, 3600)
                        minutes = remainder // 60
                        time_left = f"{hours} saat {minutes} dakika"
                    else:
                        time_left = "Şimdi!"
                except:
                    time_left = "N/A"
                    scheduled_at = None
            else:
                time_left = "N/A"
                scheduled_at = None

            vtype = (next_post.get('visual_type') or 'post').lower()
            icon = type_icons.get(vtype, '📌')

            text = "⏭️ *SIRADAKİ İÇERİK*\n━━━━━━━━━━━━━━━━━━━\n\n"
            text += "✅ *Hazır içerik bekliyor*\n\n"
            text += f"📌 Tür: {icon} {vtype.capitalize()}\n"
            if scheduled_at:
                text += f"📅 Tarih: {scheduled_at.strftime('%d/%m/%Y')}\n"
                text += f"⏰ Saat: {scheduled_at.strftime('%H:%M')}\n"
            text += f"⏳ Kalan: {time_left}\n"

            if next_post.get('topic'):
                topic = next_post['topic'][:50]
                text += f"\n📋 *Konu:*\n\"{topic}...\"\n"

            keyboard = [
                [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
            ]
        else:
            # Scheduled post yok, slot bilgisini göster
            next_slot = get_next_schedule_slot()

            if next_slot:
                icon = type_icons.get(next_slot['type'], '📌')

                # Kalan süreyi formatla
                minutes = next_slot['minutes_until']
                if minutes < 60:
                    time_left = f"{minutes} dakika"
                elif minutes < 1440:  # 24 saat
                    hours = minutes // 60
                    mins = minutes % 60
                    time_left = f"{hours} saat {mins} dakika"
                else:
                    days = minutes // 1440
                    hours = (minutes % 1440) // 60
                    time_left = f"{days} gün {hours} saat"

                text = "⏭️ *SIRADAKİ SLOT*\n━━━━━━━━━━━━━━━━━━━\n\n"
                text += "⚠️ *İçerik henüz oluşturulmadı*\n\n"
                text += f"📅 Gün: {next_slot['day']}\n"
                text += f"⏰ Saat: {next_slot['time']}\n"
                text += f"📌 Tür: {icon} {next_slot['type'].capitalize()}\n"
                text += f"⏳ Kalan: {time_left}\n\n"
                text += "Bu slot için içerik oluşturmak\nister misiniz?"

                # İçerik tipine göre buton
                if next_slot['type'] == 'reels':
                    create_btn = InlineKeyboardButton("🎬 Reels Oluştur", callback_data="create_reels")
                elif next_slot['type'] == 'carousel':
                    create_btn = InlineKeyboardButton("🎠 Carousel Oluştur", callback_data="create_carousel")
                else:
                    create_btn = InlineKeyboardButton("📝 İçerik Oluştur", callback_data="start_daily")

                keyboard = [
                    [create_btn],
                    [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
                ]
            else:
                text = "⏭️ *SIRADAKİ İÇERİK*\n━━━━━━━━━━━━━━━━━━━\n\n"
                text += "📭 Zamanlama bulunamadı.\n"
                keyboard = [
                    [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
                ]

        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== HIZLI DURUM =====
    elif action == "quick_status":
        summary = get_todays_summary()
        weekly = get_weekly_progress()

        text = "📊 *BUGÜNÜN DURUMU*\n━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"✅ Yayınlanan: {summary.get('published', 0)}\n"
        text += f"⏳ Bekleyen: {summary.get('scheduled', 0)}\n"
        text += f"❌ Başarısız: {summary.get('failed', 0)}\n"
        text += f"📝 Taslak: {summary.get('draft', 0)}\n\n"

        text += "━━━━━━━━━━━━━━━━━━━\n"
        text += "📈 *BU HAFTA:*\n"
        text += f"Toplam: {weekly.get('total', 0)} içerik\n"
        text += f"🎬 Reels: {weekly.get('reels', 0)}\n"
        text += f"🎠 Carousel: {weekly.get('carousel', 0)}\n"
        text += f"📝 Post: {weekly.get('post', 0)}\n"

        # En iyi performans
        best = get_best_performing_content(days=7)
        if best:
            text += "\n━━━━━━━━━━━━━━━━━━━\n"
            text += "🔥 *En iyi performans:*\n"
            topic = (best.get('topic') or 'N/A')[:30]
            text += f"\"{topic}...\"\n"
            if best.get('ig_reach'):
                text += f"→ {best.get('ig_reach', 0):,} reach"
                if best.get('ig_engagement_rate'):
                    text += f", {best.get('ig_engagement_rate', 0):.1f}% eng."
                text += "\n"

        keyboard = [
            [InlineKeyboardButton("🔄 Yenile", callback_data="quick_status")],
            [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== METRICS SYNC =====
    elif action == "sync_metrics":
        await query.edit_message_text("🔄 *Metrikler senkronize ediliyor...*", parse_mode="Markdown")

        try:
            from app.insights_helper import sync_insights_to_database
            result = await sync_insights_to_database()

            if result.get('success'):
                text = "✅ *Senkronizasyon Tamamlandı*\n\n"
                text += f"📊 Güncellenen post: {result.get('synced', 0)}\n"
                text += f"❌ Hata: {result.get('errors', 0)}\n"
                text += f"📋 Toplam: {result.get('total', 0)}\n"
            else:
                text = f"❌ *Senkronizasyon Hatası*\n\n{result.get('error', 'Bilinmeyen hata')}"
        except ImportError:
            text = "⚠️ *Sync fonksiyonu bulunamadı*\n\ninsights_helper modülü yüklenmedi."
        except Exception as e:
            text = f"❌ *Hata:* {str(e)}"

        keyboard = [
            [InlineKeyboardButton("📈 Analytics", callback_data="analytics_report")],
            [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== YARDIM =====
    elif action == "help":
        text = "❓ *YARDIM*\n━━━━━━━━━━━━━━━━━━━\n\n"

        text += "*İçerik Oluşturma:*\n"
        text += "📝 Günlük İçerik - Onay bekler\n"
        text += "🎬 Reels - Video içerik\n"
        text += "🎠 Carousel - Kaydırmalı post\n"
        text += "🤖 Otonom - Tam otomatik (7+/10)\n\n"

        text += "*Planlama:*\n"
        text += "📋 İçerik Planı - Bu haftanın konuları\n"
        text += "📆 Zamanlama - Sabit program (gün/saat)\n"
        text += "⏭️ Sıradaki - Bekleyen içerik\n"
        text += "📊 Hızlı Durum - Özet bilgi\n\n"

        text += "*Analytics:*\n"
        text += "📈 Analytics - 7 günlük rapor\n"
        text += "🔄 Sync - Metrikleri güncelle\n"
        text += "⚙️ Strateji - Hedefler ve ayarlar\n\n"

        text += "*Komutlar:*\n"
        text += "/start - Ana menü\n"
        text += "/status - Sistem durumu\n"
        text += "/stats - Hızlı durum\n"
        text += "/next - Sıradaki içerik\n"
        text += "/schedule - Haftalık program\n"
        text += "/sync - Metrics sync\n"
        text += "/cc <soru> - Claude Code'a sor\n"

        keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== CAROUSEL OLUŞTUR - KONU SEÇİMİ =====
    elif action == "create_carousel":
        keyboard = [
            [InlineKeyboardButton("🤖 Otomatik Konu", callback_data="carousel_auto")],
            [InlineKeyboardButton("✏️ Manuel Konu", callback_data="carousel_manual")],
            [InlineKeyboardButton("« Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            "🎠 *CAROUSEL - Konu Seçimi*\n\n"
            "• *Otomatik*: AI optimal konu seçer\n"
            "• *Manuel*: Kendi konunuzu yazın",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== CAROUSEL - OTOMATİK KONU =====
    elif action == "carousel_auto":
        keyboard = [
            [InlineKeyboardButton("📝 HTML Template (~$0.01)", callback_data="carousel_type:html:auto")],
            [InlineKeyboardButton("📊 Nano Banana AI (~$0.75)", callback_data="carousel_type:nano_banana:auto")],
            [InlineKeyboardButton("« Geri", callback_data="create_carousel")]
        ]
        await query.edit_message_text(
            "🎠 *CAROUSEL - Görsel Tipi*\n\n"
            "• *HTML Template*: Hızlı, tutarlı tasarım\n"
            "• *Nano Banana*: AI infographic, oklu kutucuklar\n\n"
            "💡 Her iki yöntemde de 5 slide oluşturulur.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== CAROUSEL - MANUEL KONU =====
    elif action == "carousel_manual":
        pending_input["type"] = "carousel_manual_topic"
        pending_input["user_id"] = user_id
        await query.edit_message_text(
            "✏️ *Manuel Carousel Konusu*\n\n"
            "Carousel için konu yazın:\n\n"
            "Örnek:\n"
            "• `LoRaWAN Gateway türleri karşılaştırma`\n"
            "• `Sera otomasyonunda 5 kritik sensör`",
            parse_mode="Markdown"
        )

    # ===== CAROUSEL - TİP SEÇİMİ =====
    elif action.startswith("carousel_type:"):
        parts = action.split(":")
        carousel_type = parts[1]  # html veya nano_banana
        topic_mode = parts[2]  # auto veya manual
        manual_topic = pending_input.pop("carousel_topic", None) if topic_mode == "manual" else None

        type_names = {
            "html": "HTML Template",
            "nano_banana": "Nano Banana AI"
        }

        await query.edit_message_text(
            f"🎠 *CAROUSEL* başlatılıyor...\n\n"
            f"📊 *Görsel:* {type_names.get(carousel_type, carousel_type)}\n"
            f"📝 *Konu:* {'Manuel - ' + escape_markdown(manual_topic[:40]) + '...' if manual_topic else 'Otomatik'}\n\n"
            "Kaydırmalı içerik oluşturulacak:\n"
            "• Konu seçimi/onayı\n"
            "• Slide metinleri (5 slide)\n"
            "• Her slide için görsel\n"
            "• Instagram Carousel post\n\n"
            "⏳ Bu işlem 3-5 dakika sürebilir...",
            parse_mode="Markdown"
        )

        # Carousel pipeline'ı arka planda çalıştır
        asyncio.create_task(pipeline.run_carousel_pipeline(
            carousel_type=carousel_type,
            manual_topic=manual_topic
        ))

    # ===== PIPELINE ONAYLARI =====
    elif action == "approve_topic":
        pipeline.set_approval({"action": "approve"})

    elif action == "new_topic":
        pipeline.set_approval({"action": "new_topic"})

    elif action == "approve_content":
        pipeline.set_approval({"action": "approve"})

    elif action == "regenerate_content":
        await query.edit_message_text("✏️ *Geri bildiriminizi yazın:*", parse_mode="Markdown")
        pending_input["type"] = "content_feedback"

    elif action == "approve_visual":
        pipeline.set_approval({"action": "approve"})

    elif action == "regenerate_visual":
        pipeline.set_approval({"action": "regenerate"})

    elif action == "retry_visual":
        # Hata sonrası tekrar deneme - aynı regenerate mantığı
        pipeline.set_approval({"action": "regenerate"})

    elif action == "change_visual_type":
        # Görsel tipi seçim menüsü göster
        keyboard = [
            [InlineKeyboardButton("🧠 AI Infographic", callback_data="set_type_nano_banana")],
            [InlineKeyboardButton("🖼️ FLUX Görsel", callback_data="set_type_flux")],
            [InlineKeyboardButton("🎬 Video", callback_data="set_type_video")],
            [InlineKeyboardButton("📱 Carousel", callback_data="set_type_carousel")],
            [InlineKeyboardButton("❌ İptal", callback_data="cancel")]
        ]
        menu_text = (
            "🎨 *Görsel Tipi Seçin:*\n\n"
            "🧠 AI Infographic - Nano Banana (~$0.15)\n"
            "🖼️ FLUX - AI görsel üretimi (~$0.03)\n"
            "🎬 Video - AI video üretimi\n"
            "📱 Carousel - Çoklu slayt formatı"
        )
        # Fotoğraf/video mesajı ise caption düzenle, değilse text düzenle
        if query.message.photo or query.message.video:
            await query.edit_message_caption(
                caption=menu_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text(
                menu_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif action.startswith("set_type_"):
        # Görsel tipi seçildi
        new_type = action.replace("set_type_", "")
        type_names = {
            "infographic": "İnfografik",
            "nano_banana": "AI Infographic (Nano Banana)",
            "flux": "FLUX Görsel",
            "video": "Video",
            "carousel": "Carousel"
        }
        status_text = (
            f"🎨 Görsel tipi değiştirildi: *{type_names.get(new_type, new_type)}*\n\n"
            "Yeni görsel üretiliyor..."
        )
        # Fotoğraf/video mesajı ise caption düzenle, değilse text düzenle
        if query.message.photo or query.message.video:
            await query.edit_message_caption(
                caption=status_text,
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                status_text,
                parse_mode="Markdown"
            )
        pipeline.set_approval({"action": "change_type", "new_type": new_type})

    elif action == "publish_now":
        pipeline.set_approval({"action": "publish_now"})
        # Audit log
        try:
            current_state = pipeline.current_state or {}
            log_approval_decision(
                post_id=current_state.get("post_id"),
                decision="approved",
                user_id=query.from_user.id,
                username=query.from_user.username or query.from_user.first_name,
                topic=current_state.get("topic"),
                content_type=current_state.get("visual_type", "post"),
                scheduler_mode="manual",
                new_status="publishing"
            )
        except Exception as e:
            print(f"Audit log hatası: {e}")

    elif action == "revise":
        await query.edit_message_text(
            "✏️ *Revize için geri bildiriminizi yazın:*\n\n"
            "Neyi değiştirmemi istersiniz?",
            parse_mode="Markdown"
        )
        pending_input["type"] = "revise_feedback"
        pending_input["user_id"] = query.from_user.id
        pending_input["username"] = query.from_user.username or query.from_user.first_name

    elif action == "schedule":
        await query.edit_message_text("⏰ *Saat girin (HH:MM):*", parse_mode="Markdown")
        pending_input["type"] = "schedule_time"
        pending_input["user_id"] = query.from_user.id
        pending_input["username"] = query.from_user.username or query.from_user.first_name

    elif action == "cancel":
        pipeline.set_approval({"action": "cancel"})
        # Audit log
        try:
            current_state = pipeline.current_state or {}
            log_approval_decision(
                post_id=current_state.get("post_id"),
                decision="rejected",
                user_id=query.from_user.id,
                username=query.from_user.username or query.from_user.first_name,
                topic=current_state.get("topic"),
                content_type=current_state.get("visual_type", "post"),
                reason="User cancelled",
                scheduler_mode="manual",
                new_status="rejected"
            )
        except Exception as e:
            print(f"Audit log hatası: {e}")
        await query.edit_message_text("❌ İptal edildi.")

    # ===== STORY BOOST CALLBACKS =====
    elif action.startswith("story_done:"):
        boost_id = int(action.split(":")[1])
        from app.database.crud import update_story_boost
        update_story_boost(boost_id, "published", "manual")
        await query.edit_message_text(
            f"✅ Story boost #{boost_id} tamamlandı.",
            parse_mode="Markdown"
        )

    elif action.startswith("story_skip:"):
        boost_id = int(action.split(":")[1])
        from app.database.crud import update_story_boost
        update_story_boost(boost_id, "skipped")
        await query.edit_message_text(
            f"⏭️ Story boost #{boost_id} atlandı.",
            parse_mode="Markdown"
        )


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Metin inputlarını işle - Authorization kontrolü ile"""
    global pending_input, pipeline

    user_id = update.effective_user.id

    # Authorization check
    if not is_admin(user_id):
        await update.message.reply_text(
            f"⛔ *Yetkisiz Erişim*\n\nKullanıcı ID: `{user_id}`",
            parse_mode="Markdown"
        )
        return

    text = update.message.text

    if pending_input.get("type") == "content_feedback":
        pipeline.set_approval({"action": "regenerate_content", "feedback": text})
        pending_input = {}
        await update.message.reply_text("✅ Geri bildirim alındı, içerik revize ediliyor...")

    elif pending_input.get("type") == "schedule_time":
        pipeline.set_approval({"action": "schedule", "time": text})
        # Audit log for scheduling
        try:
            current_state = pipeline.current_state or {}
            log_approval_decision(
                post_id=current_state.get("post_id"),
                decision="scheduled",
                user_id=pending_input.get("user_id"),
                username=pending_input.get("username"),
                topic=current_state.get("topic"),
                content_type=current_state.get("visual_type", "post"),
                reason=f"Scheduled for {text}",
                scheduler_mode="manual",
                new_status="scheduled"
            )
        except Exception as e:
            print(f"Audit log hatası: {e}")
        pending_input = {}
        await update.message.reply_text(f"✅ {text} için zamanlandı.")

    elif pending_input.get("type") == "revise_feedback":
        # Direkt metin revizesi yap - görsel değiştirmek için ayrı buton var
        pipeline.set_approval({"action": "revise_content", "feedback": text})
        pending_input = {}
        await update.message.reply_text("✏️ İçerik revize ediliyor...")

    elif pending_input.get("type") == "daily_manual_topic":
        # ATOMIC: Race condition önlemek için hemen pop et
        input_type = pending_input.pop("type", None)
        if input_type != "daily_manual_topic":
            return  # Başka thread zaten işledi

        topic = text.strip()

        if len(topic) < 5:
            # Hata durumunda type'ı geri koy
            pending_input["type"] = "daily_manual_topic"
            await update.message.reply_text(
                "⚠️ *Konu çok kısa!*\n\n"
                "En az 5 karakter olmalı.",
                parse_mode="Markdown"
            )
            return

        # Görsel tipi seçim menüsü göster
        pending_input["topic"] = topic

        keyboard = [
            [InlineKeyboardButton("📊 AI Infographic", callback_data="daily_visual:nano_banana")],
            [InlineKeyboardButton("🎨 Carousel", callback_data="daily_visual:carousel"),
             InlineKeyboardButton("📸 Tek Görsel", callback_data="daily_visual:single")],
            [InlineKeyboardButton("❌ İptal", callback_data="cancel")]
        ]

        await update.message.reply_text(
            f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n\n"
            "Görsel tipi seçin:\n"
            "• *AI Infographic*: Nano Banana (~$0.15)\n"
            "• *Carousel*: Flux AI çoklu görsel\n"
            "• *Tek Görsel*: Flux AI single post",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif pending_input.get("type") == "reels_manual_topic":
        # ATOMIC: Race condition önlemek için hemen pop et
        input_type = pending_input.pop("type", None)
        if input_type != "reels_manual_topic":
            return  # Başka thread zaten işledi

        topic = text.strip()
        model = pending_input.get("model", "kling_pro")
        visual_style = pending_input.get("visual_style", "cinematic_4k")

        if len(topic) < 5:
            pending_input["type"] = "reels_manual_topic"
            await update.message.reply_text(
                "⚠️ *Konu çok kısa!*\n\n"
                "En az 5 karakter olmalı.",
                parse_mode="Markdown"
            )
            return

        model_names = {
            "sora2": "Sora 2",
            "kling_v3_pro": "Kling 3.0 Pro",
        }
        model_name = model_names.get(model, model)

        pending_input.clear()
        await update.message.reply_text(
            f"🎬 *REELS* başlatılıyor...\n\n"
            f"📝 *Konu:* {escape_markdown(topic[:80])}{'...' if len(topic) > 80 else ''}\n"
            f"🎯 *Model:* {model_name}\n\n"
            "⏳ Bu işlem 5-10 dakika sürebilir...",
            parse_mode="Markdown"
        )
        asyncio.create_task(pipeline.run_reels_content(force_model=model, topic=topic, manual_topic_mode=True, visual_style=visual_style))

    elif pending_input.get("type") == "carousel_manual_topic":
        # ATOMIC: Race condition önlemek için hemen pop et
        input_type = pending_input.pop("type", None)
        if input_type != "carousel_manual_topic":
            return  # Başka thread zaten işledi

        topic = text.strip()

        if len(topic) < 5:
            pending_input["type"] = "carousel_manual_topic"
            await update.message.reply_text(
                "⚠️ *Konu çok kısa!*\n\n"
                "En az 5 karakter olmalı.",
                parse_mode="Markdown"
            )
            return

        # Konu kaydedilip tip seçim menüsü göster
        pending_input["carousel_topic"] = topic

        keyboard = [
            [InlineKeyboardButton("📝 HTML Template (~$0.01)", callback_data="carousel_type:html:manual")],
            [InlineKeyboardButton("📊 Nano Banana AI (~$0.75)", callback_data="carousel_type:nano_banana:manual")],
            [InlineKeyboardButton("« Geri", callback_data="create_carousel")]
        ]

        await update.message.reply_text(
            f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n\n"
            "🎠 *Carousel Görsel Tipi Seçin:*\n\n"
            "• *HTML Template*: Hızlı, tutarlı tasarım\n"
            "• *Nano Banana*: AI infographic, oklu kutucuklar",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif pending_input.get("type") == "voice_topic_manual":
        # Sesli Reels için manuel konu girişi
        topic = text.strip()

        # Validasyon: minimum 5 karakter
        if len(topic) < 5:
            await update.message.reply_text(
                "⚠️ *Konu çok kısa!*\n\n"
                "En az 5 karakter olmalı.\n"
                "Daha detaylı bir konu yazın.",
                parse_mode="Markdown"
            )
            return  # State'i koru, yeni input bekle

        # Multi-model flow: model_id ve duration zaten pending_input'ta mı?
        model_id = pending_input.get("model_id")
        duration = pending_input.get("duration")
        visual_style = pending_input.get("visual_style", "cinematic_4k")

        if model_id and duration:
            # YENİ FLOW: Model ve süre zaten seçildi, direkt pipeline başlat
            config = get_model_config(model_id)
            pending_input.clear()

            await update.message.reply_text(
                f"🎙️ *SESLİ REELS* başlatılıyor...\n\n"
                f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n"
                f"🎬 *Model:* {config['emoji']} {config['name']}\n"
                f"⏱️ *Süre:* {duration} saniye\n"
                f"🔊 *Ses:* Türkçe AI voiceover\n\n"
                "⏳ Bu işlem 5-10 dakika sürebilir...",
                parse_mode="Markdown"
            )

            # Pipeline başlat
            asyncio.create_task(pipeline.run_reels_voice_content(
                topic=topic,
                target_duration=duration,
                model_id=model_id,
                manual_topic_mode=True,
                visual_style=visual_style
            ))
        else:
            # ESKİ FLOW (backward compatibility): Süre henüz seçilmedi
            pending_input["manual_topic"] = topic
            pending_input["type"] = None  # Text bekleme durumunu kapat

            duration_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🎙️ 8s Kısa", callback_data="voice_reels_manual:8"),
                    InlineKeyboardButton("🎙️ 12s Standart ⭐", callback_data="voice_reels_manual:12"),
                ],
                [
                    InlineKeyboardButton("❌ İptal", callback_data="voice_reels_menu"),
                ]
            ])

            await update.message.reply_text(
                f"✅ *Konu kabul edildi:*\n_{topic[:80]}{'...' if len(topic) > 80 else ''}_\n\n"
                "🎙️ *Süre seçin:*\n"
                "• *8s*: Kısa, tek mesajlı\n"
                "• *12s*: Standart (önerilen)\n"
                "🎥 Video: Sora 2",
                parse_mode="Markdown",
                reply_markup=duration_keyboard
            )

    elif pending_input.get("type") == "long_video_manual":
        # Uzun video için manuel konu girişi
        input_type = pending_input.pop("type", None)
        if input_type != "long_video_manual":
            return

        topic = text.strip()

        # Validasyon: minimum 5 karakter
        if len(topic) < 5:
            pending_input["type"] = "long_video_manual"
            await update.message.reply_text(
                "⚠️ *Konu çok kısa!*\n\n"
                "En az 5 karakter olmalı.\n"
                "Daha detaylı bir konu yazın.",
                parse_mode="Markdown"
            )
            return

        segment_count = pending_input.get("segment_count", 2)
        model_id = pending_input.get("model_id", "kling-3.0-pro")
        visual_style = pending_input.get("visual_style", "cinematic_4k")
        pending_input.clear()

        model_config = get_model_config(model_id)
        model_name = model_config.get("name", model_id)
        max_duration = get_max_duration(model_id)
        total_duration = segment_count * max_duration

        await update.message.reply_text(
            f"🎥 *UZUN VIDEO* başlatılıyor...\n\n"
            f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n"
            f"🎬 *Segment:* {segment_count}x{max_duration}s = {total_duration}s\n"
            f"📹 *Model:* {model_name}\n\n"
            "Pipeline aşamaları:\n"
            "1️⃣ Konu işleme\n"
            "2️⃣ Caption üretimi\n"
            "3️⃣ Voiceover scripti\n"
            "4️⃣ TTS ses üretimi\n"
            "5️⃣ Multi-scene prompt\n"
            f"6️⃣ Paralel video üretimi ({segment_count}x)\n"
            "7️⃣ Video birleştirme\n"
            "8️⃣ Audio-video merge\n"
            "9️⃣ Instagram yayını\n\n"
            "⏳ Bu işlem 4-5 dakika sürebilir...",
            parse_mode="Markdown"
        )

        asyncio.create_task(pipeline.run_long_video_pipeline(
            topic=topic,
            segment_count=segment_count,
            model_id=model_id,
            manual_topic_mode=True,
            visual_style=visual_style
        ))

    elif pending_input.get("type") == "manual_topic":
        # Manuel konu ile pipeline başlat (genel içerik için)
        pending_input = {}
        await update.message.reply_text("🚀 İçerik oluşturuluyor...")
        # TODO: Manuel topic ile pipeline

    elif pending_input.get("type") == "conv_topic":
        # Conversational Reels için manuel konu girişi
        input_type = pending_input.pop("type", None)
        if input_type != "conv_topic":
            return

        topic = text.strip()
        visual_style = pending_input.get("visual_style", "cinematic_4k")
        model_id = pending_input.get("model_id", "sora-2")
        pending_input.clear()

        model_config = get_model_config(model_id)
        model_name = f"{model_config.get('emoji', '🎬')} {model_config.get('name', model_id)}"

        native_speech_models = ["sora-2", "sora-2-pro"]
        if model_id in native_speech_models:
            pipeline_info = f"{model_id.upper()} native speech"
            pipeline_steps = (
                "1️⃣ Konu işleme\n"
                "2️⃣ Dialog içeriği\n"
                f"3️⃣ Conversation video ({model_id} native speech)\n"
                "4️⃣ B-roll voiceover (TTS)\n"
                "5️⃣ B-roll video\n"
                "6️⃣ Video birleştirme\n"
                "7️⃣ Altyazı ekleme"
            )
        else:
            pipeline_info = "TTS + Video + Lipsync"
            pipeline_steps = (
                "1️⃣ Konu işleme\n"
                "2️⃣ Dialog içeriği\n"
                "3️⃣ Multi-voice TTS\n"
                "4️⃣ Avatar video\n"
                "5️⃣ Lipsync işleme\n"
                "6️⃣ B-roll voiceover\n"
                "7️⃣ B-roll video\n"
                "8️⃣ Video birleştirme\n"
                "9️⃣ Altyazı ekleme"
            )

        await update.message.reply_text(
            f"🎭 *CONVERSATIONAL REELS* başlatılıyor...\n\n"
            f"📋 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n"
            f"📹 *Model:* {model_name}\n"
            f"🗣️ *Konuşma:* {pipeline_info}\n\n"
            f"*Pipeline aşamaları:*\n{pipeline_steps}\n\n"
            "⏳ Bu işlem 8-15 dakika sürebilir...",
            parse_mode="Markdown"
        )

        asyncio.create_task(pipeline.run_conversational_reels(
            topic=topic,
            manual_topic_mode=True,
            visual_style=visual_style,
            model_id=model_id
        ))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Network hatalarını gracefully handle et"""
    error = context.error

    if isinstance(error, NetworkError):
        print(f"⚠️ Network hatası (retry edilecek): {error}")
    elif isinstance(error, TimedOut):
        print(f"⚠️ Timeout hatası (retry edilecek): {error}")
    elif isinstance(error, RetryAfter):
        print(f"⚠️ Rate limit - {error.retry_after}s bekle")
        await asyncio.sleep(error.retry_after)
    else:
        print(f"❌ Beklenmeyen hata: {type(error).__name__}: {error}")


# ============ V2 MONITORING COMMANDS ============

async def cmd_pool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Opportunity pool durumu"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    opps = get_top_opportunities(limit=10, min_score=0)

    if not opps:
        await update.message.reply_text("📭 Havuzda fırsat yok.")
        return

    lines = ["📊 Opportunity Pool (Top 10)\n"]
    for i, o in enumerate(opps, 1):
        title = str(o.get("title", "?"))[:40]
        score = o.get("combined_score", 0)
        source = str(o.get("source_type", "?"))
        status = str(o.get("status", "?"))
        lines.append(f"{i}. {title}\n   Score: {score:.0f} | {source} | {status}")

    await update.message.reply_text("\n".join(lines))


def _get_topic_short(opp_id, reason: str) -> str:
    """Opportunity title (25 chars max), fallback to reason."""
    if opp_id:
        try:
            opp = get_opportunity(int(opp_id))
            if opp and opp.get("title"):
                t = str(opp["title"])[:25]
                return t
        except Exception:
            pass
    r = str(reason or "")
    return r[:25] if r else "?"


def _shorten_model(model_id: str) -> str:
    """Strip version numbers: 'kling-3.0-pro' → 'kling-pro'."""
    if not model_id:
        return "?"
    import re
    return re.sub(r'-?\d+\.?\d*', '', model_id).replace('--', '-').strip('-') or model_id


def _shorten_content_type(ct: str) -> str:
    """Compact content type names."""
    mapping = {"image_to_video": "i2v", "news_reels": "news", "voice_reels": "voice"}
    return mapping.get(ct, ct or "?")


def _format_production_status(prod) -> str:
    """One-line production status."""
    if not prod or not isinstance(prod, dict):
        return "⏳ Üretiliyor..."
    inner = prod.get("production_result", prod)
    if not isinstance(inner, dict):
        return "⏳ Üretiliyor..."
    success = inner.get("success")
    if success is True:
        return "✅ Yayınlandı"
    if success is False:
        err = str(inner.get("error", "?"))[:30]
        return f"❌ {err}"
    return "⏳ Üretiliyor..."


def _format_brain_decision(d: dict) -> str:
    """Ultra-compact brain decision: max 3 lines."""
    action = str(d.get("action", "?"))

    # Timestamp HH:MM
    ts_raw = str(d.get("timestamp", ""))
    hhmm = ts_raw[11:16] if len(ts_raw) >= 16 else ts_raw

    if action == "produce":
        ct = d.get("content_type", "")
        emoji = {"image_post": "📸", "carousel": "📊"}.get(ct, "🎬")
        topic = _get_topic_short(d.get("opportunity_id"), d.get("reason", ""))
        model = _shorten_model(str(d.get("model_id", "")))
        ct_short = _shorten_content_type(ct)
        status = _format_production_status(d.get("production_result"))
        return f"{emoji} produce — {hhmm}\n{topic} → {ct_short} ({model})\n{status}"

    # skip / wait / adjust_strategy
    emoji = {"wait": "⏸️", "skip": "⏸️", "adjust_strategy": "🔄"}.get(action, "🧠")
    reason = str(d.get("reason", ""))
    if len(reason) > 60:
        reason = reason[:60] + "…"
    return f"{emoji} {action} — {hhmm}\n{reason}"


async def cmd_brain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Brain Agent son kararları — ultra-compact"""
    global brain_agent

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    # Collect decisions: in-memory first, DB fallback
    decisions = []
    if brain_agent and hasattr(brain_agent, "get_last_decisions"):
        decisions = brain_agent.get_last_decisions(5)

    if not decisions:
        logs = get_agent_logs(agent_name="brain", limit=5)
        if not logs:
            await update.message.reply_text("🧠 Brain henüz karar almadı.")
            return
        for log in logs:
            output = log.get("output_data", "{}")
            try:
                data = json.loads(output) if isinstance(output, str) else (output or {})
                # Handle double-encoded JSON
                if isinstance(data, str):
                    data = json.loads(data)
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}
            decisions.append({
                "action": data.get("action", "?"),
                "timestamp": str(log.get("timestamp", "")),
                "reason": data.get("reason", ""),
                "opportunity_id": data.get("opportunity_id", ""),
                "content_type": data.get("content_type", ""),
                "model_id": data.get("model_id", ""),
                "production_result": data.get("production_result"),
            })

    lines = ["🧠 Brain"]
    for d in decisions:
        lines.append(_format_brain_decision(d))

    # Weekly footer
    try:
        wb = get_weekly_content_breakdown()
        parts = []
        if wb['video_reels']:
            parts.append(f"{wb['video_reels']} reels")
        if wb['image_post']:
            parts.append(f"{wb['image_post']} image")
        if wb['carousel']:
            parts.append(f"{wb['carousel']} carousel")
        if wb['voice_reels']:
            parts.append(f"{wb['voice_reels']} voice")
        week_str = ", ".join(parts) if parts else "0"
        lines.append(f"📊 Bu hafta: {week_str}")
        lines.append(f"💰 Tahmini: ~${wb['estimated_cost']:.2f}")
    except Exception:
        pass

    dry_run = brain_agent.is_dry_run if brain_agent else True
    mode = "DRY-RUN" if dry_run else "LIVE"
    lines.append(f"⏰ Mod: {mode} | Cycle: {BRAIN_CYCLE_MINUTES}dk")

    msg = "\n".join(lines)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n…"
    await update.message.reply_text(msg)


async def cmd_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feed ve havuz istatistikleri"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    stats = get_opportunity_stats()

    by_status = stats.get("by_status", {})
    by_source = stats.get("by_source", {})

    status_lines = "\n".join([f"  {k}: {v}" for k, v in by_status.items()]) or "  Veri yok"
    source_lines = "\n".join([f"  {k}: {v}" for k, v in by_source.items()]) or "  Veri yok"

    text = (
        f"📡 Feed & Pool Stats\n\n"
        f"Aktif: {stats.get('active_count', 0)}\n"
        f"Ort. Skor: {stats.get('avg_score', 0)}\n"
        f"Max Skor: {stats.get('max_score', 0)}\n\n"
        f"Status:\n{status_lines}\n\n"
        f"Kaynak:\n{source_lines}"
    )

    await update.message.reply_text(text)


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Brain Agent'ı duraklat"""
    global brain_agent

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    if not brain_agent:
        await update.message.reply_text("⚠️ Brain Agent aktif değil.")
        return

    brain_agent.state_manager.is_paused = True
    await update.message.reply_text("⏸️ Brain Agent duraklatıldı.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Brain Agent'ı devam ettir"""
    global brain_agent

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    if not brain_agent:
        await update.message.reply_text("⚠️ Brain Agent aktif değil.")
        return

    brain_agent.state_manager.is_paused = False
    await update.message.reply_text("▶️ Brain Agent devam ediyor.")


async def cmd_force(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Belirli bir opportunity'yi zorla üret: /force <opp_id> [content_type]"""
    global brain_agent

    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    if not brain_agent:
        await update.message.reply_text("⚠️ Brain Agent aktif değil.")
        return

    args = context.args or []
    if not args:
        await update.message.reply_text("Kullanım: /force <opp_id> [content_type]\nÖrnek: /force 42 reels")
        return

    try:
        opp_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Geçersiz opportunity ID.")
        return

    content_type = args[1] if len(args) > 1 else "reels"

    opp = get_opportunity(opp_id)
    if not opp:
        await update.message.reply_text(f"❌ Opportunity {opp_id} bulunamadı.")
        return

    await update.message.reply_text(
        f"🚀 Force production başlatılıyor...\n"
        f"ID: {opp_id}\nTip: {content_type}\nKonu: {opp.get('title', '?')[:50]}"
    )

    result = await brain_agent.force_produce(opp_id, content_type)

    if result.get("error"):
        await update.message.reply_text(f"❌ Hata: {result['error']}")
    else:
        await update.message.reply_text(f"✅ Production tetiklendi: {result.get('triggered', False)}")


async def cc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ad-hoc Claude Code query from Telegram"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yetkiniz yok.")
        return

    if not context.args:
        await update.message.reply_text("Kullanım: /cc <soru veya komut>")
        return

    prompt = " ".join(context.args)
    await update.message.reply_text("⏳ Çalışıyor...")

    try:
        process = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt, "--print",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/opt/olivenet-social-bot"
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=120
        )

        result = stdout.decode("utf-8", errors="replace").strip()
        if not result:
            result = "Boş yanıt döndü."

        # Telegram 4096 char limit
        if len(result) <= 4000:
            await update.message.reply_text(result)
        else:
            for i in range(0, len(result), 4000):
                await update.message.reply_text(result[i:i+4000])

    except asyncio.TimeoutError:
        await update.message.reply_text("⏰ Timeout (120s)")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {str(e)[:500]}")


async def main():
    """Ana fonksiyon"""
    global pipeline, scheduler, admin_chat_id

    import os
    from dotenv import load_dotenv
    load_dotenv()

    # Pipeline oluştur
    pipeline = ContentPipeline(telegram_callback=telegram_notify)

    # Scheduler oluştur
    scheduler = create_default_scheduler(pipeline)

    # Admin chat ID
    admin_chat_id = int(os.getenv("TELEGRAM_ADMIN_CHAT_ID", "0"))

    # HTTPXRequest ile retry/backoff ayarları
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
        pool_timeout=10.0,
    )

    # Telegram bot - retry mekanizması ile
    app = (
        Application.builder()
        .token(os.getenv("TELEGRAM_BOT_TOKEN"))
        .request(request)
        .get_updates_request(request)
        .build()
    )

    # Handler'lar - Komutlar
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("manual", cmd_manual))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler("prompts", cmd_prompts))

    # Handler'lar - v2 Monitoring Komutları
    app.add_handler(CommandHandler("pool", cmd_pool))
    app.add_handler(CommandHandler("brain", cmd_brain))
    app.add_handler(CommandHandler("feeds", cmd_feeds))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("force", cmd_force))
    app.add_handler(CommandHandler("cc", cc_command))

    # Handler'lar - Callback ve Mesaj
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    # Error handler ekle
    app.add_error_handler(error_handler)

    print("🤖 Telegram Pipeline Bot başlatılıyor...")
    print(f"📍 Admin Chat ID: {admin_chat_id}")

    # Scheduler'ı arka planda başlat
    asyncio.create_task(scheduler.start(check_interval=60))

    # Bot'u başlat - drop_pending_updates ile eski mesajları atla
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

    print("✅ Bot çalışıyor! (Retry mekanizması aktif)")

    # Sonsuza kadar çalış
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
