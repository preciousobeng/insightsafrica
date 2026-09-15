// Chrome acceptance check with mocked Supabase/API responses; no live keys.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import puppeteer from 'puppeteer-core';

const html = await readFile(new URL('../frontend/ghana/hub.html', import.meta.url), 'utf8');
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
  headless: true, args: ['--no-sandbox', '--disable-gpu'],
});
try {
  const page = await browser.newPage();
  const errors = [], calls = [], alerts = [], writes = [];
  let keys = [], failCreate = false;
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('dialog', async dialog => {
    if (dialog.type() === 'alert') alerts.push(dialog.message());
    await dialog.accept();
  });
  await page.exposeFunction('mockRpc', (name, params) => {
    calls.push({ name, params });
    if (name === 'create_api_key') {
      if (failCreate) return { data: null, error: { message: 'API key limit reached (max 5 active keys).' } };
      const row = { id: '11111111-1111-1111-1111-111111111111', name: params.key_name,
        tier: 'free', requests_today: 0, created_at: '2026-09-15T12:00:00Z' };
      keys = [row];
      return { data: row, error: null };
    }
    assert.equal(name, 'revoke_api_key');
    assert.equal(params.key_id, keys[0].id);
    keys = [];
    return { data: null, error: null };
  });
  await page.evaluateOnNewDocument(() => {
    window.supabase = { createClient: () => ({
      auth: { getSession: async () => ({ data: { session: { access_token: 'mock' } } }) },
      rpc: (name, params) => window.mockRpc(name, params),
    }) };
  });
  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = new URL(request.url());
    if (request.method() !== 'GET') writes.push(request.url());
    if (url.pathname === '/ghana/hub.html') {
      return request.respond({ status: 200, contentType: 'text/html', body: html });
    }
    if (url.pathname.startsWith('/api/')) {
      const fixtures = {
        '/api/keys': keys,
        '/api/flood/layers': [{ rainfall_mm: { mean: 100 }, label: 'Test month' }],
        '/api/crop/layers': [{ stress_score: { severe_stress: 10 }, label: 'Test period' }],
        '/api/heat/layers': [{ city_id: 'accra', date: '2026-01-01', stats: { uhi_intensity_c: 2 } }],
        '/api/mine/sites': [],
      };
      return request.respond({ status: 200, contentType: 'application/json',
        body: JSON.stringify(fixtures[url.pathname] || []) });
    }
    return request.respond({ status: 200, contentType: request.resourceType() === 'script'
      ? 'application/javascript' : 'text/css', body: '' });
  });
  await page.goto('https://insightsafrica.test/ghana/hub.html', { waitUntil: 'networkidle0' });
  await page.waitForSelector('#keys-section', { visible: true });
  await page.type('#key-name-input', 'My browser key');
  await page.click('#btn-generate');
  await page.waitForSelector('.key-row');
  const raw = await page.$eval('#key-reveal-value', element => element.textContent);
  assert.match(raw, /^ia_[A-Za-z0-9_-]{43}$/);
  assert.deepEqual(calls[0], { name: 'create_api_key', params: {
    key_name: 'My browser key', key_hash_input: createHash('sha256').update(raw).digest('hex'),
  } });
  assert.equal(JSON.stringify(calls).includes(raw), false, 'plaintext must never be sent to the RPC');
  assert.equal(await page.$eval('.key-row-name', element => element.textContent), 'My browser key');
  failCreate = true;
  await page.evaluate(() => generateKey());
  assert.match(alerts[0], /API key limit reached/);
  assert.equal(await page.$eval('#btn-generate', element => element.disabled), false);
  await page.click('.btn-revoke');
  await page.waitForFunction(() => !document.querySelector('.key-row'));
  assert.equal(calls.at(-1).name, 'revoke_api_key');
  assert.deepEqual(writes, [], 'UI must not use direct table writes or legacy POST/DELETE');
  assert.deepEqual(errors, []);
  console.log('PASS: create/list/reveal, SHA-256 compatibility, quota error, revoke; 0 browser errors');
} finally {
  await browser.close();
}
