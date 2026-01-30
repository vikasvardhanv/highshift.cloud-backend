import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.user import User
from app.models.brand_kit import BrandKit
from app.models.scheduled_post import ScheduledPost
from app.models.analytics import AnalyticsSnapshot
from app.models.oauth_state import OAuthState
from app.models.media import Media
from app.models.activity import ActivityLog
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
from app.utils.auth import get_current_user # Added import

# Load environment variables
load_dotenv()

db_initialized = False

async def ensure_beanie_initialized():
    global db_initialized
    if db_initialized:
        return
    
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("CRITICAL: MONGODB_URI not found")
        return

    try:
        client = AsyncIOMotorClient(mongo_uri)
        
        # Safely get database name
        try:
            db = client.get_default_database()
        except Exception:
            # If no default db in URI (raises ConfigurationError), use 'highshift'
            db = client["highshift"]
        
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
    except Exception as e:
        print(f"Failed to initialize Beanie: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_beanie_initialized()
    
    # Start Scheduler
    from app.services.scheduler_service import scheduler
    scheduler.start()
    
    yield
    
    # Shutdown logic
    scheduler.stop()

app = FastAPI(title="HighShift AI Backend", version="1.0.0", lifespan=lifespan)

# CORS configuration
# Priority: Get from env, but handle the case where env is empty or just "*"
env_origins = os.getenv("CORS_ORIGINS", "").split(",")
origins = [o.strip() for o in env_origins if o.strip()]

# Explicitly add production and common dev domains
production_domains = [
    "https://highshift.cloud", 
    "https://www.highshift.cloud",
    "https://highshift-cloud.vercel.app"
]
for d in production_domains:
    if d not in origins:
        origins.append(d)

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
                if "*" in origins or origin in origins:
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
app.include_router(legacy_routes.router)
app.include_router(profile_routes.router)
app.include_router(media_routes.router)  # Media upload/serve for Instagram
app.include_router(connect_router)  # Alias for /connect/{platform}/callback
app.include_router(cron_routes.router)  # Cron jobs for scheduled publishing

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
    try:
        # Check if initialized
        if not db_initialized:
            await ensure_beanie_initialized()
            
        # Try a simple query
        await User.count()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    return {
        "status": "ok" if "error" not in db_status else "degraded", 
        "message": "HighShift Cloud Backend is running",
        "database": db_status,
        "initialized": db_initialized
    }

@app.get("/")
async def root():
    return {"message": "Welcome to HighShift Cloud API (Python/FastAPI)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 3000)), reload=True)
