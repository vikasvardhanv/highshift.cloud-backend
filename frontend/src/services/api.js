import axios from 'axios';

// If VITE_API_URL is set, use it. Otherwise:
// - If running in development (detected via import.meta.env.DEV), default to localhost:3000
// - If running in production (served by backend), default to relative path '' (same origin)
const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:3000' : '');

const api = axios.create({
    baseURL: API_URL,
});

api.interceptors.request.use((config) => {
    const apiKey = localStorage.getItem('social_api_key');
    if (apiKey) {
        config.headers['X-API-Key'] = apiKey;
    }
    return config;
});

export const getAuthUrl = async (platform, redirectUrl) => {
    // redirectUrl is optional, backend supports it
    const res = await axios.get(`${API_URL}/connect/${platform}`, {
        params: { redirect: redirectUrl }
    });
    return res.data.authUrl;
};

export const getAccounts = async () => {
    const res = await api.get('/linked-accounts');
    // Backend returns JSON with list of accounts
    return res.data;
};

export const disconnectAccount = async (platform, accountId) => {
    await api.delete(`/linked-accounts/disconnect/${platform}/${accountId}`);
};

export const postContent = async (accounts, content) => {
    // accounts is array of { platform, accountId }
    // Endpoint: /post/multi
    const res = await api.post('/post/multi', {
        accounts,
        content
    });
    return res.data;
};

export const regenerateKey = async () => {
    const res = await api.post('/key/regenerate-key');
    return res.data.apiKey;
};

// Analytics
export const getAnalytics = async (accountId, range = 30) => {
    const res = await api.get(`/analytics/${accountId}?range=${range}`);
    return res.data;
};

// Scheduling
export const schedulePost = async (accounts, content, scheduledFor, media = []) => {
    const res = await api.post('/schedule', { accounts, content, scheduledFor, media });
    return res.data;
};

export const getScheduledPosts = async () => {
    const res = await api.get('/schedule');
    return res.data.posts;
};

export const cancelScheduledPost = async (id) => {
    await api.delete(`/schedule/${id}`);
};

// Brand Kit
export const getBrandKit = async () => {
    const res = await api.get('/brand');
    return res.data.brand;
};

export const updateBrandKit = async (data) => {
    const res = await api.post('/brand', data);
    return res.data.brand;
};

// AI Ghostwriter
export const generateContent = async (topic, platform, tone) => {
    const res = await api.post('/ai/generate', { topic, platform, tone });
    return res.data.result;
};
