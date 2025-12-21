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
        'reviewer_feedback', 'revision_count', 'post_text_ig', 'post_text_fb',
        # Hook & A/B tracking
        'hook_type', 'hook_text', 'tone', 'ab_test_id', 'is_ab_winner'
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


# ============ HOOK PERFORMANCE ============

def update_hook_performance(
    hook_type: str,
    topic_category: str,
    platform: str,
    reach: int,
    engagement: int,
    saves: int = 0,
    shares: int = 0,
    engagement_rate: float = 0,
    save_rate: float = 0,
    share_rate: float = 0,
    non_follower_pct: float = 0
):
    """Hook performance metriklerini güncelle veya oluştur"""
    conn = get_connection()
    cursor = conn.cursor()

    # Mevcut kaydı kontrol et
    cursor.execute('''
        SELECT id, usage_count, total_reach, total_engagement, total_saves, total_shares
        FROM hook_performance
        WHERE hook_type = ? AND topic_category = ? AND platform = ?
    ''', (hook_type, topic_category, platform))

    row = cursor.fetchone()

    if row:
        # Güncelle
        new_count = row['usage_count'] + 1
        new_reach = row['total_reach'] + reach
        new_engagement = row['total_engagement'] + engagement
        new_saves = row['total_saves'] + saves
        new_shares = row['total_shares'] + shares

        # Ortalama hesapla
        new_avg_engagement = engagement_rate  # Son değeri al veya weighted average yap
        new_avg_save = save_rate
        new_avg_share = share_rate
        new_avg_non_follower = non_follower_pct

        # Viral score hesapla
        viral_score = new_avg_save * 2 + new_avg_share * 3 + new_avg_engagement + new_avg_non_follower * 0.015

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
            new_avg_engagement, new_avg_save, new_avg_share, new_avg_non_follower,
            viral_score, row['id']
        ))
    else:
        # Yeni kayıt oluştur
        viral_score = save_rate * 2 + share_rate * 3 + engagement_rate + non_follower_pct * 0.015

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
