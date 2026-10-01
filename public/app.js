const $ = id => document.getElementById(id);
let address = sessionStorage.getItem('inbox') || '';
$('address').value = address;
const status = text => { $('status').textContent = text; };
const endpoint = () => `/api/inboxes/${address.split('@')[0]}`;
async function api(path, method = 'GET') {
  const res = await fetch(path, { method, headers: { Authorization: `Bearer ${$('token').value}` } });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}
async function refresh() {
  if (!address || !$('token').value) return;
  const current = address;
  const data = await api(endpoint());
  if (address !== current) return;
  $('expiry').textContent = `Expires ${new Date(data.expires).toLocaleString()}`;
  $('messages').replaceChildren();
  for (const mail of data.messages) {
    const article = document.createElement('article');
    for (const [tag, text, cls] of [['small', `${mail.from} · ${new Date(mail.received).toLocaleString()}`], ['h2', mail.subject], ['div', mail.code || 'No code detected', 'code'], ['pre', mail.text]]) {
      const element = document.createElement(tag); element.textContent = text; if (cls) element.className = cls; article.append(element);
    }
    if (mail.code) {
      const button = document.createElement('button'); button.textContent = 'Copy code';
      button.onclick = () => navigator.clipboard.writeText(mail.code).catch(() => status('Copy failed'));
      article.append(button);
    }
    if (mail.attachments.length) { const note = document.createElement('p'); note.textContent = 'Attachments (not stored): ' + mail.attachments.map(a => a.filename).join(', '); article.append(note); }
    $('messages').append(article);
  }
  status(data.messages.length ? `${data.messages.length} messages${data.truncated ? ' (showing newest 100)' : ''} · Auto-refresh on` : 'Waiting for incoming mail…');
}
const safe = fn => async () => { try { await fn(); } catch (error) { status(error.message); } };
$('create').onclick = safe(async () => {
  const inbox = await api('/api/inboxes', 'POST'); address = inbox.address;
  sessionStorage.setItem('inbox', address); $('address').value = address; $('messages').replaceChildren();
  $('expiry').textContent = `Expires ${new Date(inbox.expires).toLocaleString()}`;
  status('Inbox created. Waiting for mail…');
});
$('refresh').onclick = safe(refresh);
$('copy').onclick = safe(async () => { if (address) { await navigator.clipboard.writeText(address); status('Address copied'); } });
$('delete').onclick = safe(async () => {
  if (!address || !confirm('Permanently delete this inbox and its messages?')) return;
  await api(endpoint(), 'DELETE'); address = ''; sessionStorage.removeItem('inbox');
  $('address').value = ''; $('expiry').textContent = ''; $('messages').replaceChildren(); status('Inbox deleted');
});
setInterval(safe(refresh), 5000);
