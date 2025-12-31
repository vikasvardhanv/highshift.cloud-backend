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
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    
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
    print("Beanie initialized with models")

# Include Routers
app.include_router(ai_routes.router)
app.include_router(analytics_routes.router)
app.include_router(auth_routes.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "HighShift Backend is healthy"}

@app.get("/")
async def root():
    return {"message": "Welcome to HighShift AI API (Python/FastAPI)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 3000)), reload=True)
