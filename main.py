import os
import re
import logging
import asyncio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from contextlib import suppress
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False

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

# Initialize Sentry for error tracking
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN and HAS_SENTRY:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            FastApiIntegration(auto_enabling_instrumentations=True),
            AsyncioIntegration(),
        ],
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment=os.getenv("ENVIRONMENT", "production"),
    )

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
    # Startup
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

app = FastAPI(
    title="Social Raven AI Backend", 
    version="1.0.0", 
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# --- Middleware Stack (order matters!) ---

# 1. GZip Compression (should be first)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. CORS Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").strip().lower()
IS_DEV = ENVIRONMENT in {"dev", "development", "local"}

env_origins = os.getenv("CORS_ORIGINS", "").split(",")
origins = [o.strip().rstrip("/") for o in env_origins if o.strip()]
origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"^https://([a-z0-9-]+\.)*highshift\.cloud$|^https://(www\.)?socialraven\.online$|^https://highshift-cloud-frontend.*\.vercel\.app$",
)
origin_re = re.compile(origin_regex)

# Explicitly add production domains
production_domains = [
    "https://highshift.cloud",
    "https://www.highshift.cloud",
    "https://app.highshift.cloud",
    "https://highshift-cloud-frontend.vercel.app",
    "https://socialraven.meganai.cloud",
    "https://www.socialraven.meganai.cloud",
    "https://socialraven.meganai.cloud.vercel.app",
    "https://socialraven.online",
    "https://www.socialraven.online",
]
for d in production_domains:
    normalized = d.rstrip("/")
    if normalized not in origins:
        origins.append(normalized)


def _is_credentialed_safe(origin: str) -> bool:
    """Cookies and Authorization headers go to every allowed origin, so a
    plaintext http origin is only acceptable for loopback development hosts."""
    if origin.startswith("https://"):
        return True
    return origin.startswith(("http://localhost", "http://127.0.0.1"))


_rejected = [o for o in origins if not _is_credentialed_safe(o)]
origins = [o for o in origins if _is_credentialed_safe(o)]
if _rejected:
    logging.getLogger("main").warning(
        "Ignoring insecure CORS origins (credentials require https or loopback): %s",
        ", ".join(_rejected),
    )

# Wildcard is opt-in. An empty CORS_ORIGINS must never silently allow every origin.
allow_all = IS_DEV and os.getenv("CORS_ALLOW_ALL", "false").strip().lower() in {"1", "true", "yes"}
if allow_all:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",  # DEV ONLY: echoes any origin back, with credentials
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

# 3. Global Exception Handler to Ensure CORS Headers on 500s
class ErrorMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Add CORS headers to error responses
                origin = None
                for header in scope.get("headers", []):
                    if header[0] == b"origin":
                        origin = header[1].decode()
                        break
                
                if origin:
                    normalized_origin = origin.rstrip("/")
                    if (
                        allow_all
                        or normalized_origin in origins
                        or origin_re.match(normalized_origin)
                    ):
                        # Check if this is an error response
                        if message.get("status", 200) >= 400:
                            headers = list(message.get("headers", []))
                            headers.append((b"access-control-allow-origin", origin.encode()))
                            headers.append((b"access-control-allow-credentials", b"true"))
                            headers.append((b"access-control-allow-methods", b"*"))
                            headers.append((b"access-control-allow-headers", b"*"))
                            message["headers"] = headers
            
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            logger = logging.getLogger("main")
            logger.error(f"Unhandled Exception: {e}", exc_info=True)
            
            # Send error response with CORS headers
            origin_header = None
            for header in scope.get("headers", []):
                if header[0] == b"origin":
                    origin_header = header[1].decode()
                    break
            
            cors_headers = []
            if origin_header:
                normalized_origin = origin_header.rstrip("/")
                if (
                    allow_all
                    or normalized_origin in origins
                    or origin_re.match(normalized_origin)
                ):
                    cors_headers = [
                        (b"access-control-allow-origin", origin_header.encode()),
                        (b"access-control-allow-credentials", b"true"),
                        (b"access-control-allow-methods", b"*"),
                        (b"access-control-allow-headers", b"*"),
                    ]
            
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    *cors_headers,
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail": "Internal Server Error"}',
            })

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
from app.routes import org_routes, notification_routes, webhook_routes, autopost_routes, inbox_routes, video_tools_routes

app.include_router(legacy_routes.router)
app.include_router(profile_routes.router)
app.include_router(media_routes.router)  # Media upload/serve for Instagram
app.include_router(connect_router)  # Alias for /connect/{platform}/callback
app.include_router(cron_routes.router)  # Cron jobs for scheduled publishing

# New routes
app.include_router(inbox_routes.router)
app.include_router(org_routes.router)
app.include_router(notification_routes.router)
app.include_router(webhook_routes.router)
app.include_router(autopost_routes.router)
app.include_router(video_tools_routes.router)  # Video downloader + uniquifier

from fastapi.staticfiles import StaticFiles

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

# Configuration Checker (Postiz-style)
def check_configuration():
    """Validate required environment variables on startup."""
    issues = []
    warnings = []
    
    # Accept either DATABASE_URL (Postgres) or MONGODB_URI (Mongo)
    if not (os.getenv("DATABASE_URL") or os.getenv("MONGODB_URI")):
        issues.append("Missing required database configuration: DATABASE_URL or MONGODB_URI must be set")
    
    if not os.getenv("JWT_SECRET"):
        issues.append("Missing required environment variable: JWT_SECRET")
    
    recommended_vars = [
        "CORS_ORIGINS",
        "FRONTEND_URL",
        "BACKEND_URL",
        "SENTRY_DSN",
        "REDIS_URL",
    ]
    
    for var in recommended_vars:
        if not os.getenv(var):
            warnings.append(f"Recommended environment variable not set: {var}")
    
    # Check JWT secret strength
    jwt_secret = os.getenv("JWT_SECRET", "")
    if jwt_secret and jwt_secret in ("changethis_secret_key_please", "secret", "test"):
        warnings.append("JWT_SECRET appears to be using a default/weak value")
    
    env = os.getenv("ENVIRONMENT", "development").lower()
    if issues:
        for issue in issues:
            logging.getLogger("main").warning(f"CONFIG WARNING: {issue}")
        # Only crash on import if explicitly in production and not skipping
        if env == "production" and not os.getenv("SKIP_CONFIG_CHECK"):
            raise RuntimeError(f"Configuration errors: {'; '.join(issues)}")
    
    for warning in warnings:
        logging.getLogger("main").warning(f"CONFIG WARNING: {warning}")
    
    if not issues:
        print("Configuration check completed without any issues")

# Run configuration check on startup
check_configuration()

# Custom OpenAPI schema with security schemes
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Social Raven AI Backend",
        version="1.0.0",
        description="Social media management API with AI-powered content generation",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        },
    }
    
    # Apply security globally
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []},
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/health")
async def health_check():
    db_url = os.getenv("DATABASE_URL") or os.getenv("MONGODB_URI")
    postgres_mode = is_postgres_url(db_url)
    redis_status = "unknown"
    
    # Check Redis if configured
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis.asyncio as redis
            r = redis.from_url(redis_url)
            await r.ping()
            await r.close()
            redis_status = "connected"
        except Exception as e:
            redis_status = f"error: {str(e)}"
    
    try:
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
        
    overall_status = "ok"
    if "error" in db_status or "error" in redis_status:
        overall_status = "degraded"
    if "error" in db_status and "error" in redis_status:
        overall_status = "down"
         
    return {
        "status": overall_status, 
        "message": "Social Raven Cloud Backend is running",
        "database": db_status,
        "redis": redis_status,
        "initialized": db_initialized,
        "environment": ENVIRONMENT,
    }

@app.get("/")
async def root():
    return {
        "message": "Welcome to Social Raven Cloud API (Python/FastAPI)",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 3000)))