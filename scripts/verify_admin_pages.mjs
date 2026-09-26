import puppeteer from 'puppeteer-core';
import { writeFileSync } from 'node:fs';

const base = process.argv[2] || 'http://127.0.0.1:8017';
const output = process.argv[3];
const cases = [['ghana', 'districts', 260], ['nigeria', 'lgas', 775],
  ['ivorycoast', 'regions', 33], ['senegal', 'departments', 45],
  ['capeverde', 'islands', 22], ['southafrica', 'districts', 52]];
const browser = await puppeteer.launch({executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
  headless: 'new', args: ['--no-sandbox', '--disable-gpu']});
const results = [];
try {
  for (const [country, level, count] of cases) {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
      if (message.type() === 'error' && !message.text().includes('Failed to load resource')) errors.push(message.text());
    });
    const response = await page.goto(`${base}/${country}/flood/`, {waitUntil: 'domcontentloaded', timeout: 30000});
    if (!response.ok()) throw new Error(`Page HTTP ${response.status()}: ${country}`);
    await page.waitForFunction(level => activeLayerStats[level] && Object.keys(activeLayerStats[level]).length > 0,
      {timeout: 20000}, level);
    await page.evaluate(async level => {
      if (!boundaryLayers[level]) await toggleBoundary(level);
    }, level);
    await page.waitForFunction((level, count) => boundaryLayers[level]?.getLayers().length === count,
      {timeout: 20000}, level, count);
    const rainfall = await page.evaluate(level => {
      const layer = boundaryLayers[level].getLayers()[0];
      layer.fire('mouseover');
      const content = layer.getTooltip().getContent();
      return {count: Object.keys(activeLayerStats[level]).length,
        keys: Object.keys(activeLayerStats[level]),
        tooltip: typeof content === 'function' ? content(layer) : content};
    }, level);
    if (rainfall.count !== count || rainfall.keys.some(key => !key.split('|')[0])) throw new Error(`Invalid rainfall keys: ${country}`);
    if (/undefined|NaN/.test(rainfall.tooltip)) throw new Error(`Broken rainfall tooltip: ${country}`);
    await page.click('#btn-mode-anomaly');
    await page.waitForFunction(level => currentAnomalyData?.anomaly?.[level], {timeout: 20000}, level);
    const anomaly = await page.evaluate(level => ({count: Object.keys(currentAnomalyData.anomaly[level]).length,
      empty: Object.keys(currentAnomalyData.anomaly[level]).some(key => !key.split('|')[0])}), level);
    if (anomaly.empty) throw new Error(`Invalid anomaly keys: ${country}`);
    if (errors.length) throw new Error(`${country}: ${errors.join('; ')}`);
    const result = {country, fine_level: level, polygons: count, rainfall_areas: rainfall.count,
      anomaly_areas: anomaly.count, fatal_errors: errors.length};
    results.push(result);
    console.log(JSON.stringify(result));
    await page.close();
  }
  if (output) writeFileSync(output, JSON.stringify({passed: true, base, results}, null, 2), {flag: 'wx'});
} finally {
  await browser.close();
}
