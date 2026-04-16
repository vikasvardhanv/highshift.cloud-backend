import os
import re
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from contextlib import suppress
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.user import User
from app.models.brand_kit import BrandKit
from app.models.scheduled_post import ScheduledPost
from app.models.analytics import AnalyticsSnapshot
from app.models.oauth_state import OAuthState
from app.models.media import Media
from app.models.activity import ActivityLog
from app.db.postgres import get_pool, init_postgres, is_postgres_url
from app.routes import (
    ai_routes, 
    analytics_routes, 
    auth_routes, 
    key_routes, 
    post_routes,
    brand_routes,
    schedule_routes,
    history_routes,
    account_routes,
    activity_routes
)

# Load environment variables
load_dotenv()

db_initialized = False

async def ensure_beanie_initialized():
    global db_initialized
    if db_initialized:
        return True
    
    # Primary config going forward
    database_url = os.getenv("DATABASE_URL") or os.getenv("MONGODB_URI")
    if not database_url:
        print("CRITICAL: DATABASE_URL not found")
        return False

    if is_postgres_url(database_url):
        try:
            await init_postgres(database_url)
            db_initialized = True
            print("Postgres initialized successfully")
            return True
        except Exception as e:
            print(f"Failed to initialize Postgres ({type(e).__name__}): {repr(e)}")
            return False

    try:
        client = AsyncIOMotorClient(database_url)
        
        # Safely get database name
        try:
            db = client.get_default_database()
        except Exception:
            # If no default db in URI (raises ConfigurationError), use 'socialraven'
            db = client["socialraven"]
        
        await init_beanie(
            database=db,
            document_models=[
                User,
                BrandKit,
                ScheduledPost,
                AnalyticsSnapshot,
                OAuthState,
                Media,
                ActivityLog
            ]
        )
        db_initialized = True
        print("Beanie initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize Beanie: {e}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_beanie_initialized()
    temporal_worker_task = None
    
    # Start Scheduler (Postiz-style explicit cron runner switch)
    from app.services.scheduler_service import scheduler
    db_url = os.getenv("DATABASE_URL") or os.getenv("MONGODB_URI")
    default_scheduler = "false" if is_postgres_url(db_url) else "true"
    run_scheduler = os.getenv("RUN_SCHEDULER", default_scheduler).lower() in {"1", "true", "yes"}
    if run_scheduler and db_initialized:
        scheduler.start()
    elif run_scheduler and not db_initialized:
        print("Scheduler not started because DB initialization failed.")
    else:
        print("Scheduler disabled (RUN_SCHEDULER=false)")

    # Optional: run Temporal worker in-process for simple deployments.
    temporal_enabled = os.getenv("TEMPORAL_ENABLED", "false").lower() in {"1", "true", "yes"}
    run_temporal_worker = os.getenv("RUN_TEMPORAL_WORKER", "false").lower() in {"1", "true", "yes"}
    if temporal_enabled and run_temporal_worker:
        from app.temporal.worker import run_temporal_worker as run_worker

        temporal_worker_task = asyncio.create_task(run_worker())
        print("Temporal worker started in-process")
    
    yield
    
    # Shutdown logic
    if run_scheduler and db_initialized:
        scheduler.stop()
    if temporal_worker_task:
        temporal_worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await temporal_worker_task

app = FastAPI(title="Social Raven AI Backend", version="1.0.0", lifespan=lifespan)

# CORS configuration
# Priority: Get from env, but handle the case where env is empty or just "*"
env_origins = os.getenv("CORS_ORIGINS", "").split(",")
origins = [o.strip().rstrip("/") for o in env_origins if o.strip()]
origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"^https://([a-z0-9-]+\.)*highshift\.cloud$|^https://highshift-cloud-frontend.*\.vercel\.app$|^http://(localhost|127\.0\.0\.1)(:\d+)?$",
)
origin_re = re.compile(origin_regex)

# Explicitly add production and common dev domains
production_domains = [
    "https://highshift.cloud",
    "https://www.highshift.cloud",
    "https://app.highshift.cloud",
    "https://highshift-cloud-frontend.vercel.app",
    "https://socialraven.meganai.cloud",
    "https://www.socialraven.meganai.cloud",
    "https://socialraven.meganai.cloud.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
for d in production_domains:
    normalized = d.rstrip("/")
    if normalized not in origins:
        origins.append(normalized)

# For development, if "*" is in origins, we allow all
if "*" in origins or not origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",  # Allows all origins with credentials (DEV ONLY)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )

# --- Global Exception Handler to Ensure CORS Headers on 500s ---
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class ErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            import logging
            logger = logging.getLogger("main")
            logger.error(f"Unhandled Exception: {e}", exc_info=True)
            
            # Create error response
            content = {"detail": "Internal Server Error", "error": str(e)}
            response = JSONResponse(status_code=500, content=content)
            
            # MANUALLY ADD CORS HEADERS for errors
            origin = request.headers.get("origin")
            if origin:
                # Basic check: allow if in our list or if we are in wildcard mode
                normalized_origin = origin.rstrip("/")
                if (
                    "*" in origins
                    or normalized_origin in origins
                    or origin_re.match(normalized_origin)
                ):
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    response.headers["Access-Control-Allow-Methods"] = "*"
                    response.headers["Access-Control-Allow-Headers"] = "*"
            
            return response

app.add_middleware(ErrorMiddleware)

# Include Routers
app.include_router(ai_routes.router)
app.include_router(analytics_routes.router)
app.include_router(auth_routes.router)
app.include_router(key_routes.router)
app.include_router(post_routes.router)
app.include_router(brand_routes.router)
app.include_router(schedule_routes.router)
app.include_router(history_routes.router)
app.include_router(account_routes.router)
app.include_router(activity_routes.router)
from app.routes import legacy_routes, profile_routes, media_routes, cron_routes
from app.routes.auth_routes import connect_router
from app.routes import org_routes, notification_routes, webhook_routes, autopost_routes

app.include_router(legacy_routes.router)
app.include_router(profile_routes.router)
app.include_router(media_routes.router)  # Media upload/serve for Instagram
app.include_router(connect_router)  # Alias for /connect/{platform}/callback
app.include_router(cron_routes.router)  # Cron jobs for scheduled publishing

# New routes
app.include_router(org_routes.router)
app.include_router(notification_routes.router)
app.include_router(webhook_routes.router)
app.include_router(autopost_routes.router)

from fastapi.staticfiles import StaticFiles
import logging

# Safe static file mounting for Vercel/Serverless (Read-only filesystem)
try:
    # Create static directory if not exists (only works if filesystem is writable)
    if not os.path.exists("app/static/uploads"):
        os.makedirs("app/static/uploads")
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception as e:
    # Log warning but don't crash the app
    print(f"WARNING: Static file serving could not be initialized (likely read-only filesystem): {e}")

@app.get("/health")
async def health_check():
    global db_initialized
    db_url = os.getenv("DATABASE_URL") or os.getenv("MONGODB_URI")
    postgres_mode = is_postgres_url(db_url)
    try:
        # Check if initialized
        if not db_initialized:
            await ensure_beanie_initialized()

        if postgres_mode:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute("select 1")
        else:
            await User.count()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    return {
        "status": "ok" if "error" not in db_status else "degraded", 
        "message": "Social Raven Cloud Backend is running",
        "database": db_status,
        "initialized": db_initialized
    }

@app.get("/")
async def root():
    return {"message": "Welcome to Social Raven Cloud API (Python/FastAPI)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 3000)), reload=True)
