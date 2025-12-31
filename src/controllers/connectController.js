const Joi = require('joi');
const OAuthState = require('../models/OAuthState');
const User = require('../models/User');

const { getAdapter } = require('../platforms');
const { randomVerifier, challengeFromVerifier, randomState } = require('../utils/pkce');
const { encrypt } = require('../utils/crypto');
const { generateApiKey, hashApiKey, verifyApiKey } = require('../utils/apiKey');
const { AppError } = require('../utils/errors');

function callbackUrl(platform) {
  const base = process.env.OAUTH_CALLBACK_BASE_URL || `${process.env.BASE_URL || 'http://localhost:3000'}/connect`;
  return `${base.replace(/\/$/, '')}/${platform}/callback`;
}

/**
 * GET /connect/:platform
 * Optional query: apiKey=<existing key> to link another account to same user
 * Optional query: redirect=<client URL> overrides CLIENT_SUCCESS_REDIRECT for this flow only
 *
 * @route GET /connect/{platform}
 * @param {string} platform.path.required - twitter|facebook|instagram|linkedin|youtube
 * @param {string} apiKey.query - existing API key to link another account
 * @param {string} redirect.query - override client success redirect
 * @returns {object} 200 - { authUrl }
 */
async function connect(req, res, next) {
  try {
    const platform = String(req.params.platform || '').toLowerCase();
    const adapter = getAdapter(platform);
    if (!adapter) throw new AppError('Unsupported platform', 400, 'unsupported_platform');

    const schema = Joi.object({
      apiKey: Joi.string().min(10).max(200).optional(),
      redirect: Joi.string().uri().optional()
    });
    const { error, value } = schema.validate(req.query, { stripUnknown: true });
    if (error) throw new AppError('Validation error', 400, 'validation_error', error.details);

    let userId = null;
    if (value.apiKey) {
      // Lookup user by comparing bcrypt hashes (same approach as middleware)
      const candidates = await User.find({}, { apiKeyHash: 1 }).limit(5000);
      for (const u of candidates) {
        // eslint-disable-next-line no-await-in-loop
        const ok = await verifyApiKey(value.apiKey, u.apiKeyHash);
        if (ok) { userId = u._id; break; }
      }
      if (!userId) throw new AppError('Invalid apiKey provided for linking', 401, 'invalid_api_key');
    }

    const verifier = randomVerifier();
    const challenge = challengeFromVerifier(verifier);
    const state = randomState();

    await OAuthState.create({
      state,
      platform,
      codeVerifier: verifier,
      userId,
      clientRedirect: value.redirect
    });

    const redirectUri = callbackUrl(platform);
    const authUrl = adapter.getAuthUrl({ redirectUri, state, codeChallenge: challenge });

    res.json({ authUrl });
  } catch (err) {
    next(err);
  }
}

/**
 * GET /connect/:platform/callback
 * Provider redirects here.
 *
 * @route GET /connect/{platform}/callback
 * @param {string} platform.path.required
 * @param {string} code.query.required
 * @param {string} state.query.required
 * @returns {object} 200 - JSON or redirects to CLIENT_SUCCESS_REDIRECT
 */
async function callback(req, res, next) {
  try {
    const platform = String(req.params.platform || '').toLowerCase();
    const adapter = getAdapter(platform);
    if (!adapter) throw new AppError('Unsupported platform', 400, 'unsupported_platform');

    const schema = Joi.object({
      code: Joi.string().required(),
      state: Joi.string().required(),
      error: Joi.string().optional(),
      error_description: Joi.string().optional()
    });
    const { error, value } = schema.validate(req.query, { stripUnknown: true });
    if (error) throw new AppError('Validation error', 400, 'validation_error', error.details);

    if (value.error) {
      throw new AppError(`OAuth error: ${value.error}`, 400, 'oauth_error', value.error_description);
    }

    const st = await OAuthState.findOne({ state: value.state, platform });
    if (!st) throw new AppError('Invalid or expired state', 400, 'invalid_state');

    const redirectUri = callbackUrl(platform);

    const token = await adapter.exchangeCode({
      code: value.code,
      redirectUri,
      codeVerifier: st.codeVerifier
    });

    const accessToken = token.access_token;
    const refreshToken = token.refresh_token;
    const expiresAt = token.expires_in ? new Date(Date.now() + token.expires_in * 1000) : null;

    const profile = await adapter.getProfile({ accessToken });

    // Upsert user
    let user = null;
    let rawApiKey = null;

    if (st.userId) {
      user = await User.findById(st.userId);
      if (!user) throw new AppError('User for linking not found', 404, 'user_not_found');
    } else {
      rawApiKey = generateApiKey();
      const apiKeyHash = await hashApiKey(rawApiKey);
      user = await User.create({ apiKeyHash, linkedAccounts: [] });
    }

    // Prevent duplicates
    const exists = user.linkedAccounts.some(a => a.platform === platform && a.accountId === profile.accountId);
    if (!exists) {
      user.linkedAccounts.push({
        platform,
        accountId: profile.accountId,
        username: profile.username,
        displayName: profile.displayName,
        accessTokenEnc: encrypt(accessToken),
        refreshTokenEnc: refreshToken ? encrypt(refreshToken) : '',
        expiresAt,
        scope: token.scope,
        tokenType: token.token_type,
        rawProfile: profile.rawProfile
      });
      await user.save();
    }

    await OAuthState.deleteOne({ _id: st._id });

    const clientOk = st.clientRedirect || process.env.CLIENT_SUCCESS_REDIRECT;
    if (clientOk) {
      const u = new URL(clientOk);
      if (rawApiKey) u.searchParams.set('apiKey', rawApiKey);
      u.searchParams.set('platform', platform);
      u.searchParams.set('accountId', profile.accountId);
      return res.redirect(u.toString());
    }

    res.json({
      ok: true,
      apiKey: rawApiKey, // only present if newly created
      linked: { platform, accountId: profile.accountId }
    });
  } catch (err) {
    const platform = String(req.params.platform || '').toLowerCase();
    const adapter = getAdapter(platform);
    const mapped = adapter?.mapAxiosError ? adapter.mapAxiosError(err) : err;
    next(mapped);
  }
}

module.exports = { connect, callback };
