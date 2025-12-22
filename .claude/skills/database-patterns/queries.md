# Database Query Examples

## Posts

### Get Post by ID
```python
def get_post(post_id: int) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
```

### Get Posts by Status
```python
def get_posts_by_status(status: str, limit: int = 10) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC LIMIT ?",
        (status, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

### Get Published Posts (Last N Days)
```python
def get_published_posts(days: int = 30) -> List[Dict]:
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
```

## Analytics

### Analytics Summary
```python
def get_analytics_summary(days: int = 30) -> Dict:
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
```

### Update Post Analytics
```python
def update_post_analytics(post_id: int, analytics_data: Dict) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO analytics
        (post_id, ig_reach, ig_likes, ig_comments, ig_saves, ig_shares, ig_engagement_rate, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (
        post_id,
        analytics_data.get('ig_reach', 0),
        analytics_data.get('ig_likes', 0),
        analytics_data.get('ig_comments', 0),
        analytics_data.get('ig_saves', 0),
        analytics_data.get('ig_shares', 0),
        analytics_data.get('ig_engagement_rate', 0)
    ))

    conn.commit()
    conn.close()
    return True
```

## Hook Performance

### Get Best Performing Hooks
```python
def get_best_performing_hooks(
    platform: str = 'instagram',
    limit: int = 5
) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            hook_type,
            usage_count,
            avg_engagement_rate,
            avg_save_rate,
            viral_score
        FROM hook_performance
        WHERE platform = ? AND usage_count >= 3
        ORDER BY viral_score DESC
        LIMIT ?
    ''', (platform, limit))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

### Update Hook Performance
```python
def update_hook_performance(
    hook_type: str,
    topic_category: str,
    platform: str,
    metrics: Dict
) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    # Calculate viral score
    viral_score = (
        (metrics.get('saves', 0) * 2) +
        (metrics.get('shares', 0) * 3) +
        metrics.get('engagement', 0) +
        (metrics.get('non_follower_reach', 0) * 0.015)
    )

    cursor.execute('''
        INSERT INTO hook_performance
        (hook_type, topic_category, platform, usage_count, total_reach, viral_score)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(hook_type, topic_category, platform)
        DO UPDATE SET
            usage_count = usage_count + 1,
            total_reach = total_reach + ?,
            viral_score = (viral_score + ?) / 2,
            last_updated = CURRENT_TIMESTAMP
    ''', (hook_type, topic_category, platform,
          metrics.get('reach', 0), viral_score,
          metrics.get('reach', 0), viral_score))

    conn.commit()
    conn.close()
    return True
```

## Prompt History

### Check Duplicate Prompt
```python
def check_duplicate_prompt(prompt: str, days: int = 30, threshold: float = 0.85) -> Dict:
    """
    Check if a similar prompt was used recently.
    Uses hash for exact match, SequenceMatcher for fuzzy match.
    """
    prompt_hash = get_prompt_hash(prompt)

    conn = get_connection()
    cursor = conn.cursor()
    since = datetime.now() - timedelta(days=days)

    # Exact hash match
    cursor.execute('''
        SELECT id, prompt_text, prompt_style, reach
        FROM prompt_history
        WHERE prompt_hash = ? AND created_at > ?
        LIMIT 1
    ''', (prompt_hash, since))

    row = cursor.fetchone()
    if row:
        conn.close()
        return {"is_duplicate": True, "match_type": "exact", "match": dict(row)}

    # Fuzzy match for recent prompts
    cursor.execute('''
        SELECT id, prompt_text, prompt_style
        FROM prompt_history
        WHERE created_at > ?
        ORDER BY created_at DESC
        LIMIT 50
    ''', (since,))

    for row in cursor.fetchall():
        similarity = SequenceMatcher(None, prompt.lower(), row["prompt_text"].lower()).ratio()
        if similarity >= threshold:
            conn.close()
            return {
                "is_duplicate": True,
                "match_type": "similar",
                "similarity": similarity,
                "match": dict(row)
            }

    conn.close()
    return {"is_duplicate": False}
```

### Get Prompt Hash
```python
def get_prompt_hash(prompt: str) -> str:
    """Normalize and hash a prompt for duplicate detection."""
    normalized = ' '.join(prompt.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]
```

### Get Top Performing Prompts
```python
def get_top_performing_prompts(limit: int = 5, prompt_type: str = None) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()

    query = '''
        SELECT prompt_text, prompt_type, prompt_style,
               reach, engagement_rate, saves, shares
        FROM prompt_history
        WHERE reach > 0
    '''
    params = []

    if prompt_type:
        query += ' AND prompt_type = ?'
        params.append(prompt_type)

    query += ' ORDER BY (saves * 2 + shares * 3 + engagement_rate) DESC LIMIT ?'
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

## Strategy

### Get Current Strategy
```python
def get_current_strategy() -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if row:
        result = dict(row)
        # Parse JSON fields
        result['best_days'] = json.loads(result.get('best_days') or '[]')
        result['best_hours'] = json.loads(result.get('best_hours') or '[]')
        result['content_mix'] = json.loads(result.get('content_mix') or '{}')
        result['visual_mix'] = json.loads(result.get('visual_mix') or '{}')
        return result

    return {}
```

### Update Strategy
```python
def update_strategy(updates: Dict) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    # Serialize JSON fields
    if 'best_days' in updates:
        updates['best_days'] = json.dumps(updates['best_days'])
    if 'content_mix' in updates:
        updates['content_mix'] = json.dumps(updates['content_mix'])

    # Get current strategy
    cursor.execute("SELECT id FROM strategy ORDER BY updated_at DESC LIMIT 1")
    row = cursor.fetchone()

    if row:
        # Update existing
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [row['id']]
        cursor.execute(f"UPDATE strategy SET {set_clause} WHERE id = ?", values)
    else:
        # Create new
        cols = ", ".join(updates.keys())
        placeholders = ", ".join(["?" for _ in updates])
        cursor.execute(f"INSERT INTO strategy ({cols}) VALUES ({placeholders})", list(updates.values()))

    conn.commit()
    conn.close()
    return True
```

## Timezone Helper

```python
def get_kktc_now() -> datetime:
    """Get current time in KKTC timezone (UTC+2)"""
    return datetime.utcnow() + timedelta(hours=2)
```
