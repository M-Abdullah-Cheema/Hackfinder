-- HackFinder Global — Phase 1 migration
-- Run via: python scripts/apply_migration_001.py
-- Or paste into Supabase SQL Editor.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS city VARCHAR;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS country VARCHAR;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS start_datetime_utc TIMESTAMPTZ;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS end_datetime_utc TIMESTAMPTZ;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS local_timezone VARCHAR;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS domain VARCHAR;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS format VARCHAR;
ALTER TABLE final_opportunities ADD COLUMN IF NOT EXISTS location geography(Point, 4326);

CREATE INDEX IF NOT EXISTS ix_final_opportunities_city ON final_opportunities (city);
CREATE INDEX IF NOT EXISTS ix_final_opportunities_country ON final_opportunities (country);
CREATE INDEX IF NOT EXISTS ix_final_opportunities_domain ON final_opportunities (domain);
CREATE INDEX IF NOT EXISTS ix_final_opportunities_start_utc ON final_opportunities (start_datetime_utc);

UPDATE final_opportunities
SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL
  AND location IS NULL;

CREATE INDEX IF NOT EXISTS ix_final_opportunities_location_gist
  ON final_opportunities
  USING GIST (location);
