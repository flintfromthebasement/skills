#!/usr/bin/env node
/**
 * wp-screenshots / capture
 *
 * Puppeteer-driven WordPress screenshot harness. Reads a JSON brief
 * describing each shot (URL, viewport, login state, hover/click targets,
 * etc.) and writes PNGs into an output folder.
 *
 * Usage:
 *   node capture.mjs --brief brief.json
 *   node capture.mjs --brief brief.json --site https://example.com
 *   node capture.mjs --brief brief.json --only 02-customizer,03-front-page
 *
 * Auth options (only needed for admin shots):
 *   --user <login>                Brief takes precedence if set
 *   --pass <password>             Inline (avoid on shared shells)
 *   --pass-env <ENV_NAME>         Read password from env var (preferred)
 *
 * The brief MAY include a top-level "site" and "auth" block:
 *   {
 *     "topic": "my-shots",
 *     "site": "https://example.com",
 *     "auth": { "user": "admin", "passEnv": "MYSITE_PASS" },
 *     "dpr": 2,
 *     "shots": [ ... ]
 *   }
 *
 * See briefs/example.json for the full shot schema.
 *
 * Plugin isolation (optional): with a WP-CLI prefix in "wp" and a list of
 * plugin slugs in "plugins" (brief-level or per shot), only those plugins are
 * active while a shot is captured. The site's original active plugins are
 * restored when the run ends, and on the next run if one crashes.
 */

import puppeteer from 'puppeteer-core';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, rmSync } from 'node:fs';
import { parseArgs } from 'node:util';
import { join, resolve, isAbsolute, dirname, basename } from 'node:path';

const HIDE_NOTICES_CSS = `
  .notice, .updated, .update-nag, .error,
  .notice-error, .notice-warning, .notice-info, .notice-success,
  #wp-admin-bar-updates, .update-plugins, .menu-counter,
  .components-modal__screen-overlay { display: none !important; }
  /* keep Gutenberg start-pattern picker visible — intentional content */
  .components-modal__screen-overlay:has(.editor-start-page-options) { display: flex !important; }
`;

const CHROMIUM_CANDIDATES = [
  process.env.WP_SCREENSHOTS_CHROMIUM,
  process.env.PUPPETEER_EXECUTABLE_PATH,
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
].filter(Boolean);

function findChromium() {
  // Puppeteer cache (puppeteer-core needs an external binary; the regular
  // `puppeteer` package would manage its own. We prefer system Chromium.)
  const cacheRoot = join(process.env.HOME || '', '.cache/puppeteer/chrome');
  if (existsSync(cacheRoot)) {
    try {
      const dirs = readdirSync(cacheRoot).sort().reverse();
      for (const d of dirs) {
        const p = join(cacheRoot, d, 'chrome-linux64/chrome');
        if (existsSync(p)) return p;
        const m = join(cacheRoot, d, 'chrome-mac/Chromium.app/Contents/MacOS/Chromium');
        if (existsSync(m)) return m;
      }
    } catch {}
  }
  for (const c of CHROMIUM_CANDIDATES) if (c && existsSync(c)) return c;
  return null;
}

const { values } = parseArgs({
  options: {
    brief:    { type: 'string' },
    site:     { type: 'string' },
    user:     { type: 'string' },
    pass:     { type: 'string' },
    'pass-env': { type: 'string' },
    'out-dir':  { type: 'string' },
    only:     { type: 'string' },
    wp:       { type: 'string' },
    'no-login': { type: 'boolean' },
    help:     { type: 'boolean' },
  },
  strict: false,
});

if (values.help || !values.brief) {
  console.log(`Usage: node capture.mjs --brief <path-to-brief.json> [options]

Options:
  --site <url>          Base URL (overrides brief.site)
  --user <user>         WP admin user (overrides brief.auth.user)
  --pass <pass>         WP admin password (prefer --pass-env)
  --pass-env <NAME>     Read password from this env var
  --out-dir <dir>       Output directory (default: ./screenshots/<topic>/)
  --only <slugs>        Comma-separated list of slugs to capture
  --wp <command>        WP-CLI command prefix for the site (overrides brief.wp)
  --no-login            Skip login (anonymous-only briefs)
  --help                Show this help
`);
  process.exit(values.help ? 0 : 1);
}

const briefPath = resolve(values.brief);
const brief = JSON.parse(readFileSync(briefPath, 'utf-8'));

if (!brief.topic || !Array.isArray(brief.shots)) {
  console.error('FAIL: brief must have { topic, shots: [...] }');
  process.exit(1);
}

const SITE = (values.site || brief.site || '').replace(/\/+$/, '');
if (!SITE) {
  console.error('FAIL: missing site URL. Set brief.site or pass --site <url>.');
  process.exit(1);
}

const briefAuth = brief.auth || {};
const USER = values.user || briefAuth.user || '';
const PASS_ENV = values['pass-env'] || briefAuth.passEnv || '';
const PASS = values.pass || (PASS_ENV ? process.env[PASS_ENV] : '') || briefAuth.pass || '';

const needsLogin = !values['no-login'] && brief.shots.some(s => !s.loggedOut);
if (needsLogin && (!USER || !PASS)) {
  console.error('FAIL: brief contains logged-in shots but no credentials provided.');
  console.error('  Set --user + --pass-env (recommended) or --pass.');
  console.error('  Or pass --no-login if every shot in the brief sets loggedOut: true.');
  process.exit(1);
}

const onlySet = values.only ? new Set(values.only.split(',').map(s => s.trim())) : null;
const shots = onlySet ? brief.shots.filter(s => onlySet.has(s.slug)) : brief.shots;

const DEFAULT_OPTIMIZE = 'lossy';
const OPTIMIZE_MODES = ['lossy', 'lossless', 'none'];
const badOptimize = shots
  .map(s => [s.slug, s.optimize ?? brief.optimize ?? DEFAULT_OPTIMIZE])
  .filter(([, mode]) => !OPTIMIZE_MODES.includes(mode));
if (badOptimize.length) {
  for (const [slug, mode] of badOptimize) console.error(`FAIL: ${slug || '?'}: optimize must be one of ${OPTIMIZE_MODES.join(', ')} (got ${JSON.stringify(mode)})`);
  process.exit(1);
}

const WP = values.wp || brief.wp || '';
const SLUG_RE = /^[A-Za-z0-9._-]+$/;
// A shot's "plugins": false captures with the site's own active plugins.
const pluginsFor = spec => (spec.plugins === false ? null : spec.plugins ?? brief.plugins);
const pluginSets = shots.map(pluginsFor).filter(Boolean);
if (pluginSets.length) {
  if (!WP) {
    console.error('FAIL: "plugins" is set but there is no WP-CLI command. Set brief.wp or pass --wp.');
    process.exit(1);
  }
  const bad = pluginSets.flat().filter(p => typeof p !== 'string' || !SLUG_RE.test(p));
  if (bad.length || pluginSets.some(p => !Array.isArray(p))) {
    console.error(`FAIL: "plugins" must be arrays of plugin slugs (got ${JSON.stringify(bad.length ? bad : pluginSets)})`);
    process.exit(1);
  }
}

const defaultOutDir = join(process.cwd(), 'screenshots', brief.topic);
const rawOutDir = values['out-dir'] || brief.outDir || defaultOutDir;
const outDir = isAbsolute(rawOutDir) ? rawOutDir : resolve(process.cwd(), rawOutDir);
mkdirSync(outDir, { recursive: true });

const chromium = findChromium();
if (!chromium) {
  console.error('FAIL: no Chromium/Chrome binary found.');
  console.error('  Set WP_SCREENSHOTS_CHROMIUM=/path/to/chrome,');
  console.error('  or install one (apt install chromium-browser / brew install --cask google-chrome).');
  process.exit(2);
}

console.log(`Site:    ${SITE}`);
console.log(`Output:  ${outDir}`);
console.log(`Capturing ${shots.length} shot(s)\n`);

const DEFAULT_DPR = 2;

// Recompress a PNG in place: 'lossy' = 256-color palette (TinyPNG-style), 'lossless' = max zlib, 'none' = skip.
// The full-size capture is kept at originals/<slug>.png whenever the file is rewritten.
async function optimizePng(path, mode) {
  const original = join(dirname(path), 'originals', basename(path));
  rmSync(original, { force: true });
  if (mode === 'none') return '';
  const { default: sharp } = await import('sharp');
  const raw = readFileSync(path);
  let out = await sharp(raw).png({ compressionLevel: 9, effort: 10, adaptiveFiltering: true }).toBuffer();
  if (mode === 'lossy') {
    const lossy = await sharp(raw).png({ palette: true, quality: 90, effort: 10, compressionLevel: 9 }).toBuffer();
    if (lossy.length < out.length) out = lossy;
  }
  if (out.length >= raw.length) return ' (already optimal)';
  mkdirSync(dirname(original), { recursive: true });
  writeFileSync(original, raw);
  writeFileSync(path, out);
  return ` (${mode} ${Math.round(raw.length / 1024)}KB -> ${Math.round(out.length / 1024)}KB)`;
}

// ---- Plugin isolation (brief.wp + plugins) ----

function wp(args) {
  return execFileSync('/bin/bash', ['-c', `${WP} ${args}`], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}

function pluginNames(filter = '') {
  return wp(`plugin list ${filter} --field=name`).split('\n').map(s => s.trim()).filter(s => SLUG_RE.test(s));
}

// The site's original active plugins, saved before the first switch. Keyed by the WP-CLI command
// so a crashed run is restored by the next run against the same site, whatever its output folder.
const RESTORE_FILE = join(process.env.HOME || '.', '.config', 'wp-screenshots',
  `restore-${Buffer.from(WP).toString('base64url').slice(0, 60)}.json`);
let originalActive = null;
let currentSet = null;

function setActivePlugins(target) {
  const active = pluginNames('--status=active');
  const off = active.filter(p => !target.includes(p));
  const on = target.filter(p => !active.includes(p));
  if (off.length) wp(`plugin deactivate ${off.join(' ')}`);
  if (on.length) wp(`plugin activate ${on.join(' ')}`);
  return { off, on };
}

function restorePlugins() {
  if (!existsSync(RESTORE_FILE)) return;
  const { active } = JSON.parse(readFileSync(RESTORE_FILE, 'utf8'));
  const { off, on } = setActivePlugins(active);
  rmSync(RESTORE_FILE, { force: true });
  console.log(`Restored the site's plugins (${on.length} back on, ${off.length} back off).`);
}

function usePlugins(target) {
  if (!target) {
    if (originalActive && currentSet) {
      setActivePlugins(originalActive);
      currentSet = null;
    }
    return;
  }
  const key = [...target].sort().join(' ');
  if (key === currentSet) return;
  if (!originalActive) {
    originalActive = pluginNames('--status=active');
    mkdirSync(dirname(RESTORE_FILE), { recursive: true });
    writeFileSync(RESTORE_FILE, JSON.stringify({ wp: WP, active: originalActive }));
  }
  const { off } = setActivePlugins(target);
  currentSet = key;
  console.log(`\n  plugins: only ${target.join(', ') || '(none)'} active${off.length ? ` (${off.length} switched off)` : ''}`);
}

// Print what else could end up in the shots: active plugins outside the brief's list, and
// pending updates (update bubbles are hidden by CSS, but the real fix is a site without them).
function preflight() {
  const installed = pluginNames();
  const missing = [...new Set(pluginSets.flat())].filter(p => !installed.includes(p));
  if (missing.length) {
    console.error(`FAIL: not installed on the site: ${missing.join(', ')}`);
    process.exit(1);
  }
  const allowed = new Set(pluginSets.flat());
  const active = pluginNames('--status=active');
  console.log(`Active plugins: ${active.join(', ') || 'none'}`);
  const extra = active.filter(p => !allowed.has(p));
  if (extra.length && shots.some(s => !pluginsFor(s))) {
    console.log(`  ! shots without "plugins" will show these too: ${extra.join(', ')}`);
  }
  let updates = [];
  try { updates = pluginNames('--update=available'); } catch {}
  if (updates.length) console.log(`  ! plugins with updates pending: ${updates.join(', ')}`);
  console.log('');
}

async function login(page) {
  await page.goto(`${SITE}/wp-login.php`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#user_login');
  await page.type('#user_login', USER);
  await page.type('#user_pass', PASS);
  await Promise.all([
    page.click('#wp-submit'),
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }),
  ]);
  if (!page.url().includes('/wp-admin/')) {
    throw new Error(`login failed (now at ${page.url()})`);
  }
}

function resolveUrl(spec) {
  const u = spec.url || '/';
  return u.startsWith('http') ? u : `${SITE}${u.startsWith('/') ? '' : '/'}${u}`;
}

async function applyShot(page, spec) {
  const isAdmin = (spec.url || '').includes('/wp-admin/');
  const vw = spec.viewport || (isAdmin ? [1600, 1000] : [1440, 900]);
  const dpr = spec.dpr ?? brief.dpr ?? DEFAULT_DPR;
  await page.setViewport({ width: vw[0], height: vw[1], deviceScaleFactor: dpr });

  const url = resolveUrl(spec);
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

  const hide = spec.hideNotices !== undefined ? spec.hideNotices : isAdmin;
  if (hide) {
    await page.addStyleTag({ content: HIDE_NOTICES_CSS }).catch(() => {});
  }

  if (spec.scrollTo) {
    await page.evaluate(sel => {
      const el = document.querySelector(sel);
      if (el) el.scrollIntoView({ block: 'center' });
    }, spec.scrollTo).catch(() => {});
  }

  if (spec.evaluateBefore) {
    await page.evaluate(spec.evaluateBefore).catch(e => {
      console.log(`  evaluateBefore warned: ${e.message}`);
    });
  }

  if (spec.click) {
    await page.click(spec.click).catch(() => {});
  }

  if (spec.hover) {
    const box = await page.evaluate(sel => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.x + Math.min(100, r.width / 2), y: r.y + Math.min(30, r.height / 2) };
    }, spec.hover);
    if (box) await page.mouse.move(box.x, box.y);
  }

  const delay = spec.delay ?? 1500;
  if (delay > 0) await new Promise(r => setTimeout(r, delay));

  const target = join(outDir, `${spec.slug}.png`);
  await page.screenshot({ path: target, type: 'png', fullPage: !!spec.fullPage });
  let note;
  try {
    note = await optimizePng(target, spec.optimize ?? brief.optimize ?? DEFAULT_OPTIMIZE);
  } catch (e) {
    note = ` (optimize failed: ${e.message}; raw capture kept)`;
  }
  return { path: target, note };
}

// Accept "leave this page?" prompts (an editor shot with unsaved changes would otherwise
// block the next shot's navigation); dismiss everything else.
function handleDialog(d) {
  (d.type() === 'beforeunload' ? d.accept() : d.dismiss()).catch(() => {});
}

async function main() {
  if (WP) {
    try {
      restorePlugins();
      if (pluginSets.length) preflight();
    } catch (e) {
      console.error(`FAIL: WP-CLI command failed: ${(e.stderr || e.message || '').toString().trim().split('\n').pop()}`);
      process.exit(1);
    }
  }
  if (pluginSets.length) {
    for (const sig of ['SIGINT', 'SIGTERM']) {
      process.on(sig, () => { try { restorePlugins(); } finally { process.exit(130); } });
    }
  }
  let code = 2;
  try {
    code = await captureAll();
  } finally {
    if (pluginSets.length) restorePlugins();
  }
  process.exit(code);
}

async function captureAll() {
  const browser = await puppeteer.launch({
    executablePath: chromium,
    headless: true,
    args: ['--no-sandbox', '--ignore-certificate-errors', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1600, height: 1000 },
  });

  let authPage = null;
  if (needsLogin) {
    authPage = await browser.newPage();
    authPage.on('dialog', handleDialog);
    console.log('Logging in...');
    try {
      await login(authPage);
    } catch (e) {
      console.error(`FAIL: ${e.message}`);
      await browser.close();
      return 1;
    }
  }

  let anonContext = null;
  let anonPage = null;
  async function getAnonPage() {
    if (anonPage) return anonPage;
    anonContext = await browser.createBrowserContext();
    anonPage = await anonContext.newPage();
    anonPage.on('dialog', handleDialog);
    return anonPage;
  }

  const results = [];
  for (const spec of shots) {
    if (!spec.slug || !spec.url) {
      console.log(`SKIP: missing slug or url`);
      results.push({ slug: spec.slug || '?', ok: false, error: 'missing slug or url' });
      continue;
    }
    try {
      if (pluginSets.length) usePlugins(pluginsFor(spec));
    } catch (e) {
      const msg = `plugin switch failed: ${(e.stderr || e.message || '').toString().trim().split('\n').pop()}`;
      console.log(`  ${spec.slug.padEnd(40)} FAIL: ${msg}`);
      results.push({ slug: spec.slug, ok: false, error: msg });
      continue;
    }
    process.stdout.write(`  ${spec.slug.padEnd(40)} `);
    try {
      const page = spec.loggedOut || !authPage ? await getAnonPage() : authPage;
      const { path, note } = await applyShot(page, spec);
      console.log(`OK  -> ${path}${note}`);
      results.push({ slug: spec.slug, ok: true, path });
    } catch (e) {
      console.log(`FAIL: ${e.message}`);
      results.push({ slug: spec.slug, ok: false, error: e.message });
    }
  }

  await browser.close();

  const ok = results.filter(r => r.ok).length;
  const fail = results.length - ok;
  console.log(`\nDone: ${ok}/${results.length} captured (${fail} failed)`);
  if (fail > 0) {
    console.log('Failed:');
    for (const r of results.filter(r => !r.ok)) console.log(`  ${r.slug}: ${r.error}`);
    return 1;
  }
  return 0;
}

main().catch(e => { console.error('FAIL:', e); process.exit(2); });
