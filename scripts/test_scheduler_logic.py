import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Ensure we can import app modules
sys.path.append(os.getcwd())

from app.models.scheduled_post import ScheduledPost
from app.models.user import User
from app.services.scheduler_service import scheduler

async def test_scheduler():
    # Load env for DB connection
    load_dotenv()
    
    # Initialize Beanie
    from main import ensure_beanie_initialized
    await ensure_beanie_initialized()
    
    print("--- Test Started ---")
    
    # 1. Create a dummy user if needed or pick first one
    user = await User.find_one({})
    if not user:
        print("No user found. Please create a user first.")
        return
        
    print(f"Using user: {user.email} ({user.id})")

    # 2. Create a Scheduled Post for 1 minute ago (Past)
    post = ScheduledPost(
        user_id=user,
        content="Test automated post",
        accounts=[{"platform": "twitter", "accountId": "fake_id"}],
        status="pending",
        scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1),
        media=[]
    )
    await post.insert()
    print(f"Created test post: {post.id} (Status: {post.status})")

    # 3. Trigger Scheduler Check
    print("Running scheduler check...")
    await scheduler.check_due_posts()
    
    # 4. Verify Status Change
    updated_post = await ScheduledPost.get(post.id)
    print(f"Updated post status: {updated_post.status}")
    
    if updated_post.status in ["processing", "published", "failed"]:
        print("SUCCESS: Scheduler picked up the post.")
    else:
        print("FAILURE: Post matches criteria but was not picked up.")

    # 5. Verify Retrieval (GET /schedule logic)
    print("Testing GET /schedule query logic...")
    from bson import ObjectId
    # Updated matching logic from checks
    posts_list = await ScheduledPost.find({"userId.$id": ObjectId(user.id)}).sort("-scheduled_for").to_list()
    print(f"Found {len(posts_list)} posts for user {user.id}")
    
    found_our_post = any(str(p.id) == str(post.id) for p in posts_list)
    if found_our_post:
        print("SUCCESS: GET Query found the test post.")
    else:
        print("FAILURE: GET Query did NOT find the test post. Query syntax might be wrong.")

    # 6. Cleanup
    await updated_post.delete()
    print("Test post deleted.")

if __name__ == "__main__":
    asyncio.run(test_scheduler())
