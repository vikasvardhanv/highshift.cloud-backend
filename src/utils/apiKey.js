const crypto = require('crypto');
const bcrypt = require('bcrypt');

function generateApiKey() {
  // 32 bytes => 43ish chars base64url
  const raw = crypto.randomBytes(32).toString('base64url');
  return raw;
}

async function hashApiKey(raw) {
  const saltRounds = 12;
  return bcrypt.hash(raw, saltRounds);
}

async function verifyApiKey(raw, hash) {
  return bcrypt.compare(raw, hash);
}

module.exports = { generateApiKey, hashApiKey, verifyApiKey };
