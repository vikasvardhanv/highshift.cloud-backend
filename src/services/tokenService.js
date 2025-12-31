const { decrypt, encrypt } = require('../utils/crypto');
const { AppError } = require('../utils/errors');
const logger = require('../utils/logger');
const User = require('../models/User');
const { getAdapter } = require('../platforms');

function nowPlus(seconds) {
  return new Date(Date.now() + seconds * 1000);
}

async function ensureValidAccessToken(userId, linkedAccountId) {
  const user = await User.findById(userId);
  if (!user) throw new AppError('User not found', 404, 'user_not_found');

  const acc = user.linkedAccounts.id(linkedAccountId);
  if (!acc) throw new AppError('Linked account not found', 404, 'linked_account_not_found');

  const adapter = getAdapter(acc.platform);
  if (!adapter) throw new AppError('Unsupported platform', 400, 'unsupported_platform');

  const accessToken = decrypt(acc.accessTokenEnc);
  const refreshToken = acc.refreshTokenEnc ? decrypt(acc.refreshTokenEnc) : null;

  const expSoon = acc.expiresAt && acc.expiresAt.getTime() <= Date.now() + 60 * 1000;
  if (!expSoon) return { user, acc, accessToken };

  if (!refreshToken || typeof adapter.refreshToken !== 'function') {
    throw new AppError(`Token expired and refresh not available for ${acc.platform}`, 401, 'token_expired');
  }

  try {
    const refreshed = await adapter.refreshToken({ refreshToken });
    const newAccess = refreshed.access_token;
    const newRefresh = refreshed.refresh_token || refreshToken;
    const expiresIn = refreshed.expires_in;

    acc.accessTokenEnc = encrypt(newAccess);
    acc.refreshTokenEnc = newRefresh ? encrypt(newRefresh) : acc.refreshTokenEnc;
    acc.expiresAt = expiresIn ? nowPlus(expiresIn) : acc.expiresAt;
    acc.tokenType = refreshed.token_type || acc.tokenType;
    acc.scope = refreshed.scope || acc.scope;

    await user.save();
    logger.info('token_refreshed', { platform: acc.platform, linkedAccountId: String(acc._id), userId: String(user._id) });

    return { user, acc, accessToken: newAccess };
  } catch (err) {
    throw adapter.mapAxiosError ? adapter.mapAxiosError(err) : new AppError('Token refresh failed', 401, 'token_refresh_failed', err.response?.data || err.message);
  }
}

module.exports = { ensureValidAccessToken };
