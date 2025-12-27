-- Database Schema for Olivenet Social Bot
-- SQLite3

-- ============ POSTS ============
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP,
    published_at TIMESTAMP,

    -- Content
    topic TEXT NOT NULL,
    post_text TEXT NOT NULL,
    post_text_ig TEXT,      -- Instagram-specific text (platform optimize)
    visual_type TEXT,       -- infographic, gemini, flux, video, carousel
    visual_path TEXT,
    visual_prompt TEXT,
    video_prompt TEXT,      -- Video generation prompt
    prompt_style TEXT,      -- cinematic, documentary, pov, etc.

    -- Status
    status TEXT DEFAULT 'draft',  -- draft, scheduled, approved, published, rejected
    rejection_reason TEXT,

    -- Platform
    platform TEXT DEFAULT 'instagram',  -- instagram (primary platform)
    instagram_post_id TEXT,

    -- Hook & A/B Tracking
    hook_type TEXT,
    hook_text TEXT,
    tone TEXT,
    ab_test_id INTEGER,
    is_ab_winner BOOLEAN,

    -- AI Metadata
    orchestrator_notes TEXT,
    reviewer_feedback TEXT,
    revision_count INTEGER DEFAULT 0
);

-- ============ ANALYTICS ============
CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Basic Metrics
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,

    -- Instagram-specific
    ig_reach INTEGER DEFAULT 0,
    ig_likes INTEGER DEFAULT 0,
    ig_comments INTEGER DEFAULT 0,
    ig_saves INTEGER DEFAULT 0,
    ig_shares INTEGER DEFAULT 0,
    ig_engagement_rate REAL DEFAULT 0,

    -- Calculated
    engagement_rate REAL DEFAULT 0,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- ============ CONTENT CALENDAR ============
CREATE TABLE IF NOT EXISTS content_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Planning
    week_start DATE,
    day_of_week INTEGER,  -- 0=Monday, 6=Sunday
    scheduled_time TIME,

    -- Content Plan
    topic_category TEXT,  -- egitici, tanitim, ipucu, haber, basari_hikayesi
    topic_suggestion TEXT,
    visual_type_suggestion TEXT,

    -- Status
    status TEXT DEFAULT 'planned',  -- planned, content_created, published
    post_id INTEGER,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- ============ STRATEGY ============
CREATE TABLE IF NOT EXISTS strategy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,

    -- General Strategy
    posts_per_week INTEGER DEFAULT 5,
    best_days TEXT,       -- JSON: ["monday", "wednesday", "friday"]
    best_hours TEXT,      -- JSON: ["09:00", "13:00", "18:00"]

    -- Content Mix
    content_mix TEXT,     -- JSON: {"egitici": 30, "tanitim": 20, ...}
    visual_mix TEXT,      -- JSON: {"flux": 40, "infographic": 30, ...}

    -- Learned Insights
    insights TEXT,        -- JSON: AI learned patterns

    -- Performance Baseline
    avg_engagement_rate REAL DEFAULT 0,
    avg_reach INTEGER DEFAULT 0,

    -- Top Performing Hooks
    best_hooks TEXT       -- JSON: ["question", "statistic", ...]
);

-- ============ AGENT LOGS ============
CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_name TEXT,      -- orchestrator, planner, creator, reviewer, publisher
    action TEXT,
    input_data TEXT,      -- JSON
    output_data TEXT,     -- JSON
    success BOOLEAN,
    error_message TEXT
);

-- ============ HOOK PERFORMANCE ============
CREATE TABLE IF NOT EXISTS hook_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Hook Info
    hook_type TEXT NOT NULL,  -- question, statistic, bold_claim, problem, value, fear, before_after, list, comparison, local
    topic_category TEXT,
    platform TEXT DEFAULT 'instagram',  -- instagram (primary platform)

    -- Aggregated Metrics
    usage_count INTEGER DEFAULT 0,
    total_reach INTEGER DEFAULT 0,
    total_engagement INTEGER DEFAULT 0,
    total_saves INTEGER DEFAULT 0,
    total_shares INTEGER DEFAULT 0,
    avg_engagement_rate REAL DEFAULT 0,
    avg_save_rate REAL DEFAULT 0,
    avg_share_rate REAL DEFAULT 0,
    avg_non_follower_pct REAL DEFAULT 0,

    -- Viral Score = (saves*2) + (shares*3) + engagement + (non_follower*0.015)
    viral_score REAL DEFAULT 0,

    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(hook_type, topic_category, platform)
);

-- ============ A/B TEST RESULTS ============
CREATE TABLE IF NOT EXISTS ab_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Test Info
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

    -- Results
    selected_variant TEXT,    -- 'A' or 'B'
    selection_reason TEXT,
    actual_performance REAL,
    winner_confirmed BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- ============ APPROVAL LOGS ============
CREATE TABLE IF NOT EXISTS approval_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    post_id INTEGER,
    stage TEXT,           -- topic, content, visual, review, final
    action TEXT,          -- approved, rejected, revised
    user_id TEXT,
    feedback TEXT,
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- ============ PROMPT HISTORY ============
CREATE TABLE IF NOT EXISTS prompt_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    prompt_type TEXT NOT NULL,    -- 'video' or 'image'
    prompt_text TEXT NOT NULL,
    prompt_style TEXT,            -- 'cinematic', 'documentary', 'pov', 'aerial', etc.
    prompt_hash TEXT,             -- MD5 hash for duplicate detection

    -- Performance Metrics
    reach INTEGER DEFAULT 0,
    engagement_rate REAL DEFAULT 0,
    likes INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    performance_updated_at TIMESTAMP,

    FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- ============ INDEXES ============
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled ON posts(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published_at);
CREATE INDEX IF NOT EXISTS idx_analytics_post ON analytics(post_id);
CREATE INDEX IF NOT EXISTS idx_hook_perf_type ON hook_performance(hook_type);
CREATE INDEX IF NOT EXISTS idx_prompt_hash ON prompt_history(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_prompt_type ON prompt_history(prompt_type);
