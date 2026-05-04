import { existsSync, mkdirSync } from 'node:fs';
import { appendFile } from 'node:fs/promises';
import path from 'node:path';
import { getCacheDir } from './cache.mjs';

const FALLBACK_FILE = '_memory-fallback.jsonl';
const STORE_TIMEOUT_MS = 8000;

async function appendFallback(record) {
  const dir = getCacheDir();
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const file = path.join(dir, FALLBACK_FILE);
  await appendFile(file, JSON.stringify(record) + '\n');
  return { stored: 'fallback', file };
}

async function postMemory(body) {
  const endpoint = process.env.AUTOMEM_ENDPOINT;
  if (!endpoint) {
    return appendFallback({ ts: new Date().toISOString(), reason: 'no-endpoint', body });
  }
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (process.env.AUTOMEM_API_KEY) {
      headers['Authorization'] = `Bearer ${process.env.AUTOMEM_API_KEY}`;
    }
    const res = await fetch(`${endpoint.replace(/\/$/, '')}/memory`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(STORE_TIMEOUT_MS),
    });
    if (!res.ok) {
      return appendFallback({ ts: new Date().toISOString(), reason: `http-${res.status}`, body });
    }
    return { stored: 'automem' };
  } catch (err) {
    return appendFallback({ ts: new Date().toISOString(), reason: err.message, body });
  }
}

function sourceSlug(source) {
  if (!source) return null;
  const slug = source.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return slug || null;
}

export async function storeReadMemory({ title, source, url, kind, depth }) {
  const tags = ['reading', kind || 'article'];
  const slug = sourceSlug(source);
  if (slug) tags.push(`read-source:${slug}`);
  if (depth) tags.push(`depth:${depth}`);

  const content = `Read: "${title || 'Untitled'}"${source ? ` from ${source}` : ''}. ${url}`;
  return postMemory({
    content,
    tags,
    importance: 0.5,
    type: 'Context',
    metadata: { url, title, source, kind, depth },
  });
}

export async function storeSubscribeMemory({ name, feedUrl, sourceUrl, slug, kind }) {
  const tags = ['reading', 'subscribe', kind || 'rss'];
  if (slug) tags.push(`feed-source:${slug}`);
  const content = `Subscribed to feed: "${name || feedUrl}". ${feedUrl}`;
  return postMemory({
    content,
    tags,
    importance: 0.5,
    type: 'Context',
    metadata: { name, feed_url: feedUrl, source_url: sourceUrl, slug, kind },
  });
}
