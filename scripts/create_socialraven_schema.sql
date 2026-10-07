-- Socialraven: create + expose the `socialraven` schema on the shared Supabase
-- instance at https://supabasemedhavn.viktron.ai
--
-- IMPORTANT: that Supabase is SHARED. It already backs nexus, loomfold,
-- tensorarena, auraguide, soil_did_it, medhavn and aurapath, one schema each.
-- Never `ALTER ROLE authenticator SET pgrst.db_schemas = '<literal list>'` --
-- a plain SET replaces the whole list and silently un-exposes every other
-- app's schema. Section 4 below appends instead.
--
-- Run in Supabase Studio -> SQL Editor. Idempotent; safe to re-run.
-- Table shapes mirror app/db/postgres.py (init_postgres) as of 2026-10-04.

-- ---------------------------------------------------------------------------
-- 1. Schema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS socialraven;

-- gen_random_uuid() is core in PostgreSQL 13+, which Supabase runs, so no
-- pgcrypto extension is required.

-- ---------------------------------------------------------------------------
-- 2. Tables
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS socialraven.users (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email                  text UNIQUE,
  full_name              text,
  avatar_url             text,
  password_hash          text,
  google_id              text,
  is_active              boolean     NOT NULL DEFAULT true,
  api_key_hash           text UNIQUE,
  api_keys               jsonb       NOT NULL DEFAULT '[]'::jsonb,
  linked_accounts        jsonb       NOT NULL DEFAULT '[]'::jsonb,
  profiles               jsonb       NOT NULL DEFAULT '[]'::jsonb,
  developer_keys         jsonb       NOT NULL DEFAULT '{}'::jsonb,
  brand_kit              jsonb       NOT NULL DEFAULT '{}'::jsonb,
  plan_tier              text        NOT NULL DEFAULT 'starter',
  max_profiles           integer     NOT NULL DEFAULT 50,
  stripe_customer_id     text,
  stripe_subscription_id text,
  subscription_status    text,
  subscription_tier      text,
  credits                integer     NOT NULL DEFAULT 100,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.organizations (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                   text        NOT NULL,
  slug                   text UNIQUE,
  logo                   text,
  owner_id               uuid        REFERENCES socialraven.users(id) ON DELETE SET NULL,
  settings               jsonb       NOT NULL DEFAULT '{}'::jsonb,
  billing_email          text,
  stripe_customer_id     text,
  stripe_subscription_id text,
  subscription_tier      text        DEFAULT 'free',
  subscription_status    text,
  billing_cycle_start    timestamptz,
  billing_cycle_end      timestamptz,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.organization_members (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid        REFERENCES socialraven.organizations(id) ON DELETE CASCADE,
  user_id         uuid        REFERENCES socialraven.users(id) ON DELETE CASCADE,
  role            text        NOT NULL DEFAULT 'user',
  invited_by      uuid        REFERENCES socialraven.users(id),
  status          text        NOT NULL DEFAULT 'active',
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, user_id)
);

CREATE TABLE IF NOT EXISTS socialraven.oauth_states (
  state_id      text PRIMARY KEY,
  code_verifier text,
  extra_data    jsonb       NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.scheduled_posts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid        NOT NULL REFERENCES socialraven.users(id) ON DELETE CASCADE,
  organization_id uuid        REFERENCES socialraven.organizations(id) ON DELETE SET NULL,
  accounts        jsonb       NOT NULL DEFAULT '[]'::jsonb,
  content         text        NOT NULL DEFAULT '',
  media           jsonb       NOT NULL DEFAULT '[]'::jsonb,
  scheduled_for   timestamptz NOT NULL,
  status          text        NOT NULL DEFAULT 'pending',
  job_id          text,
  result          jsonb,
  error           text,
  attempts        integer     NOT NULL DEFAULT 0,
  last_attempt_at timestamptz,
  published_at    timestamptz,
  tags            jsonb       NOT NULL DEFAULT '[]'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.activity_logs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid        REFERENCES socialraven.users(id) ON DELETE CASCADE,
  organization_id uuid        REFERENCES socialraven.organizations(id) ON DELETE SET NULL,
  title           text        NOT NULL,
  platform        text,
  type            text        NOT NULL DEFAULT 'info',
  meta            jsonb,
  time            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.webhooks (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid        REFERENCES socialraven.users(id) ON DELETE CASCADE,
  organization_id   uuid        REFERENCES socialraven.organizations(id) ON DELETE SET NULL,
  name              text        NOT NULL,
  url               text        NOT NULL,
  events            jsonb       NOT NULL DEFAULT '[]'::jsonb,
  secret            text,
  is_active         boolean     NOT NULL DEFAULT true,
  last_triggered_at timestamptz,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.notifications (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid        REFERENCES socialraven.users(id) ON DELETE CASCADE,
  organization_id uuid        REFERENCES socialraven.organizations(id) ON DELETE SET NULL,
  title           text        NOT NULL,
  message         text,
  type            text        NOT NULL DEFAULT 'info',
  is_read         boolean     NOT NULL DEFAULT false,
  link            text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.autopost_configs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid        REFERENCES socialraven.users(id) ON DELETE CASCADE,
  organization_id uuid        REFERENCES socialraven.organizations(id) ON DELETE SET NULL,
  name            text        NOT NULL,
  feed_url        text        NOT NULL,
  platforms       jsonb       NOT NULL DEFAULT '[]'::jsonb,
  post_template   text,
  is_active       boolean     NOT NULL DEFAULT true,
  last_fetched_at timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS socialraven.media_assets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid        REFERENCES socialraven.users(id) ON DELETE CASCADE,
  organization_id uuid        REFERENCES socialraven.organizations(id) ON DELETE SET NULL,
  filename        text,
  content_type    text,
  file_type       text,
  cloud_url       text,
  data_url        text,
  local_path      text,
  size_bytes      bigint,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 3. Indexes (mirror setup_indices.py, plus the lookups postgres.py does)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_activity_logs_user_time
  ON socialraven.activity_logs (user_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_user_time
  ON socialraven.scheduled_posts (user_id, scheduled_for DESC);
CREATE INDEX IF NOT EXISTS idx_scheduled_posts_due
  ON socialraven.scheduled_posts (status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_users_email_lower
  ON socialraven.users (lower(email));
CREATE INDEX IF NOT EXISTS idx_users_google_id
  ON socialraven.users (google_id);
CREATE INDEX IF NOT EXISTS idx_media_assets_user
  ON socialraven.media_assets (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
  ON socialraven.notifications (user_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_org_members_user
  ON socialraven.organization_members (user_id);

-- ---------------------------------------------------------------------------
-- 4. Expose the schema to the API -- APPEND, never SET a literal list
-- ---------------------------------------------------------------------------
DO $do$
DECLARE
  current_schemas text;
BEGIN
  SELECT split_part(cfg, '=', 2)
    INTO current_schemas
    FROM pg_roles r, unnest(coalesce(r.rolconfig, '{}')) AS cfg
   WHERE r.rolname = 'authenticator'
     AND cfg LIKE 'pgrst.db_schemas=%';

  current_schemas := coalesce(current_schemas, 'public, storage, graphql_public');

  IF NOT ('socialraven' = ANY (string_to_array(replace(current_schemas, ' ', ''), ','))) THEN
    current_schemas := current_schemas || ', socialraven';
  END IF;

  EXECUTE format('ALTER ROLE authenticator SET pgrst.db_schemas = %L', current_schemas);
  RAISE NOTICE 'pgrst.db_schemas = %', current_schemas;
END
$do$;

-- PostgREST needs USAGE on the schema to see it at all. Table privileges go to
-- authenticated/service_role only; `anon` deliberately gets none, and RLS in
-- section 5 is deny-by-default on top of that.
GRANT USAGE ON SCHEMA socialraven TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES    IN SCHEMA socialraven TO authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA socialraven TO authenticated, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA socialraven TO authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA socialraven
  GRANT ALL ON TABLES TO authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA socialraven
  GRANT ALL ON SEQUENCES TO authenticated, service_role;

-- Reload config first (db_schemas is a config change), then the schema cache.
NOTIFY pgrst, 'reload config';
NOTIFY pgrst, 'reload schema';

-- ---------------------------------------------------------------------------
-- 5. RLS: deny-by-default. The FastAPI backend connects over asyncpg as its
--    own owner/service role and bypasses RLS, so this only gates PostgREST.
--    Add per-table policies when a client should query the API directly.
-- ---------------------------------------------------------------------------
ALTER TABLE socialraven.users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.organizations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.oauth_states         ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.scheduled_posts      ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.activity_logs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.webhooks             ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.notifications        ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.autopost_configs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE socialraven.media_assets         ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 6. Verify
-- ---------------------------------------------------------------------------
SELECT rolconfig FROM pg_roles WHERE rolname = 'authenticator';

SELECT table_name
  FROM information_schema.tables
 WHERE table_schema = 'socialraven'
 ORDER BY table_name;
