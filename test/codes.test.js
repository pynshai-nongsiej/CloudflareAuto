import { test } from 'node:test';
import assert from 'node:assert/strict';
import { extractCode } from '../src/codes.js';
test('extracts contextual OTP and preserves leading zeros', () => {
  assert.equal(extractCode('Your OTP for Example is: 012345. This OTP will expire in 10 minutes.'), '012345');
  assert.equal(extractCode('One-Time Password\n654321'), '654321');
  assert.equal(extractCode('123456 is your verification code'), '123456');
  assert.equal(extractCode('Copyright 2026. Order 123456.'), null);
});
