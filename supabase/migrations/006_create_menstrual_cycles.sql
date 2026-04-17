-- Cycle tracking: period dates, cycle length, symptoms
CREATE TABLE IF NOT EXISTS menstrual_cycles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    start_date   DATE NOT NULL,            -- first day of period
    end_date     DATE,                     -- last day of period (NULL = ongoing)
    cycle_length INT DEFAULT 28,           -- average cycle length in days
    period_length INT DEFAULT 5,           -- average period duration in days
    symptoms     JSONB DEFAULT '[]'::jsonb,-- e.g. ["cramps","headache","bloating"]
    mood         INT CHECK (mood BETWEEN 1 AND 10),
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

-- Row-Level Security
ALTER TABLE menstrual_cycles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own cycles" ON menstrual_cycles
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users insert own cycles" ON menstrual_cycles
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own cycles" ON menstrual_cycles
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users delete own cycles" ON menstrual_cycles
    FOR DELETE USING (auth.uid() = user_id);

-- Index for fast lookups
CREATE INDEX idx_cycles_user_date ON menstrual_cycles(user_id, start_date DESC);