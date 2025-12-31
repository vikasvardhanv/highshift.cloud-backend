const express = require('express');
const router = express.Router();
const { getBrandKit, updateBrandKit } = require('../controllers/brandController');

/**
 * @route GET /brand
 * @group BrandKit
 * @security ApiKeyAuth
 */
router.get('/', getBrandKit);

/**
 * @route POST /brand
 * @group BrandKit
 * @security ApiKeyAuth
 */
router.post('/', updateBrandKit);

module.exports = router;
