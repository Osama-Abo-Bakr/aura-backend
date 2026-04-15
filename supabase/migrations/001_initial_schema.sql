-- =============================================================================
-- 001_initial_schema.sql
-- Aura Health — initial database schema
-- =============================================================================
-- Run order: this file must be applied first.
-- Compatible with PostgreSQL 15+ (Supabase).
-- =============================================================================

-- Enable UUID generation (already available in Supabase by default)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- PROFILES
-- =============================================================================

CREATE TABLE IF NOT EXISTS profiles (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name           TEXT        NOT NULL,
    date_of_birth       DATE,
    language            TEXT        NOT NULL DEFAULT 'ar' CHECK (language IN ('ar', 'en')),
    country             CHAR(2),    -- ISO 3166-1 alpha-2
    avatar_url          TEXT,
    health_goals        TEXT[]      NOT NULL DEFAULT '{}',
    conditions          TEXT[]      NOT NULL DEFAULT '{}',  -- self-reported chronic conditions
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_profile"
    ON profiles FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users_insert_own_profile"
    ON profiles FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_update_own_profile"
    ON profiles FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- SUBSCRIPTIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS subscriptions (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    tier                    TEXT        NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'premium')),
    status                  TEXT        NOT NULL DEFAULT 'active'
                                            CHECK (status IN ('active', 'cancelled', 'past_due', 'trialing')),
    stripe_customer_id      TEXT,
    stripe_subscription_id  TEXT,
    current_period_end      TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_subscription"
    ON subscriptions FOR SELECT
    USING (auth.uid() = user_id);

-- Only the service role (backend) may insert / update subscriptions.
-- No INSERT / UPDATE policy for authenticated users intentionally.

CREATE TRIGGER trg_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- AI_INTERACTIONS  (quota tracking)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ai_interactions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    interaction_type    TEXT        NOT NULL CHECK (interaction_type IN ('chat', 'skin', 'report')),
    tokens_used         INTEGER,
    latency_ms          INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE ai_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_interactions"
    ON ai_interactions FOR SELECT
    USING (auth.uid() = user_id);

-- Index used by the monthly quota check in deps.py
CREATE INDEX IF NOT EXISTS idx_ai_interactions_user_type_date
    ON ai_interactions (user_id, interaction_type, created_at DESC);

-- =============================================================================
-- CONVERSATIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title               TEXT,
    language            TEXT        NOT NULL DEFAULT 'ar' CHECK (language IN ('ar', 'en')),
    last_message_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_conversations"
    ON conversations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users_insert_own_conversations"
    ON conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_update_own_conversations"
    ON conversations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "users_delete_own_conversations"
    ON conversations FOR DELETE
    USING (auth.uid() = user_id);

-- =============================================================================
-- MESSAGES
-- =============================================================================

CREATE TABLE IF NOT EXISTS messages (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID        NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role                TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content             TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_messages"
    ON messages FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users_insert_own_messages"
    ON messages FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Index used when loading a conversation's message thread
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (conversation_id, created_at ASC);

-- =============================================================================
-- ANALYSES  (skin + medical report results)
-- =============================================================================

CREATE TABLE IF NOT EXISTS analyses (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    analysis_type       TEXT        NOT NULL CHECK (analysis_type IN ('skin', 'report')),
    status              TEXT        NOT NULL DEFAULT 'queued'
                                        CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    file_path           TEXT        NOT NULL,
    result              JSONB,      -- full structured result from Gemini
    result_summary      TEXT,       -- short human-readable summary
    language            TEXT        NOT NULL DEFAULT 'ar',
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_analyses"
    ON analyses FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users_insert_own_analyses"
    ON analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE TRIGGER trg_analyses_updated_at
    BEFORE UPDATE ON analyses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Index used when listing analysis history
CREATE INDEX IF NOT EXISTS idx_analyses_user_created
    ON analyses (user_id, created_at DESC);

-- =============================================================================
-- HEALTH_LOGS
-- =============================================================================

CREATE TABLE IF NOT EXISTS health_logs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    log_date            DATE        NOT NULL,
    mood                SMALLINT    CHECK (mood BETWEEN 1 AND 10),
    energy              SMALLINT    CHECK (energy BETWEEN 1 AND 10),
    sleep_hours         NUMERIC(4,1) CHECK (sleep_hours >= 0 AND sleep_hours <= 24),
    water_ml            INTEGER     CHECK (water_ml >= 0),
    exercise_minutes    INTEGER     CHECK (exercise_minutes >= 0),
    symptoms            TEXT[]      NOT NULL DEFAULT '{}',
    notes               TEXT,
    metadata            JSONB,      -- flexible: menstrual cycle data, medications, etc.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Only one log entry per user per day
    CONSTRAINT uq_health_logs_user_date UNIQUE (user_id, log_date)
);

ALTER TABLE health_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_health_logs"
    ON health_logs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users_insert_own_health_logs"
    ON health_logs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_update_own_health_logs"
    ON health_logs FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_delete_own_health_logs"
    ON health_logs FOR DELETE
    USING (auth.uid() = user_id);

CREATE TRIGGER trg_health_logs_updated_at
    BEFORE UPDATE ON health_logs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Index used for trend queries (last 30 days, etc.)
CREATE INDEX IF NOT EXISTS idx_health_logs_user_date
    ON health_logs (user_id, log_date DESC);

-- =============================================================================
-- WELLNESS_PLANS
-- =============================================================================

CREATE TABLE IF NOT EXISTS wellness_plans (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title               TEXT        NOT NULL,
    description         TEXT,
    tasks               JSONB       NOT NULL DEFAULT '[]',  -- array of WellnessPlanTask
    start_date          DATE,
    end_date            DATE,
    generated_by_ai     BOOLEAN     NOT NULL DEFAULT TRUE,
    language            TEXT        NOT NULL DEFAULT 'ar' CHECK (language IN ('ar', 'en')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE wellness_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_select_own_wellness_plans"
    ON wellness_plans FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "users_insert_own_wellness_plans"
    ON wellness_plans FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_delete_own_wellness_plans"
    ON wellness_plans FOR DELETE
    USING (auth.uid() = user_id);

-- =============================================================================
-- BOOTSTRAP: create a free subscription row whenever a new user signs up
-- =============================================================================

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO subscriptions (user_id, tier, status)
    VALUES (NEW.id, 'free', 'active')
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
