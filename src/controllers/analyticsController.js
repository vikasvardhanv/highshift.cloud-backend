const { AppError } = require('../utils/errors');
const { ensureMockData, getAnalyticsSummary } = require('../services/analyticsService');

async function getAccountAnalytics(req, res, next) {
    try {
        const { accountId } = req.params;
        const range = parseInt(req.query.range || '30', 10);

        // Verify ownership
        const linked = req.user.linkedAccounts.id(accountId);
        if (!linked) throw new AppError('Account not found', 404, 'account_not_found');

        // Generate mock data if missing (for demo purposes)
        await ensureMockData(req.user._id, accountId, linked.platform);

        const data = await getAnalyticsSummary(req.user._id, accountId, range);

        // Calculate totals
        const totalImpressions = data.reduce((sum, d) => sum + d.metrics.impressions, 0);
        const totalEngagement = data.reduce((sum, d) => sum + d.metrics.engagement, 0);

        // Growth (last vs first)
        const startFollowers = data[0]?.metrics.followers || 0;
        const endFollowers = data[data.length - 1]?.metrics.followers || 0;
        const followerGrowth = endFollowers - startFollowers;

        res.json({
            ok: true,
            summary: {
                totalImpressions,
                totalEngagement,
                followerGrowth,
                currentFollowers: endFollowers
            },
            daily: data
        });
    } catch (err) {
        next(err);
    }
}

module.exports = { getAccountAnalytics };
