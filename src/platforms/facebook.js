const axios = require('axios');
const { AppError } = require('../utils/errors');

/**
 * Facebook Graph API:
 * - A user token alone is usually NOT enough to post. You typically need a Page access token.
 * This adapter implements a pragmatic approach:
 * 1) exchange code -> user token
 * 2) list user's pages
 * 3) pick the first page by default (or the client can pass pageId/accountId later)
 * 4) use page access token to post to /{page-id}/feed
 *
 * Extend as needed for selecting Pages and permissions review.
 */

function getConfig() {
  const appId = process.env.FACEBOOK_APP_ID;
  const appSecret = process.env.FACEBOOK_APP_SECRET;
  if (!appId || !appSecret) throw new Error('FACEBOOK_APP_ID/FACEBOOK_APP_SECRET missing');
  const scopes = (process.env.FACEBOOK_SCOPES || '').split(',').map(s => s.trim()).filter(Boolean);
  return { appId, appSecret, scopes };
}

function getAuthUrl({ redirectUri, state, codeChallenge }) {
  // Facebook does not require PKCE for confidential clients; it will ignore unknown parameters.
  const { appId, scopes } = getConfig();
  const params = new URLSearchParams({
    client_id: appId,
    redirect_uri: redirectUri,
    state,
    response_type: 'code',
    scope: scopes.join(',')
  });
  // include PKCE params for consistency if supported
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
  // Facebook long-lived tokens are obtained via a separate exchange (not a classic refresh token).
  // For production, implement: GET /oauth/access_token?grant_type=fb_exchange_token
  throw new AppError('Facebook token refresh is not implemented (use long-lived token exchange)', 501, 'facebook_refresh_not_implemented');
}

async function getProfile({ accessToken }) {
  const res = await axios.get('https://graph.facebook.com/v24.0/me?fields=id,name', {
    params: { access_token: accessToken }
  });
  return { accountId: res.data?.id, displayName: res.data?.name, rawProfile: res.data };
}

async function getPages({ accessToken }) {
  const res = await axios.get('https://graph.facebook.com/v24.0/me/accounts', {
    params: { access_token: accessToken }
  });
  return res.data?.data || [];
}

async function post({ accessToken, content, accountId }) {
  // accountId is treated as a Page ID.
  let pageId = accountId;
  let pageAccessToken = null;

  if (!pageId) {
    const pages = await getPages({ accessToken });
    const first = pages[0];
    pageId = first?.id;
    pageAccessToken = first?.access_token;
  }

  if (!pageId) throw new AppError('No Facebook Page found for this user', 400, 'facebook_no_page');
  if (!pageAccessToken) {
    // Find matching page token
    const pages = await getPages({ accessToken });
    const p = pages.find(x => x.id === pageId);
    pageAccessToken = p?.access_token;
  }
  if (!pageAccessToken) throw new AppError('Missing Page access token for selected Page', 400, 'facebook_missing_page_token');

  const res = await axios.post(`https://graph.facebook.com/v24.0/${pageId}/feed`, null, {
    params: { message: content, access_token: pageAccessToken }
  });
  return { id: res.data?.id, raw: res.data };
}

function mapAxiosError(err) {
  const status = err.response?.status;
  if (status === 401) return new AppError('Facebook auth failed', 401, 'facebook_auth_failed');
  if (status === 429) return new AppError('Facebook rate limit', 429, 'facebook_rate_limited', err.response?.data);
  return new AppError('Facebook API error', status || 502, 'facebook_api_error', err.response?.data || err.message);
}

module.exports = { platform: 'facebook', getAuthUrl, exchangeCode, refreshToken, getProfile, post, mapAxiosError };
