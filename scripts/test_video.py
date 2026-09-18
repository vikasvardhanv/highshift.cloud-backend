import asyncio
import os
import sys

sys.path.append(os.getcwd())
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/socialraven"
os.environ.pop("AGENT_MEDIA_API_KEY", None)

from app.services.ai_service import generate_video

async def main():
    print("Testing Video Generation without API key...")
    video_url = await generate_video("Make a video about social raven")
    print("Video URL:", video_url)

asyncio.run(main())
