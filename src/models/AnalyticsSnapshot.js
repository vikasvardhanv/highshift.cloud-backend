const mongoose = require('mongoose');

const analyticsSnapshotSchema = new mongoose.Schema({
    userId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User',
        required: true,
        index: true
    },
    // Link to the specific connected account in User.linkedAccounts
    accountId: {
        type: String,
        required: true
    },
    platform: {
        type: String,
        enum: ['twitter', 'facebook', 'instagram', 'linkedin', 'youtube'],
        required: true
    },
    date: {
        type: Date,
        required: true,
        index: true // Efficient date range queries
    },
    metrics: {
        followers: { type: Number, default: 0 },
        impressions: { type: Number, default: 0 },
        engagement: { type: Number, default: 0 },
        engagementRate: { type: Number, default: 0 } // Percentage (0.05 = 5%)
    }
}, {
    timestamps: true
});

// Compound index to ensure one snapshot per account per day
analyticsSnapshotSchema.index({ accountId: 1, date: 1 }, { unique: true });

module.exports = mongoose.model('AnalyticsSnapshot', analyticsSnapshotSchema);
