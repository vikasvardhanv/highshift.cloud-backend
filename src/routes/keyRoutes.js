const router = require('express').Router();
const { apiKeyAuth } = require('../middlewares/apiKeyAuth');
const { regenerate } = require('../controllers/keyController');

router.post('/regenerate-key', apiKeyAuth, regenerate);

module.exports = router;
