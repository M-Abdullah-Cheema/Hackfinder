-- HackFinder Global — Phase 2 residual fields
-- Taxonomy subcategory + staging geo/time columns

ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS subcategory VARCHAR;
CREATE INDEX IF NOT EXISTS ix_final_opportunities_subcategory ON final_opportunities (subcategory);
CREATE INDEX IF NOT EXISTS ix_final_taxonomy ON final_opportunities (domain, subcategory, format);

ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS city VARCHAR;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS country VARCHAR;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS start_datetime_utc TIMESTAMPTZ;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS end_datetime_utc TIMESTAMPTZ;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS local_timezone VARCHAR;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS domain VARCHAR;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS subcategory VARCHAR;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS format VARCHAR;
ALTER TABLE scraped_opportunities ADD COLUMN IF NOT EXISTS registration_url VARCHAR;
