# Olivenet Social Bot - Veritabanı Dokümantasyonu

## Genel Bilgi

- **Veritabanı:** SQLite
- **Dosya:** `/opt/olivenet-social-bot/data/content.db`
- **Modüller:** `app/database/models.py`, `app/database/crud.py`

---

## Tablo Şeması

### 1. posts (Ana İçerik Tablosu)

Post yaşam döngüsü ve tüm içerik bilgilerini saklar.

```sql
CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP,

    -- İçerik
    topic TEXT NOT NULL,
    post_text TEXT NOT NULL,
    post_text_ig TEXT,           -- Instagram optimize metin
    visual_type TEXT,            -- infographic, gemini, flux, video, carousel
    visual_path TEXT,
    visual_prompt TEXT,
    video_prompt TEXT,
    prompt_style TEXT,           -- cinematic, documentary, pov, aerial

    -- Durum
    status TEXT DEFAULT 'draft', -- draft, scheduled, approved, published, rejected
    rejection_reason TEXT,

    -- Platform
    platform TEXT DEFAULT 'instagram',
    instagram_post_id TEXT,

    -- Hook & Tone
    hook_type TEXT,              -- question, statistic, bold_claim, problem, value
    hook_text TEXT,
    tone TEXT,

    -- A/B Testing
    ab_test_id INTEGER,
    is_ab_winner BOOLEAN,

    -- Voice Reels (TTS)
    speech_script TEXT,
    audio_path TEXT,
    voice_id TEXT,
    audio_duration REAL DEFAULT 0,
    voice_mode BOOLEAN DEFAULT 0,

    -- Kategori & Revizyon
    topic_category TEXT,
    revision_count INTEGER DEFAULT 0,

    -- AI Metadata
    orchestrator_notes TEXT,
    reviewer_feedback TEXT,

    -- Instagram Metrikleri (sync edilir)
    ig_reach INTEGER DEFAULT 0,
    ig_likes INTEGER DEFAULT 0,
    ig_comments INTEGER DEFAULT 0,
    ig_saves INTEGER DEFAULT 0,
    ig_shares INTEGER DEFAULT 0,
    ig_plays INTEGER DEFAULT 0,
    ig_engagement_rate REAL DEFAULT 0,
    ig_avg_watch_time REAL DEFAULT 0,
    ig_total_watch_time INTEGER DEFAULT 0,
    ig_reach_followers INTEGER DEFAULT 0,
    ig_reach_non_followers INTEGER DEFAULT 0,
    insights_updated_at TIMESTAMP
);
```

**Durum Geçişleri:**
```
draft → scheduled → approved → published
          ↘          ↘
         rejected    rejected
```

---

### 2. analytics (Performans Metrikleri)

Her post için zaman serisi performans verileri.

```sql
CREATE TABLE analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Temel Metrikler
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,

    -- Instagram Özel
    ig_reach INTEGER DEFAULT 0,
    ig_likes INTEGER DEFAULT 0,
    ig_comments INTEGER DEFAULT 0,
    ig_saves INTEGER DEFAULT 0,
    ig_shares INTEGER DEFAULT 0,
    ig_engagement_rate REAL DEFAULT 0,

    -- Hesaplanan
    engagement_rate REAL DEFAULT 0,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);
```

---

### 3. content_calendar (Haftalık Planlama)

OrchestratorAgent tarafından oluşturulan haftalık içerik planı.

```sql
CREATE TABLE content_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Zamanlama
    week_start DATE,
    day_of_week INTEGER,         -- 0=Pazartesi, 6=Pazar
    scheduled_time TIME,

    -- İçerik Planı
    topic_category TEXT,         -- egitici, tanitim, ipucu, haber
    topic_suggestion TEXT,
    visual_type_suggestion TEXT, -- post, reels, carousel

    -- Durum
    status TEXT DEFAULT 'planned', -- planned, content_created, published
    post_id INTEGER,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);
```

---

### 4. strategy (AI Öğrenme Tablosu)

Sistemin öğrendiği stratejiler ve optimizasyonlar.

```sql
CREATE TABLE strategy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,

    -- Genel Strateji
    posts_per_week INTEGER DEFAULT 5,
    best_days TEXT,              -- JSON: ["monday", "wednesday"]
    best_hours TEXT,             -- JSON: ["10:00", "19:00"]

    -- İçerik Mix
    content_mix TEXT,            -- JSON: {"egitici": 30, "tanitim": 25}
    visual_mix TEXT,             -- JSON: {"flux": 35, "infographic": 30}

    -- Öğrenilen Insights
    insights TEXT,               -- JSON: AI öğrenmeler

    -- Performans Baseline
    avg_engagement_rate REAL DEFAULT 0,
    avg_reach INTEGER DEFAULT 0,

    -- En İyi Hooklar
    best_hooks TEXT              -- JSON: ["question", "statistic"]
);
```

---

### 5. hook_performance (Hook Analizi)

Her hook tipinin performans verileri.

```sql
CREATE TABLE hook_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Hook Bilgisi
    hook_type TEXT NOT NULL,     -- question, statistic, bold_claim, problem, value
    topic_category TEXT,
    platform TEXT DEFAULT 'instagram',

    -- Aggregated Metrikler
    usage_count INTEGER DEFAULT 0,
    total_reach INTEGER DEFAULT 0,
    total_engagement INTEGER DEFAULT 0,
    total_saves INTEGER DEFAULT 0,
    total_shares INTEGER DEFAULT 0,
    avg_engagement_rate REAL DEFAULT 0,
    avg_save_rate REAL DEFAULT 0,
    avg_share_rate REAL DEFAULT 0,
    avg_non_follower_pct REAL DEFAULT 0,

    -- Viral Skor
    viral_score REAL DEFAULT 0,

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(hook_type, topic_category, platform)
);
```

**Viral Skor Formülü:**
```
viral_score = (saves × 2) + (shares × 3) + engagement + (non_follower_pct × 0.015)
```

---

### 6. ab_test_results (A/B Test Sonuçları)

Varyant karşılaştırma ve tahmin doğruluğu.

```sql
CREATE TABLE ab_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    post_id INTEGER,
    topic TEXT,
    platform TEXT,

    -- Varyant A
    variant_a_hook_type TEXT,
    variant_a_tone TEXT,
    variant_a_score REAL,
    variant_a_text TEXT,

    -- Varyant B
    variant_b_hook_type TEXT,
    variant_b_tone TEXT,
    variant_b_score REAL,
    variant_b_text TEXT,

    -- Sonuç
    winner TEXT,                 -- 'A' veya 'B'
    margin REAL,
    confidence TEXT,             -- high, medium, low
    reasoning TEXT,
    learning TEXT,

    -- Post-Publish Performance
    actual_engagement_rate REAL,
    actual_save_rate REAL,
    prediction_accurate BOOLEAN,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);
```

---

### 7. approval_logs (Onay Audit Trail)

Tüm onay/red kararlarının geçmişi.

```sql
CREATE TABLE approval_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    post_id INTEGER,
    topic TEXT,
    content_type TEXT,           -- post, reels, carousel

    -- Karar
    decision TEXT NOT NULL,      -- approved, rejected, scheduled, revised
    decision_by_user_id INTEGER,
    decision_by_username TEXT,

    -- Bağlam
    review_score REAL,
    reason TEXT,
    scheduler_mode TEXT,         -- manual, autonomous, scheduled

    -- Durum Değişikliği
    previous_status TEXT,
    new_status TEXT,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);
```

---

### 8. prompt_history (Prompt Takibi)

Video/görsel prompt'larının performans takibi.

```sql
CREATE TABLE prompt_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    prompt_type TEXT NOT NULL,   -- 'video' veya 'image'
    prompt_text TEXT NOT NULL,
    prompt_style TEXT,           -- cinematic, documentary, pov, aerial
    prompt_hash TEXT,            -- MD5 (duplicate check)

    -- Performans
    reach INTEGER DEFAULT 0,
    engagement_rate REAL DEFAULT 0,
    likes INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    performance_updated_at TIMESTAMP,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE INDEX idx_prompt_hash ON prompt_history(prompt_hash);
CREATE INDEX idx_prompt_type ON prompt_history(prompt_type);
```

---

### 9. ad_campaigns (Meta Ads Verileri)

Reklam kampanyası performans verileri.

```sql
CREATE TABLE ad_campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,

    -- Meta IDs
    campaign_id TEXT,
    campaign_name TEXT,
    adset_id TEXT,
    adset_name TEXT,
    ad_id TEXT UNIQUE,
    ad_name TEXT,

    -- Performans
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

    -- Video Metrikleri
    video_25_pct INTEGER DEFAULT 0,
    video_50_pct INTEGER DEFAULT 0,
    video_75_pct INTEGER DEFAULT 0,
    video_100_pct INTEGER DEFAULT 0,

    -- Tarihler
    date_start DATE,
    date_stop DATE,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);
```

---

### 10. agent_logs (Agent Aktiviteleri)

Her agent'ın işlem geçmişi.

```sql
CREATE TABLE agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_name TEXT,             -- orchestrator, planner, creator, reviewer, publisher
    action TEXT,
    input_data TEXT,             -- JSON
    output_data TEXT,            -- JSON
    success BOOLEAN,
    error_message TEXT
);
```

---

## ER Diyagramı (ASCII)

```
┌─────────────────┐       ┌─────────────────┐
│      posts      │───┬───│    analytics    │
└────────┬────────┘   │   └─────────────────┘
         │            │
         │            ├───┌─────────────────┐
         │            │   │ approval_logs   │
         │            │   └─────────────────┘
         │            │
         │            ├───┌─────────────────┐
         │            │   │ ab_test_results │
         │            │   └─────────────────┘
         │            │
         │            ├───┌─────────────────┐
         │            │   │ prompt_history  │
         │            │   └─────────────────┘
         │            │
         │            └───┌─────────────────┐
         │                │  ad_campaigns   │
         │                └─────────────────┘
         │
┌────────▼────────┐
│ content_calendar│
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│    strategy     │       │ hook_performance│
└─────────────────┘       └─────────────────┘

┌─────────────────┐
│   agent_logs    │
└─────────────────┘
```

---

## Örnek Sorgular

### En İyi Performanslı Hooklar
```sql
SELECT hook_type,
       avg_engagement_rate,
       viral_score,
       usage_count
FROM hook_performance
WHERE platform = 'instagram'
ORDER BY viral_score DESC
LIMIT 5;
```

### Son 7 Günün Postları
```sql
SELECT id, topic, status, ig_reach, ig_engagement_rate
FROM posts
WHERE created_at >= datetime('now', '-7 days')
ORDER BY created_at DESC;
```

### Yayınlanmamış Onaylı İçerikler
```sql
SELECT id, topic, scheduled_at
FROM posts
WHERE status = 'approved' AND published_at IS NULL
ORDER BY scheduled_at;
```

### Haftalık Performans Özeti
```sql
SELECT
    strftime('%Y-%W', published_at) as week,
    COUNT(*) as total_posts,
    AVG(ig_reach) as avg_reach,
    AVG(ig_engagement_rate) as avg_engagement
FROM posts
WHERE status = 'published'
GROUP BY week
ORDER BY week DESC
LIMIT 4;
```

---

## Migration Notları

Yeni sütun eklemek için `models.py`'deki `alter_statements` listesine ekleyin:

```python
alter_statements = [
    "ALTER TABLE posts ADD COLUMN new_column TEXT",
    # ...
]
```

Sistem otomatik olarak eksik sütunları ekler.

---

## İlgili Dosyalar

- `app/database/models.py` - Şema tanımları ve init
- `app/database/crud.py` - CRUD operasyonları
- `.claude/skills/database-patterns/` - Skill referansı
