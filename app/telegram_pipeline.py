"""
Telegram Bot - Pipeline Entegrasyonu
Semi-autonomous mod için onay akışı
"""

import asyncio
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from app.scheduler import ContentPipeline, ContentScheduler, create_default_scheduler
from app.database import get_current_strategy, get_analytics_summary

# Global değişkenler
pipeline: ContentPipeline = None
scheduler: ContentScheduler = None
admin_chat_id: int = None
pending_input: dict = {}  # Kullanıcıdan beklenen input

async def telegram_notify(message: str, data: dict = None, buttons: list = None):
    """Pipeline'dan Telegram'a bildirim"""
    global admin_chat_id

    if not admin_chat_id:
        print("[TELEGRAM] Admin chat ID not set!")
        return

    from telegram import Bot
    import os

    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))

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
                await bot.send_photo(
                    chat_id=admin_chat_id,
                    photo=photo,
                    caption=message[:1024],
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                return
        except Exception as e:
            print(f"[TELEGRAM] Photo send error: {e}")

    # Video varsa gönder
    if data and data.get("video_path"):
        try:
            with open(data["video_path"], "rb") as video:
                await bot.send_video(
                    chat_id=admin_chat_id,
                    video=video,
                    caption=message[:1024],
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                return
        except Exception as e:
            print(f"[TELEGRAM] Video send error: {e}")

    # Normal mesaj gönder
    await bot.send_message(
        chat_id=admin_chat_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ============ KOMUTLAR ============

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ana menü"""
    global admin_chat_id
    admin_chat_id = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton("🚀 Günlük İçerik Başlat", callback_data="start_daily")],
        [InlineKeyboardButton("📅 Haftalık Plan", callback_data="weekly_plan")],
        [InlineKeyboardButton("📊 Strateji Göster", callback_data="show_strategy")],
        [InlineKeyboardButton("📈 Analytics Raporu", callback_data="analytics_report")],
        [InlineKeyboardButton("⏰ Scheduler Durumu", callback_data="scheduler_status")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🤖 *Olivenet AI Content System*\n\n"
        "Semi-autonomous içerik üretim sistemi.\n"
        "Her aşamada sizden onay bekler.\n\n"
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


# ============ CALLBACK HANDLER'LAR ============

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tüm callback'leri yönet"""
    global pipeline, scheduler, pending_input

    query = update.callback_query
    await query.answer()

    action = query.data

    # ===== ANA MENÜ =====
    if action == "main_menu":
        keyboard = [
            [InlineKeyboardButton("🚀 Günlük İçerik Başlat", callback_data="start_daily")],
            [InlineKeyboardButton("📅 Haftalık Plan", callback_data="weekly_plan")],
            [InlineKeyboardButton("📊 Strateji Göster", callback_data="show_strategy")],
            [InlineKeyboardButton("📈 Analytics Raporu", callback_data="analytics_report")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🤖 *Olivenet AI Content System*\n\nNe yapmak istersiniz?",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    # ===== GÜNLÜK İÇERİK BAŞLAT =====
    elif action == "start_daily":
        await query.edit_message_text("🚀 *Günlük içerik pipeline'ı başlatılıyor...*", parse_mode="Markdown")

        # Pipeline'ı arka planda çalıştır
        asyncio.create_task(pipeline.run_daily_content())

    # ===== HAFTALIK PLAN =====
    elif action == "weekly_plan":
        await query.edit_message_text("📅 *Haftalık plan oluşturuluyor...*", parse_mode="Markdown")

        from app.agents import OrchestratorAgent
        orchestrator = OrchestratorAgent()
        result = await orchestrator.execute({"action": "plan_week"})

        if "error" not in result:
            plan_text = "📅 *Haftalık Plan*\n\n"
            for item in result.get("week_plan", [])[:7]:
                plan_text += f"• *{item.get('day', 'N/A').title()}* {item.get('time', '')}: {item.get('topic', 'N/A')}\n"

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
        strategy = get_current_strategy()

        text = f"""📊 *Mevcut Strateji*

📅 *Haftalık Post:* {strategy.get('posts_per_week', 5)}
📆 *En İyi Günler:* {', '.join(strategy.get('best_days', [])[:3])}
⏰ *En İyi Saatler:* {', '.join(strategy.get('best_hours', [])[:3])}

📝 *İçerik Mix:*
{chr(10).join([f"• {k}: %{v}" for k, v in strategy.get('content_mix', {}).items()])}

🎨 *Görsel Mix:*
{chr(10).join([f"• {k}: %{v}" for k, v in strategy.get('visual_mix', {}).items()])}
"""
        keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== ANALYTICS RAPORU =====
    elif action == "analytics_report":
        summary = get_analytics_summary(days=7)

        text = f"""📈 *Son 7 Gün Performansı*

📊 *Toplam Post:* {summary.get('total_posts', 0)}
👁️ *Görüntüleme:* {summary.get('total_views', 0)}
👍 *Beğeni:* {summary.get('total_likes', 0)}
💬 *Yorum:* {summary.get('total_comments', 0)}
🔄 *Paylaşım:* {summary.get('total_shares', 0)}

📈 *Ortalama Engagement:* {summary.get('avg_engagement_rate', 0):.2f}%
👥 *Ortalama Reach:* {summary.get('avg_reach', 0):.0f}
"""
        keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== SCHEDULER DURUMU =====
    elif action == "scheduler_status":
        status = scheduler.get_status() if scheduler else {"running": False, "tasks": []}

        text = f"⏰ *Scheduler Durumu*\n\n"
        text += f"*Durum:* {'🟢 Çalışıyor' if status['running'] else '🔴 Durdu'}\n\n"
        text += "*Görevler:*\n"

        for task in status.get("tasks", []):
            text += f"• {task['name']}: "
            if task.get('hour') is not None:
                text += f"{task['hour']:02d}:{task.get('minute', 0):02d}"
            text += f" ({'Aktif' if task['enabled'] else 'Pasif'})\n"

        keyboard = [
            [InlineKeyboardButton("▶️ Başlat" if not status['running'] else "⏹️ Durdur",
                                  callback_data="toggle_scheduler")],
            [InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

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

    elif action == "publish_now":
        pipeline.set_approval({"action": "publish_now"})

    elif action == "schedule":
        await query.edit_message_text("⏰ *Saat girin (HH:MM):*", parse_mode="Markdown")
        pending_input["type"] = "schedule_time"

    elif action == "cancel":
        pipeline.set_approval({"action": "cancel"})
        await query.edit_message_text("❌ İptal edildi.")


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Metin inputlarını işle"""
    global pending_input, pipeline

    text = update.message.text

    if pending_input.get("type") == "content_feedback":
        pipeline.set_approval({"action": "regenerate_content", "feedback": text})
        pending_input = {}
        await update.message.reply_text("✅ Geri bildirim alındı, içerik revize ediliyor...")

    elif pending_input.get("type") == "schedule_time":
        pipeline.set_approval({"action": "schedule", "time": text})
        pending_input = {}
        await update.message.reply_text(f"✅ {text} için zamanlandı.")

    elif pending_input.get("type") == "manual_topic":
        # Manuel konu ile pipeline başlat
        pending_input = {}
        await update.message.reply_text("🚀 İçerik oluşturuluyor...")
        # TODO: Manuel topic ile pipeline


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

    # Telegram bot
    app = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Handler'lar
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("manual", cmd_manual))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    print("🤖 Telegram Pipeline Bot başlatılıyor...")
    print(f"📍 Admin Chat ID: {admin_chat_id}")

    # Scheduler'ı arka planda başlat
    asyncio.create_task(scheduler.start(check_interval=60))

    # Bot'u başlat
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    print("✅ Bot çalışıyor!")

    # Sonsuza kadar çalış
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
