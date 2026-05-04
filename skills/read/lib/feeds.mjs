import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile, readdir, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import Parser from 'rss-parser';
import { JSDOM } from 'jsdom';

const SLUG_MAX = 60;
const FEED_TIMEOUT_MS = 20000;
const HEAD_TIMEOUT_MS = 8000;
const HTML_TIMEOUT_MS = 15000;
const USER_AGENT = 'Mozilla/5.0 (compatible; ReadSkill/0.2; +https://github.com/flintfromthebasement/skills)';

const RSS_HINT_REGEX = /\.(rss|xml|atom)(\?|$)/i;
const RSS_CONTENT_TYPES = ['application/rss+xml', 'application/atom+xml', 'application/xml', 'text/xml'];

const parser = new Parser({
  timeout: FEED_TIMEOUT_MS,
  headers: { 'User-Agent': USER_AGENT },
});

export function getFeedsDir() {
  return process.env.READ_FEEDS_DIR || path.join(os.homedir(), 'data', 'feeds');
}

function slugify(s) {
  const out = (s || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, SLUG_MAX);
  return out || 'feed';
}

export function generateSlug({ title, feedUrl, sourceUrl }) {
  if (title) return slugify(title);
  try {
    const u = new URL(feedUrl || sourceUrl);
    const host = u.hostname.replace(/^www\./, '');
    const pathPart = u.pathname.replace(/\.(rss|xml|atom)$/i, '').replace(/\/+/g, '-').replace(/^-+|-+$/g, '');
    return slugify(pathPart ? `${host}-${pathPart}` : host);
  } catch {
    return 'feed';
  }
}

async function readSubscriptions() {
  const file = path.join(getFeedsDir(), 'subscriptions.json');
  if (!existsSync(file)) return [];
  try {
    return JSON.parse(await readFile(file, 'utf-8'));
  } catch {
    return [];
  }
}

async function writeSubscriptions(subs) {
  const dir = getFeedsDir();
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, 'subscriptions.json'), JSON.stringify(subs, null, 2));
}

async function isLikelyRssUrl(url) {
  if (RSS_HINT_REGEX.test(url)) return true;
  try {
    const res = await fetch(url, {
      method: 'HEAD',
      headers: { 'User-Agent': USER_AGENT },
      signal: AbortSignal.timeout(HEAD_TIMEOUT_MS),
      redirect: 'follow',
    });
    const ct = (res.headers.get('content-type') || '').toLowerCase();
    return RSS_CONTENT_TYPES.some((t) => ct.includes(t));
  } catch {
    return false;
  }
}

function ytChannelFeed(url) {
  try {
    const u = new URL(url);
    if (!/(^|\.)youtube\.com$/i.test(u.hostname)) return null;
    const m = u.pathname.match(/^\/channel\/(UC[A-Za-z0-9_-]{20,})/);
    if (m) return `https://www.youtube.com/feeds/videos.xml?channel_id=${m[1]}`;
    return null;
  } catch {
    return null;
  }
}

async function discoverFeedFromHtml(url) {
  const res = await fetch(url, {
    headers: { 'User-Agent': USER_AGENT },
    signal: AbortSignal.timeout(HTML_TIMEOUT_MS),
    redirect: 'follow',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`);
  const html = await res.text();
  const dom = new JSDOM(html, { url });
  const links = dom.window.document.querySelectorAll('link[rel="alternate"]');
  for (const link of links) {
    const type = (link.getAttribute('type') || '').toLowerCase();
    if (RSS_CONTENT_TYPES.some((t) => type.includes(t))) {
      const href = link.getAttribute('href');
      if (href) return new URL(href, url).toString();
    }
  }
  return null;
}

export async function resolveFeedUrl(input) {
  const yt = ytChannelFeed(input);
  if (yt) return { feedUrl: yt, sourceUrl: input, kind: 'youtube' };
  if (await isLikelyRssUrl(input)) {
    return { feedUrl: input, sourceUrl: input, kind: 'rss' };
  }
  const found = await discoverFeedFromHtml(input);
  if (found) return { feedUrl: found, sourceUrl: input, kind: 'rss' };
  const err = new Error(`No RSS/Atom feed found for: ${input}`);
  err.code = 'NO_FEED_FOUND';
  throw err;
}

export async function fetchFeed(feedUrl) {
  return parser.parseURL(feedUrl);
}

export async function subscribe(input) {
  const resolved = await resolveFeedUrl(input);
  const parsed = await fetchFeed(resolved.feedUrl);
  const title = parsed.title || resolved.feedUrl;
  const slug = generateSlug({ title, feedUrl: resolved.feedUrl, sourceUrl: resolved.sourceUrl });
  const subs = await readSubscriptions();
  const existing = subs.find((s) => s.slug === slug || s.feed_url === resolved.feedUrl);
  if (existing) {
    return { ok: false, error: 'ALREADY_SUBSCRIBED', subscription: existing };
  }
  const record = {
    slug,
    name: title,
    feed_url: resolved.feedUrl,
    source_url: resolved.sourceUrl,
    kind: resolved.kind,
    added: new Date().toISOString(),
    last_poll: null,
    item_count: parsed.items?.length || 0,
    tier: 'free',
  };
  subs.push(record);
  await writeSubscriptions(subs);
  return { ok: true, subscription: record };
}

export async function listSubscriptions() {
  return readSubscriptions();
}

async function writeState(slug, state) {
  const dir = path.join(getFeedsDir(), 'state');
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, `${slug}.json`), JSON.stringify(state, null, 2));
}

function itemHash(item) {
  const key = item.guid || item.link || `${item.title}-${item.pubDate}`;
  return crypto.createHash('sha1').update(key).digest('hex').slice(0, 16);
}

async function readKnownItemHashes(slug) {
  const dir = path.join(getFeedsDir(), 'items', slug);
  if (!existsSync(dir)) return new Set();
  const files = await readdir(dir);
  return new Set(files.filter((f) => f.endsWith('.json')).map((f) => f.replace(/\.json$/, '')));
}

async function writeItemRecord(slug, hash, record) {
  const dir = path.join(getFeedsDir(), 'items', slug);
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, `${hash}.json`), JSON.stringify(record, null, 2));
}

export async function refresh({ slug = null } = {}) {
  const subs = await readSubscriptions();
  const targets = slug ? subs.filter((s) => s.slug === slug) : subs;
  if (slug && targets.length === 0) {
    return { ok: false, error: 'NOT_FOUND', slug };
  }
  const results = [];
  for (const sub of targets) {
    try {
      const parsed = await fetchFeed(sub.feed_url);
      const known = await readKnownItemHashes(sub.slug);
      const newItems = [];
      for (const item of parsed.items || []) {
        const hash = itemHash(item);
        if (known.has(hash)) continue;
        const record = {
          id: hash,
          feed_slug: sub.slug,
          title: item.title || '',
          url: item.link || '',
          published: item.isoDate || item.pubDate || null,
          summary: item.contentSnippet || item.summary || '',
          discovered: new Date().toISOString(),
        };
        await writeItemRecord(sub.slug, hash, record);
        newItems.push(record);
      }
      sub.last_poll = new Date().toISOString();
      sub.item_count = parsed.items?.length || 0;
      await writeState(sub.slug, { last_poll: sub.last_poll });
      results.push({ slug: sub.slug, name: sub.name, new_items: newItems });
    } catch (err) {
      results.push({ slug: sub.slug, name: sub.name, error: err.message });
    }
  }
  await writeSubscriptions(subs);
  return { ok: true, results };
}

export async function unsubscribe(input) {
  const subs = await readSubscriptions();
  const idx = subs.findIndex(
    (s) => s.slug === input || s.feed_url === input || s.source_url === input
  );
  if (idx < 0) return { ok: false, error: 'NOT_FOUND' };
  const removed = subs.splice(idx, 1)[0];
  await writeSubscriptions(subs);
  try {
    await rm(path.join(getFeedsDir(), 'state', `${removed.slug}.json`), { force: true });
    await rm(path.join(getFeedsDir(), 'items', removed.slug), { recursive: true, force: true });
  } catch {
    // best-effort cleanup
  }
  return { ok: true, removed };
}
