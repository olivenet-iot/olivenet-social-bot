---
name: database-patterns
description: SQLite veritabani yapisi ve CRUD pattern referansi. Use when working with database operations, queries, or understanding the data model.
---

# Database Patterns

**Database:** `data/content.db` (SQLite)

## Tables (12 tablo)

| # | Table | Purpose |
|---|-------|---------|
| 1 | posts | Icerik, durum, platform ID'leri |
| 2 | analytics | Post performans metrikleri |
| 3 | content_calendar | Planlanan icerikler |
| 4 | strategy | AI ogrenmis stratejiler |
| 5 | hook_performance | Hook type performanslari |
| 6 | ab_test_results | A/B test sonuclari |
| 7 | approval_logs | Onay audit trail |
| 8 | prompt_history | Video/image prompt tracking |
| 9 | ad_campaigns | Meta Ads verileri |
| 10 | agent_logs | Agent aktiviteleri |
| 11 | content_opportunities | v2 icerik firsatlari havuzu |
| 12 | story_boosts | Story promosyon takibi |

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

## Common CRUD Functions

```python
from app.database.crud import (
    get_post, create_post, update_post,
    get_published_posts, get_analytics_summary,
    get_best_performing_hooks, get_current_strategy
)

post = get_post(post_id)
posts = get_published_posts(days=30)
stats = get_analytics_summary(days=30)
hooks = get_best_performing_hooks(limit=5)
strategy = get_current_strategy()
```

## content_opportunities (v2)

Brain Agent'in icerik havuzu. Feed'lerden toplanan firsatlar.

```python
from app.database.crud import (
    get_opportunity, update_opportunity,
    get_opportunity_stats, expire_old_opportunities
)

# Firsat durumu guncelle
update_opportunity(opp_id, status="producing", selected_at=datetime.utcnow().isoformat())

# Havuz istatistikleri
stats = get_opportunity_stats()
# -> {active_count, by_status: {ready: 15, enriched: 8, ...}}

# Eski firsatlari temizle (72 saat)
expired = expire_old_opportunities(max_age_hours=72)
```

### Opportunity Status Lifecycle
```
discovered → enriched → scored → ready → selected → producing → used
                                            ↓
                                         expired (72h)
                                            ↓
                                         dropped
```

### Opportunity Fields
| Alan | Aciklama |
|------|----------|
| source_type | rss, evergreen, calendar, manual |
| source_name | Feed adi (IoT Now, Hackaday, ...) |
| title | Firsat basligi |
| combined_score | relevance + timeliness + virality |
| content_type_suggestion | reels, carousel, post, voice_reels |
| hook_suggestion | Hook tipi onerisi |
| status | Lifecycle durumu |

## story_boosts (v2)

Post sonrasi otomatik Story promosyonu.

```python
# Story boost kaydi
# status: scheduled → executed | failed
# sequence_type: initial, reminder
# publish_method: api, telegram_fallback
```

## Update Post

```python
from app.database.crud import update_post

update_post(post_id,
    status="published",
    instagram_post_id="17901234567890123",
    published_at=datetime.now()
)
```

## Viral Score Formula

```python
viral_score = (saves * 2) + (shares * 3) + engagement + (non_follower_reach * 0.015)
```

## Timezone

```python
def get_kktc_now():
    return datetime.utcnow() + timedelta(hours=2)  # UTC+2
```

## Key Status Values

**posts.status:** draft → scheduled → approved → published | rejected
**content_calendar.status:** planned → content_created → published
**content_opportunities.status:** discovered → enriched → scored → ready → producing → used | expired

## Deep Links

- `app/database/models.py` - Schema, init (12 tablo)
- `app/database/crud.py` - All CRUD functions
- `DATABASE.md` - Full schema reference
