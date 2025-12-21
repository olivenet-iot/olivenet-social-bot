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
from app.scheduler import ContentPipeline, ContentScheduler, create_default_scheduler
from app.database import (
    get_current_strategy, get_analytics_summary, log_approval_decision,
    get_week_calendar, get_published_posts,
    get_todays_summary, get_weekly_progress, get_next_scheduled,
    get_best_performing_content, get_next_schedule_slot
)
from app.config import settings

# Global değişkenler
pipeline: ContentPipeline = None
scheduler: ContentScheduler = None
admin_chat_id: int = None
pending_input: dict = {}  # Kullanıcıdan beklenen input


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
    text += f"Toplam: {weekly.get('total', 0)}/{weekly.get('total_target', 12)}\n"
    text += f"🎬 Reels: {weekly.get('reels', 0)}/{weekly.get('reels_target', 7)}\n"
    text += f"🎠 Carousel: {weekly.get('carousel', 0)}/{weekly.get('carousel_target', 2)}\n"
    text += f"📝 Post: {weekly.get('post', 0)}/{weekly.get('post_target', 3)}\n"

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

    # ===== GÜNLÜK İÇERİK BAŞLAT (ONAYLI) =====
    elif action == "start_daily":
        await query.edit_message_text("🚀 *Günlük içerik pipeline'ı başlatılıyor (Onaylı Mod)...*", parse_mode="Markdown")

        # Pipeline'ı arka planda çalıştır
        asyncio.create_task(pipeline.run_daily_content())

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

    # ===== REELS OLUŞTUR =====
    elif action == "create_reels":
        await query.edit_message_text(
            "🎬 *REELS MOD* baslatiliyor...\n\n"
            "Video icerigi olusturulacak:\n"
            "• Konu secimi (AI)\n"
            "• Caption uretimi (IG+FB)\n"
            "• Video prompt (Sora/Veo format)\n"
            "• Video uretimi (Sora 2 → Veo 3 fallback)\n"
            "• Instagram Reels + Facebook Video\n\n"
            "Bu islem 5-10 dakika surebilir..."
        )

        # Reels pipeline'ı arka planda çalıştır
        asyncio.create_task(pipeline.run_reels_content())

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
        text += f"Toplam: {weekly.get('total', 0)}/{weekly.get('total_target', 12)} içerik\n"
        text += f"🎬 Reels: {weekly.get('reels', 0)}/{weekly.get('reels_target', 7)}\n"
        text += f"🎠 Carousel: {weekly.get('carousel', 0)}/{weekly.get('carousel_target', 2)}\n"
        text += f"📝 Post: {weekly.get('post', 0)}/{weekly.get('post_target', 3)}\n"

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
                text += f"📊 Güncellenen post: {result.get('updated', 0)}\n"
                if result.get('duration'):
                    text += f"⏱️ Süre: {result.get('duration', 0):.1f}s\n"
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

        keyboard = [[InlineKeyboardButton("🏠 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # ===== CAROUSEL OLUŞTUR =====
    elif action == "create_carousel":
        await query.edit_message_text(
            "🎠 *CAROUSEL MOD* başlatılıyor...\n\n"
            "Kaydırmalı içerik oluşturulacak:\n"
            "• Konu seçimi (carousel optimize)\n"
            "• Slide metinleri (3-7 slide)\n"
            "• Her slide için görsel\n"
            "• Instagram Carousel post\n\n"
            "⏳ Bu işlem 3-5 dakika sürebilir...",
            parse_mode="Markdown"
        )

        # Carousel pipeline'ı arka planda çalıştır
        # TODO: pipeline.run_carousel_content() implement edilmeli
        # asyncio.create_task(pipeline.run_carousel_content())

        # Şimdilik bilgi mesajı
        await asyncio.sleep(1)
        text = "🎠 *Carousel Pipeline*\n\n"
        text += "⚠️ Carousel pipeline henüz tam olarak implement edilmedi.\n\n"
        text += "Şimdilik Günlük İçerik modunu kullanarak\n"
        text += "carousel tipinde içerik oluşturabilirsiniz."

        keyboard = [
            [InlineKeyboardButton("📝 Günlük İçerik", callback_data="start_daily")],
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

    elif pending_input.get("type") == "manual_topic":
        # Manuel konu ile pipeline başlat
        pending_input = {}
        await update.message.reply_text("🚀 İçerik oluşturuluyor...")
        # TODO: Manuel topic ile pipeline


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
