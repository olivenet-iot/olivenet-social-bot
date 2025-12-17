"""
Database Models - SQLite ile içerik ve analitik takibi
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

DB_PATH = Path("/opt/olivenet-social-bot/data/content.db")

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
            visual_type TEXT,  -- infographic, gemini, flux, video
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
            avg_reach INTEGER DEFAULT 0
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
