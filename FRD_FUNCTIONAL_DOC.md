# Functional Requirements Document (FRD)

## 1. Objective

Highshift is a social media automation platform that lets users:

- Connect social accounts with OAuth.
- Publish immediately to multiple platforms.
- Schedule posts for future publishing.
- Manage media, API keys, profiles, and organizations.
- Use AI-assisted content generation and instant-publish workflows.

This FRD covers both:

- `highshift.cloud-backend` (FastAPI)
- `highshift.cloud-frontend` (React + Vite)

## 2. System Components

- Frontend SPA (`highshift.cloud-frontend`)
  - User auth/session handling
  - Dashboard, scheduling, profiles, media, analytics, settings
  - Calls backend REST APIs via `src/services/api.js`
- Backend API (`highshift.cloud-backend`)
  - FastAPI app in `main.py`
  - Route modules in `app/routes/*`
  - Business logic in `app/services/*`
  - Social adapters in `app/platforms/*`
- Data stores
  - PostgreSQL primary path (users, scheduled posts, organizations, notifications, webhooks, media metadata)
  - Optional Beanie/Mongo compatibility path still present in model layer
- Scheduling/Background
  - Primary: APScheduler + cron route processing due scheduled posts
  - Optional: Temporal-based workflow execution (feature-flagged)

## 3. User Roles

- End User
  - Creates account/login, links social accounts, posts/schedules content.
- Developer/API User
  - Uses API keys, webhooks, and automation endpoints.
- Organization Owner/Admin
  - Manages org metadata, billing fields, and team-level settings.

## 4. Core Functional Requirements

### FR-1 Authentication & Session

- Support local registration/login.
- Support OAuth connect flows for social platforms.
- Support API-key and Bearer-token auth at backend.
- `/auth/me` must return normalized user profile, linked accounts, plan, and keys.

### FR-2 Account Connections

- Users can connect/disconnect platform accounts.
- Linked account metadata should persist with platform/account IDs and encrypted tokens.
- Multiple accounts per user are supported with profile grouping.

### FR-3 Publishing (Instant)

- User selects one or more connected accounts.
- Backend validates content/media against platform requirements.
- Backend dispatches to platform adapters and returns per-platform status.

### FR-4 Scheduled Publishing

- User creates scheduled post with future UTC datetime.
- Scheduled posts persist with status lifecycle:
  - `pending -> processing -> published|failed|canceled`
- Due posts are atomically claimed and processed to avoid duplicates.
- Cron endpoint supports minute-level trigger for due posts.

### FR-5 Media Management

- Upload media files and store metadata.
- Return URLs for posting and media library listing.
- Support delete operation for user media assets.

### FR-6 AI Features

- AI content generation endpoint for topic/platform/tone.
- Instant publish workflow endpoint for prebuilt automation trigger.

### FR-7 Profiles & Organizations

- CRUD profiles (logical grouping of linked accounts).
- Organization listing/creation/update endpoints.

### FR-8 API Keys & Developer Access

- Create/list/delete API keys.
- Track key usage (`lastUsed`) and support developer keys.

### FR-9 Webhooks & Notifications

- CRUD webhook endpoints.
- Webhook test + logs retrieval endpoints.
- Notification list/read/count endpoints.

### FR-10 Reliability & Operations

- Health endpoint reports API + DB status.
- CORS and error middleware should return structured failures.
- Feature flags should allow running with/without Temporal.

## 5. API Surface (High-level)

Implemented route groups in backend:

- `/auth`, `/linked-accounts`, `/post`, `/schedule`, `/analytics`, `/ai`, `/brand`
- `/profiles`, `/keys`, `/organizations`, `/notifications`, `/webhooks`, `/autopost`
- `/activity`, `/history`, `/cron`, `/health`

## 6. Non-Functional Requirements

- Security
  - Token encryption for social access/refresh tokens.
  - JWT/API-key verification for protected routes.
- Performance
  - API should keep P95 low enough for dashboard interactions.
- Availability
  - Scheduled publishing must continue after restarts/cron retries.
- Observability
  - Structured logs for publish attempts and scheduler outcomes.

## 7. Environment & Deployment Requirements

### Backend required baseline

- `DATABASE_URL` (Postgres recommended)
- `JWT_SECRET`
- Platform OAuth client credentials

### Optional Temporal (disabled by default)

- `TEMPORAL_ENABLED=true|false`
- `TEMPORAL_TARGET_HOST`
- `TEMPORAL_NAMESPACE`
- `TEMPORAL_TASK_QUEUE`
- `TEMPORAL_API_KEY` (Temporal Cloud)

### Frontend

- `VITE_API_URL`
- `VITE_CLIENT_REDIRECT`

## 8. Acceptance Criteria

- User can login and call `/auth/me` without 500 errors.
- User can connect accounts and publish immediate post.
- User can schedule post and see status transition through publish lifecycle.
- `npm run build` passes for frontend.
- Backend python compile checks pass for runtime modules.
- Cron publish endpoint processes due posts and returns processing stats.
