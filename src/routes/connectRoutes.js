const router = require('express').Router();
const { connect, callback } = require('../controllers/connectController');

/**
 * @route GET /connect/{platform}
 */
router.get('/:platform', connect);

/**
 * @route GET /connect/{platform}/callback
 */
router.get('/:platform/callback', callback);

module.exports = router;
