-- Add media support and audience targeting to People Operations announcements.
ALTER TABLE people_announcements ADD COLUMN IF NOT EXISTS media_key VARCHAR(100) NOT NULL DEFAULT '';
ALTER TABLE people_announcements ADD COLUMN IF NOT EXISTS audience_ids TEXT NOT NULL DEFAULT '[]';
