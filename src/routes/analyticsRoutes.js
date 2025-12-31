const express = require('express');
const router = express.Router();
const { getAccountAnalytics } = require('../controllers/analyticsController');

/**
 * @route GET /analytics/:accountId
 * @group Analytics
 * @security ApiKeyAuth
 */
router.get('/:accountId', getAccountAnalytics);

module.exports = router;
