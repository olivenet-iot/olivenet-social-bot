"""
Database CRUD Operations
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher
from .models import get_connection


# ============ VIRAL SCORE v2 CONFIGURATION ============

VIRAL_SCORE_WEIGHTS = {
    "save_rate": 2.0,
    "share_rate": 3.0,
    "comment_rate": 2.0,
    "engagement_rate": 1.0,
    "non_follower_pct": 0.01,
    "watch_time_pct": 0.015,
    "replay_bonus": 0.5,
    "content_multipliers": {
        "reels": 1.2, "video": 1.15, "carousel": 1.1, "post": 1.0
    },
    "hook_performance_bonus": {
        "top_performer": 0.2, "above_average": 0.1, "average": 0.0, "below_average": -0.1
    }
}

VIRAL_SCORE_THRESHOLDS = {
    "viral": 25.0, "high_performer": 15.0, "good": 8.0, "average": 4.0, "low": 0.0
}


def get_kktc_now() -> datetime:
    """
    KKTC saatini al (UTC+3)
    """
    return datetime.utcnow() + timedelta(hours=3)


# ============ POSTS ============

def create_post(
    topic: str,
    post_text: str = None,
    visual_type: Optional[str] = None,
    scheduled_at: Optional[datetime] = None,
    platform: str = "both",
    post_text_ig: str = None,
    post_text_fb: str = None,
    topic_category: str = None,
    hook_type: str = None,
    voice_mode: bool = False
) -> int:
    """Yeni post oluştur - platform-specific text destekli"""
    conn = get_connection()
    cursor = conn.cursor()

    # post_text yoksa post_text_fb, o da yoksa topic kullan (NULL olamaz)
    final_post_text = post_text if post_text else (post_text_fb if post_text_fb else topic)

    cursor.execute('''
        INSERT INTO posts (topic, post_text, visual_type, scheduled_at, platform, status, post_text_ig, post_text_fb, topic_category, hook_type, voice_mode)
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)
    ''', (topic, final_post_text, visual_type, scheduled_at, platform, post_text_ig, post_text_fb, topic_category, hook_type, voice_mode))

    post_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return post_id

def update_post(post_id: int, **kwargs) -> bool:
    """Post güncelle"""
    conn = get_connection()
    cursor = conn.cursor()

    valid_fields = [
        'topic', 'post_text', 'visual_type', 'visual_path', 'visual_prompt',
        'status', 'rejection_reason', 'scheduled_at', 'published_at',
        'facebook_post_id', 'instagram_post_id', 'orchestrator_notes',
        'reviewer_feedback', 'revision_count', 'post_text_ig', 'post_text_fb',
        # Hook & A/B tracking
        'hook_type', 'hook_text', 'tone', 'ab_test_id', 'is_ab_winner',
        # Voice Reels (ElevenLabs TTS)
        'speech_script', 'audio_path', 'voice_id', 'audio_duration', 'voice_mode',
        # Topic category
        'topic_category',
        # Multi-segment video
        'video_segment_count', 'total_video_duration', 'segment_prompts', 'video_model'
    ]

    updates = []
    values = []
    for key, value in kwargs.items():
        if key in valid_fields:
            updates.append(f"{key} = ?")
            values.append(value)

    if updates:
        values.append(post_id)
        cursor.execute(f'''
            UPDATE posts SET {", ".join(updates)} WHERE id = ?
        ''', values)
        conn.commit()

    conn.close()
    return True

def get_post(post_id: int) -> Optional[Dict]:
    """Post getir"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_posts_by_status(status: str, limit: int = 10) -> List[Dict]:
    """Duruma göre postları getir"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC LIMIT ?",
        (status, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_scheduled_posts(from_date: datetime, to_date: datetime) -> List[Dict]:
    """Tarih aralığındaki planlanmış postları getir"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM posts
        WHERE scheduled_at BETWEEN ? AND ?
        AND status IN ('scheduled', 'approved')
        ORDER BY scheduled_at ASC
    ''', (from_date, to_date))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_published_posts(days: int = 30) -> List[Dict]:
    """Son X günün yayınlanmış postlarını getir"""
    conn = get_connection()
    cursor = conn.cursor()
    since = datetime.now() - timedelta(days=days)
    cursor.execute('''
        SELECT * FROM posts
        WHERE status = 'published' AND published_at > ?
        ORDER BY published_at DESC
    ''', (since,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============ ANALYTICS ============

def record_analytics(
    post_id: int,
    views: int = 0,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
    clicks: int = 0,
    reach: int = 0
) -> int:
    """Analitik kaydet"""
    conn = get_connection()
    cursor = conn.cursor()

    # Engagement rate hesapla
    total_engagement = likes + comments + shares + clicks
    engagement_rate = (total_engagement / reach * 100) if reach > 0 else 0

    cursor.execute('''
        INSERT INTO analytics (post_id, views, likes, comments, shares, clicks, reach, engagement_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (post_id, views, likes, comments, shares, clicks, reach, engagement_rate))

    analytics_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return analytics_id

def get_post_analytics(post_id: int) -> List[Dict]:
    """Post'un analitiklerini getir"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM analytics WHERE post_id = ? ORDER BY recorded_at DESC",
        (post_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_analytics_summary(days: int = 30) -> Dict:
    """
    Son X günün analitik özeti.
    NOT: posts tablosundaki ig_* alanlarından okur (analytics tablosu değil).
    """
    conn = get_connection()
    cursor = conn.cursor()
    since = datetime.now() - timedelta(days=days)

    # Posts tablosundan Instagram metriklerini çek
    cursor.execute('''
        SELECT
            COUNT(*) as total_posts,
            SUM(COALESCE(ig_reach, 0)) as total_reach,
            SUM(COALESCE(ig_likes, 0)) as total_likes,
            SUM(COALESCE(ig_comments, 0)) as total_comments,
            SUM(COALESCE(ig_saves, 0)) as total_saves,
            SUM(COALESCE(ig_shares, 0)) as total_shares,
            SUM(COALESCE(ig_plays, 0)) as total_plays,
            AVG(CASE WHEN ig_reach >= 10 THEN ig_engagement_rate ELSE NULL END) as avg_engagement_rate,
            AVG(CASE WHEN ig_reach > 0 THEN ig_reach ELSE NULL END) as avg_reach,
            AVG(CASE WHEN ig_reach > 0 THEN ig_saves ELSE NULL END) as avg_saves,
            AVG(CASE WHEN ig_reach > 0 THEN ig_shares ELSE NULL END) as avg_shares,
            AVG(CASE WHEN ig_avg_watch_time > 0 THEN ig_avg_watch_time ELSE NULL END) as avg_watch_time
        FROM posts
        WHERE status = 'published'
        AND published_at > ?
    ''', (since,))

    row = cursor.fetchone()
    conn.close()

    if row:
        result = dict(row)
        # Legacy uyumluluk için views = reach
        result['total_views'] = result.get('total_reach', 0)

        # Save rate ve share rate hesapla (kalite göstergesi)
        total_reach = result.get('total_reach', 0) or 0
        total_saves = result.get('total_saves', 0) or 0
        total_shares = result.get('total_shares', 0) or 0
        if total_reach > 0:
            result['save_rate'] = round((total_saves / total_reach) * 100, 2)
            result['share_rate'] = round((total_shares / total_reach) * 100, 2)
        else:
            result['save_rate'] = 0.0
            result['share_rate'] = 0.0

        return result
    return {}

# ============ STRATEGY ============

def get_current_strategy() -> Dict:
    """Mevcut stratejiyi getir"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        strategy = dict(row)
        # JSON alanları parse et
        for field in ['best_days', 'best_hours', 'content_mix', 'visual_mix', 'insights', 'best_hooks']:
            if strategy.get(field):
                try:
                    strategy[field] = json.loads(strategy[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return strategy
    return {}


def get_strategy_version() -> int:
    """Mevcut strateji version'ını getir (feedback loop için)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM strategy ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row['version'] if row and row['version'] else 1

def update_strategy(**kwargs) -> int:
    """
    Stratejiyi güncelle ve version'ı increment et.
    Returns: Yeni version numarası (feedback loop için)
    """
    conn = get_connection()
    cursor = conn.cursor()

    # JSON alanları serialize et
    for field in ['best_days', 'best_hours', 'content_mix', 'visual_mix', 'insights', 'best_hooks']:
        if field in kwargs and isinstance(kwargs[field], (dict, list)):
            kwargs[field] = json.dumps(kwargs[field])

    # Mevcut strateji ID ve version'ını al
    cursor.execute("SELECT id, version FROM strategy ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()

    new_version = 1
    if row:
        strategy_id = row['id']
        current_version = row['version'] or 1
        new_version = current_version + 1

        updates = []
        values = []
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)

        # Version ve updated_at her zaman güncellenir
        updates.append("version = ?")
        values.append(new_version)
        updates.append("updated_at = ?")
        values.append(datetime.now())
        values.append(strategy_id)

        cursor.execute(f'''
            UPDATE strategy SET {", ".join(updates)} WHERE id = ?
        ''', values)
        conn.commit()

    conn.close()
    return new_version

# ============ CONTENT CALENDAR ============

def create_calendar_entry(
    week_start: datetime,
    day_of_week: int,
    scheduled_time: str,
    topic_category: str,
    topic_suggestion: str,
    visual_type_suggestion: str
) -> int:
    """Takvim girişi oluştur"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO content_calendar
        (week_start, day_of_week, scheduled_time, topic_category, topic_suggestion, visual_type_suggestion)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (week_start, day_of_week, scheduled_time, topic_category, topic_suggestion, visual_type_suggestion))

    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id

def get_week_calendar(week_start: datetime) -> List[Dict]:
    """Haftanın takvimini getir"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM content_calendar
        WHERE week_start = ?
        ORDER BY day_of_week, scheduled_time
    ''', (week_start,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_todays_calendar(day_of_week: int = None) -> List[Dict]:
    """Bugünün takvim girişlerini getir"""
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now()

    if day_of_week is None:
        day_of_week = today.weekday()

    week_start = today - timedelta(days=today.weekday())

    cursor.execute('''
        SELECT * FROM content_calendar
        WHERE week_start = DATE(?) AND day_of_week = ? AND status != 'published'
        ORDER BY scheduled_time
    ''', (week_start.date(), day_of_week))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_calendar_status(calendar_id: int, status: str, post_id: int = None):
    """Calendar entry durumunu güncelle"""
    conn = get_connection()
    cursor = conn.cursor()

    if post_id:
        cursor.execute('''
            UPDATE content_calendar
            SET status = ?, post_id = ?
            WHERE id = ?
        ''', (status, post_id, calendar_id))
    else:
        cursor.execute('''
            UPDATE content_calendar
            SET status = ?
            WHERE id = ?
        ''', (status, calendar_id))

    conn.commit()
    conn.close()

# ============ AGENT LOGS ============

def log_agent_action(
    agent_name: str,
    action: str,
    input_data: Dict = None,
    output_data: Dict = None,
    success: bool = True,
    error_message: str = None
):
    """Agent aktivitesini logla"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO agent_logs (agent_name, action, input_data, output_data, success, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        agent_name,
        action,
        json.dumps(input_data) if input_data else None,
        json.dumps(output_data) if output_data else None,
        success,
        error_message
    ))

    conn.commit()
    conn.close()

def get_agent_logs(agent_name: str = None, limit: int = 50) -> List[Dict]:
    """Agent loglarını getir"""
    conn = get_connection()
    cursor = conn.cursor()

    if agent_name:
        cursor.execute(
            "SELECT * FROM agent_logs WHERE agent_name = ? ORDER BY timestamp DESC LIMIT ?",
            (agent_name, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM agent_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ============ ANALYTICS ============

def update_post_analytics(post_id: int, analytics: dict):
    """Post analytics verilerini güncelle"""
    conn = get_connection()
    cursor = conn.cursor()

    updates = []
    values = []

    # Desteklenen analytics alanları
    allowed_fields = [
        # Facebook
        'fb_reach', 'fb_likes', 'fb_comments', 'fb_shares', 'fb_engagement_rate',
        # Instagram temel
        'ig_reach', 'ig_likes', 'ig_comments', 'ig_engagement_rate',
        # Instagram Reels/Video
        'ig_saves', 'ig_shares', 'ig_plays',
        'ig_avg_watch_time', 'ig_total_watch_time',
        'ig_reach_followers', 'ig_reach_non_followers'
    ]

    for key, value in analytics.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)

    if updates:
        updates.append("insights_updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(post_id)

        query = f"UPDATE posts SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()

    conn.close()


def get_posts_with_analytics(days: int = 30) -> List[Dict]:
    """Analytics verileri ile postları al"""
    conn = get_connection()
    cursor = conn.cursor()

    since = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT id, topic, visual_type, status,
               facebook_post_id, instagram_post_id,
               fb_reach, fb_likes, fb_comments, fb_shares, fb_engagement_rate,
               ig_reach, ig_likes, ig_comments, ig_engagement_rate,
               published_at, insights_updated_at
        FROM posts
        WHERE status = 'published' AND published_at > ?
        ORDER BY published_at DESC
    """, (since,))

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    return [dict(zip(columns, row)) for row in rows]


# ============ HOOK PERFORMANCE ============

def calculate_viral_score_v2(
    reach: int,
    saves: int,
    shares: int,
    comments: int,
    likes: int,
    engagement_rate: float,
    non_follower_pct: float,
    watch_time_pct: float = 0,
    replays: int = 0,
    content_type: str = "post",
    hook_type: str = None
) -> dict:
    """
    Viral Score v2 hesapla - Comment rate ve watch time dahil.

    Formula:
    base_score = save_rate×2 + share_rate×3 + comment_rate×2 + engagement_rate +
                 non_follower_pct×0.01 + watch_time_pct×0.015 + replay_bonus
    final_score = base_score × content_multiplier × (1 + hook_bonus)
    """
    w = VIRAL_SCORE_WEIGHTS

    # Rate hesaplamaları
    save_rate = (saves / reach * 100) if reach > 0 else 0
    share_rate = (shares / reach * 100) if reach > 0 else 0
    comment_rate = (comments / reach * 100) if reach > 0 else 0

    # Replay bonus (replays / plays oranına göre)
    replay_bonus = min(replays / (reach / 10), 5) * w["replay_bonus"] if reach > 0 else 0

    # Base score hesapla
    base_score = (
        save_rate * w["save_rate"] +
        share_rate * w["share_rate"] +
        comment_rate * w["comment_rate"] +
        engagement_rate * w["engagement_rate"] +
        non_follower_pct * w["non_follower_pct"] +
        watch_time_pct * w["watch_time_pct"] +
        replay_bonus
    )

    # Content type multiplier
    content_mult = w["content_multipliers"].get(content_type, 1.0)

    # Hook performance bonus (gelecekte DB'den çekilecek)
    hook_bonus = 0
    if hook_type:
        # Default olarak average kabul et
        hook_bonus = w["hook_performance_bonus"].get("average", 0)

    # Final score
    viral_score = base_score * content_mult * (1 + hook_bonus)

    # Tier belirleme
    tier = "low"
    for tier_name, threshold in sorted(VIRAL_SCORE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if viral_score >= threshold:
            tier = tier_name
            break

    # Recommendations
    recommendations = []
    if save_rate < 2:
        recommendations.append("Save trigger ekle - değerli içerik vurgusu yap")
    if share_rate < 1:
        recommendations.append("Paylaşım hook'u ekle - 'arkadaşını etiketle' CTA")
    if comment_rate < 1:
        recommendations.append("Yorum CTA'sı güçlendir - soru veya poll ekle")
    if watch_time_pct < 50 and content_type in ["reels", "video"]:
        recommendations.append("Watch time düşük - hook'u güçlendir, pattern interrupt ekle")
    if non_follower_pct < 20:
        recommendations.append("Discovery düşük - hashtag ve hook stratejisini değiştir")

    return {
        "viral_score_v2": round(viral_score, 2),
        "tier": tier,
        "breakdown": {
            "save_contribution": round(save_rate * w["save_rate"], 2),
            "share_contribution": round(share_rate * w["share_rate"], 2),
            "comment_contribution": round(comment_rate * w["comment_rate"], 2),
            "engagement_contribution": round(engagement_rate * w["engagement_rate"], 2),
            "non_follower_contribution": round(non_follower_pct * w["non_follower_pct"], 2),
            "watch_time_contribution": round(watch_time_pct * w["watch_time_pct"], 2),
            "replay_bonus": round(replay_bonus, 2),
            "content_multiplier": content_mult,
            "base_score": round(base_score, 2)
        },
        "rates": {
            "save_rate": round(save_rate, 2),
            "share_rate": round(share_rate, 2),
            "comment_rate": round(comment_rate, 2)
        },
        "recommendations": recommendations
    }


def update_hook_performance(
    hook_type: str,
    topic_category: str,
    platform: str,
    reach: int,
    engagement: int,
    saves: int = 0,
    shares: int = 0,
    comments: int = 0,
    likes: int = 0,
    engagement_rate: float = 0,
    save_rate: float = 0,
    share_rate: float = 0,
    comment_rate: float = 0,
    non_follower_pct: float = 0,
    watch_time_pct: float = 0,
    replays: int = 0,
    content_type: str = "post"
):
    """Hook performance metriklerini güncelle veya oluştur - Viral Score v2"""
    conn = get_connection()
    cursor = conn.cursor()

    # Mevcut kaydı kontrol et
    cursor.execute('''
        SELECT id, usage_count, total_reach, total_engagement, total_saves, total_shares
        FROM hook_performance
        WHERE hook_type = ? AND topic_category = ? AND platform = ?
    ''', (hook_type, topic_category, platform))

    row = cursor.fetchone()

    # Viral Score v2 hesapla
    viral_result = calculate_viral_score_v2(
        reach=reach,
        saves=saves,
        shares=shares,
        comments=comments,
        likes=likes,
        engagement_rate=engagement_rate,
        non_follower_pct=non_follower_pct,
        watch_time_pct=watch_time_pct,
        replays=replays,
        content_type=content_type,
        hook_type=hook_type
    )
    viral_score = viral_result["viral_score_v2"]

    if row:
        # Güncelle
        new_count = row['usage_count'] + 1
        new_reach = row['total_reach'] + reach
        new_engagement = row['total_engagement'] + engagement
        new_saves = row['total_saves'] + saves
        new_shares = row['total_shares'] + shares

        cursor.execute('''
            UPDATE hook_performance SET
                usage_count = ?,
                total_reach = ?,
                total_engagement = ?,
                total_saves = ?,
                total_shares = ?,
                avg_engagement_rate = ?,
                avg_save_rate = ?,
                avg_share_rate = ?,
                avg_non_follower_pct = ?,
                viral_score = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            new_count, new_reach, new_engagement, new_saves, new_shares,
            engagement_rate, save_rate, share_rate, non_follower_pct,
            viral_score, row['id']
        ))
    else:
        # Yeni kayıt oluştur
        cursor.execute('''
            INSERT INTO hook_performance (
                hook_type, topic_category, platform,
                usage_count, total_reach, total_engagement, total_saves, total_shares,
                avg_engagement_rate, avg_save_rate, avg_share_rate, avg_non_follower_pct,
                viral_score
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            hook_type, topic_category, platform,
            reach, engagement, saves, shares,
            engagement_rate, save_rate, share_rate, non_follower_pct,
            viral_score
        ))

    conn.commit()
    conn.close()

    return viral_result


def get_best_performing_hooks(limit: int = 5) -> List[Dict]:
    """En iyi performans gösteren hook type'ları getir"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT hook_type, topic_category, platform,
               usage_count, avg_engagement_rate, avg_save_rate, avg_share_rate,
               viral_score
        FROM hook_performance
        WHERE usage_count >= 3
        ORDER BY viral_score DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_viral_score_leaderboard(days: int = 30, limit: int = 10) -> List[Dict]:
    """En yüksek viral score'a sahip postları getir"""
    conn = get_connection()
    cursor = conn.cursor()

    since = get_kktc_now() - timedelta(days=days)

    cursor.execute('''
        SELECT
            p.id,
            p.topic,
            p.hook_type,
            p.visual_type,
            p.topic_category,
            p.published_at,
            p.ig_reach,
            p.ig_saves,
            p.ig_shares,
            p.ig_comments,
            p.ig_likes,
            p.ig_engagement_rate,
            p.ig_watch_time_pct,
            p.ig_replays,
            COALESCE(p.viral_score_v2, 0) as viral_score_v2,
            CASE
                WHEN COALESCE(p.viral_score_v2, 0) >= 25 THEN 'viral'
                WHEN COALESCE(p.viral_score_v2, 0) >= 15 THEN 'high_performer'
                WHEN COALESCE(p.viral_score_v2, 0) >= 8 THEN 'good'
                WHEN COALESCE(p.viral_score_v2, 0) >= 4 THEN 'average'
                ELSE 'low'
            END as tier
        FROM posts p
        WHERE p.status = 'published'
          AND p.published_at > ?
          AND p.ig_reach > 0
        ORDER BY viral_score_v2 DESC
        LIMIT ?
    ''', (since, limit))

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    results = []
    for row in rows:
        post_data = dict(zip(columns, row))

        # Viral Score v2 hesapla (eğer kayıtlı değilse)
        if not post_data.get("viral_score_v2") and post_data.get("ig_reach", 0) > 0:
            viral_result = calculate_viral_score_v2(
                reach=post_data.get("ig_reach", 0),
                saves=post_data.get("ig_saves", 0),
                shares=post_data.get("ig_shares", 0),
                comments=post_data.get("ig_comments", 0),
                likes=post_data.get("ig_likes", 0),
                engagement_rate=post_data.get("ig_engagement_rate", 0),
                non_follower_pct=0,
                watch_time_pct=post_data.get("ig_watch_time_pct", 0),
                replays=post_data.get("ig_replays", 0),
                content_type=post_data.get("visual_type", "post"),
                hook_type=post_data.get("hook_type")
            )
            post_data["viral_score_v2"] = viral_result["viral_score_v2"]
            post_data["tier"] = viral_result["tier"]
            post_data["breakdown"] = viral_result["breakdown"]
            post_data["recommendations"] = viral_result["recommendations"]

        results.append(post_data)

    return results


def update_post_viral_score(post_id: int) -> dict:
    """Post için viral score v2 hesapla ve kaydet"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ig_reach, ig_saves, ig_shares, ig_comments, ig_likes,
               ig_engagement_rate, ig_watch_time_pct, ig_replays,
               ig_reach_non_followers, ig_reach, visual_type, hook_type
        FROM posts WHERE id = ?
    ''', (post_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return {}

    # Non-follower yüzdesi hesapla
    non_follower_pct = 0
    if row['ig_reach'] and row['ig_reach'] > 0:
        non_followers = row['ig_reach_non_followers'] or 0
        non_follower_pct = (non_followers / row['ig_reach']) * 100

    viral_result = calculate_viral_score_v2(
        reach=row['ig_reach'] or 0,
        saves=row['ig_saves'] or 0,
        shares=row['ig_shares'] or 0,
        comments=row['ig_comments'] or 0,
        likes=row['ig_likes'] or 0,
        engagement_rate=row['ig_engagement_rate'] or 0,
        non_follower_pct=non_follower_pct,
        watch_time_pct=row['ig_watch_time_pct'] or 0,
        replays=row['ig_replays'] or 0,
        content_type=row['visual_type'] or "post",
        hook_type=row['hook_type']
    )

    # Kaydet
    cursor.execute('''
        UPDATE posts SET
            viral_score_v2 = ?,
            ig_comment_rate = ?
        WHERE id = ?
    ''', (
        viral_result["viral_score_v2"],
        viral_result["rates"]["comment_rate"],
        post_id
    ))

    conn.commit()
    conn.close()

    return viral_result


def get_hook_performance_by_type(hook_type: str) -> Dict:
    """Belirli hook type'ın performansını getir"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT hook_type,
               SUM(usage_count) as total_usage,
               AVG(avg_engagement_rate) as avg_engagement,
               AVG(avg_save_rate) as avg_save,
               AVG(viral_score) as avg_viral_score
        FROM hook_performance
        WHERE hook_type = ?
        GROUP BY hook_type
    ''', (hook_type,))

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


def get_hook_recommendations(topic_category: str = None, platform: str = None) -> List[str]:
    """Kategori ve platforma göre hook önerileri getir"""
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT hook_type, AVG(viral_score) as score
        FROM hook_performance
        WHERE usage_count >= 2
    '''
    params = []

    if topic_category:
        query += " AND topic_category = ?"
        params.append(topic_category)

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    query += " GROUP BY hook_type ORDER BY score DESC LIMIT 3"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [row['hook_type'] for row in rows]


def get_hook_weights_for_selection(platform: str = None) -> Dict[str, float]:
    """
    Hook type'ları için ağırlık değerleri hesapla (weighted random selection için).

    Yüksek viral score = yüksek ağırlık = daha sık seçilme
    Minimum 3 kullanım gereken hook'lar dahil edilir.

    Returns:
        Dict[str, float]: hook_type -> weight mapping
        Example: {"statistic": 0.25, "question": 0.20, ...}
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT hook_type,
               SUM(usage_count) as total_usage,
               AVG(viral_score) as avg_viral_score,
               AVG(avg_engagement_rate) as avg_engagement
        FROM hook_performance
        WHERE usage_count >= 1
    '''
    params = []

    if platform:
        query += " AND platform = ?"
        params.append(platform)

    query += " GROUP BY hook_type HAVING SUM(usage_count) >= 2"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        # Veri yoksa eşit ağırlıklar döndür
        default_hooks = [
            "statistic", "question", "bold_claim", "problem", "value",
            "fear", "before_after", "list", "comparison", "local"
        ]
        return {hook: 1.0 / len(default_hooks) for hook in default_hooks}

    # Viral score'a göre ağırlık hesapla
    weights = {}
    total_score = sum(max(row['avg_viral_score'] or 0, 0.1) for row in rows)

    for row in rows:
        hook_type = row['hook_type']
        score = max(row['avg_viral_score'] or 0, 0.1)  # Minimum 0.1
        weights[hook_type] = score / total_score if total_score > 0 else 0.1

    # Eksik hook'ları düşük ağırlıkla ekle
    all_hooks = [
        "statistic", "question", "bold_claim", "problem", "value",
        "fear", "before_after", "list", "comparison", "local"
    ]

    for hook in all_hooks:
        if hook not in weights:
            weights[hook] = 0.05  # Yeni/denenmemiş hook'lara düşük ağırlık

    # Normalize et
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    return weights


def get_underperforming_hooks(threshold_viral: float = 5.0) -> List[str]:
    """
    Düşük performans gösteren hook type'larını getir (kaçınılması gereken).

    Args:
        threshold_viral: Bu değerin altında viral score olan hook'lar

    Returns:
        List[str]: Düşük performanslı hook type listesi
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT hook_type, AVG(viral_score) as avg_viral
        FROM hook_performance
        WHERE usage_count >= 3
        GROUP BY hook_type
        HAVING avg_viral < ?
    ''', (threshold_viral,))

    rows = cursor.fetchall()
    conn.close()

    return [row['hook_type'] for row in rows]


# ============ A/B TEST RESULTS ============

def log_ab_test_result(
    topic: str,
    platform: str,
    variant_a: Dict,
    variant_b: Dict,
    winner: str,
    margin: float,
    confidence: str,
    reasoning: str,
    learning: str,
    post_id: int = None
) -> int:
    """A/B test sonucunu kaydet"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO ab_test_results (
            post_id, topic, platform,
            variant_a_hook_type, variant_a_tone, variant_a_score, variant_a_text,
            variant_b_hook_type, variant_b_tone, variant_b_score, variant_b_text,
            winner, margin, confidence, reasoning, learning
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        post_id, topic, platform,
        variant_a.get('hook_type'), variant_a.get('tone'), variant_a.get('score'), variant_a.get('text'),
        variant_b.get('hook_type'), variant_b.get('tone'), variant_b.get('score'), variant_b.get('text'),
        winner, margin, confidence, reasoning, learning
    ))

    test_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return test_id


def update_ab_test_actual_performance(
    test_id: int,
    actual_engagement_rate: float,
    actual_save_rate: float
):
    """A/B test sonrasında gerçek performansı güncelle"""
    conn = get_connection()
    cursor = conn.cursor()

    # Önce winner'ın predicted score'unu al
    cursor.execute('''
        SELECT winner, variant_a_score, variant_b_score
        FROM ab_test_results
        WHERE id = ?
    ''', (test_id,))

    row = cursor.fetchone()
    if row:
        winner_score = row['variant_a_score'] if row['winner'] == 'A' else row['variant_b_score']
        # Prediction doğru mu? (winner yüksek performans gösterdiyse)
        prediction_accurate = actual_engagement_rate >= winner_score * 0.7  # %70 tolerans

        cursor.execute('''
            UPDATE ab_test_results SET
                actual_engagement_rate = ?,
                actual_save_rate = ?,
                prediction_accurate = ?
            WHERE id = ?
        ''', (actual_engagement_rate, actual_save_rate, prediction_accurate, test_id))

        conn.commit()

    conn.close()


def get_ab_test_results(days: int = 30, limit: int = 20) -> List[Dict]:
    """Son A/B test sonuçlarını getir"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT *
        FROM ab_test_results
        WHERE created_at > datetime('now', ? || ' days')
        ORDER BY created_at DESC
        LIMIT ?
    ''', (f'-{days}', limit))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_ab_test_learnings() -> Dict:
    """A/B testlerden öğrenilen pattern'ları analiz et"""
    conn = get_connection()
    cursor = conn.cursor()

    # Hook type win rates
    cursor.execute('''
        SELECT
            variant_a_hook_type as hook_type,
            COUNT(*) as times_tested,
            SUM(CASE WHEN winner = 'A' THEN 1 ELSE 0 END) as wins
        FROM ab_test_results
        GROUP BY variant_a_hook_type
        UNION ALL
        SELECT
            variant_b_hook_type as hook_type,
            COUNT(*) as times_tested,
            SUM(CASE WHEN winner = 'B' THEN 1 ELSE 0 END) as wins
        FROM ab_test_results
        GROUP BY variant_b_hook_type
    ''')

    hook_stats = {}
    for row in cursor.fetchall():
        hook = row['hook_type']
        if hook not in hook_stats:
            hook_stats[hook] = {'tested': 0, 'wins': 0}
        hook_stats[hook]['tested'] += row['times_tested']
        hook_stats[hook]['wins'] += row['wins']

    # Win rate hesapla
    for hook, stats in hook_stats.items():
        stats['win_rate'] = (stats['wins'] / stats['tested'] * 100) if stats['tested'] > 0 else 0

    # En çok kazanan hook'lar
    best_hooks = sorted(
        hook_stats.items(),
        key=lambda x: (x[1]['win_rate'], x[1]['tested']),
        reverse=True
    )[:5]

    # Prediction accuracy
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN prediction_accurate = 1 THEN 1 ELSE 0 END) as accurate
        FROM ab_test_results
        WHERE prediction_accurate IS NOT NULL
    ''')

    accuracy_row = cursor.fetchone()
    accuracy = (accuracy_row['accurate'] / accuracy_row['total'] * 100) if accuracy_row['total'] > 0 else 0

    conn.close()

    return {
        'hook_performance': {h: s for h, s in best_hooks},
        'total_tests': sum(s['tested'] for s in hook_stats.values()) // 2,
        'prediction_accuracy': round(accuracy, 2),
        'top_hooks': [h for h, _ in best_hooks[:3]]
    }


# ============ APPROVAL AUDIT TRAIL ============

def log_approval_decision(
    post_id: int,
    decision: str,  # approved, rejected, scheduled, revised
    user_id: int = None,
    username: str = None,
    topic: str = None,
    content_type: str = None,
    review_score: float = None,
    reason: str = None,
    scheduler_mode: str = "manual",  # manual, autonomous, scheduled
    previous_status: str = None,
    new_status: str = None
) -> int:
    """
    Onay kararını audit trail'e kaydet.

    Args:
        post_id: İlgili post ID
        decision: Karar (approved, rejected, scheduled, revised)
        user_id: Karar veren kullanıcı ID
        username: Karar veren kullanıcı adı
        topic: Post konusu
        content_type: İçerik tipi (post, reels, carousel)
        review_score: Reviewer puanı
        reason: Red veya revizyon nedeni
        scheduler_mode: Zamanlama modu
        previous_status: Önceki durum
        new_status: Yeni durum

    Returns:
        Oluşturulan log ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO approval_logs (
            post_id, topic, content_type,
            decision, decision_by_user_id, decision_by_username,
            review_score, reason, scheduler_mode,
            previous_status, new_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        post_id, topic, content_type,
        decision, user_id, username,
        review_score, reason, scheduler_mode,
        previous_status, new_status
    ))

    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return log_id


def get_approval_history(post_id: int = None, days: int = 30, limit: int = 50) -> List[Dict]:
    """
    Onay geçmişini getir.

    Args:
        post_id: Belirli bir post için (opsiyonel)
        days: Son kaç gün
        limit: Maksimum kayıt sayısı
    """
    conn = get_connection()
    cursor = conn.cursor()

    if post_id:
        cursor.execute('''
            SELECT * FROM approval_logs
            WHERE post_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (post_id, limit))
    else:
        cursor.execute('''
            SELECT * FROM approval_logs
            WHERE created_at > datetime('now', ? || ' days')
            ORDER BY created_at DESC
            LIMIT ?
        ''', (f'-{days}', limit))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_approval_stats(days: int = 30) -> Dict[str, Any]:
    """
    Onay istatistiklerini getir.

    Returns:
        Approval/rejection rates, top approvers, common rejection reasons
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Genel istatistikler
    cursor.execute('''
        SELECT
            decision,
            COUNT(*) as count
        FROM approval_logs
        WHERE created_at > datetime('now', ? || ' days')
        GROUP BY decision
    ''', (f'-{days}',))

    decision_counts = {row['decision']: row['count'] for row in cursor.fetchall()}

    # Kullanıcı bazında onay sayıları
    cursor.execute('''
        SELECT
            decision_by_username,
            COUNT(*) as total,
            SUM(CASE WHEN decision = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN decision = 'rejected' THEN 1 ELSE 0 END) as rejected
        FROM approval_logs
        WHERE created_at > datetime('now', ? || ' days')
          AND decision_by_username IS NOT NULL
        GROUP BY decision_by_username
        ORDER BY total DESC
        LIMIT 10
    ''', (f'-{days}',))

    user_stats = [dict(row) for row in cursor.fetchall()]

    # Mod bazında dağılım
    cursor.execute('''
        SELECT
            scheduler_mode,
            COUNT(*) as count
        FROM approval_logs
        WHERE created_at > datetime('now', ? || ' days')
        GROUP BY scheduler_mode
    ''', (f'-{days}',))

    mode_counts = {row['scheduler_mode']: row['count'] for row in cursor.fetchall()}

    conn.close()

    total = sum(decision_counts.values())
    return {
        'total_decisions': total,
        'decision_breakdown': decision_counts,
        'approval_rate': round(decision_counts.get('approved', 0) / total * 100, 2) if total > 0 else 0,
        'rejection_rate': round(decision_counts.get('rejected', 0) / total * 100, 2) if total > 0 else 0,
        'user_stats': user_stats,
        'mode_breakdown': mode_counts,
        'period_days': days
    }


# ============ TELEGRAM BOT HELPER FUNCTIONS ============

def get_todays_summary() -> Dict[str, int]:
    """
    Bugünün içerik özeti - yayınlanan, bekleyen, başarısız post sayıları.

    Returns:
        Dict with keys: published, scheduled, failed, draft
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Bugünün başlangıcı
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    cursor.execute('''
        SELECT
            status,
            COUNT(*) as count
        FROM posts
        WHERE (
            (status = 'published' AND DATE(published_at) = DATE('now'))
            OR (status = 'scheduled' AND DATE(scheduled_at) = DATE('now'))
            OR (status = 'failed' AND DATE(created_at) = DATE('now'))
            OR (status = 'draft' AND DATE(created_at) = DATE('now'))
        )
        GROUP BY status
    ''')

    rows = cursor.fetchall()
    conn.close()

    result = {'published': 0, 'scheduled': 0, 'failed': 0, 'draft': 0}
    for row in rows:
        if row['status'] in result:
            result[row['status']] = row['count']

    return result


def get_weekly_progress() -> Dict[str, Any]:
    """
    Bu haftanın içerik ilerleme durumu - hedeflere göre.

    Returns:
        Dict with keys: total, reels, carousel, post (actual counts)
        and targets: reels_target, carousel_target, post_target
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Bu haftanın başlangıcı (Pazartesi)
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    cursor.execute('''
        SELECT
            visual_type,
            COUNT(*) as count
        FROM posts
        WHERE status = 'published'
          AND published_at >= ?
        GROUP BY visual_type
    ''', (week_start,))

    rows = cursor.fetchall()
    conn.close()

    # İçerik tiplerine göre say
    counts = {'reels': 0, 'carousel': 0, 'post': 0, 'flux': 0}
    for row in rows:
        vtype = (row['visual_type'] or 'post').lower()
        if vtype in counts:
            counts[vtype] = row['count']
        elif vtype == 'flux':
            counts['post'] += row['count']  # flux = post

    # Post ve flux'u birleştir
    post_count = counts['post'] + counts.get('flux', 0)

    return {
        'total': sum(counts.values()),
        'reels': counts['reels'],
        'carousel': counts['carousel'],
        'post': post_count,
        # Config hedefleri (hardcoded - config import döngüsel olabilir)
        'reels_target': 7,
        'carousel_target': 2,
        'post_target': 3,
        'total_target': 12,
        'week_start': week_start.strftime('%Y-%m-%d')
    }


def get_next_scheduled() -> Optional[Dict]:
    """
    Sıradaki planlanmış içerik.

    Returns:
        Dict with post details or None if no scheduled content
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now()

    cursor.execute('''
        SELECT id, topic, visual_type, status, scheduled_at, platform
        FROM posts
        WHERE status IN ('scheduled', 'approved')
          AND scheduled_at > ?
        ORDER BY scheduled_at ASC
        LIMIT 1
    ''', (now,))

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_best_performing_content(days: int = 7) -> Optional[Dict]:
    """
    Belirtilen süre içindeki en iyi performans gösteren içerik.

    Sıralama: ig_engagement_rate > ig_reach > fb_engagement_rate

    Args:
        days: Kaç gün geriye bakılacak

    Returns:
        Dict with post details and metrics, or None
    """
    conn = get_connection()
    cursor = conn.cursor()

    since = datetime.now() - timedelta(days=days)

    cursor.execute('''
        SELECT
            id, topic, visual_type,
            ig_reach, ig_likes, ig_comments, ig_engagement_rate,
            ig_saves, ig_shares,
            fb_reach, fb_likes, fb_comments, fb_engagement_rate,
            published_at
        FROM posts
        WHERE status = 'published'
          AND published_at > ?
          AND (ig_reach > 0 OR fb_reach > 0)
        ORDER BY
            COALESCE(ig_engagement_rate, 0) DESC,
            COALESCE(ig_reach, 0) DESC,
            COALESCE(fb_engagement_rate, 0) DESC
        LIMIT 1
    ''', (since,))

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_next_schedule_slot() -> Optional[Dict]:
    """
    Config'deki WEEKLY_SCHEDULE'dan sıradaki slot'u bul.

    KKTC saatine göre (UTC+3) şu anki zamandan sonraki ilk slot.

    Returns:
        {
            "day": "Pazar",
            "day_index": 6,
            "time": "14:00",
            "type": "reels",
            "platform": "instagram",
            "minutes_until": 180,
            "datetime": datetime object
        }
        or None if no schedule defined
    """
    # Hardcoded schedule (orchestrator.py'den)
    WEEKLY_SCHEDULE = [
        {"day": 0, "day_name": "Pazartesi", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 0, "day_name": "Pazartesi", "time": "19:00", "type": "post", "platform": "instagram"},
        {"day": 1, "day_name": "Salı", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 1, "day_name": "Salı", "time": "19:00", "type": "carousel", "platform": "instagram"},
        {"day": 2, "day_name": "Çarşamba", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 2, "day_name": "Çarşamba", "time": "19:00", "type": "post", "platform": "instagram"},
        {"day": 3, "day_name": "Perşembe", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 3, "day_name": "Perşembe", "time": "19:00", "type": "reels", "platform": "instagram"},
        {"day": 4, "day_name": "Cuma", "time": "10:00", "type": "reels", "platform": "instagram"},
        {"day": 4, "day_name": "Cuma", "time": "19:00", "type": "post", "platform": "instagram"},
        {"day": 5, "day_name": "Cumartesi", "time": "14:00", "type": "carousel", "platform": "instagram"},
        {"day": 6, "day_name": "Pazar", "time": "14:00", "type": "reels", "platform": "instagram"},
    ]

    now = get_kktc_now()  # KKTC timezone kullan
    current_weekday = now.weekday()  # 0=Pazartesi, 6=Pazar
    current_time = now.strftime("%H:%M")

    # Bu haftada kalan slotları bul
    for slot in WEEKLY_SCHEDULE:
        slot_day = slot["day"]
        slot_time = slot["time"]

        # Bugünden sonraki günler veya bugün ama saatten sonra
        if slot_day > current_weekday:
            # Gelecek gün
            days_until = slot_day - current_weekday
        elif slot_day == current_weekday and slot_time > current_time:
            # Bugün ama henüz geçmemiş
            days_until = 0
        else:
            continue  # Bu slot geçmiş

        # Slot zamanını hesapla
        slot_hour, slot_minute = map(int, slot_time.split(":"))
        slot_datetime = now.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
        slot_datetime += timedelta(days=days_until)

        # Kalan dakikayı hesapla
        minutes_until = int((slot_datetime - now).total_seconds() / 60)

        return {
            "day": slot["day_name"],
            "day_index": slot_day,
            "time": slot_time,
            "type": slot["type"],
            "platform": slot["platform"],
            "minutes_until": minutes_until,
            "datetime": slot_datetime
        }

    # Bu haftada slot kalmadı, gelecek haftanın ilk slotunu al
    first_slot = WEEKLY_SCHEDULE[0]
    days_until = 7 - current_weekday + first_slot["day"]

    slot_hour, slot_minute = map(int, first_slot["time"].split(":"))
    slot_datetime = now.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
    slot_datetime += timedelta(days=days_until)

    minutes_until = int((slot_datetime - now).total_seconds() / 60)

    return {
        "day": first_slot["day_name"],
        "day_index": first_slot["day"],
        "time": first_slot["time"],
        "type": first_slot["type"],
        "platform": first_slot["platform"],
        "minutes_until": minutes_until,
        "datetime": slot_datetime
    }


def get_todays_content_by_type(content_type: str) -> List[Dict]:
    """
    Bugün oluşturulan belirli tipteki içerikleri getir.

    Args:
        content_type: 'reels', 'carousel', veya 'post'

    Returns:
        Bugün oluşturulan içeriklerin listesi
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = get_kktc_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    cursor.execute("""
        SELECT * FROM posts
        WHERE visual_type = ?
        AND (
            (published_at >= ? AND published_at <= ?)
            OR (created_at >= ? AND created_at <= ? AND status IN ('published', 'scheduled', 'approved'))
        )
        ORDER BY created_at DESC
    """, (content_type, today_start.isoformat(), today_end.isoformat(),
          today_start.isoformat(), today_end.isoformat()))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def should_run_scheduled_content(content_type: str, scheduled_time: datetime = None) -> Dict[str, Any]:
    """
    Bu slot için otomatik içerik oluşturulmalı mı kontrol et.

    Manuel veya daha önce otonom oluşturulan içerik varsa,
    duplicate üretimi engellemek için False döner.

    Args:
        content_type: 'reels', 'carousel', veya 'post'
        scheduled_time: Planlanmış zaman (varsayılan: şimdi)

    Returns:
        {
            "should_run": True/False,
            "reason": "no_existing_content" / "content_already_exists",
            "existing_posts": [...] (varsa)
        }
    """
    if scheduled_time is None:
        scheduled_time = get_kktc_now()

    # Bugün bu tipte içerik var mı?
    todays_content = get_todays_content_by_type(content_type)

    if todays_content:
        return {
            "should_run": False,
            "reason": "content_already_exists",
            "existing_posts": todays_content,
            "message": f"Bugün zaten {len(todays_content)} adet {content_type} oluşturuldu."
        }

    return {
        "should_run": True,
        "reason": "no_existing_content",
        "existing_posts": [],
        "message": f"Bugün henüz {content_type} oluşturulmadı, devam edilebilir."
    }


# ============ PROMPT TRACKING ============

def get_prompt_hash(prompt: str) -> str:
    """
    Prompt'un kısa hash'ini oluştur (duplicate check için).

    Args:
        prompt: Prompt metni

    Returns:
        12 karakterlik MD5 hash
    """
    normalized = ' '.join(prompt.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def save_prompt(
    post_id: int,
    prompt_text: str,
    prompt_type: str,  # 'video' veya 'image'
    style: str = None
) -> int:
    """
    Prompt'u prompt_history tablosuna kaydet.

    Args:
        post_id: İlişkili post ID
        prompt_text: Prompt metni
        prompt_type: 'video' veya 'image'
        style: Prompt stili (aerial, cinematic, vb.)

    Returns:
        Oluşturulan prompt_history ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    prompt_hash = get_prompt_hash(prompt_text)

    cursor.execute('''
        INSERT INTO prompt_history (post_id, prompt_type, prompt_text, prompt_style, prompt_hash)
        VALUES (?, ?, ?, ?, ?)
    ''', (post_id, prompt_type, prompt_text, style, prompt_hash))

    prompt_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return prompt_id


def check_duplicate_prompt(
    prompt: str,
    days: int = 30,
    threshold: float = 0.85
) -> Dict[str, Any]:
    """
    Son X gün içinde benzer prompt kullanılmış mı kontrol et.

    Args:
        prompt: Kontrol edilecek prompt
        days: Kaç gün geriye bakılacak
        threshold: Benzerlik eşiği (0-1 arası, varsayılan 0.85 = %85)

    Returns:
        {
            "is_duplicate": bool,
            "similar_prompts": [{"id": 1, "text": "...", "similarity": 90.5, "date": "..."}],
            "recommendation": "ok" | "too_similar",
            "message": "..."
        }
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Son X günün prompt'larını al
    cursor.execute('''
        SELECT id, prompt_text, created_at, prompt_style
        FROM prompt_history
        WHERE created_at > datetime('now', ? || ' days')
        ORDER BY created_at DESC
        LIMIT 100
    ''', (f'-{days}',))

    recent = cursor.fetchall()
    conn.close()

    similar = []
    prompt_lower = prompt.lower()

    for row in recent:
        ratio = SequenceMatcher(None, prompt_lower, row['prompt_text'].lower()).ratio()
        if ratio >= threshold:
            text = row['prompt_text']
            similar.append({
                "id": row['id'],
                "text": text[:80] + "..." if len(text) > 80 else text,
                "similarity": round(ratio * 100, 1),
                "date": row['created_at'],
                "style": row['prompt_style']
            })

    if similar:
        return {
            "is_duplicate": True,
            "similar_prompts": similar,
            "recommendation": "too_similar",
            "message": f"{len(similar)} benzer prompt bulundu (son {days} gün)"
        }

    return {
        "is_duplicate": False,
        "similar_prompts": [],
        "recommendation": "ok",
        "message": "Benzer prompt bulunamadı"
    }


def get_recent_prompts(
    days: int = 7,
    prompt_type: str = None
) -> List[Dict]:
    """
    Son X günün prompt'larını getir.

    Args:
        days: Kaç gün geriye bakılacak
        prompt_type: 'video' veya 'image' (opsiyonel filtre)

    Returns:
        Prompt listesi
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT
            ph.id, ph.post_id, ph.prompt_type, ph.prompt_text, ph.prompt_style,
            ph.reach, ph.engagement_rate, ph.likes, ph.saves, ph.shares,
            ph.created_at, ph.performance_updated_at
        FROM prompt_history ph
        WHERE ph.created_at > datetime('now', ? || ' days')
    '''
    params = [f'-{days}']

    if prompt_type:
        query += " AND ph.prompt_type = ?"
        params.append(prompt_type)

    query += " ORDER BY ph.created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_prompt_performance(post_id: int, metrics: Dict[str, Any]) -> bool:
    """
    Post metrikleri çekildiğinde prompt performansını güncelle.

    Args:
        post_id: Post ID (bu post'a bağlı prompt'lar güncellenir)
        metrics: {
            'reach': int,
            'engagement_rate': float,
            'likes': int,
            'saves': int,
            'shares': int
        }

    Returns:
        Güncelleme başarılı mı
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE prompt_history
        SET
            reach = ?,
            engagement_rate = ?,
            likes = ?,
            saves = ?,
            shares = ?,
            performance_updated_at = datetime('now')
        WHERE post_id = ?
    ''', (
        metrics.get('reach', 0),
        metrics.get('engagement_rate', 0),
        metrics.get('likes', 0),
        metrics.get('saves', 0),
        metrics.get('shares', 0),
        post_id
    ))

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return updated


def get_top_performing_prompts(
    limit: int = 5,
    prompt_type: str = None
) -> List[Dict]:
    """
    En iyi performans gösteren prompt'ları getir.

    Sıralama: viral_score = saves*3 + shares*2 + likes, sonra engagement_rate

    Args:
        limit: Kaç prompt döndürülecek
        prompt_type: 'video' veya 'image' (opsiyonel filtre)

    Returns:
        En iyi performanslı prompt listesi
    """
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT
            prompt_text, prompt_style, prompt_type,
            reach, engagement_rate, likes, saves, shares,
            created_at,
            (saves * 3 + shares * 2 + likes) as viral_score
        FROM prompt_history
        WHERE reach > 0
    '''

    if prompt_type:
        query += f" AND prompt_type = ?"
        cursor.execute(query + '''
            ORDER BY
                (saves * 3 + shares * 2 + likes) DESC,
                engagement_rate DESC
            LIMIT ?
        ''', (prompt_type, limit))
    else:
        cursor.execute(query + '''
            ORDER BY
                (saves * 3 + shares * 2 + likes) DESC,
                engagement_rate DESC
            LIMIT ?
        ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_prompt_style_stats(days: int = 30) -> Dict[str, Any]:
    """
    Prompt stil dağılımı ve performans istatistikleri.

    Args:
        days: Kaç gün geriye bakılacak

    Returns:
        {
            'total_prompts': int,
            'by_type': {'video': 10, 'image': 15},
            'by_style': {'aerial': 5, 'cinematic': 8, ...},
            'avg_engagement_by_style': {'aerial': 5.2, ...}
        }
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Toplam ve tipe göre
    cursor.execute('''
        SELECT
            prompt_type,
            COUNT(*) as count
        FROM prompt_history
        WHERE created_at > datetime('now', ? || ' days')
        GROUP BY prompt_type
    ''', (f'-{days}',))

    by_type = {row['prompt_type']: row['count'] for row in cursor.fetchall()}

    # Stile göre
    cursor.execute('''
        SELECT
            prompt_style,
            COUNT(*) as count,
            AVG(engagement_rate) as avg_engagement,
            AVG(saves) as avg_saves
        FROM prompt_history
        WHERE created_at > datetime('now', ? || ' days')
          AND prompt_style IS NOT NULL
        GROUP BY prompt_style
        ORDER BY count DESC
    ''', (f'-{days}',))

    style_rows = cursor.fetchall()
    by_style = {row['prompt_style']: row['count'] for row in style_rows}
    avg_engagement_by_style = {
        row['prompt_style']: round(row['avg_engagement'] or 0, 2)
        for row in style_rows
    }

    conn.close()

    return {
        'total_prompts': sum(by_type.values()),
        'by_type': by_type,
        'by_style': by_style,
        'avg_engagement_by_style': avg_engagement_by_style,
        'period_days': days
    }


# ============ STORY BOOSTS ============

def log_story_boost(
    post_id: int,
    instagram_post_id: str,
    post_type: str,
    sequence_type: str
) -> int:
    """Story boost kaydı oluştur"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO story_boosts (post_id, instagram_post_id, post_type, sequence_type, scheduled_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (post_id, instagram_post_id, post_type, sequence_type, datetime.now().isoformat()))

    boost_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return boost_id


def update_story_boost(
    boost_id: int,
    status: str,
    method: str = None,
    story_id: str = None,
    error: str = None
):
    """Story boost durumunu güncelle"""
    conn = get_connection()
    cursor = conn.cursor()

    updates = ["status = ?", "executed_at = ?"]
    values = [status, datetime.now().isoformat()]

    if method:
        updates.append("publish_method = ?")
        values.append(method)
    if story_id:
        updates.append("story_id = ?")
        values.append(story_id)
    if error:
        updates.append("error_message = ?")
        values.append(error[:500])
    if method == "telegram":
        updates.append("telegram_sent = ?")
        values.append(True)

    values.append(boost_id)
    cursor.execute(f"UPDATE story_boosts SET {', '.join(updates)} WHERE id = ?", values)

    conn.commit()
    conn.close()


def get_story_boosts_for_post(post_id: int) -> List[Dict]:
    """Post için tüm story boost kayıtlarını getir"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM story_boosts
        WHERE post_id = ?
        ORDER BY sequence_type
    ''', (post_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_story_boost_stats(days: int = 7) -> Dict[str, Any]:
    """Story boost istatistikleri"""
    conn = get_connection()
    cursor = conn.cursor()

    since = datetime.now() - timedelta(days=days)

    cursor.execute('''
        SELECT status, COUNT(*) as cnt
        FROM story_boosts
        WHERE created_at > ?
        GROUP BY status
    ''', (since,))

    rows = cursor.fetchall()
    conn.close()

    stats = {"total": 0, "published": 0, "manual_sent": 0, "failed": 0, "skipped": 0}
    for row in rows:
        stats["total"] += row["cnt"]
        if row["status"] in stats:
            stats[row["status"]] = row["cnt"]

    return stats
