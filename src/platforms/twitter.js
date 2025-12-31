const axios = require('axios');
const { AppError } = require('../utils/errors');

const AUTH_BASE = 'https://twitter.com/i/oauth2/authorize';
const TOKEN_URL = 'https://api.x.com/2/oauth2/token';

function getConfig() {
  const clientId = process.env.TWITTER_CLIENT_ID;
  if (!clientId) throw new Error('TWITTER_CLIENT_ID missing');
  const scopes = (process.env.TWITTER_SCOPES || 'tweet.read tweet.write users.read offline.access').split(/\s+/).filter(Boolean);
  return { clientId, scopes };
}

function getAuthUrl({ redirectUri, state, codeChallenge }) {
  const { clientId, scopes } = getConfig();
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: scopes.join(' '),
    state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256'
  });
  return `${AUTH_BASE}?${params.toString()}`;
}

async function exchangeCode({ code, redirectUri, codeVerifier }) {
  const { clientId } = getConfig();
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    code_verifier: codeVerifier
  });

  const res = await axios.post(TOKEN_URL, body.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return res.data;
}

async function refreshToken({ refreshToken }) {
  const { clientId } = getConfig();
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: refreshToken,
    client_id: clientId
  });
  const res = await axios.post(TOKEN_URL, body.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return res.data;
}

async function getProfile({ accessToken }) {
  // v2 "users/me"
  const res = await axios.get('https://api.x.com/2/users/me?user.fields=username,name', {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  const u = res.data?.data;
  return {
    accountId: u?.id,
    username: u?.username,
    displayName: u?.name,
    rawProfile: res.data
  };
}

async function post({ accessToken, content }) {
  // Text only, media support is a clean extension point.
  const res = await axios.post('https://api.x.com/2/tweets', { text: content }, {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  return { id: res.data?.data?.id, raw: res.data };
}

function mapAxiosError(err) {
  const status = err.response?.status;
  if (status === 401) return new AppError('Twitter auth failed', 401, 'twitter_auth_failed');
  if (status === 429) return new AppError('Twitter rate limit', 429, 'twitter_rate_limited', err.response?.data);
  return new AppError('Twitter API error', status || 502, 'twitter_api_error', err.response?.data || err.message);
}

module.exports = { platform: 'twitter', getAuthUrl, exchangeCode, refreshToken, getProfile, post, mapAxiosError };
