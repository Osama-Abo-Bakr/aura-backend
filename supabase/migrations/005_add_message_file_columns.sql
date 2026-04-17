-- 005_add_message_file_columns.sql
-- Add file attachment and analysis reference columns to messages table

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS file_path TEXT,
  ADD COLUMN IF NOT EXISTS file_type TEXT,
  ADD COLUMN IF NOT EXISTS analysis_id UUID REFERENCES analyses(id);

-- Index for quick lookup of analysis by conversation
CREATE INDEX IF NOT EXISTS idx_messages_analysis_id ON messages(analysis_id) WHERE analysis_id IS NOT NULL;