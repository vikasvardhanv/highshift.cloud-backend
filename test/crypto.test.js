const { encrypt, decrypt } = require('../src/utils/crypto');

describe('crypto utils', () => {
  beforeAll(() => {
    process.env.TOKEN_ENC_KEY_BASE64 = Buffer.alloc(32, 7).toString('base64');
  });

  test('encrypt/decrypt roundtrip', () => {
    const enc = encrypt('hello');
    const dec = decrypt(enc);
    expect(dec).toBe('hello');
  });
});
