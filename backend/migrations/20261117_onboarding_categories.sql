-- Configurable onboarding categories. Existing task references continue to use stable slugs.
CREATE TABLE IF NOT EXISTS people_onboarding_categories (
 id SERIAL PRIMARY KEY,
 slug VARCHAR(30) NOT NULL UNIQUE,
 display_name VARCHAR(80) NOT NULL,
 active BOOLEAN NOT NULL DEFAULT TRUE
);
INSERT INTO people_onboarding_categories(slug,display_name,active)
VALUES ('document','Document',TRUE),('asset','Asset',TRUE),('induction','Induction',TRUE),('hr','HR',TRUE),('it','IT',TRUE)
ON CONFLICT (slug) DO NOTHING;
