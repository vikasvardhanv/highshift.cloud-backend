const axios = require('axios');
const { AppError } = require('../utils/errors');

function getConfig() {
  const clientId = process.env.LINKEDIN_CLIENT_ID;
  const clientSecret = process.env.LINKEDIN_CLIENT_SECRET;
  if (!clientId || !clientSecret) throw new Error('LINKEDIN_CLIENT_ID/LINKEDIN_CLIENT_SECRET missing');
  const scopes = (process.env.LINKEDIN_SCOPES || 'openid profile w_member_social offline_access').split(/\s+/).filter(Boolean);
  return { clientId, clientSecret, scopes };
}

function getAuthUrl({ redirectUri, state, codeChallenge }) {
  const { clientId, scopes } = getConfig();
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: clientId,
    redirect_uri: redirectUri,
    state,
    scope: scopes.join(' '),
    code_challenge: codeChallenge,
    code_challenge_method: 'S256'
  });
  return `https://www.linkedin.com/oauth/v2/authorization?${params.toString()}`;
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

  const res = await axios.post('https://www.linkedin.com/oauth/v2/accessToken', body.toString(), {
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
  const res = await axios.post('https://www.linkedin.com/oauth/v2/accessToken', body.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return res.data;
}

async function getProfile({ accessToken }) {
  // OpenID endpoints can be used for profile if openid scope granted
  const res = await axios.get('https://api.linkedin.com/v2/userinfo', {
    headers: { Authorization: `Bearer ${accessToken}` }
  });
  return {
    accountId: res.data?.sub,
    username: res.data?.preferred_username,
    displayName: res.data?.name,
    rawProfile: res.data
  };
}

async function post({ accessToken, content }) {
  // Use REST Posts API (member share). Requires w_member_social.
  const me = await axios.get('https://api.linkedin.com/v2/me', { headers: { Authorization: `Bearer ${accessToken}` } });
  const author = `urn:li:person:${me.data.id}`;

  const payload = {
    author,
    lifecycleState: 'PUBLISHED',
    specificContent: {
      'com.linkedin.ugc.ShareContent': {
        shareCommentary: { text: content },
        shareMediaCategory: 'NONE'
      }
    },
    visibility: { 'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC' }
  };

  const res = await axios.post('https://api.linkedin.com/v2/ugcPosts', payload, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'X-Restli-Protocol-Version': '2.0.0'
    }
  });
  return { id: res.headers?.location || 'unknown', raw: res.data };
}

function mapAxiosError(err) {
  const status = err.response?.status;
  if (status === 401) return new AppError('LinkedIn auth failed', 401, 'linkedin_auth_failed');
  if (status === 429) return new AppError('LinkedIn rate limit', 429, 'linkedin_rate_limited', err.response?.data);
  return new AppError('LinkedIn API error', status || 502, 'linkedin_api_error', err.response?.data || err.message);
}

module.exports = { platform: 'linkedin', getAuthUrl, exchangeCode, refreshToken, getProfile, post, mapAxiosError };
