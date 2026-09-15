// Real Chrome regression checks; all page resources and auth calls are mocked.
// Run: node tests/verify_password_recovery.mjs
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import puppeteer from 'puppeteer-core';

const html = await readFile(new URL('../frontend/login.html', import.meta.url), 'utf8');
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
  headless: true, args: ['--no-sandbox', '--disable-gpu'],
});
try {
  for (const scenario of [
    { name: 'recovery session', suffix: '?reset=1', session: true, recovery: true },
    { name: 'recovery fragment', suffix: '#type=recovery', session: true, recovery: true },
    { name: 'recovery event', suffix: '?reset=1', session: false, recovery: true, event: true },
    { name: 'ordinary session', suffix: '', session: true, recovery: false },
    { name: 'anonymous login', suffix: '', session: false, recovery: false },
  ]) {
    const page = await browser.newPage();
    const errors = [];
    let savedPassword;
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
    await page.exposeFunction('recordPassword', value => { savedPassword = value; });
    await page.evaluateOnNewDocument(hasSession => {
      window.supabase = { createClient: () => ({ auth: {
        getSession: async () => ({ data: { session: hasSession ? { access_token: 'mock' } : null } }),
        onAuthStateChange: callback => { window.emitRecovery = () => callback('PASSWORD_RECOVERY'); },
        updateUser: async ({ password }) => {
          await window.recordPassword(password);
          return { error: null };
        },
      } }) };
    }, scenario.session);
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.hostname === 'insightsafrica.test' && url.pathname === '/login.html') {
        return request.respond({ status: 200, contentType: 'text/html', body: html });
      }
      if (url.hostname === 'insightsafrica.test' && url.pathname === '/ghana/hub.html') {
        return request.respond({ status: 200, contentType: 'text/html', body: '<p>Hub</p>' });
      }
      return request.respond({ status: 200, contentType: request.resourceType() === 'script'
        ? 'application/javascript' : 'text/css', body: '' });
    });
    await page.goto('http://insightsafrica.test/login.html' + scenario.suffix,
      { waitUntil: 'networkidle0' });
    if (scenario.event) await page.evaluate(() => window.emitRecovery());
    if (scenario.recovery) {
      await page.waitForSelector('#reset-modal.open');
      assert.equal(new URL(page.url()).pathname, '/login.html');
      await page.type('#reset-pw-input', 'test-password-only');
      await Promise.all([
        page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
        page.evaluate(() => handleReset()),
      ]);
      assert.equal(savedPassword, 'test-password-only');
      assert.equal(new URL(page.url()).pathname, '/ghana/hub.html');
    } else if (scenario.session) {
      assert.equal(new URL(page.url()).pathname, '/ghana/hub.html');
    } else {
      assert.equal(new URL(page.url()).pathname, '/login.html');
      assert.equal(await page.$('#reset-modal.open'), null);
    }
    assert.deepEqual(errors, []);
    console.log(`PASS ${scenario.name}: 0 browser errors`);
    await page.close();
  }
} finally {
  await browser.close();
}
