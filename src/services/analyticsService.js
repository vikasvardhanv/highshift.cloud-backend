const AnalyticsSnapshot = require('../models/AnalyticsSnapshot');

/**
 * Generates mock analytics data for the last 30 days if none exists.
 * This ensures the dashboard always has data to show.
 */
async function ensureMockData(userId, accountId, platform) {
    const count = await AnalyticsSnapshot.countDocuments({ accountId });
    if (count > 0) return;

    const snapshots = [];
    const now = new Date();

    // Base metrics that vary slightly per platform
    let followers = Math.floor(Math.random() * 5000) + 100;

    for (let i = 29; i >= 0; i--) {
        const date = new Date(now);
        date.setDate(date.getDate() - i);
        date.setHours(0, 0, 0, 0);

        // Random daily growth
        followers += Math.floor(Math.random() * 10) - 2;
        const impressions = Math.floor(Math.random() * 500) + 50;
        const engagement = Math.floor(impressions * (Math.random() * 0.1)); // 0-10% engagement

        snapshots.push({
            userId,
            accountId,
            platform,
            date,
            metrics: {
                followers,
                impressions,
                engagement,
                engagementRate: impressions > 0 ? (engagement / impressions) : 0
            }
        });
    }

    await AnalyticsSnapshot.insertMany(snapshots);
}

async function getAnalyticsSummary(userId, accountId, range = 30) {
    // Calculate date range
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - range);

    const snapshots = await AnalyticsSnapshot.find({
        userId,
        accountId,
        date: { $gte: startDate, $lte: endDate }
    }).sort({ date: 1 });

    return snapshots;
}

module.exports = { ensureMockData, getAnalyticsSummary };
