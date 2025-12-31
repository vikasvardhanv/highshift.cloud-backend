const axios = require('axios');
const { AppError } = require('../utils/errors');

function getConfig() {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  if (!clientId || !clientSecret) throw new Error('GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET missing');
  const scopes = (process.env.GOOGLE_SCOPES || 'https://www.googleapis.com/auth/youtube.upload').split(/\s+/).filter(Boolean);
  return { clientId, clientSecret, scopes };
}

function getAuthUrl({ redirectUri, state, codeChallenge }) {
  const { clientId, scopes } = getConfig();
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: scopes.join(' '),
    state,
    access_type: 'offline',
    prompt: 'consent',
    code_challenge: codeChallenge,
    code_challenge_method: 'S256'
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

async function exchangeCode({ code, redirectUri, codeVerifier }) {
  const { clientId, clientSecret } = getConfig();
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: redirectUri,
    client_id: clientId,
    client_secret: clientSecret,
    code_verifier: codeVerifier
  });
  const res = await axios.post('https://oauth2.googleapis.com/token', body.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return res.data;
}

async function refreshToken({ refreshToken }) {
  const { clientId, clientSecret } = getConfig();
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: refreshToken,
    client_id: clientId,
    client_secret: clientSecret
  });
  const res = await axios.post('https://oauth2.googleapis.com/token', body.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return res.data;
}

async function getProfile({ accessToken }) {
  const res = await axios.get('https://www.googleapis.com/oauth2/v3/userinfo', {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  return {
    accountId: res.data?.sub,
    username: res.data?.email,
    displayName: res.data?.name,
    rawProfile: res.data
  };
}

async function post() {
  // YouTube doesn't support "text posts" via Data API.
  // Uploading videos uses resumable uploads.
  throw new AppError('YouTube posting is not implemented. Extend youtube.js for video uploads.', 501, 'youtube_not_implemented');
}

function mapAxiosError(err) {
  const status = err.response?.status;
  if (status === 401) return new AppError('Google/YouTube auth failed', 401, 'youtube_auth_failed');
  if (status === 429) return new AppError('Google/YouTube rate limit', 429, 'youtube_rate_limited', err.response?.data);
  return new AppError('YouTube API error', status || 502, 'youtube_api_error', err.response?.data || err.message);
}

module.exports = { platform: 'youtube', getAuthUrl, exchangeCode, refreshToken, getProfile, post, mapAxiosError };
