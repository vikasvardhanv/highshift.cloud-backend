# import pandas as pd (REMOVED)
from datetime import datetime, timedelta
from typing import List
from app.models.analytics import AnalyticsSnapshot
from app.utils.logger import logger

async def get_account_analytics(user_id: str, account_id: str, days: int = 30):
    """
    Calculate follower growth and engagement using standard Python (No Pandas).
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Fetch snapshots from DB
        snapshots = await AnalyticsSnapshot.find({
            "userId": user_id,
            "accountId": account_id,
            "timestamp": {"$gte": start_date}
        }).to_list()

        if not snapshots:
            return {"message": "No data found for this period", "data": []}

        # Convert to list of dicts & Sort by timestamp
        data_points = [s.dict() for s in snapshots]
        data_points.sort(key=lambda x: x['timestamp'])

        # Calculate Growth
        first = data_points[0]
        last = data_points[-1]
        total_growth = last.get('followers', 0) - first.get('followers', 0)
        
        # Calculate Average Engagement
        engagements = [d.get('engagement', 0) for d in data_points]
        avg_engagement = sum(engagements) / len(engagements) if engagements else 0

        # Format for frontend
        # Keep only necessary fields if needed, or pass full dict
        chart_data = [
            {
                "timestamp": d['timestamp'],
                "followers": d.get('followers', 0),
                "engagement": d.get('engagement', 0)
            }
            for d in data_points
        ]

        return {
            "accountId": account_id,
            "totalGrowth": int(total_growth),
            "averageEngagement": float(avg_engagement),
            "period": f"{days} days",
            "data": chart_data
        }

    except Exception as e:
        logger.error(f"Analytics calculation failed: {e}")
        return {"error": str(e)}
