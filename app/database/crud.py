"""
Database CRUD Operations
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from .models import get_connection

# ============ POSTS ============

def create_post(
    topic: str,
    post_text: str = None,
    visual_type: Optional[str] = None,
    scheduled_at: Optional[datetime] = None,
    platform: str = "both",
    post_text_ig: str = None,
    post_text_fb: str = None,
    topic_category: str = None
) -> int:
    """Yeni post oluştur - platform-specific text destekli"""
    conn = get_connection()
    cursor = conn.cursor()

    # post_text yoksa post_text_fb kullan
    final_post_text = post_text or post_text_fb

    cursor.execute('''
        INSERT INTO posts (topic, post_text, visual_type, scheduled_at, platform, status, post_text_ig, post_text_fb)
        VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
    ''', (topic, final_post_text, visual_type, scheduled_at, platform, post_text_ig, post_text_fb))

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
        'reviewer_feedback', 'revision_count', 'post_text_ig', 'post_text_fb'
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
    """Son X günün analitik özeti"""
    conn = get_connection()
    cursor = conn.cursor()
    since = datetime.now() - timedelta(days=days)

    cursor.execute('''
        SELECT
            COUNT(DISTINCT post_id) as total_posts,
            SUM(views) as total_views,
            SUM(likes) as total_likes,
            SUM(comments) as total_comments,
            SUM(shares) as total_shares,
            AVG(engagement_rate) as avg_engagement_rate,
            AVG(reach) as avg_reach
        FROM analytics
        WHERE recorded_at > ?
    ''', (since,))

    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

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
        for field in ['best_days', 'best_hours', 'content_mix', 'visual_mix', 'insights']:
            if strategy.get(field):
                strategy[field] = json.loads(strategy[field])
        return strategy
    return {}

def update_strategy(**kwargs) -> bool:
    """Stratejiyi güncelle"""
    conn = get_connection()
    cursor = conn.cursor()

    # JSON alanları serialize et
    for field in ['best_days', 'best_hours', 'content_mix', 'visual_mix', 'insights']:
        if field in kwargs and isinstance(kwargs[field], (dict, list)):
            kwargs[field] = json.dumps(kwargs[field])

    # Mevcut strateji ID'sini al
    cursor.execute("SELECT id FROM strategy ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()

    if row:
        strategy_id = row['id']
        updates = []
        values = []
        for key, value in kwargs.items():
            updates.append(f"{key} = ?")
            values.append(value)

        updates.append("updated_at = ?")
        values.append(datetime.now())
        values.append(strategy_id)

        cursor.execute(f'''
            UPDATE strategy SET {", ".join(updates)} WHERE id = ?
        ''', values)
        conn.commit()

    conn.close()
    return True

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
