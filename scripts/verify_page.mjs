// Headless render check for InsightsAfrica pages.
// A page can be valid HTML yet throw on load (this codebase has a history of it).
// Static checks miss that; this loads the page in real Chrome and fails on any
// console/page error. Prints the rendered Leaflet polygon count as a sanity signal.
//
// Usage:   node scripts/verify_page.mjs <url-or-file>
//   e.g.   node scripts/verify_page.mjs http://127.0.0.1:8001/nigeria/flood/
//   e.g.   node scripts/verify_page.mjs frontend/nigeria/flood/index.html
//
// Setup (dev only, kept out of prod):  npm i puppeteer-core
// Chrome is located via CHROME_PATH, falling back to /usr/bin/google-chrome.
// Exit code 0 = clean, 1 = errors found (or bad usage).

import { resolve } from 'node:path';
import puppeteer from 'puppeteer-core';

const arg = process.argv[2];
if (!arg) {
  console.error('usage: node scripts/verify_page.mjs <url-or-file>');
  process.exit(1);
}

const target = /^https?:\/\//.test(arg) ? arg : 'file://' + resolve(arg);
const chromePath = process.env.CHROME_PATH || '/usr/bin/google-chrome';

// Hard failures: uncaught JS exceptions. This is the signal that catches the
// "X is not defined" class of bug that has silently killed pages here before.
const fatal = [];
// Soft signals: resource/network noise, often environmental (sandbox blocks the
// Cloudflare beacon, favicon 404s, etc.). Reported but do not fail the run.
const warnings = [];

// Resource failures from these are environmental noise, not page-logic bugs.
const benign = (url) =>
  url.endsWith('/favicon.ico') || url.includes('cloudflareinsights.com');

const browser = await puppeteer.launch({
  executablePath: chromePath,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'],
});

try {
  const page = await browser.newPage();

  page.on('pageerror', (err) => fatal.push('pageerror: ' + err.message));
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    // Generic resource-load failures are surfaced via requestfailed, not here.
    if (text.includes('Failed to load resource')) return;
    fatal.push('console.error: ' + text);
  });
  page.on('requestfailed', (req) => {
    const url = req.url();
    if (!benign(url)) {
      warnings.push('requestfailed: ' + url + ' (' + req.failure().errorText + ')');
    }
  });

  const resp = await page.goto(target, { waitUntil: 'networkidle2', timeout: 30000 });
  if (resp && !resp.ok() && /^https?:/.test(target)) {
    warnings.push('http ' + resp.status() + ' for ' + target);
  }

  // Give Leaflet/Chart.js a moment to paint after network idle.
  await new Promise((r) => setTimeout(r, 1500));

  const polygons = await page.evaluate(
    () => document.querySelectorAll('path.leaflet-interactive').length,
  );

  // Catch-block / swallowed-error detection: a module whose loadLayers/loadSites threw
  // shows one of these fallback messages even though no pageerror fired. (This is how the
  // crop `layers`-vs-`allLayers` regression hid from the pageerror-only check.)
  const brokenState = await page.evaluate(() => {
    const phrases = ['activate this module', 'Could not reach', 'Is the server running', 'API offline'];
    const body = document.body.innerText || '';
    return phrases.find((p) => body.includes(p)) || null;
  });
  if (brokenState) {
    fatal.push('broken-state message on page: "' + brokenState + '" (a loadLayers/loadSites catch fired)');
  }

  console.log('target:   ' + target);
  console.log('polygons: ' + polygons);
  console.log('fatal:    ' + fatal.length);
  for (const e of fatal) console.log('  x ' + e);
  console.log('warnings: ' + warnings.length);
  for (const w of warnings) console.log('  - ' + w);
  if (polygons === 0) {
    console.log('NOTE: 0 polygons rendered — if this page has a boundary map, that is a red flag.');
  }

  await browser.close();
  process.exit(fatal.length ? 1 : 0);
} catch (e) {
  console.error('harness failure: ' + e.message);
  await browser.close();
  process.exit(1);
}
