const router = require('express').Router();
const { apiKeyAuth } = require('../middlewares/apiKeyAuth');
const { postSingle, postMulti } = require('../controllers/postController');

router.use(apiKeyAuth);

router.post('/multi', postMulti);
router.post('/:platform', postSingle);

module.exports = router;
