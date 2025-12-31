const { AppError } = require('../utils/errors');

/**
 * GET /linked-accounts
 * @route GET /linked-accounts
 * @security ApiKeyAuth
 * @returns {object} 200 - { linkedAccounts: [...] }
 */
async function list(req, res, next) {
  try {
    const accounts = req.user.linkedAccounts.map(a => ({
      id: a._id,
      platform: a.platform,
      accountId: a.accountId,
      username: a.username,
      displayName: a.displayName,
      expiresAt: a.expiresAt
    }));
    res.json({ linkedAccounts: accounts });
  } catch (err) {
    next(err);
  }
}

/**
 * DELETE /linked-accounts/disconnect/:platform/:linkedAccountId
 * @route DELETE /linked-accounts/disconnect/{platform}/{linkedAccountId}
 * @security ApiKeyAuth
 */
async function disconnect(req, res, next) {
  try {
    const platform = String(req.params.platform || '').toLowerCase();
    const id = req.params.linkedAccountId;

    const acc = req.user.linkedAccounts.id(id);
    if (!acc) throw new AppError('Linked account not found', 404, 'linked_account_not_found');
    if (acc.platform !== platform) throw new AppError('Platform mismatch', 400, 'platform_mismatch');

    acc.deleteOne();
    await req.user.save();

    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
}

module.exports = { list, disconnect };
