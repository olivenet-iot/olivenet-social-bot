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
from app.video_models import VIDEO_MODELS, get_model_config, get_model_durations

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
            InlineKeyboardButton("🎥 Uzun Video", callback_data="create_long_video")
        ],
        [
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

    # ===== REELS OLUŞTUR - MODEL SEÇİM MENÜSÜ =====
    elif action == "create_reels":
        # Video model seçim menüsü göster
        video_model_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎬 Veo 3", callback_data="video_model:veo3"),
                InlineKeyboardButton("🎥 Sora 2", callback_data="video_model:sora2"),
            ],
            [
                InlineKeyboardButton("⚡ Kling 2.5", callback_data="video_model:kling_pro"),
                InlineKeyboardButton("🔊 Kling 2.6", callback_data="video_model:kling_26_pro"),
            ],
            [
                InlineKeyboardButton("🌀 Hailuo Pro", callback_data="video_model:hailuo_pro"),
                InlineKeyboardButton("🎞️ Wan 2.6", callback_data="video_model:wan_26"),
            ],
            [
                InlineKeyboardButton("💎 Kling 2.1 Master", callback_data="video_model:kling_master"),
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
            "• *Veo 3*: Google, 8s, yüksek kalite\n"
            "• *Sora 2*: OpenAI, 8s, yaratıcı\n"
            "• *Kling 2.5 Pro*: fal.ai, 10s, hızlı\n"
            "• *Kling 2.6 Pro*: fal.ai, 10s, 🔊 ambient sesli\n"
            "• *Hailuo Pro*: 🌀 Dinamik hareketler, 6s\n"
            "• *Wan 2.6*: 🎞️ Multi-shot, sinematik, 15s\n"
            "• *Kling 2.1 Master*: fal.ai, 10s, en iyi kalite\n\n"
            "🎙️ *Sesli Reels*: Türkçe voiceover + video\n\n"
            "💡 Tüm modeller 9:16 dikey format kullanır.",
            parse_mode="Markdown",
            reply_markup=video_model_keyboard
        )

    # ===== VIDEO MODEL SEÇİMİ - KONU SEÇİM MENÜSÜ =====
    elif action.startswith("video_model:"):
        model = action.replace("video_model:", "")

        model_names = {
            "veo3": "Veo 3 (Google)",
            "sora2": "Sora 2 (OpenAI)",
            "kling_pro": "Kling 2.5 Pro (fal.ai)",
            "kling_26_pro": "Kling 2.6 Pro (fal.ai)",
            "hailuo_pro": "Hailuo 02 Pro (fal.ai)",
            "wan_26": "Wan 2.6 (fal.ai)",
            "kling_master": "Kling 2.1 Master (fal.ai)"
        }
        model_name = model_names.get(model, model)

        # Konu seçim menüsü göster
        keyboard = [
            [InlineKeyboardButton("🤖 Otomatik Konu", callback_data=f"reels_auto:{model}"),
             InlineKeyboardButton("✏️ Manuel Konu", callback_data=f"reels_manual:{model}")],
            [InlineKeyboardButton("◀️ Geri", callback_data="create_reels")]
        ]
        await query.edit_message_text(
            f"🎬 *Reels - {model_name}*\n\n"
            "Konu seçimi:\n"
            "• *Otomatik*: AI trend konuyu seçer\n"
            "• *Manuel*: Kendi konunu yaz",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== REELS - OTOMATİK KONU =====
    elif action.startswith("reels_auto:"):
        model = action.replace("reels_auto:", "")

        model_names = {
            "veo3": "Veo 3 (Google)",
            "sora2": "Sora 2 (OpenAI)",
            "kling_pro": "Kling 2.5 Pro (fal.ai)",
            "kling_26_pro": "Kling 2.6 Pro (fal.ai)",
            "hailuo_pro": "Hailuo 02 Pro (fal.ai)",
            "wan_26": "Wan 2.6 (fal.ai)",
            "kling_master": "Kling 2.1 Master (fal.ai)"
        }
        model_name = model_names.get(model, model)

        await query.edit_message_text(
            f"🎬 *REELS MOD* başlatılıyor...\n\n"
            f"🎯 *Model:* {model_name}\n\n"
            "Video içeriği oluşturulacak:\n"
            "• Konu seçimi (AI)\n"
            "• Caption üretimi (IG+FB)\n"
            "• Video prompt\n"
            f"• Video üretimi ({model_name})\n"
            "• Instagram Reels + Facebook Video\n\n"
            "⏳ Bu işlem 5-10 dakika sürebilir...",
            parse_mode="Markdown"
        )
        asyncio.create_task(pipeline.run_reels_content(force_model=model))

    # ===== REELS - MANUEL KONU =====
    elif action.startswith("reels_manual:"):
        model = action.replace("reels_manual:", "")

        model_names = {
            "veo3": "Veo 3 (Google)",
            "sora2": "Sora 2 (OpenAI)",
            "kling_pro": "Kling 2.5 Pro (fal.ai)",
            "kling_26_pro": "Kling 2.6 Pro (fal.ai)",
            "hailuo_pro": "Hailuo 02 Pro (fal.ai)",
            "wan_26": "Wan 2.6 (fal.ai)",
            "kling_master": "Kling 2.1 Master (fal.ai)"
        }
        model_name = model_names.get(model, model)

        pending_input["type"] = "reels_manual_topic"
        pending_input["model"] = model
        pending_input["user_id"] = query.from_user.id
        await query.edit_message_text(
            f"✏️ *Manuel Konu Girişi*\n\n"
            f"🎬 Model: {model_name}\n\n"
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
            # Wan 2.1 için yıldız ekle (en uzun video)
            star = " ⭐" if model_id == "wan-2.1" else ""
            button_text = f"{emoji} {name} (max {max_dur}s){star}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"voice_model:{model_id}")])

        keyboard.append([InlineKeyboardButton("❌ İptal", callback_data="create_reels")])

        await query.edit_message_text(
            "🎬 *SESLİ REELS* - Model Seç\n\n"
            "Hangi AI modeli ile video oluşturmak istersin?\n\n"
            "🌟 *Sora 2* - En yüksek kalite, gerçekçi (max 12s)\n"
            "🎥 *Veo 2* - Google, hızlı ve tutarlı (max 8s)\n"
            "🎬 *Kling 2.5 Pro* - Hızlı üretim (max 10s)\n"
            "🎥 *Kling 2.6 Pro* - Cinematic 1080p kalite ⭐ (max 10s)\n"
            "🌊 *Wan 2.1* - En uzun video! (max 15s)\n"
            "🎯 *Minimax* - Hızlı ve ekonomik (max 5s)\n\n"
            "🔊 Tüm modellerde Türkçe AI voiceover eklenir.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SESLİ REELS - MODEL SEÇİLDİ → SÜRE MENÜSÜ =====
    elif action.startswith("voice_model:"):
        model_id = action.replace("voice_model:", "")
        config = get_model_config(model_id)
        durations = get_model_durations(model_id)

        keyboard = []
        for duration in durations:
            is_default = duration == config.get("default_duration")
            emoji = "⭐" if is_default else "⏱️"
            suffix = " (önerilen)" if is_default else ""
            button_text = f"{emoji} {duration} saniye{suffix}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"voice_duration:{model_id}:{duration}")])

        keyboard.append([InlineKeyboardButton("⬅️ Geri", callback_data="voice_reels_menu")])

        await query.edit_message_text(
            f"⏱️ *{config['emoji']} {config['name']}* - Süre Seç\n\n"
            f"_{config['description']}_\n\n"
            "Kaç saniyelik video oluşturmak istersin?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SESLİ REELS - SÜRE SEÇİLDİ → KONU MENÜSÜ =====
    elif action.startswith("voice_duration:"):
        parts = action.split(":")
        model_id = parts[1]
        duration = int(parts[2])
        config = get_model_config(model_id)

        keyboard = [
            [InlineKeyboardButton("🎲 Otomatik Konu", callback_data=f"voice_topic:{model_id}:{duration}:auto")],
            [InlineKeyboardButton("✏️ Manuel Konu", callback_data=f"voice_topic:{model_id}:{duration}:manual")],
            [InlineKeyboardButton("⬅️ Geri", callback_data=f"voice_model:{model_id}")]
        ]

        await query.edit_message_text(
            f"📝 *Konu Seç*\n\n"
            f"🎬 Model: {config['emoji']} {config['name']}\n"
            f"⏱️ Süre: {duration} saniye\n\n"
            "Konu nasıl belirlensin?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SESLİ REELS - KONU SEÇİLDİ =====
    elif action.startswith("voice_topic:") and ":" in action[12:]:
        # Yeni format: voice_topic:{model}:{duration}:{auto|manual}
        parts = action.split(":")
        model_id = parts[1]
        duration = int(parts[2])
        topic_mode = parts[3]
        config = get_model_config(model_id)

        if topic_mode == "auto":
            # Otomatik konu ile pipeline başlat
            await query.edit_message_text(
                f"🎙️ *SESLİ REELS* başlatılıyor...\n\n"
                f"🎬 *Model:* {config['emoji']} {config['name']}\n"
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
                model_id=model_id
            ))
        else:
            # Manuel konu girişi bekle
            pending_input["type"] = "voice_topic_manual"
            pending_input["model_id"] = model_id
            pending_input["duration"] = duration
            pending_input["user_id"] = query.from_user.id
            pending_input["username"] = query.from_user.username or query.from_user.first_name

            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ İptal", callback_data="voice_reels_menu")]
            ])

            await query.edit_message_text(
                f"✏️ *MANUEL KONU GİRİŞİ*\n\n"
                f"🎬 Model: {config['emoji']} {config['name']}\n"
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
                InlineKeyboardButton("⏱️ 20 saniye", callback_data="long_duration:20"),
                InlineKeyboardButton("⏱️ 30 saniye", callback_data="long_duration:30")
            ],
            [InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text(
            "🎥 *UZUN VIDEO*\n\n"
            "Multi-segment video pipeline.\n"
            "2-3 segment paralel üretilip birleştirilir.\n\n"
            "💰 *Maliyet:* ~$0.60-$1.50\n"
            "⏳ *Süre:* ~4-5 dakika\n\n"
            "⏱️ *Süre seçin:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action.startswith("long_duration:"):
        duration = int(action.split(":")[1])
        segment_count = duration // 10
        keyboard = [
            [
                InlineKeyboardButton("🎬 Kling 2.6", callback_data=f"long_model:{duration}:kling-2.6-pro"),
                InlineKeyboardButton("🌟 Sora 2", callback_data=f"long_model:{duration}:sora-2")
            ],
            [
                InlineKeyboardButton("🎯 Veo 2", callback_data=f"long_model:{duration}:veo-2"),
                InlineKeyboardButton("🌊 Wan 2.1", callback_data=f"long_model:{duration}:wan-2.1")
            ],
            [InlineKeyboardButton("◀️ Geri", callback_data="create_long_video")]
        ]
        await query.edit_message_text(
            f"🎥 *UZUN VIDEO* - {duration}s ({segment_count} segment)\n\n"
            "🎬 *Model seçin:*\n\n"
            "• *Kling 2.6:* Dengeli kalite/fiyat (~$0.30/segment)\n"
            "• *Sora 2:* En yüksek kalite (~$0.50/segment)\n"
            "• *Veo 2:* Hızlı üretim (~$0.20/segment)\n"
            "• *Wan 2.1:* Uzun segment desteği (~$0.15/segment)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action.startswith("long_model:"):
        parts = action.split(":")
        duration = int(parts[1])
        model_id = parts[2]
        model_config = get_model_config(model_id)
        model_name = model_config.get("name", model_id)

        keyboard = [
            [InlineKeyboardButton("🎲 Otomatik Konu", callback_data=f"long_topic:{duration}:{model_id}:auto")],
            [InlineKeyboardButton("✏️ Manuel Konu", callback_data=f"long_topic:{duration}:{model_id}:manual")],
            [InlineKeyboardButton("◀️ Geri", callback_data=f"long_duration:{duration}")]
        ]
        await query.edit_message_text(
            f"🎥 *UZUN VIDEO*\n\n"
            f"⏱️ *Süre:* {duration}s\n"
            f"🎬 *Model:* {model_name}\n\n"
            "📝 *Konu seçin:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif action.startswith("long_topic:"):
        parts = action.split(":")
        duration = int(parts[1])
        model_id = parts[2]
        topic_mode = parts[3]
        segment_count = duration // 10

        if topic_mode == "auto":
            await query.edit_message_text(
                f"🎥 *UZUN VIDEO* başlatılıyor...\n\n"
                f"⏱️ *Süre:* {duration}s ({segment_count} segment)\n"
                f"🎬 *Model:* {model_id}\n"
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
                total_duration=duration,
                model_id=model_id
            ))
        else:
            pending_input["type"] = "long_video_manual"
            pending_input["duration"] = duration
            pending_input["model_id"] = model_id
            pending_input["user_id"] = query.from_user.id

            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ İptal", callback_data="create_long_video")]
            ])

            await query.edit_message_text(
                "✏️ *MANUEL KONU GİRİŞİ*\n\n"
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
            [InlineKeyboardButton("📊 İnfografik", callback_data="set_type_infographic")],
            [InlineKeyboardButton("🧠 AI Infographic", callback_data="set_type_nano_banana")],
            [InlineKeyboardButton("🖼️ FLUX Görsel", callback_data="set_type_flux")],
            [InlineKeyboardButton("🎬 Video (Veo)", callback_data="set_type_video")],
            [InlineKeyboardButton("📱 Carousel", callback_data="set_type_carousel")],
            [InlineKeyboardButton("❌ İptal", callback_data="cancel")]
        ]
        menu_text = (
            "🎨 *Görsel Tipi Seçin:*\n\n"
            "📊 İnfografik - HTML tabanlı (~$0)\n"
            "🧠 AI Infographic - Nano Banana (~$0.15)\n"
            "🖼️ FLUX - AI görsel üretimi (~$0.03)\n"
            "🎬 Video - Veo ile video üretimi\n"
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
            "video": "Video (Veo)",
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
            [InlineKeyboardButton("🖼️ Infographic", callback_data="daily_visual:infographic"),
             InlineKeyboardButton("📊 AI Infographic", callback_data="daily_visual:nano_banana")],
            [InlineKeyboardButton("🎨 Carousel", callback_data="daily_visual:carousel"),
             InlineKeyboardButton("📸 Tek Görsel", callback_data="daily_visual:single")],
            [InlineKeyboardButton("❌ İptal", callback_data="cancel")]
        ]

        await update.message.reply_text(
            f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n\n"
            "Görsel tipi seçin:\n"
            "• *Infographic*: HTML şablon (~$0)\n"
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

        if len(topic) < 5:
            pending_input["type"] = "reels_manual_topic"
            await update.message.reply_text(
                "⚠️ *Konu çok kısa!*\n\n"
                "En az 5 karakter olmalı.",
                parse_mode="Markdown"
            )
            return

        model_names = {
            "veo3": "Veo 3",
            "sora2": "Sora 2",
            "kling_pro": "Kling 2.5 Pro",
            "kling_26_pro": "Kling 2.6 Pro",
            "hailuo_pro": "Hailuo 02 Pro",
            "wan_26": "Wan 2.6",
            "kling_master": "Kling 2.1 Master"
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
        asyncio.create_task(pipeline.run_reels_content(force_model=model, topic=topic, manual_topic_mode=True))

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
                manual_topic_mode=True
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

        duration = pending_input.get("duration", 30)
        model_id = pending_input.get("model_id", "kling-2.6-pro")
        segment_count = duration // 10
        pending_input.clear()

        model_config = get_model_config(model_id)
        model_name = model_config.get("name", model_id)

        await update.message.reply_text(
            f"🎥 *UZUN VIDEO* başlatılıyor...\n\n"
            f"📝 *Konu:* {escape_markdown(topic[:60])}{'...' if len(topic) > 60 else ''}\n"
            f"⏱️ *Süre:* {duration}s ({segment_count} segment)\n"
            f"🎬 *Model:* {model_name}\n\n"
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
            total_duration=duration,
            model_id=model_id,
            manual_topic_mode=True
        ))

    elif pending_input.get("type") == "manual_topic":
        # Manuel konu ile pipeline başlat (genel içerik için)
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
    app.add_handler(CommandHandler("prompts", cmd_prompts))

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
