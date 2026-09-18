import asyncio
from app.db.postgres import get_db_pool

async def main():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM scheduled_posts ORDER BY created_at DESC LIMIT 1;")
        for r in rows:
            print(dict(r))

asyncio.run(main())
