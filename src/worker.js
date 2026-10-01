import PostalMime from 'postal-mime';
import { extractCode } from './codes.js';
import { createLocalPart, LOCAL_PART } from './addresses.js';

const TTL = 86400;
const headers = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' };
const json = (data, status = 200) => Response.json(data, { status, headers });
async function authorized(request, env) {
  if (!env.ADMIN_TOKEN) return false;
  const value = request.headers.get('Authorization') || '';
  const digest = async text => new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
  const [a, b] = await Promise.all([digest(value), digest(`Bearer ${env.ADMIN_TOKEN}`)]);
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/')) {
      const asset = await env.ASSETS.fetch(request);
      const response = new Response(asset.body, asset);
      response.headers.set('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
      response.headers.set('Referrer-Policy', 'no-referrer');
      return response;
    }
    if (!await authorized(request, env)) return json({ error: 'Unauthorized' }, 401);
    if (url.pathname === '/api/inboxes' && request.method === 'POST') {
      // Parse optional request body for clean format or custom local part
      let useClean = false;
      let customLocal = null;
      try {
        const body = await request.json();
        if (body.clean === true) useClean = true;
        if (body.localPart && typeof body.localPart === 'string') {
          customLocal = body.localPart.toLowerCase().replace(/[^a-z0-9.]/g, '').slice(0, 50);
        }
      } catch (e) { /* No body or invalid JSON, use defaults */ }

      let local = customLocal || createLocalPart(useClean);
      for (let attempt = 0; await env.MAIL.get(`inbox:${local}`); attempt++) {
        if (attempt >= 5) return json({ error: 'Please retry creating the inbox' }, 503);
        local = customLocal ? `${customLocal}${Math.floor(Math.random() * 999)}` : createLocalPart(useClean);
      }
      const inbox = { address: `${local}@${env.MAIL_DOMAIN}`, expires: Date.now() + TTL * 1000 };
      await env.MAIL.put(`inbox:${local}`, JSON.stringify(inbox), { expirationTtl: TTL });
      return json(inbox, 201);
    }
    const match = url.pathname.match(/^\/api\/inboxes\/([^/]+)(?:\/(code))?$/);
    if (!match || !LOCAL_PART.test(match[1])) return json({ error: 'Not found' }, 404);
    const local = match[1];
    const inbox = await env.MAIL.get(`inbox:${local}`, 'json');
    if (!inbox || inbox.expires <= Date.now()) return json({ error: 'Inbox expired or missing' }, 404);
    if (request.method === 'DELETE') {
      await env.MAIL.delete(`inbox:${local}`);
      let cursor;
      do {
        const page = await env.MAIL.list({ prefix: `mail:${local}:`, cursor });
        await Promise.all(page.keys.map(key => env.MAIL.delete(key.name)));
        cursor = page.list_complete ? undefined : page.cursor;
      } while (cursor);
      return json({ deleted: true });
    }
    if (request.method !== 'GET') return json({ error: 'Method not allowed' }, 405);
    const page = await env.MAIL.list({ prefix: `mail:${local}:`, limit: 100 });
    const messages = (await Promise.all(page.keys.map(key => env.MAIL.get(key.name, 'json'))))
      .filter(Boolean).filter(m => m.expires > Date.now()).sort((a, b) => b.received - a.received);
    if (match[2]) {
      const code = messages[0]?.code;
      return new Response(code || null, { status: code ? 200 : 204, headers: { ...headers, 'Content-Type': 'text/plain; charset=utf-8' } });
    }
    return json({ ...inbox, messages, truncated: !page.list_complete });
  },

  async email(message, env) {
    const [local, domain] = message.to.toLowerCase().split('@');
    if (domain !== env.MAIL_DOMAIN || !LOCAL_PART.test(local)) return message.setReject('Unknown temporary address');
    const inbox = await env.MAIL.get(`inbox:${local}`, 'json');
    if (!inbox || inbox.expires <= Date.now()) return message.setReject('Address expired or missing');
    if (message.rawSize > 2 * 1024 * 1024) return message.setReject('Message exceeds 2 MiB');
    const raw = await new Response(message.raw).arrayBuffer();
    if (raw.byteLength > 2 * 1024 * 1024) return message.setReject('Message exceeds 2 MiB');
    const parsed = await PostalMime.parse(raw);
    // Only display inert text; never execute email HTML or load tracking pixels.
    const text = parsed.text || (parsed.html || '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ');
    const received = Date.now();
    const record = { id: crypto.randomUUID(), from: message.from, subject: parsed.subject || '(No subject)', text,
      code: extractCode(text), received, expires: inbox.expires,
      attachments: (parsed.attachments || []).map(a => ({ filename: a.filename, mimeType: a.mimeType })) };
    const remaining = Math.ceil((inbox.expires - received) / 1000);
    if (remaining < 60) return message.setReject('Address expiring');
    // Reverse timestamp puts newest messages first in KV listing.
    await env.MAIL.put(`mail:${local}:${9999999999999 - received}:${record.id}`, JSON.stringify(record), { expirationTtl: remaining });
  }
};
