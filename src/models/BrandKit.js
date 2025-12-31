const mongoose = require('mongoose');

const brandKitSchema = new mongoose.Schema({
    userId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'User',
        required: true,
        unique: true // One Brand Kit per user (for now)
    },
    name: {
        type: String,
        default: 'My Brand'
    },
    voiceDescription: {
        type: String,
        // e.g., "Professional, confident, and witty. Uses emojis sparingly."
        default: ''
    },
    website: {
        type: String,
        default: ''
    },
    // Brand Colors (Hex codes)
    colors: [{
        type: String,
        match: /^#([0-9a-f]{3}){1,2}$/i
    }],
    // Reference documents for RAG (Retrieval Augmented Generation)
    // Simple array of URLs for now
    documents: [{
        name: String,
        url: String,
        type: String // 'pdf', 'txt', 'md'
    }]
}, {
    timestamps: true
});

module.exports = mongoose.model('BrandKit', brandKitSchema);
