import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';
test('static assets preserve body and content type', async () => {
  const response = await worker.fetch(new Request('https://example.test/'), {
    ASSETS: { fetch: async () => new Response('<h1>Inbox</h1>', { headers: { 'Content-Type': 'text/html' } }) }
  });
  assert.equal(await response.text(), '<h1>Inbox</h1>');
  assert.equal(response.headers.get('Content-Type'), 'text/html');
});
test('private inbox receives MIME email and returns only code; deletion revokes access', async () => {
  const store = new Map();
  const env = { ADMIN_TOKEN: 'test-only-token', MAIL_DOMAIN: 'daribha.online', MAIL: {
    put: async (k, v) => store.set(k, v),
    get: async (k, type) => store.has(k) ? type === 'json' ? JSON.parse(store.get(k)) : store.get(k) : null,
    delete: async k => store.delete(k),
    list: async ({ prefix }) => ({ keys: [...store.keys()].filter(k => k.startsWith(prefix)).sort().map(name => ({ name })), list_complete: true })
  }};
  const request = (path, method = 'GET', auth = true) => new Request('https://example.test' + path, { method, headers: auth ? { Authorization: 'Bearer test-only-token' } : {} });
  assert.equal((await worker.fetch(request('/api/inboxes', 'POST', false), env)).status, 401);
  const inbox = await (await worker.fetch(request('/api/inboxes', 'POST'), env)).json();
  const path = '/api/inboxes/' + inbox.address.split('@')[0];
  assert.match(inbox.address, /^[a-z]+\.[a-z]+\.[a-f0-9]{12}@daribha\.online$/);
  assert.equal((await worker.fetch(request(path + '/code'), env)).status, 204);
  const raw = new TextEncoder().encode('From: sender@example.test\r\nSubject: Sign in\r\nContent-Type: text/plain\r\n\r\nYour OTP for Example is: 012345.');
  await worker.email({ to: inbox.address, from: 'sender@example.test', raw, rawSize: raw.length, setReject: msg => assert.fail(msg) }, env);
  assert.equal(await (await worker.fetch(request(path + '/code'), env)).text(), '012345');
  await worker.fetch(request(path, 'DELETE'), env);
  assert.equal((await worker.fetch(request(path), env)).status, 404);
});
