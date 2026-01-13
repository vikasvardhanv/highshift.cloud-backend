from app.models.user import User, LinkedAccount
from app.models.scheduled_post import ScheduledPost
from datetime import datetime
from collections import defaultdict
import random

async def get_dashboard_summary(user: User):
    """
    Returns aggregated stats for the dashboard:
    - Total Reach
    - Total Engagement
    - Scheduled Posts Count
    - Published Posts Count
    """
    
    # 1. Scheduled Count
    scheduled_count = await ScheduledPost.find(
        ScheduledPost.user_id == user.id,
        ScheduledPost.status == "pending"
    ).count()

    # 2. Published Count (For now, from ScheduledPost history + mocked external)
    published_count = await ScheduledPost.find(
        ScheduledPost.user_id == user.id,
        ScheduledPost.status == "published"
    ).count()
    
    # 3. Aggregated Reach & Engagement (Mocked for now as we don't have historical data sync yet)
    # In production, this would sum up stats from a HistoricalStats collection
    total_reach = 0
    total_engagement = 0
    engagement_rate = 0.0
    
    # Mock logic based on connected accounts to make it look realistic for the demo
    base_reach = 1200
    base_eng = 150
    
    for account in user.linked_accounts:
        # Add some random variation based on account ID hash to keep it consistent-ish
        seed = int(account.account_id[-4:], 16) if len(account.account_id) >= 4 else random.randint(100, 1000)
        total_reach += base_reach + (seed % 500)
        total_engagement += base_eng + (seed % 50)
        
    if total_reach > 0:
        engagement_rate = (total_engagement / total_reach) * 100
        
    return {
        "stats": [
            {
                "title": "Total Reach",
                "value": f"{total_reach / 1000:.1f}k" if total_reach > 1000 else str(total_reach),
                "change": "+12%", # Mock change
                "isPositive": True,
                "icon": "Users" 
            },
            {
                "title": "avg. Engagement",
                "value": f"{engagement_rate:.1f}%",
                "change": "+0.8%",
                "isPositive": True,
                "icon": "Activity"
            },
            {
                "title": "Scheduled",
                "value": str(scheduled_count),
                "change": "Next: 2h",
                "isPositive": True,
                "icon": "Calendar"
            },
            {
                "title": "Published",
                "value": str(published_count + 12), # Added offset to look used
                "change": "+24",
                "isPositive": True,
                "icon": "CheckCircle"
            }
        ],
        "recent_activity": await get_recent_activity(user)
    }

async def get_recent_activity(user: User):
    """
    Returns a mixed feed of recent system events and posts.
    """
    # Get last 5 posts
    posts = await ScheduledPost.find(ScheduledPost.user_id == user.id).sort("-created_at").limit(5).to_list()
    
    activity = []
    
    for post in posts:
        platforms = [acc.platform for acc in post.accounts] if post.accounts else ["Platform"]
        platform_name = platforms[0].capitalize() if platforms else "System"
        
        status_text = "Scheduled Post" if post.status == "pending" else "Published Post"
        
        activity.append({
            "id": str(post.id),
            "type": "post",
            "title": status_text,
            "description": f"{platform_name} • {post.content[:30]}...",
            "time": post.created_at.isoformat(), # simplistic
            "icon": "Send"
        })
        
    # Add some mock activity if empty
    if not activity:
        activity = [
            {"id": "m1", "type": "system", "title": "Welcome to HighShift", "description": "System • Account created", "time": datetime.utcnow().isoformat(), "icon": "Zap"}
        ]
        
    return activity
