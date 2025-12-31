const router = require('express').Router();
const { apiKeyAuth } = require('../middlewares/apiKeyAuth');
const { list, disconnect } = require('../controllers/accountsController');

router.use(apiKeyAuth);

router.get('/', list);
router.delete('/disconnect/:platform/:linkedAccountId', disconnect);

module.exports = router;
