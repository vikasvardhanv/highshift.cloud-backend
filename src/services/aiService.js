const BrandKit = require('../models/BrandKit');

/**
 * Stub service for AI content generation.
 * In a real implementation, this would call OpenAI/Anthropic APIs.
 */
async function generatePostContent(userId, topic, platform, tone) {
    const brand = await BrandKit.findOne({ userId });

    const brandVoice = brand ? brand.voiceDescription : 'neutral';

    // Mock generation logic
    const templates = [
        `Excited to share our thoughts on ${topic}! 🚀 It's a game changer. #${topic.replace(/\s+/g, '')} #Innovation`,
        `Here's why ${topic} matters more than ever. What do you think? 👇`,
        `Just explored ${topic} and mind = blown. 🤯 Check it out!`,
        `Pro tip: Master ${topic} to level up your game. 💪`,
        `Unpopular opinion: ${topic} is actually amazing if you do it right.`
    ];

    // Pick a random template
    let content = templates[Math.floor(Math.random() * templates.length)];

    // Add platform specific nuances (mock)
    if (platform === 'twitter') {
        content = content.substring(0, 280);
    } else if (platform === 'linkedin') {
        content += '\n\nLet\'s discuss in the comments! 👇';
    }

    return {
        content,
        approximatedTokens: 50,
        model: 'gpt-4o-mock'
    };
}

module.exports = { generatePostContent };
