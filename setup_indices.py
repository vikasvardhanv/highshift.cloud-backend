import asyncio
from app.db.postgres import init_db, get_pool

async def main():
    await init_db()
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Creating activity_logs index...")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_activity_logs_user_time ON activity_logs (user_id, time DESC)")
        print("Creating scheduled_posts index...")
        # Note: sometimes scheduled_for is called scheduled_time depending on the DB schema version, but I'll try scheduled_for first.
        try:
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_user_time ON scheduled_posts (user_id, scheduled_for DESC)")
        except Exception as e:
            print("Failed for scheduled_for, trying scheduled_time: ", e)
            try:
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_user_time ON scheduled_posts (user_id, scheduled_time DESC)")
            except Exception as e2:
                print("Failed again: ", e2)
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
