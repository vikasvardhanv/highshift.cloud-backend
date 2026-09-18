import asyncio
import os
import json
import mimetypes
from pymongo import MongoClient

# Setup MONGODB
mongo_uri = os.environ.get("MONGO_URI", "mongodb+srv://admin:V6eS3U4QW1X3@socialraven-cluster.a8j0s.mongodb.net/?retryWrites=true&w=majority&appName=socialraven-cluster")
# We will just print the media URLs from the last scheduled post.

# Setup POSTGRES
import asyncpg

async def main():
    DATABASE_URL = "postgres://postgres:postgres@localhost:5432/postgres" # Wait, I don't know the DATABASE_URL.
    # Wait, let's use app.db.postgres.get_pool!
    
    # We can use the existing backend code!
    os.environ["DATABASE_URL"] = "postgres://postgres:postgres@localhost:5432/postgres" # This will fail if not correct
    
    try:
        from app.db.postgres import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM scheduled_posts ORDER BY created_at DESC LIMIT 1")
            print("Last scheduled post:")
            print(dict(row))
            print("Media:", row['media'])
    except Exception as e:
        print(f"Failed to connect to PG: {e}")

asyncio.run(main())
