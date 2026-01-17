"""
Database Models - SQLite ile içerik ve analitik takibi
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("database")

DB_PATH = settings.database_path

def get_connection():
    """Database bağlantısı al"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Database tablolarını oluştur"""
    conn = get_connection()
    cursor = conn.cursor()

    # Posts tablosu - Tüm postlar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scheduled_at TIMESTAMP,
            published_at TIMESTAMP,

            -- İçerik
            topic TEXT NOT NULL,
            post_text TEXT NOT NULL,
            visual_type TEXT,  -- infographic, gemini, flux, video, carousel
            visual_path TEXT,
            visual_prompt TEXT,

            -- Durum
            status TEXT DEFAULT 'draft',  -- draft, scheduled, approved, published, rejected
            rejection_reason TEXT,

            -- Platform
            platform TEXT DEFAULT 'facebook',  -- facebook, instagram, both
            facebook_post_id TEXT,
            instagram_post_id TEXT,

            -- AI Metadata
            orchestrator_notes TEXT,
            reviewer_feedback TEXT,
            revision_count INTEGER DEFAULT 0
        )
    ''')

    # Analytics tablosu - Post performansları
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Metrikler
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            reach INTEGER DEFAULT 0,

            -- Hesaplanan
            engagement_rate REAL DEFAULT 0,

            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Content Calendar tablosu - Planlanan içerikler
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Planlama
            week_start DATE,
            day_of_week INTEGER,  -- 0=Pazartesi, 6=Pazar
            scheduled_time TIME,

            -- İçerik planı
            topic_category TEXT,  -- egitici, tanitim, ipucu, haber, basari_hikayesi
            topic_suggestion TEXT,
            visual_type_suggestion TEXT,

            -- Durum
            status TEXT DEFAULT 'planned',  -- planned, content_created, published
            post_id INTEGER,

            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Strategy tablosu - AI'ın öğrendiği stratejiler
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            version INTEGER DEFAULT 1,  -- Feedback loop için version tracking

            -- Genel strateji
            posts_per_week INTEGER DEFAULT 5,
            best_days TEXT,  -- JSON: ["monday", "wednesday", "friday"]
            best_hours TEXT,  -- JSON: ["09:00", "13:00", "18:00"]

            -- İçerik mix
            content_mix TEXT,  -- JSON: {"egitici": 30, "tanitim": 20, ...}
            visual_mix TEXT,   -- JSON: {"flux": 40, "infographic": 30, ...}

            -- Öğrenilen insights
            insights TEXT,  -- JSON: AI'ın öğrendiği şeyler

            -- Performans baseline
            avg_engagement_rate REAL DEFAULT 0,
            avg_reach INTEGER DEFAULT 0,

            -- Top performing hooks (feedback loop için)
            best_hooks TEXT  -- JSON: ["question", "statistic", ...]
        )
    ''')

    # Agent Logs tablosu - Agent aktiviteleri
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            agent_name TEXT,  -- orchestrator, planner, creator, reviewer, publisher
            action TEXT,
            input_data TEXT,  -- JSON
            output_data TEXT,  -- JSON
            success BOOLEAN,
            error_message TEXT
        )
    ''')

    # Hook Performance tablosu - Hook type performans takibi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hook_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Hook bilgisi
            hook_type TEXT NOT NULL,  -- question, statistic, bold_claim, problem, value, fear, before_after, list, comparison, local
            topic_category TEXT,
            platform TEXT,  -- instagram, facebook, both

            -- Performance metrikleri (aggregated)
            usage_count INTEGER DEFAULT 0,
            total_reach INTEGER DEFAULT 0,
            total_engagement INTEGER DEFAULT 0,
            total_saves INTEGER DEFAULT 0,
            total_shares INTEGER DEFAULT 0,
            avg_engagement_rate REAL DEFAULT 0,
            avg_save_rate REAL DEFAULT 0,
            avg_share_rate REAL DEFAULT 0,
            avg_non_follower_pct REAL DEFAULT 0,

            -- Viral score
            viral_score REAL DEFAULT 0,

            -- Son güncelleme
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(hook_type, topic_category, platform)
        )
    ''')

    # A/B Test Results tablosu - A/B test sonuçları
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ab_test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Test bilgisi
            post_id INTEGER,
            topic TEXT,
            platform TEXT,

            -- Variant A
            variant_a_hook_type TEXT,
            variant_a_tone TEXT,
            variant_a_score REAL,
            variant_a_text TEXT,

            -- Variant B
            variant_b_hook_type TEXT,
            variant_b_tone TEXT,
            variant_b_score REAL,
            variant_b_text TEXT,

            -- Sonuç
            winner TEXT,  -- A veya B
            margin REAL,  -- Skor farkı
            confidence TEXT,  -- high, medium, low
            reasoning TEXT,
            learning TEXT,

            -- Post-publish performance (sonradan güncellenir)
            actual_engagement_rate REAL,
            actual_save_rate REAL,
            prediction_accurate BOOLEAN,

            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Approval Audit Trail tablosu - Onay geçmişi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS approval_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- İçerik bilgisi
            post_id INTEGER,
            topic TEXT,
            content_type TEXT,  -- post, reels, carousel

            -- Karar bilgisi
            decision TEXT NOT NULL,  -- approved, rejected, scheduled, revised
            decision_by_user_id INTEGER,
            decision_by_username TEXT,

            -- Bağlam
            review_score REAL,
            reason TEXT,
            scheduler_mode TEXT,  -- manual, autonomous, scheduled

            -- Metadata
            previous_status TEXT,
            new_status TEXT,

            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Prompt History tablosu - Prompt tracking ve performans takibi
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompt_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            prompt_type TEXT NOT NULL,  -- 'video' veya 'image'
            prompt_text TEXT NOT NULL,
            prompt_style TEXT,  -- 'cinematic', 'documentary', 'pov', 'aerial', vb.

            -- Basit hash (duplicate check için)
            prompt_hash TEXT,

            -- Performans (sonradan güncellenir)
            reach INTEGER DEFAULT 0,
            engagement_rate REAL DEFAULT 0,
            likes INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            performance_updated_at TIMESTAMP,

            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Prompt history index'leri
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompt_hash ON prompt_history(prompt_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompt_style ON prompt_history(prompt_style)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompt_type ON prompt_history(prompt_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prompt_created ON prompt_history(created_at)')

    # Ad Campaigns tablosu - Meta Ads performans verileri
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ad_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,

            -- Meta IDs
            campaign_id TEXT,
            campaign_name TEXT,
            adset_id TEXT,
            adset_name TEXT,
            ad_id TEXT UNIQUE,
            ad_name TEXT,

            -- Performans metrikleri
            impressions INTEGER DEFAULT 0,
            reach INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            spend REAL DEFAULT 0.0,

            -- Aksiyonlar
            follows INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            engagements INTEGER DEFAULT 0,
            video_views INTEGER DEFAULT 0,

            -- Maliyetler
            cpc REAL DEFAULT 0.0,
            cpm REAL DEFAULT 0.0,
            cost_per_follow REAL DEFAULT 0.0,
            cost_per_save REAL DEFAULT 0.0,
            frequency REAL DEFAULT 0.0,

            -- Video metrikleri
            video_25_pct INTEGER DEFAULT 0,
            video_50_pct INTEGER DEFAULT 0,
            video_75_pct INTEGER DEFAULT 0,
            video_100_pct INTEGER DEFAULT 0,

            -- Tarihler
            date_start DATE,
            date_stop DATE,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')

    # Ad campaigns index'leri
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ad_campaign_id ON ad_campaigns(campaign_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ad_ad_id ON ad_campaigns(ad_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ad_synced ON ad_campaigns(synced_at)')

    conn.commit()

    # Analytics kolonlarını posts tablosuna ekle (migration)
    alter_statements = [
        "ALTER TABLE posts ADD COLUMN fb_reach INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN fb_likes INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN fb_comments INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN fb_shares INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN fb_engagement_rate REAL DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_reach INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_likes INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_comments INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_engagement_rate REAL DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN insights_updated_at TIMESTAMP",
        "ALTER TABLE posts ADD COLUMN post_text_ig TEXT",
        "ALTER TABLE posts ADD COLUMN post_text_fb TEXT",
        # Instagram Reels/Video metrikleri
        "ALTER TABLE posts ADD COLUMN ig_saves INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_shares INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_plays INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_avg_watch_time REAL DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_total_watch_time INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_reach_followers INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_reach_non_followers INTEGER DEFAULT 0",
        # Hook tracking
        "ALTER TABLE posts ADD COLUMN hook_type TEXT",
        "ALTER TABLE posts ADD COLUMN hook_text TEXT",
        "ALTER TABLE posts ADD COLUMN tone TEXT",
        # A/B testing
        "ALTER TABLE posts ADD COLUMN ab_test_id INTEGER",
        "ALTER TABLE posts ADD COLUMN is_ab_winner BOOLEAN",
        # Prompt tracking
        "ALTER TABLE posts ADD COLUMN video_prompt TEXT",
        "ALTER TABLE posts ADD COLUMN prompt_style TEXT",
        # Voice Reels (ElevenLabs TTS)
        "ALTER TABLE posts ADD COLUMN speech_script TEXT",
        "ALTER TABLE posts ADD COLUMN audio_path TEXT",
        "ALTER TABLE posts ADD COLUMN voice_id TEXT",
        "ALTER TABLE posts ADD COLUMN audio_duration REAL DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN voice_mode BOOLEAN DEFAULT 0",
        # Topic category tracking
        "ALTER TABLE posts ADD COLUMN topic_category TEXT",
        # Multi-segment video support
        "ALTER TABLE posts ADD COLUMN video_segment_count INTEGER DEFAULT 1",
        "ALTER TABLE posts ADD COLUMN total_video_duration REAL DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN segment_prompts TEXT",
        "ALTER TABLE posts ADD COLUMN video_model TEXT",
        # Viral Score v2 Metrikleri
        "ALTER TABLE posts ADD COLUMN ig_watch_time_pct REAL DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_replays INTEGER DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN ig_comment_rate REAL DEFAULT 0",
        "ALTER TABLE posts ADD COLUMN viral_score_v2 REAL DEFAULT 0"
    ]

    for stmt in alter_statements:
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

    # Strategy tablosu için migration
    strategy_migrations = [
        "ALTER TABLE strategy ADD COLUMN version INTEGER DEFAULT 1",
        "ALTER TABLE strategy ADD COLUMN best_hooks TEXT"
    ]

    for stmt in strategy_migrations:
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError:
            pass  # Kolon zaten var

    conn.commit()
    conn.close()
    print("✅ Database initialized")

# Varsayılan strateji oluştur
def create_default_strategy():
    """İlk stratejiyi oluştur (AI sonra güncelleyecek)"""
    conn = get_connection()
    cursor = conn.cursor()

    # Strateji var mı kontrol et
    cursor.execute("SELECT COUNT(*) FROM strategy")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO strategy (
                posts_per_week,
                best_days,
                best_hours,
                content_mix,
                visual_mix,
                insights
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            5,  # Haftada 5 post ile başla
            json.dumps(["monday", "tuesday", "wednesday", "thursday", "friday"]),
            json.dumps(["10:00", "14:00", "18:00"]),
            json.dumps({
                "egitici": 30,
                "tanitim": 25,
                "ipucu": 20,
                "haber": 15,
                "basari_hikayesi": 10
            }),
            json.dumps({
                "flux": 35,
                "infographic": 30,
                "gemini": 25,
                "video": 10
            }),
            json.dumps({
                "initialized": True,
                "learning_started": False,
                "total_posts_analyzed": 0
            })
        ))
        conn.commit()
        print("✅ Default strategy created")

    conn.close()

if __name__ == "__main__":
    init_database()
    create_default_strategy()
