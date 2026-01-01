import asyncio
import os
import uuid
import hashlib
from datetime import datetime
import requests # Synchronous HTTP
# import motor.motor_asyncio # Removed as we are using sync pymongo
# If motor is missing, we can try pymongo. But motor is in requirements likely.
# Actually, the user's environment failed on `import aiohttp`.
# Let's try to make the script purely synchronous using `pymongo` and `requests` 
# to avoid async event loop issues in this script execution environment.
import pymongo
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Config
# BASE_URL = "http://localhost:8000"
BASE_URL = "https://highshift-cloud-backend.vercel.app"

def main():
    print("🧪 INITIALIZING TEST: API Key Posting Flow (E2E Production)")
    print(f"   Target: {BASE_URL}")
    
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        # Fallback for easier user execution
        default_uri = "mongodb+srv://vikashvardhan:vikashvardhan@cluster0.ty36y.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        print(f"   ℹ️  MONGODB_URI not found in env.")
        user_input = input(f"   Please paste MongoDB URI (or press Enter to use default): ").strip()
        mongo_uri = user_input if user_input else default_uri

    # 1. Setup DB Connection
    try:
        client = pymongo.MongoClient(mongo_uri)
        # Verify connection
        client.admin.command('ping')
        print("   ✅ Connected to MongoDB Atlas")
        
        # Try to parse DB name from URI if possible or just use default
        # Backend defaults to 'highshift' if not specified in URI.
        try:
            db_name = pymongo.uri_parser.parse_uri(mongo_uri).get('database') or "highshift"
        except:
             db_name = "highshift"
        
        print(f"   ℹ️  Connected to DB: {db_name}")
        db = client[db_name]
        users_collection = db["users"]
    except Exception as e:
        print(f"   ❌ DB Connection Failed: {e}")
        return
    
    # 2. Create a Test User with a known API Key
    print("   Creating temporary test user...")
    raw_key = f"hs_test_{uuid.uuid4().hex[:8]}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    
    test_user_id = str(uuid.uuid4())
    test_account_id = "test_twitter_123"
    
    test_user = {
        "_id": test_user_id,
        "email": "test_bot@highshift.ai",
        "apiKeyHash": "legacy_dummy_" + uuid.uuid4().hex, # REQUIRED by User model
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "apiKeys": [{
            "id": str(uuid.uuid4()),
            "name": "E2E Test Key",
            "keyHash": hashed_key,
            "created_at": datetime.utcnow(),
            "lastUsed": None 
        }],
        "linkedAccounts": [{
            "platform": "twitter",
            "accountId": test_account_id,
            "username": "TestBot",
            "displayName": "Test Bot Account",
            "accessTokenEnc": "mock_token",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }],
        "maxProfiles": 5,
        "planTier": "starter"
    }
    
    # Insert
    users_collection.insert_one(test_user)
    print(f"   ✅ User created. Key: {raw_key}")


    try:
        # 3. Perform the API Request
        print(f"\n📨 SENDING REQUEST to {BASE_URL}/post/multi ...")
        
        payload = {
            "accounts": [
                {"platform": "twitter", "accountId": test_account_id}
            ],
            "content": "Hello World! This is an automated test post via the HighShift API. 🚀"
        }
        
        headers = {
            "x-api-key": raw_key,
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(f"{BASE_URL}/post/multi", json=payload, headers=headers)
            print(f"   Status Code: {resp.status_code}")
            print(f"   Response: {resp.text}")
            
            if resp.status_code == 200:
                print("   ✅ API Request Success!")
            else:
                print("   ❌ API Request Failed!")
        except Exception as e:
            print(f"   ❌ Request Error: {e}")
            return

        # 4. Verify Audit Log
        print("\n🔍 VERIFYING AUDIT LOG...")
        # Poll for update (eventual consistency)
        import time
        for i in range(5):
             updated_user = users_collection.find_one({"_id": test_user_id})
             
             if updated_user and "apiKeys" in updated_user:
                 key_data = updated_user["apiKeys"][0]
                 last_used = key_data.get("last_used") or key_data.get("lastUsed")
                 
                 if last_used:
                     print(f"   ✅ Audit Confirmed! Key 'last_used' timestamp: {last_used}")
                     break
                 else:
                     if i == 4:
                         print(f"   ⚠️ Warning: 'last_used' timestamp was not updated after 5 seconds. Key Data: {key_data}")
                     else:
                         time.sleep(1)
             else:
                  print("   ❌ Error: User not found or apiKeys missing.")
                  break

    finally:
        # 5. Cleanup
        print("\n🧹 Cleaning up test data...")
        users_collection.delete_one({"_id": test_user_id})
        print("   Test complete.")

if __name__ == "__main__":
    main()
