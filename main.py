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
from app.routes import ai_routes, analytics_routes, auth_routes, key_routes, post_routes
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
                OAuthState
            ]
        )
        db_initialized = True
        print("Beanie initialized successfully")
    except Exception as e:
        print(f"Failed to initialize Beanie: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_beanie_initialized()
    yield
    # Shutdown logic (if any) can go here

app = FastAPI(title="HighShift AI Backend", version="1.0.0", lifespan=lifespan)

# CORS configuration
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(ai_routes.router)
app.include_router(analytics_routes.router)
app.include_router(auth_routes.router)
app.include_router(key_routes.router)
app.include_router(post_routes.router)

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
        "message": "Upload-Post Backend is running",
        "database": db_status,
        "initialized": db_initialized
    }

@app.get("/")
async def root():
    return {"message": "Welcome to HighShift AI API (Python/FastAPI)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 3000)), reload=True)
