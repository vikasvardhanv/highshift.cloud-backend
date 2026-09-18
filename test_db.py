import asyncio
from app.db.postgres import get_pool, fetch_user_by_email_ci

async def main():
    pool = await get_pool()
    user = await fetch_user_by_email_ci("socialraven04@gmail.com")
    print("USER EMAIL:", user.get("email"))
    print("USER NAME FROM DB?", user.get("name") if "name" in user else "NO NAME FIELD")
    await pool.close()

asyncio.run(main())
