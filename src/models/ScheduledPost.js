const mongoose = require('mongoose');

const scheduledPostSchema = new mongoose.Schema({
    userId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User',
        required: true,
        index: true
    },
    // Targets: Array of { platform, accountId }
    accounts: [{
        platform: {
            type: String,
            enum: ['twitter', 'facebook', 'instagram', 'linkedin', 'youtube'],
            required: true
        },
        accountId: { type: String, required: true }
    }],
    content: {
        type: String,
        required: true,
        maxLength: 2800
    },
    media: [{
        type: String // URLs
    }],
    scheduledFor: {
        type: Date,
        required: true,
        index: true
    },
    status: {
        type: String,
        enum: ['pending', 'processing', 'published', 'failed', 'canceled'],
        default: 'pending',
        index: true
    },
    // ID from the job queue (Agenda)
    jobId: {
        type: String
    },
    // Store results or errors after publishing
    result: {
        type: mongoose.Schema.Types.Mixed
    },
    error: {
        type: String
    }
}, {
    timestamps: true
});

module.exports = mongoose.model('ScheduledPost', scheduledPostSchema);
