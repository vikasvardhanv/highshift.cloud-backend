const { generateApiKey, hashApiKey } = require('../utils/apiKey');

/**
 * POST /regenerate-key
 * @route POST /regenerate-key
 * @security ApiKeyAuth
 */
async function regenerate(req, res, next) {
  try {
    const rawApiKey = generateApiKey();
    req.user.apiKeyHash = await hashApiKey(rawApiKey);
    await req.user.save();
    res.json({ ok: true, apiKey: rawApiKey });
  } catch (err) {
    next(err);
  }
}

module.exports = { regenerate };
