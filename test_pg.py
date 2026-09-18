import asyncio
import os
import asyncpg
from app.db.postgres import DATABASE_URL

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM scheduled_posts ORDER BY created_at DESC LIMIT 5;")
    for row in rows:
        print(f"ID: {row['id']}, media: {row['media']}")
    await conn.close()

asyncio.run(main())
