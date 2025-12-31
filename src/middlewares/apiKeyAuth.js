const User = require('../models/User');
const { verifyApiKey } = require('../utils/apiKey');
const { AppError } = require('../utils/errors');

async function apiKeyAuth(req, _res, next) {
  const raw = req.get('X-API-Key');
  if (!raw) return next(new AppError('Missing API key', 401, 'missing_api_key'));

  // We cannot query by bcrypt hash directly, so do a small scan with an index-friendly strategy:
  // store a prefix hash for lookup would be better at scale.
  // For MVP, we fetch candidates in batches.
  const candidates = await User.find({}, { apiKeyHash: 1 }).limit(5000);
  for (const u of candidates) {
    // eslint-disable-next-line no-await-in-loop
    const ok = await verifyApiKey(raw, u.apiKeyHash);
    if (ok) {
      req.user = await User.findById(u._id);
      return next();
    }
  }
  return next(new AppError('Invalid API key', 401, 'invalid_api_key'));
}

module.exports = { apiKeyAuth };
