-- ============================================================================
-- Algobattle — Postgres bootstrap (runs once on first container start)
-- ----------------------------------------------------------------------------
-- Mounted at /docker-entrypoint-initdb.d/01-init.sql in the postgres container.
-- The official postgres image runs every .sql file in that dir, sorted,
-- only on a fresh data directory.
-- ============================================================================

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- fuzzy text search
CREATE EXTENSION IF NOT EXISTS "citext";         -- case-insensitive email

-- ----------------------------------------------------------------------------
-- Schemas (organise tables for permissions + migration sanity)
-- ----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS algobattle;

-- ----------------------------------------------------------------------------
-- Roles
-- ----------------------------------------------------------------------------
-- Application role used by the API at runtime (least-privilege)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'algobattle_app') THEN
    CREATE ROLE algobattle_app LOGIN PASSWORD 'change_me_app_role_password';
  END IF;
END
$$;

-- Read-only role for analytics / BI tools
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'algobattle_readonly') THEN
    CREATE ROLE algobattle_readonly LOGIN PASSWORD 'change_me_readonly_password';
  END IF;
END
$$;

-- ----------------------------------------------------------------------------
-- Tables (minimal — full schema lives in backend/app/models and is managed
-- by Alembic. This file only ensures the DB exists with sane extensions.)
-- ----------------------------------------------------------------------------

-- Tracks migration state (Alembic also creates its own table; this is a
-- belt-and-braces fallback so we can detect "was this DB initialised?").
CREATE TABLE IF NOT EXISTS algobattle.meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO algobattle.meta (key, value)
VALUES ('initialised_at', to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')),
       ('schema_version', '1')
ON CONFLICT (key) DO NOTHING;

-- ----------------------------------------------------------------------------
-- Grants
-- ----------------------------------------------------------------------------
GRANT USAGE ON SCHEMA algobattle TO algobattle_app, algobattle_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA algobattle TO algobattle_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA algobattle
    GRANT SELECT ON TABLES TO algobattle_readonly;

-- Note: full DDL rights for the application role are granted only during
-- migrations (when the api container runs alembic upgrade head). For
-- runtime, the app role has CRUD via the per-table grants Alembic emits.
GRANT CONNECT ON DATABASE algobattle TO algobattle_app, algobattle_readonly;

-- ----------------------------------------------------------------------------
-- Connection limits — protect from runaway app pods
-- ----------------------------------------------------------------------------
ALTER ROLE algobattle_app CONNECTION LIMIT 100;
ALTER ROLE algobattle_readonly CONNECTION LIMIT 20;

-- Done.
SELECT 'Algobattle DB initialised' AS status;