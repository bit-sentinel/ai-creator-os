-- =============================================================================
-- AI Creator OS — Supabase (PostgreSQL) Schema
-- Run this in your Supabase SQL editor or via psql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- For fuzzy text dedup

-- =============================================================================
-- ACCOUNTS
-- =============================================================================
CREATE TABLE IF NOT EXISTS accounts (
    account_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform            VARCHAR(50)  NOT NULL DEFAULT 'instagram',
    username            VARCHAR(100) NOT NULL UNIQUE,
    niche               VARCHAR(100) NOT NULL,
    posting_frequency   INTEGER      NOT NULL DEFAULT 5,      -- posts/day
    preferred_post_times TEXT[]      DEFAULT '{}',            -- UTC times e.g. {"07:00","12:00"}
    hashtag_sets        JSONB        DEFAULT '[]',
    tone                VARCHAR(50)  DEFAULT 'educational',
    access_token        TEXT,                                  -- encrypted at app level
    instagram_user_id   VARCHAR(100),
    status              VARCHAR(20)  NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'paused', 'error')),
    created_at          TIMESTAMPTZ  DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- TRENDS
-- =============================================================================
CREATE TABLE IF NOT EXISTS trends (
    trend_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform        VARCHAR(50)  NOT NULL,                -- 'linkedin' | 'reddit'
    topic           TEXT         NOT NULL,
    source_url      TEXT,
    viral_score     FLOAT        DEFAULT 0,               -- 0-100 LLM-computed score
    niche           VARCHAR(100),
    raw_data        JSONB,                                -- original API response
    used            BOOLEAN      DEFAULT FALSE,
    discovered_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- POSTS
-- =============================================================================
CREATE TABLE IF NOT EXISTS posts (
    post_id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id              UUID         NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    topic                   TEXT         NOT NULL,
    hook                    TEXT         NOT NULL,
    slides                  JSONB        NOT NULL DEFAULT '[]',
    -- [{"slide_number":1,"title":"..","content":"..","image_url":"..","image_prompt":".."}]
    caption                 TEXT         NOT NULL,
    hashtags                TEXT[]       NOT NULL DEFAULT '{}',
    image_urls              TEXT[]       DEFAULT '{}',
    carousel_container_id   VARCHAR(200),                -- IG container ID during upload
    instagram_post_id       VARCHAR(200),                -- Published IG media ID
    status                  VARCHAR(20)  NOT NULL DEFAULT 'draft'
                                CHECK (status IN (
                                    'draft','generated','designed',
                                    'scheduled','published','failed'
                                )),
    scheduled_at            TIMESTAMPTZ,
    posted_at               TIMESTAMPTZ,
    content_hash            VARCHAR(64)  UNIQUE,          -- SHA-256 of topic+hook for dedup
    error_log               TEXT,
    created_at              TIMESTAMPTZ  DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- ENGAGEMENT METRICS
-- =============================================================================
CREATE TABLE IF NOT EXISTS engagement_metrics (
    metric_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id             UUID         NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    likes               INTEGER      DEFAULT 0,
    comments            INTEGER      DEFAULT 0,
    shares              INTEGER      DEFAULT 0,
    saves               INTEGER      DEFAULT 0,
    reach               INTEGER      DEFAULT 0,
    impressions         INTEGER      DEFAULT 0,
    -- Engagement score: likes*1 + comments*3 + shares*5 + saves*4
    engagement_score    FLOAT GENERATED ALWAYS AS (
                            likes * 1.0 + comments * 3.0 + shares * 5.0 + saves * 4.0
                        ) STORED,
    collected_at        TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- STRATEGY MEMORY  (one row per account, upserted by learning agent)
-- =============================================================================
CREATE TABLE IF NOT EXISTS strategy_memory (
    memory_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id          UUID         UNIQUE REFERENCES accounts(account_id) ON DELETE CASCADE,
    best_topics         JSONB        DEFAULT '[]',
    -- [{"topic":"..","avg_score":123.4,"sample_count":5}]
    best_hooks          JSONB        DEFAULT '[]',
    -- [{"hook":"..","pattern":"question|stat|story","avg_score":99}]
    best_posting_times  JSONB        DEFAULT '[]',
    -- [{"hour_utc":7,"avg_score":110.2}]
    best_carousel_format JSONB       DEFAULT '{}',
    -- {"optimal_slide_count":5,"best_cta_type":"question","best_slide1_style":"stat"}
    best_hashtags       JSONB        DEFAULT '[]',
    -- [{"tag":"#AI","avg_reach":5000}]
    worst_topics        JSONB        DEFAULT '[]',
    performance_baseline JSONB       DEFAULT '{}',
    -- {"avg_likes":200,"avg_comments":50,"avg_saves":80}
    last_updated        TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- CONTENT TEMPLATES  (reusable high-performing structures)
-- =============================================================================
CREATE TABLE IF NOT EXISTS content_templates (
    template_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(100) NOT NULL,
    niche               VARCHAR(100),
    hook_template       TEXT,            -- e.g. "X things about {topic} that will {benefit}"
    slide_structure     JSONB,           -- array of slide role descriptors
    tone                VARCHAR(50),
    avg_engagement_score FLOAT          DEFAULT 0,
    usage_count         INTEGER         DEFAULT 0,
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);

-- =============================================================================
-- SCHEDULED JOBS  (audit log for all automation runs)
-- =============================================================================
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    job_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id      UUID         REFERENCES accounts(account_id) ON DELETE SET NULL,
    post_id         UUID         REFERENCES posts(post_id) ON DELETE SET NULL,
    job_type        VARCHAR(50)  NOT NULL,
    -- 'trend_discovery'|'content_generation'|'publishing'|'analytics'|'learning'
    scheduled_at    TIMESTAMPTZ  NOT NULL,
    executed_at     TIMESTAMPTZ,
    status          VARCHAR(20)  DEFAULT 'pending'
                        CHECK (status IN ('pending','running','completed','failed')),
    result          JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_posts_account_id      ON posts(account_id);
CREATE INDEX IF NOT EXISTS idx_posts_status          ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_at    ON posts(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_posts_created_at      ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_post_id       ON engagement_metrics(post_id);
CREATE INDEX IF NOT EXISTS idx_metrics_collected_at  ON engagement_metrics(collected_at);
CREATE INDEX IF NOT EXISTS idx_trends_niche          ON trends(niche);
CREATE INDEX IF NOT EXISTS idx_trends_used           ON trends(used);
CREATE INDEX IF NOT EXISTS idx_trends_discovered_at  ON trends(discovered_at);
CREATE INDEX IF NOT EXISTS idx_jobs_account_id       ON scheduled_jobs(account_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status           ON scheduled_jobs(status);

-- Full-text on trend topics for fuzzy dedup
CREATE INDEX IF NOT EXISTS idx_trends_topic_trgm ON trends USING gin (topic gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_posts_topic_trgm  ON posts  USING gin (topic gin_trgm_ops);

-- =============================================================================
-- UPDATED-AT TRIGGER
-- =============================================================================
CREATE OR REPLACE FUNCTION _set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

CREATE TRIGGER trg_posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION _set_updated_at();

-- =============================================================================
-- HELPER FUNCTION: fuzzy duplicate check (called by supabase_client.py)
-- =============================================================================
CREATE OR REPLACE FUNCTION check_topic_similarity(
    p_topic     TEXT,
    p_since     TIMESTAMPTZ,
    p_threshold FLOAT DEFAULT 0.7
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM   trends
        WHERE  discovered_at > p_since
          AND  similarity(topic, p_topic) > p_threshold
    )
    OR EXISTS (
        SELECT 1
        FROM   posts
        WHERE  created_at > p_since
          AND  similarity(topic, p_topic) > p_threshold
    );
$$;

-- =============================================================================
-- SEED: default content templates
-- =============================================================================
INSERT INTO content_templates (name, niche, hook_template, slide_structure, tone)
VALUES
(
    'Viral List Post',
    NULL,
    '{N} {topic} secrets that {audience} wish they knew earlier',
    '[
        {"slide":1,"role":"hook","style":"bold_stat_or_number"},
        {"slide":2,"role":"core_idea","style":"definition_or_overview"},
        {"slide":3,"role":"explanation","style":"numbered_points"},
        {"slide":4,"role":"insight","style":"contrarian_take"},
        {"slide":5,"role":"cta","style":"question_or_save_prompt"}
    ]',
    'educational'
),
(
    'Story Arc',
    NULL,
    'I {negative_outcome} until I discovered {solution}',
    '[
        {"slide":1,"role":"hook","style":"personal_story_opening"},
        {"slide":2,"role":"problem","style":"pain_point"},
        {"slide":3,"role":"turning_point","style":"discovery"},
        {"slide":4,"role":"result","style":"transformation"},
        {"slide":5,"role":"cta","style":"invitation_to_try"}
    ]',
    'inspirational'
),
(
    'Myth Buster',
    NULL,
    'Everyone is wrong about {topic}. Here''s the truth:',
    '[
        {"slide":1,"role":"hook","style":"bold_claim"},
        {"slide":2,"role":"myth","style":"common_misconception"},
        {"slide":3,"role":"reality","style":"data_backed_truth"},
        {"slide":4,"role":"implication","style":"so_what"},
        {"slide":5,"role":"cta","style":"share_prompt"}
    ]',
    'educational'
)
ON CONFLICT DO NOTHING;
