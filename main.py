import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.user import User
from app.models.brand_kit import BrandKit
from app.models.scheduled_post import ScheduledPost
from app.models.analytics import AnalyticsSnapshot
from app.models.oauth_state import OAuthState
from app.routes import ai_routes, analytics_routes, auth_routes, key_routes, post_routes

# Load environment variables
load_dotenv()

app = FastAPI(title="HighShift AI Backend", version="1.0.0")

# CORS configuration
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # MongoDB Connection
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("CRITICAL: MONGODB_URI not found in environment")
        return

    try:
        client = AsyncIOMotorClient(mongo_uri)
        # Verify connection
        await client.admin.command('ping')
        
        # Initialize Beanie with models
        await init_beanie(
            database=client.get_default_database(),
            document_models=[
                User,
                BrandKit,
                ScheduledPost,
                AnalyticsSnapshot,
                OAuthState
            ]
        )
        print("Beanie initialized successfully")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize database: {e}")

# Include Routers
app.include_router(ai_routes.router)
app.include_router(analytics_routes.router)
app.include_router(auth_routes.router)
app.include_router(key_routes.router)
app.include_router(post_routes.router)

@app.get("/health")
async def health_check():
    try:
        # Check if Beanie is initialized by checking the collection state
        # We catch the StateError if it hasn't been initialized yet
        User.get_motor_collection()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
        
    return {
        "status": "ok", 
        "message": "HighShift Backend is running",
        "database": db_status
    }

@app.get("/")
async def root():
    return {"message": "Welcome to HighShift AI API (Python/FastAPI)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 3000)), reload=True)
