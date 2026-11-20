-- Retain company logo version for generated offer letters.
ALTER TABLE people_offers ADD COLUMN IF NOT EXISTS letterhead_logo_key VARCHAR(100) NOT NULL DEFAULT '';
