const { randomVerifier, challengeFromVerifier } = require('../src/utils/pkce');

test('pkce verifier/challenge', () => {
  const v = randomVerifier();
  const c = challengeFromVerifier(v);
  expect(v.length).toBeGreaterThan(40);
  expect(c.length).toBeGreaterThan(30);
});
