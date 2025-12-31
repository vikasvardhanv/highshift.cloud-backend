const crypto = require('crypto');

function getKey() {
  const b64 = process.env.TOKEN_ENC_KEY_BASE64;
  if (!b64) throw new Error('TOKEN_ENC_KEY_BASE64 missing');
  const key = Buffer.from(b64, 'base64');
  if (key.length !== 32) throw new Error('TOKEN_ENC_KEY_BASE64 must decode to 32 bytes');
  return key;
}

/**
 * AES-256-GCM encrypt. Output: base64(iv).base64(tag).base64(ciphertext)
 */
function encrypt(plainText) {
  if (!plainText) return '';
  const key = getKey();
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ciphertext = Buffer.concat([cipher.update(String(plainText), 'utf8'), cipher.final()]);
  const tag = cipher.getAuthTag();
  return [iv.toString('base64'), tag.toString('base64'), ciphertext.toString('base64')].join('.');
}

function decrypt(enc) {
  if (!enc) return '';
  const key = getKey();
  const parts = String(enc).split('.');
  if (parts.length !== 3) throw new Error('Invalid encrypted token format');
  const [ivB64, tagB64, ctB64] = parts;
  const iv = Buffer.from(ivB64, 'base64');
  const tag = Buffer.from(tagB64, 'base64');
  const ciphertext = Buffer.from(ctB64, 'base64');
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAuthTag(tag);
  const plain = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  return plain.toString('utf8');
}

module.exports = { encrypt, decrypt };
