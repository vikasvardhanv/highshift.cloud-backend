const Joi = require('joi');
const { AppError } = require('../utils/errors');
const { getAdapter } = require('../platforms');
const { ensureValidAccessToken } = require('../services/tokenService');

const postSchema = Joi.object({
  content: Joi.string().min(1).max(2800).required(),
  media: Joi.array().items(Joi.string().max(2_000_000)).max(4).optional(),
  accountId: Joi.string().optional() // linkedAccount _id
}).required();

/**
 * POST /post/:platform
 * @route POST /post/{platform}
 * @security ApiKeyAuth
 */
async function postSingle(req, res, next) {
  try {
    const platform = String(req.params.platform || '').toLowerCase();
    const adapter = getAdapter(platform);
    if (!adapter) throw new AppError('Unsupported platform', 400, 'unsupported_platform');

    const { error, value } = postSchema.validate(req.body, { stripUnknown: true });
    if (error) throw new AppError('Validation error', 400, 'validation_error', error.details);

    // Choose linked account
    let linked = null;
    if (value.accountId) {
      linked = req.user.linkedAccounts.id(value.accountId);
      if (!linked) throw new AppError('Linked account not found', 404, 'linked_account_not_found');
      if (linked.platform !== platform) throw new AppError('Platform mismatch', 400, 'platform_mismatch');
    } else {
      const matches = req.user.linkedAccounts.filter(a => a.platform === platform);
      if (matches.length === 0) throw new AppError(`No linked ${platform} account`, 400, 'no_linked_account');
      if (matches.length > 1) throw new AppError(`Multiple ${platform} accounts linked. Provide accountId.`, 400, 'account_required');
      linked = matches[0];
    }

    const { accessToken } = await ensureValidAccessToken(req.user._id, linked._id);

    // Platform special cases
    if (platform === 'instagram') {
      const imageUrl = value.media?.[0];
      if (!imageUrl) throw new AppError('Instagram requires media[0] as public image URL', 400, 'instagram_media_required');
      const out = await adapter.publishImage({
        accessToken,
        igUserId: linked.accountId,
        caption: value.content,
        imageUrl
      });
      return res.json({ ok: true, result: out });
    }

    const result = await adapter.post({
      accessToken,
      content: value.content,
      media: value.media,
      accountId: linked.accountId
    });

    res.json({ ok: true, result });
  } catch (err) {
    const platform = String(req.params.platform || '').toLowerCase();
    const adapter = getAdapter(platform);
    next(adapter?.mapAxiosError ? adapter.mapAxiosError(err) : err);
  }
}

/**
 * POST /post/multi
 * @route POST /post/multi
 * @security ApiKeyAuth
 * @param {object} POST.body - { accounts: [{platform, accountId}], content, media }
 */
async function postMulti(req, res, next) {
  try {
    const schema = Joi.object({
      // Accept 'accounts' as array of objects { platform, accountId }
      accounts: Joi.array().items(Joi.object({
        platform: Joi.string().valid('twitter', 'facebook', 'instagram', 'linkedin', 'youtube').required(),
        accountId: Joi.string().optional()
      })).min(1).required(),
      content: Joi.string().min(1).max(2800).required(),
      media: Joi.array().items(Joi.string().max(2_000_000)).max(4).optional()
    }).required();

    const { error, value } = schema.validate(req.body, { stripUnknown: true });
    if (error) throw new AppError('Validation error', 400, 'validation_error', error.details);

    const results = {};

    // We iterate over the requested accounts
    for (const reqAccount of value.accounts) {
      const { platform, accountId } = reqAccount;
      const key = accountId ? `${platform}:${accountId}` : platform;

      const adapter = getAdapter(platform);
      if (!adapter) {
        results[key] = { ok: false, error: { code: 'unsupported_platform', message: 'Unsupported platform' } };
        continue;
      }

      // Find the linked account
      let linked = null;
      if (accountId) {
        linked = req.user.linkedAccounts.id(accountId);
        if (!linked) {
          results[key] = { ok: false, error: { code: 'linked_account_not_found', message: 'Linked account not found' } };
          continue;
        }
        if (linked.platform !== platform) {
          results[key] = { ok: false, error: { code: 'platform_mismatch', message: 'Platform mismatch' } };
          continue;
        }
      } else {
        // Fallback: try to find a single account for this platform
        const matches = req.user.linkedAccounts.filter(a => a.platform === platform);
        if (matches.length === 0) {
          results[key] = { ok: false, error: { code: 'no_linked_account', message: `No linked ${platform} account` } };
          continue;
        }
        if (matches.length > 1) {
          results[key] = { ok: false, error: { code: 'account_required', message: `Multiple ${platform} accounts. Provide accountId.` } };
          continue;
        }
        linked = matches[0];
      }

      try {
        // eslint-disable-next-line no-await-in-loop
        const { accessToken } = await ensureValidAccessToken(req.user._id, linked._id);

        if (platform === 'instagram') {
          const imageUrl = value.media?.[0];
          if (!imageUrl) throw new AppError('Instagram requires media[0] as public image URL', 400, 'instagram_media_required');
          // eslint-disable-next-line no-await-in-loop
          const out = await adapter.publishImage({ accessToken, igUserId: linked.accountId, caption: value.content, imageUrl });
          results[key] = { ok: true, result: out };
          continue;
        }

        // eslint-disable-next-line no-await-in-loop
        const out = await adapter.post({ accessToken, content: value.content, media: value.media, accountId: linked.accountId });
        results[key] = { ok: true, result: out };
      } catch (e) {
        const mapped = adapter.mapAxiosError ? adapter.mapAxiosError(e) : e;
        results[key] = { ok: false, error: { code: mapped.code || 'error', message: mapped.message, details: mapped.details } };
      }
    }

    res.json({ ok: true, results });
  } catch (err) {
    next(err);
  }
}

module.exports = { postSingle, postMulti };
