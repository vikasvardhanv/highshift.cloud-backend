const Joi = require('joi');
const { AppError } = require('../utils/errors');
const BrandKit = require('../models/BrandKit');

const brandSchema = Joi.object({
    name: Joi.string().max(100).required(),
    voiceDescription: Joi.string().max(1000).allow('').optional(),
    website: Joi.string().uri().allow('').optional(),
    colors: Joi.array().items(Joi.string().pattern(/^#([0-9a-f]{3}){1,2}$/i)).max(10).optional(),
    // Documents would be uploaded separately, this accepts metadata
    documents: Joi.array().items(Joi.object({
        name: Joi.string().required(),
        url: Joi.string().uri().required(),
        type: Joi.string().valid('pdf', 'txt', 'md').required()
    })).optional()
});

async function getBrandKit(req, res, next) {
    try {
        let brand = await BrandKit.findOne({ userId: req.user._id });
        if (!brand) {
            // Return empty default instead of 404 to simplify frontend
            brand = { name: 'My Brand', voiceDescription: '', website: '', colors: [], documents: [] };
        }
        res.json({ ok: true, brand });
    } catch (err) {
        next(err);
    }
}

async function updateBrandKit(req, res, next) {
    try {
        const { error, value } = brandSchema.validate(req.body, { stripUnknown: true });
        if (error) throw new AppError('Validation error', 400, 'validation_error', error.details);

        let brand = await BrandKit.findOne({ userId: req.user._id });

        if (brand) {
            Object.assign(brand, value);
        } else {
            brand = new BrandKit({
                userId: req.user._id,
                ...value
            });
        }

        await brand.save();
        res.json({ ok: true, brand });
    } catch (err) {
        next(err);
    }
}

module.exports = { getBrandKit, updateBrandKit };
