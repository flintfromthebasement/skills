#!/usr/bin/env node
/**
 * read.mjs — fetch, cache, and serve a URL at the requested depth.
 *
 * Usage:
 *   node scripts/read.mjs <url> [--depth=skim|read|deep] [--force] [--no-store] [--json]
 *
 * Depth controls how much body is returned to the caller; the cache always
 * stores the full content. The skill itself does not run an LLM. The calling
 * agent is responsible for synthesis.
 */

import yaml from 'js-yaml';
import { readCache, writeCache } from '../lib/cache.mjs';
import { fetchArticle } from '../lib/readability.mjs';
import { isYouTubeUrl, readYouTube } from '../lib/youtube.mjs';
import { storeReadMemory } from '../lib/memory.mjs';

const VALID_DEPTHS = new Set(['skim', 'read', 'deep']);
const DEPTH_BUDGETS = {
  skim: { head: 800, tail: 400 },
  read: { head: 5000, tail: 0 },
  deep: { head: Infinity, tail: 0 },
};

function parseArgs(argv) {
  const args = argv.slice(2);
  const flags = { depth: 'deep', force: false, store: true, json: false };
  let url = null;
  for (const a of args) {
    if (a === '--force') flags.force = true;
    else if (a === '--no-store') flags.store = false;
    else if (a === '--json') flags.json = true;
    else if (a.startsWith('--depth=')) flags.depth = a.slice('--depth='.length);
    else if (!a.startsWith('--') && !url) url = a;
  }
  return { url, flags };
}

function sliceBody(body, depth) {
  const budget = DEPTH_BUDGETS[depth];
  if (!body) return { body: '', truncated: false };
  if (!Number.isFinite(budget.head)) return { body, truncated: false };
  if (body.length <= budget.head + budget.tail) return { body, truncated: false };
  const head = body.slice(0, budget.head);
  const tail = budget.tail ? body.slice(-budget.tail) : '';
  const sep = budget.tail
    ? '\n\n... (middle omitted; pass --depth=deep for full content) ...\n\n'
    : '\n\n... (truncated; pass --depth=deep for full content) ...';
  return { body: tail ? `${head}${sep}${tail}` : `${head}${sep}`, truncated: true };
}

function emitMarkdown(out) {
  const fm = yaml.dump(out.frontmatter);
  process.stdout.write(`---\n${fm}---\n\n# ${out.frontmatter.title}\n\n${out.body}\n`);
}

function emitJson(out) {
  process.stdout.write(JSON.stringify(out, null, 2) + '\n');
}

async function main() {
  const { url, flags } = parseArgs(process.argv);
  if (!url) {
    console.error('Usage: read.mjs <url> [--depth=skim|read|deep] [--force] [--no-store] [--json]');
    process.exit(1);
  }
  if (!VALID_DEPTHS.has(flags.depth)) {
    console.error(`Invalid --depth: ${flags.depth}. Use skim | read | deep.`);
    process.exit(1);
  }

  const kind = isYouTubeUrl(url) ? 'youtube' : 'article';
  let cacheStatus = 'miss';
  let frontmatter;
  let body;

  if (!flags.force) {
    const cached = await readCache(url);
    if (cached.status === 'hit') {
      cacheStatus = 'hit';
      frontmatter = cached.frontmatter;
      body = cached.body;
    } else if (cached.status === 'broken') {
      const msg = `Cached entry has too little content (${cached.bodyChars} chars). Retry with --force to refetch.`;
      if (flags.json) emitJson({ ok: false, error: 'CACHE_BROKEN', message: msg, file: cached.file });
      else process.stderr.write(`Error: ${msg}\nCACHE_BROKEN file=${cached.file}\n`);
      process.exit(3);
    }
  }

  if (cacheStatus === 'miss') {
    let fetched;
    try {
      fetched = kind === 'youtube' ? await readYouTube(url) : await fetchArticle(url);
    } catch (err) {
      const payload = { ok: false, error: err.code || 'FETCH_FAILED', message: err.message, url };
      if (flags.json) emitJson(payload);
      else process.stderr.write(`Error: ${err.message}\n`);
      process.exit(2);
    }
    const written = await writeCache(url, {
      title: fetched.title,
      source: fetched.source,
      byline: fetched.byline,
      body: fetched.body,
      kind,
      extra: kind === 'youtube' ? { video_id: fetched.video_id } : {},
    });
    frontmatter = written.frontmatter;
    body = fetched.body;
    cacheStatus = flags.force ? 'refreshed' : 'fresh';
  }

  const sliced = sliceBody(body, flags.depth);
  const outFrontmatter = {
    ...frontmatter,
    depth: flags.depth,
    cache: cacheStatus,
    body_chars_total: body.length,
    body_chars_returned: sliced.body.length,
    truncated: sliced.truncated,
  };

  let memoryResult = { stored: 'skipped' };
  if (flags.store) {
    memoryResult = await storeReadMemory({
      title: frontmatter.title,
      source: frontmatter.source,
      url,
      kind,
      depth: flags.depth,
    });
  }
  outFrontmatter.memory = memoryResult.stored;

  const result = { frontmatter: outFrontmatter, body: sliced.body };
  if (flags.json) emitJson({ ok: true, ...result });
  else emitMarkdown(result);
}

const isDirectInvocation = import.meta.url === `file://${process.argv[1]}`;
if (isDirectInvocation) {
  main().catch((err) => {
    process.stderr.write(`Unexpected error: ${err.stack || err.message}\n`);
    process.exit(1);
  });
}
