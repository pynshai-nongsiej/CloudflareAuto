import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createLocalPart, LOCAL_PART } from '../src/addresses.js';

test('Faker addresses use safe names and unique suffixes', () => {
  const names = Array.from({ length: 200 }, createLocalPart);
  assert.equal(new Set(names).size, names.length);
  for (const name of names) {
    assert.match(name, /^[a-z]+\.[a-z]+\.[a-f0-9]{12}$/);
    assert.ok(name.length <= 64);
    assert.ok(LOCAL_PART.test(name));
  }
});
test('legacy and clean inboxes remain valid; malformed addresses rejected', () => {
  assert.ok(LOCAL_PART.test('a'.repeat(32)));
  assert.ok(LOCAL_PART.test('maya.patel'));
  assert.ok(LOCAL_PART.test('maya.patel42'));
  for (const invalid of ['../secret', 'a..b', 'maya..patel', 'maya.patel@example.com', '']) {
    assert.equal(LOCAL_PART.test(invalid), false);
  }
});
