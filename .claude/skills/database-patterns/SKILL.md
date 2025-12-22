---
name: database-patterns
description: SQLite veritabani yapisi ve CRUD pattern referansi. Use when working with database operations, queries, or understanding the data model.
---

# Database Patterns

## Quick Reference

| Table | Purpose |
|-------|---------|
| posts | Tum postlar (icerik, durum, platform ID'leri) |
| analytics | Post performans metrikleri |
| content_calendar | Planlanan icerikler |
| strategy | AI ogrenmis stratejiler |
| agent_logs | Agent aktiviteleri |
| hook_performance | Hook type performanslari |
| ab_test_results | A/B test sonuclari |
| approval_logs | Onay audit trail |
| prompt_history | Video/image prompt tracking |

## Connection Pattern

```python
from app.database.models import get_connection

conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
row = cursor.fetchone()

conn.close()
return dict(row) if row else None
```

## CRUD Pattern

All CRUD functions follow this pattern:

```python
def get_something(id: int) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM table WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_something(field1: str, field2: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO table (field1, field2) VALUES (?, ?)
    ''', (field1, field2))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def update_something(id: int, **kwargs) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    updates = []
    values = []
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        values.append(value)
    values.append(id)
    cursor.execute(f'''
        UPDATE table SET {", ".join(updates)} WHERE id = ?
    ''', values)
    conn.commit()
    conn.close()
    return True
```

## JSON Field Handling

Strategy and other tables use JSON for flexible data:

```python
import json

# Saving JSON
best_days = json.dumps(["monday", "wednesday", "friday"])
cursor.execute("UPDATE strategy SET best_days = ?", (best_days,))

# Loading JSON
row = cursor.fetchone()
best_days = json.loads(row["best_days"]) if row["best_days"] else []
```

## Migration Pattern

Add new columns safely:

```python
migrations = [
    "ALTER TABLE posts ADD COLUMN video_prompt TEXT",
    "ALTER TABLE posts ADD COLUMN prompt_style TEXT"
]

for migration in migrations:
    try:
        cursor.execute(migration)
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise
```

## Viral Score Formula

Used in hook_performance table:

```python
viral_score = (
    (saves * 2) +
    (shares * 3) +
    engagement +
    (non_follower_reach * 0.015)
)
```

## Timezone Handling

KKTC timezone (UTC+2):

```python
def get_kktc_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=2)
```

## Key Tables

### posts
Main content table with status workflow:
- draft -> scheduled -> approved -> published
- Platform-specific text (post_text_ig, post_text_fb)
- Visual tracking (visual_type, visual_path, visual_prompt)

### analytics
Performance metrics per post:
- Standard: views, likes, comments, shares, reach
- Calculated: engagement_rate

### hook_performance
Aggregated hook effectiveness:
- Tracks by: hook_type, topic_category, platform
- Metrics: usage_count, avg_engagement_rate, viral_score

### prompt_history
Prompt tracking for learning:
- prompt_type: 'video' or 'image'
- prompt_style: cinematic, documentary, pov, etc.
- Performance metrics for optimization

For more details, see [schema.sql](schema.sql) and [queries.md](queries.md).
