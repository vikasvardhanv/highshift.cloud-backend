import asyncio
from app.db.postgres import get_pool, fetch_user_by_email_ci
from app.utils.auth import create_access_token
import httpx

async def main():
    pool = await get_pool()
    user = await fetch_user_by_email_ci("socialraven04@gmail.com")
    token = create_access_token(data={"sub": str(user["id"])})
    await pool.close()
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.socialraven.online/auth/connect/youtube",
            headers={"Authorization": f"Bearer {token}"}
        )
        print("STATUS:", resp.status_code)
        print("JSON:", resp.json())

asyncio.run(main())
