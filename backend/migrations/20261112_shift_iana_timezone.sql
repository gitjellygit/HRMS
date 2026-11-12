-- Run once before deploying the timezone-aware Shift model on an existing database.
-- Retain existing shift behavior as IST until HR updates each shift timezone.
ALTER TABLE time_shifts ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata';
