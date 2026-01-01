import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:3000"

async def test_auth_flow():
    async with httpx.AsyncClient() as client:
        # 1. Register
        print("Testing Registration...")
        email = f"test_{os.urandom(4).hex()}@example.com"
        password = "testpassword123"
        
        reg_res = await client.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password
        })
        
        if reg_res.status_code == 200:
            print(f"✅ Registration Success: {reg_res.json()}")
            data = reg_res.json()
            token = data["access_token"]
            api_key = data["api_key"]
        else:
            print(f"❌ Registration Failed: {reg_res.text}")
            return

        # 2. Login
        print("\nTesting Login...")
        login_res = await client.post(f"{BASE_URL}/auth/login", json={
            "email": email,
            "password": password
        })
        
        if login_res.status_code == 200:
             print(f"✅ Login Success: {login_res.json()}")
             token = login_res.json()["access_token"]
        else:
             print(f"❌ Login Failed: {login_res.text}")
             return

        # 3. Protected Route (using JWT)
        print("\nTesting Protected Route (JWT)...")
        headers = {"Authorization": f"Bearer {token}"}
        # Assuming /connect/twitter or similar checks auth, or /auth/connect/twitter (from previous files)
        # Actually let's try a simpler one: /key/list (from key_routes if exists) or just check if we can hit an endpoint that requires auth.
        # auth_routes "connect" requires get_optional_user or get_current_user depending on implementation.
        # Let's try /keys if it exists (from previous usage in api.js: /keys)
        
        # Check routing
        # app/routes/key_routes.py likely has /keys
        
        protected_res = await client.get(f"{BASE_URL}/keys", headers=headers)
        if protected_res.status_code == 200:
            print(f"✅ Protected Route (JWT) Success: {protected_res.json()}")
        else:
            print(f"Key Route Status: {protected_res.status_code}")
            # Try another one if that failed, maybe /auth/connect/instagram just to see if it lets us in (it returns a URL)
            protected_res = await client.get(f"{BASE_URL}/auth/connect/instagram", headers=headers)
            if protected_res.status_code == 200:
                 print(f"✅ Protected Route (Instagram Auth URL) Success")
            else:
                 print(f"❌ Protected Route Failed: {protected_res.text}")

        # 4. Protected Route (using API Key)
        print("\nTesting Protected Route (API Key)...")
        headers_key = {"x-api-key": api_key}
        protected_res_key = await client.get(f"{BASE_URL}/keys", headers=headers_key)
        if protected_res_key.status_code == 200:
            print(f"✅ Protected Route (API Key) Success")
        else:
             print(f"❌ Protected Route (API Key) Failed: {protected_res_key.text}")

if __name__ == "__main__":
    asyncio.run(test_auth_flow())
