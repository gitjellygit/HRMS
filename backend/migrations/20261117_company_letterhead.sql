-- Company logo metadata. Actual image stored in secure uploads volume.
CREATE TABLE IF NOT EXISTS people_company_letterhead (
 id INTEGER PRIMARY KEY,
 logo_key VARCHAR(100) NOT NULL DEFAULT '',
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
