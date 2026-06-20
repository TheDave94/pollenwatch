// PollenWatch card screenshot harness.
//
// Self-contained: starts a tiny static server that serves harness.html and maps
// /pollenwatch_card_static/* to the shipped card bundle + species icons, then
// renders the card across all four layouts (bars / compact / tiles / gauge) and
// the distinctive consensus/provenance/degraded states, writing PNGs to docs/images/.
//
// Run:  node shoot.mjs            (or: npm run screenshots)
//       node shoot.mjs bars-light # render a single shot by name
// Re-run after any change to pollenwatch-card.js.

import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve, extname } from 'node:path';
import { buildStates } from './fixtures.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, '..', '..');
const FRONTEND = join(REPO_ROOT, 'custom_components', 'pollenwatch', 'frontend');
const OUT = join(REPO_ROOT, 'docs', 'images');
const STATIC_BASE = '/pollenwatch_card_static/';

const MIME = { '.js': 'text/javascript', '.svg': 'image/svg+xml', '.html': 'text/html', '.css': 'text/css', '.json': 'application/json' };

const LIGHT = { '--app-bg':'#f2f3f5','--card-background-color':'#ffffff','--ha-card-background':'#ffffff','--primary-text-color':'#1c1c1c','--secondary-text-color':'#6f7780','--divider-color':'rgba(0,0,0,.12)','--primary-color':'#5a9c6a','--ha-card-border-radius':'12px' };
const DARK  = { '--app-bg':'#121417','--card-background-color':'#1c2025','--ha-card-background':'#1c2025','--primary-text-color':'#e6e8eb','--secondary-text-color':'#9aa3ad','--divider-color':'rgba(255,255,255,.12)','--primary-color':'#5a9c6a','--ha-card-border-radius':'12px' };

// Covers all four layouts + provenance tiers + a single-source "unknown" (degraded)
// state + a 45°-hatch "mixed"/divergence gauge.
const SHOTS = [
  { name: 'bars-light',         layout: 'bars',    theme: LIGHT, title: "Today's pollen" },
  { name: 'bars-dark',          layout: 'bars',    theme: DARK,  title: "Today's pollen" },
  { name: 'compact-light',      layout: 'compact', theme: LIGHT, title: "Today's pollen" },
  { name: 'tiles-light',        layout: 'tiles',   theme: LIGHT, title: "Today's pollen" },
  { name: 'gauge-light',        layout: 'gauge',   theme: LIGHT, species: 'grass' },
  { name: 'gauge-mixed-light',  layout: 'gauge',   theme: LIGHT, species: 'birch', expanded: true },
  { name: 'gauge-unknown-light', layout: 'gauge',  theme: LIGHT, species: 'hazel', expanded: true },
];
const only = process.argv[2];

async function main() {
  await mkdir(OUT, { recursive: true });
  const states = buildStates();

  const server = createServer(async (req, res) => {
    try {
      const url = decodeURIComponent(req.url.split('?')[0]);
      let file;
      if (url === '/' || url === '/harness.html') file = join(HERE, 'harness.html');
      else if (url.startsWith(STATIC_BASE)) file = join(FRONTEND, url.slice(STATIC_BASE.length));
      else { res.writeHead(404); return res.end('not found'); }
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream' });
      res.end(body);
    } catch {
      res.writeHead(404); res.end('not found');
    }
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ deviceScaleFactor: 2, viewport: { width: 600, height: 900 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('pageerror', (e) => errs.push(String(e.message)));

  await page.goto(`http://127.0.0.1:${port}/harness.html`, { waitUntil: 'load' });
  await page.waitForFunction(() => !!customElements.get('pollenwatch-card'));

  for (const shot of SHOTS) {
    if (only && shot.name !== only) continue;
    await page.evaluate(async ({ shot, states }) => {
      const stage = document.getElementById('stage');
      document.documentElement.removeAttribute('style');
      for (const [k, v] of Object.entries(shot.theme)) document.documentElement.style.setProperty(k, v);
      document.body.style.background = shot.theme['--app-bg'];
      stage.innerHTML = '';
      const card = document.createElement('pollenwatch-card');
      const cfg = { type: 'custom:pollenwatch-card', layout: shot.layout };
      if (shot.title) cfg.title = shot.title;
      if (shot.species) cfg.species = shot.species;
      if (shot.expanded) cfg.expanded_default = true;
      card.setConfig(cfg);
      card.hass = { states, locale: { language: 'en' }, themes: { darkMode: false }, callWS: async () => [], connection: { subscribeMessage: async () => (() => {}) } };
      stage.appendChild(card);
      if (card.updateComplete) await card.updateComplete;
    }, { shot, states });
    await page.waitForTimeout(700);
    const el = await page.$('#stage');
    await el.screenshot({ path: join(OUT, `${shot.name}.png`) });
    console.log('shot:', shot.name);
  }

  if (errs.length) console.log('card console/page errors:', JSON.stringify(errs.slice(0, 8)));
  await browser.close();
  server.close();
}

main();
