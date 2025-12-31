const express = require('express');
const router = express.Router();
const { generateContent } = require('../controllers/aiController');

/**
 * @route POST /ai/generate
 * @group AI
 * @security ApiKeyAuth
 */
router.post('/generate', generateContent);

module.exports = router;
