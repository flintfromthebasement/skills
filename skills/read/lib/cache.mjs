import { createHash } from 'node:crypto';
import { existsSync, mkdirSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import path from 'node:path';
import yaml from 'js-yaml';

const DEFAULT_CACHE_DIR = path.join(homedir(), 'data', 'read-cache');
const MIN_VALID_BODY_CHARS = 500;

export function getCacheDir() {
  const dir = process.env.READ_CACHE_DIR || DEFAULT_CACHE_DIR;
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

export function urlHash(url) {
  return createHash('sha1').update(url).digest('hex').slice(0, 16);
}

export function cachePath(url) {
  return path.join(getCacheDir(), `${urlHash(url)}.md`);
}

function parseFrontmatter(raw) {
  if (!raw.startsWith('---\n')) return { frontmatter: {}, body: raw };
  const end = raw.indexOf('\n---\n', 4);
  if (end === -1) return { frontmatter: {}, body: raw };
  const fmText = raw.slice(4, end);
  const body = raw.slice(end + 5);
  try {
    return { frontmatter: yaml.load(fmText) || {}, body };
  } catch {
    return { frontmatter: {}, body: raw };
  }
}

export async function readCache(url) {
  const file = cachePath(url);
  if (!existsSync(file)) return { status: 'miss', file };
  let raw;
  try {
    raw = await readFile(file, 'utf-8');
  } catch (err) {
    return { status: 'miss', file, error: err.message };
  }
  const { frontmatter, body } = parseFrontmatter(raw);
  const trimmed = body.trim();
  if (trimmed.length < MIN_VALID_BODY_CHARS) {
    return { status: 'broken', file, frontmatter, body: trimmed, bodyChars: trimmed.length };
  }
  return { status: 'hit', file, frontmatter, body: trimmed, bodyChars: trimmed.length };
}

export async function writeCache(url, { title, source, body, byline, kind, extra = {} }) {
  const file = cachePath(url);
  const now = new Date().toISOString();
  const existing = await readCache(url);
  const frontmatter = {
    title: title || existing.frontmatter?.title || 'Untitled',
    source: source || existing.frontmatter?.source || '',
    byline: byline || existing.frontmatter?.byline || '',
    url,
    kind: kind || existing.frontmatter?.kind || 'article',
    fetched: existing.frontmatter?.fetched || now,
    refreshed: now,
    read_count: Number(existing.frontmatter?.read_count || 0) + 1,
    ...extra,
  };
  const composed = `---\n${yaml.dump(frontmatter)}---\n\n${body.trim()}\n`;
  await writeFile(file, composed);
  return { file, frontmatter };
}
