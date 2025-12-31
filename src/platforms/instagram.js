const axios = require('axios');
const { AppError } = require('../utils/errors');

/**
 * Instagram Graph API requires:
 * - Instagram Business/Creator account
 * - Connected to a Facebook Page
 *
 * Typical posting flow:
 * 1) /{ig-user-id}/media (create container)
 * 2) /{ig-user-id}/media_publish
 *
 * This adapter includes a minimal skeleton. You will need media URLs (publicly accessible HTTPS),
 * and proper permissions and app review.
 */

function getConfig() {
  const appId = process.env.FACEBOOK_APP_ID;
  const appSecret = process.env.FACEBOOK_APP_SECRET;
  if (!appId || !appSecret) throw new Error('FACEBOOK_APP_ID/FACEBOOK_APP_SECRET missing (Instagram uses Meta app)');
  const scopes = (process.env.INSTAGRAM_SCOPES || '').split(',').map(s => s.trim()).filter(Boolean);
  return { appId, appSecret, scopes };
}

function getAuthUrl({ redirectUri, state, codeChallenge }) {
  const { appId, scopes } = getConfig();
  const params = new URLSearchParams({
    client_id: appId,
    redirect_uri: redirectUri,
    state,
    response_type: 'code',
    scope: scopes.join(',')
  });
  params.set('code_challenge', codeChallenge);
  params.set('code_challenge_method', 'S256');
  return `https://www.facebook.com/v24.0/dialog/oauth?${params.toString()}`;
}

async function exchangeCode({ code, redirectUri }) {
  const { appId, appSecret } = getConfig();
  const params = new URLSearchParams({
    client_id: appId,
    client_secret: appSecret,
    redirect_uri: redirectUri,
    code
  });
  const res = await axios.get(`https://graph.facebook.com/v24.0/oauth/access_token?${params.toString()}`);
  return res.data;
}

async function refreshToken() {
  throw new AppError('Instagram refresh is not implemented (depends on token type)', 501, 'instagram_refresh_not_implemented');
}

async function getProfile({ accessToken }) {
  // IG Graph does not expose IG user ID directly from /me; you need to traverse:
  // /me/accounts -> /{page-id}?fields=instagram_business_account
  const pagesRes = await axios.get('https://graph.facebook.com/v24.0/me/accounts', {
    params: { access_token: accessToken }
  });
  const pages = pagesRes.data?.data || [];
  const firstPage = pages[0];
  if (!firstPage?.id) throw new AppError('No Facebook Page found (required for IG Graph)', 400, 'instagram_no_page');

  const pageRes = await axios.get(`https://graph.facebook.com/v24.0/${firstPage.id}`, {
    params: { access_token: accessToken, fields: 'instagram_business_account,name' }
  });
  const ig = pageRes.data?.instagram_business_account;
  if (!ig?.id) throw new AppError('No Instagram Business/Creator account linked to this Page', 400, 'instagram_not_linked');

  return {
    accountId: ig.id,
    displayName: pageRes.data?.name,
    rawProfile: { pages: pagesRes.data, page: pageRes.data }
  };
}

async function post({ accessToken, content, media }) {
  // For now, require a single image URL in media[0].
  const imageUrl = media?.[0];
  if (!imageUrl) throw new AppError('Instagram posting requires media[0] as a public image URL', 400, 'instagram_media_required');

  // NOTE: We need the ig-user-id (stored as accountId)
  throw new AppError('Instagram publishing endpoint requires accountId; use /post/instagram with accountId from linked accounts', 400, 'instagram_account_required');
}

async function publishImage({ accessToken, igUserId, caption, imageUrl }) {
  const createRes = await axios.post(`https://graph.facebook.com/v24.0/${igUserId}/media`, null, {
    params: { image_url: imageUrl, caption, access_token: accessToken }
  });
  const containerId = createRes.data?.id;
  if (!containerId) throw new AppError('Failed to create IG media container', 502, 'instagram_container_failed', createRes.data);

  const pubRes = await axios.post(`https://graph.facebook.com/v24.0/${igUserId}/media_publish`, null, {
    params: { creation_id: containerId, access_token: accessToken }
  });
  return { id: pubRes.data?.id, raw: { createRes: createRes.data, publishRes: pubRes.data } };
}

function mapAxiosError(err) {
  const status = err.response?.status;
  if (status === 401) return new AppError('Instagram auth failed', 401, 'instagram_auth_failed');
  if (status === 429) return new AppError('Instagram rate limit', 429, 'instagram_rate_limited', err.response?.data);
  return new AppError('Instagram API error', status || 502, 'instagram_api_error', err.response?.data || err.message);
}

module.exports = {
  platform: 'instagram',
  getAuthUrl,
  exchangeCode,
  refreshToken,
  getProfile,
  post,
  publishImage,
  mapAxiosError
};
