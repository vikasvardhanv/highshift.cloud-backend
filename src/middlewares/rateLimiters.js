const rateLimit = require('express-rate-limit');

/**
 * IP limiter for all endpoints (coarse).
 */
const ipRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 300,
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * API-key limiter for protected routes (finer).
 * Uses both API key and IP as keys to avoid one noisy neighbor.
 */
const apiRateLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  keyGenerator: (req) => {
    const apiKey = req.get('X-API-Key') || 'no-key';
    return `${apiKey}:${req.ip}`;
  }
});

module.exports = { ipRateLimiter, apiRateLimiter };
