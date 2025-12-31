const Joi = require('joi');
const { AppError } = require('../utils/errors');
const { generatePostContent } = require('../services/aiService');

const generateSchema = Joi.object({
    topic: Joi.string().required().min(3),
    platform: Joi.string().valid('twitter', 'facebook', 'instagram', 'linkedin', 'youtube').required(),
    tone: Joi.string().optional()
});

async function generateContent(req, res, next) {
    try {
        const { error, value } = generateSchema.validate(req.body);
        if (error) throw new AppError('Validation error', 400, 'validation_error', error.details);

        const result = await generatePostContent(req.user._id, value.topic, value.platform, value.tone);

        res.json({ ok: true, result });
    } catch (err) {
        next(err);
    }
}

module.exports = { generateContent };
