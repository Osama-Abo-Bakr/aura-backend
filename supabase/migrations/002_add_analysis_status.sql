-- Add status column to analyses table for async processing
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'completed';

-- Index for status lookups
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses (user_id, status, created_at DESC);
