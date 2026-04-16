-- Run this script directly on your PostgreSQL database (via psql or pgAdmin)

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE,
    password_hash text,
    google_id text,
    api_key_hash text UNIQUE,
    api_keys jsonb NOT NULL DEFAULT '[]'::jsonb,
    linked_accounts jsonb NOT NULL DEFAULT '[]'::jsonb,
    profiles jsonb NOT NULL DEFAULT '[]'::jsonb,
    developer_keys jsonb NOT NULL DEFAULT '{}'::jsonb,
    plan_tier text NOT NULL DEFAULT 'starter',
    max_profiles integer NOT NULL DEFAULT 50,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- OAuth States table
CREATE TABLE IF NOT EXISTS oauth_states (
    state_id text PRIMARY KEY,
    code_verifier text,
    extra_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Scheduled Posts table
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    accounts jsonb NOT NULL DEFAULT '[]'::jsonb,
    content text NOT NULL DEFAULT '',
    media jsonb NOT NULL DEFAULT '[]'::jsonb,
    scheduled_for timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    job_id text,
    result jsonb,
    error text,
    attempts integer NOT NULL DEFAULT 0,
    last_attempt_at timestamptz,
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Activity Logs table
CREATE TABLE IF NOT EXISTS activity_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text NOT NULL,
    platform text,
    type text NOT NULL DEFAULT 'info',
    meta jsonb,
    time timestamptz NOT NULL DEFAULT now()
);

-- Media Assets table
CREATE TABLE IF NOT EXISTS media_assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename text,
    content_type text,
    file_type text,
    cloud_url text,
    data_url text,
    local_path text,
    size_bytes bigint,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Verify tables created
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';