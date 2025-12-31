const crypto = require('crypto');

function base64Url(buf) {
  return buf.toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/g, '');
}

function randomVerifier() {
  // 43-128 chars recommended by RFC 7636.
  return base64Url(crypto.randomBytes(48));
}

function challengeFromVerifier(verifier) {
  const hash = crypto.createHash('sha256').update(verifier).digest();
  return base64Url(hash);
}

function randomState() {
  return base64Url(crypto.randomBytes(24));
}

module.exports = { randomVerifier, challengeFromVerifier, randomState };
