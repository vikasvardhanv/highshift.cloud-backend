import json
import os
import uuid
from typing import Any, Dict, Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


def _normalize_pg_url(url: str) -> str:
    normalized = url.strip()
    if normalized.lower().startswith("postgres://"):
        return "postgresql://" + normalized[len("postgres://") :]
    if normalized.lower().startswith("postgresql://"):
        return normalized
    if "://" not in normalized and "@" in normalized:
        return f"postgresql://{normalized}"
    return normalized


def is_postgres_url(url: Optional[str]) -> bool:
    if not url:
        return False
    normalized = url.strip().lower()
    return normalized.startswith("postgres://") or normalized.startswith("postgresql://")


async def init_postgres(database_url: str) -> bool:
    global _pool
    if _pool:
        return True

    pg_url = _normalize_pg_url(database_url)
    try:
        _pool = await asyncpg.create_pool(pg_url, min_size=1, max_size=5, timeout=12)
        async with _pool.acquire() as conn:
            await conn.execute("create extension if not exists pgcrypto;")
            await conn.execute(
            """
            create table if not exists users (
              id uuid primary key default gen_random_uuid(),
              email text unique,
              password_hash text,
              google_id text,
              api_key_hash text unique,
              api_keys jsonb not null default '[]'::jsonb,
              linked_accounts jsonb not null default '[]'::jsonb,
              profiles jsonb not null default '[]'::jsonb,
              developer_keys jsonb not null default '{}'::jsonb,
              plan_tier text not null default 'starter',
              max_profiles integer not null default 50,
              created_at timestamptz not null default now(),
              updated_at timestamptz not null default now()
            );
            """
            )
            await conn.execute(
            """
            create table if not exists oauth_states (
              state_id text primary key,
              code_verifier text,
              extra_data jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now()
            );
            """
            )
            await conn.execute(
            """
            create table if not exists scheduled_posts (
              id uuid primary key default gen_random_uuid(),
              user_id uuid not null references users(id) on delete cascade,
              accounts jsonb not null default '[]'::jsonb,
              content text not null default '',
              media jsonb not null default '[]'::jsonb,
              scheduled_for timestamptz not null,
              status text not null default 'pending',
              job_id text,
              result jsonb,
              error text,
              attempts integer not null default 0,
              last_attempt_at timestamptz,
              published_at timestamptz,
              created_at timestamptz not null default now(),
              updated_at timestamptz not null default now()
            );
            """
            )
            await conn.execute(
            """
            create table if not exists activity_logs (
              id uuid primary key default gen_random_uuid(),
              user_id uuid not null references users(id) on delete cascade,
              title text not null,
              platform text,
              type text not null default 'info',
              meta jsonb,
              time timestamptz not null default now()
            );
            """
            )
            await conn.execute(
            """
            create table if not exists media_assets (
              id uuid primary key default gen_random_uuid(),
              user_id uuid not null references users(id) on delete cascade,
              filename text,
              content_type text,
              file_type text,
              cloud_url text,
              data_url text,
              local_path text,
              size_bytes bigint,
              created_at timestamptz not null default now()
            );
            """
            )
    except Exception:
        if _pool:
            await _pool.close()
            _pool = None
        raise
    return True


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Postgres pool is not initialized")
    return _pool


def _record_to_dict(record: Optional[asyncpg.Record]) -> Optional[Dict[str, Any]]:
    if not record:
        return None
    data = dict(record)
    # asyncpg already decodes json/jsonb to dict/list.
    return data


async def fetch_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select * from users where id=$1::uuid", user_id)
    return _record_to_dict(row)


async def fetch_user_by_email_ci(email: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select * from users where lower(email)=lower($1) limit 1", email
        )
    return _record_to_dict(row)


async def fetch_user_by_google_or_email(
    google_id: str, email: str
) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select * from users where google_id=$1 or lower(email)=lower($2) limit 1",
            google_id,
            email,
        )
    return _record_to_dict(row)


async def fetch_user_by_linked_account(platform: str, account_id: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select * from users u
            where exists (
              select 1
              from jsonb_array_elements(u.linked_accounts) as acc
              where acc->>'platform'=$1 and acc->>'accountId'=$2
            )
            limit 1
            """,
            platform,
            account_id,
        )
    return _record_to_dict(row)


async def fetch_user_by_api_key_hash(key_hash: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select * from users u
            where u.api_key_hash=$1
               or exists (
                 select 1
                 from jsonb_array_elements(u.api_keys) as k
                 where k->>'keyHash'=$1
               )
            limit 1
            """,
            key_hash,
        )
    return _record_to_dict(row)


async def insert_user(data: Dict[str, Any]) -> Dict[str, Any]:
    pool = await get_pool()
    user_id = data.get("id") or str(uuid.uuid4())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into users (
              id, email, password_hash, google_id, api_key_hash,
              api_keys, linked_accounts, profiles, developer_keys, plan_tier, max_profiles
            ) values (
              $1::uuid, $2, $3, $4, $5,
              $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb, $10, $11
            )
            returning *
            """,
            user_id,
            data.get("email"),
            data.get("password_hash"),
            data.get("google_id"),
            data.get("api_key_hash"),
            json.dumps(data.get("api_keys") or []),
            json.dumps(data.get("linked_accounts") or []),
            json.dumps(data.get("profiles") or []),
            json.dumps(data.get("developer_keys") or {}),
            data.get("plan_tier") or "starter",
            int(data.get("max_profiles") or 50),
        )
    return _record_to_dict(row)  # type: ignore


async def update_user(user_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            update users set
              email=$2,
              password_hash=$3,
              google_id=$4,
              api_key_hash=$5,
              api_keys=$6::jsonb,
              linked_accounts=$7::jsonb,
              profiles=$8::jsonb,
              developer_keys=$9::jsonb,
              plan_tier=$10,
              max_profiles=$11,
              updated_at=now()
            where id=$1::uuid
            returning *
            """,
            user_id,
            data.get("email"),
            data.get("password_hash"),
            data.get("google_id"),
            data.get("api_key_hash"),
            json.dumps(data.get("api_keys") or []),
            json.dumps(data.get("linked_accounts") or []),
            json.dumps(data.get("profiles") or []),
            json.dumps(data.get("developer_keys") or {}),
            data.get("plan_tier") or "starter",
            int(data.get("max_profiles") or 50),
        )
    return _record_to_dict(row)


async def insert_oauth_state(
    state_id: str, code_verifier: Optional[str] = None, extra_data: Optional[Dict[str, Any]] = None
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            insert into oauth_states (state_id, code_verifier, extra_data)
            values ($1, $2, $3::jsonb)
            on conflict (state_id) do update
              set code_verifier=excluded.code_verifier,
                  extra_data=excluded.extra_data,
                  created_at=now()
            """,
            state_id,
            code_verifier,
            json.dumps(extra_data or {}),
        )


async def get_oauth_state(state_id: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("select * from oauth_states where state_id=$1", state_id)
    return _record_to_dict(row)


async def delete_oauth_state(state_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("delete from oauth_states where state_id=$1", state_id)


async def insert_activity(
    user_id: str,
    title: str,
    platform: Optional[str] = None,
    type_: str = "info",
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            insert into activity_logs (user_id, title, platform, type, meta)
            values ($1::uuid, $2, $3, $4, $5::jsonb)
            """,
            user_id,
            title,
            platform,
            type_,
            json.dumps(meta or {}),
        )


async def list_activity(user_id: str, limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from activity_logs where user_id=$1::uuid order by time desc limit $2",
            user_id,
            limit,
        )
    return [dict(r) for r in rows]


async def create_scheduled_post(
    user_id: str,
    content: str,
    accounts: list,
    scheduled_for_iso: str,
    media: list,
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into scheduled_posts (user_id, content, accounts, scheduled_for, media, status)
            values ($1::uuid, $2, $3::jsonb, $4::timestamptz, $5::jsonb, 'pending')
            returning *
            """,
            user_id,
            content or "",
            json.dumps(accounts or []),
            scheduled_for_iso,
            json.dumps(media or []),
        )
    return dict(row)


async def list_scheduled_posts(user_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from scheduled_posts where user_id=$1::uuid order by scheduled_for desc",
            user_id,
        )
    return [dict(r) for r in rows]


async def cancel_scheduled_post(user_id: str, post_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            """
            update scheduled_posts
            set status='canceled', updated_at=now()
            where id=$1::uuid and user_id=$2::uuid and status in ('pending','processing')
            """,
            post_id,
            user_id,
        )
    return res.endswith("1")


async def insert_media_asset(
    user_id: str,
    filename: str,
    content_type: str,
    file_type: str,
    cloud_url: Optional[str],
    data_url: Optional[str],
    local_path: Optional[str],
    size_bytes: int,
) -> Dict[str, Any]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into media_assets (user_id, filename, content_type, file_type, cloud_url, data_url, local_path, size_bytes)
            values ($1::uuid, $2, $3, $4, $5, $6, $7, $8)
            returning *
            """,
            user_id,
            filename,
            content_type,
            file_type,
            cloud_url,
            data_url,
            local_path,
            size_bytes,
        )
    return dict(row)


async def list_media_assets(user_id: str, limit: int = 50, skip: int = 0):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select * from media_assets
            where user_id=$1::uuid
            order by created_at desc
            limit $2 offset $3
            """,
            user_id,
            limit,
            skip,
        )
    return [dict(r) for r in rows]


async def delete_media_asset(user_id: str, media_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "delete from media_assets where id=$1::uuid and user_id=$2::uuid",
            media_id,
            user_id,
        )
    return res.endswith("1")
