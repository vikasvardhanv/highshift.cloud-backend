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
from app.routes import ai_routes, analytics_routes, auth_routes

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
                AnalyticsSnapshot
            ]
        )
        print("Beanie initialized successfully")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize database: {e}")

@app.get("/health")
async def health_check():
    # Check if DB is initialized
    db_status = "connected" if User.get_motor_collection() is not None else "disconnected"
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
