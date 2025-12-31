import pandas as pd
from datetime import datetime, timedelta
from typing import List
from app.models.analytics import AnalyticsSnapshot
from app.utils.logger import logger

async def get_account_analytics(user_id: str, account_id: str, days: int = 30):
    """
    Calculate follower growth and engagement using Pandas.
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

        # Convert to Pandas DataFrame
        df = pd.DataFrame([s.dict() for s in snapshots])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        # Calculate Growth
        total_growth = df['followers'].iloc[-1] - df['followers'].iloc[0]
        avg_engagement = df['engagement'].mean()

        # Format for frontend
        chart_data = df[['timestamp', 'followers', 'engagement']].to_dict(orient='records')

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
