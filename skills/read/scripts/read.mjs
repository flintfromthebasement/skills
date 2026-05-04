#!/usr/bin/env node
/**
 * read.mjs — fetch, cache, and serve a URL at the requested depth, plus
 * lightweight feed subscriptions.
 *
 * Usage:
 *   node scripts/read.mjs <url> [--depth=skim|read|deep] [--force] [--no-store] [--json]
 *   node scripts/read.mjs sub <url> [--json]
 *   node scripts/read.mjs feeds [--json]
 *   node scripts/read.mjs refresh [--feed <slug>] [--json]
 *   node scripts/read.mjs unsub <slug-or-url> [--json]
 *
 * Depth controls how much body is returned to the caller; the cache always
 * stores the full content. The skill itself does not run an LLM. The calling
 * agent is responsible for synthesis.
 */

import yaml from 'js-yaml';
import { readCache, writeCache } from '../lib/cache.mjs';
import { fetchArticle } from '../lib/readability.mjs';
import { isYouTubeUrl, readYouTube } from '../lib/youtube.mjs';
import { storeReadMemory, storeSubscribeMemory } from '../lib/memory.mjs';
import {
  subscribe,
  listSubscriptions,
  refresh,
  unsubscribe,
} from '../lib/feeds.mjs';

const VALID_DEPTHS = new Set(['skim', 'read', 'deep']);
const DEPTH_BUDGETS = {
  skim: { head: 800, tail: 400 },
  read: { head: 5000, tail: 0 },
  deep: { head: Infinity, tail: 0 },
};
const SUBCOMMANDS = new Set(['sub', 'subscribe', 'feeds', 'list', 'refresh', 'unsub', 'unsubscribe']);

function parseReadArgs(argv) {
  const flags = { depth: 'deep', force: false, store: true, json: false };
  let url = null;
  for (const a of argv) {
    if (a === '--force') flags.force = true;
    else if (a === '--no-store') flags.store = false;
    else if (a === '--json') flags.json = true;
    else if (a.startsWith('--depth=')) flags.depth = a.slice('--depth='.length);
    else if (!a.startsWith('--') && !url) url = a;
  }
  return { url, flags };
}

function parseSimpleArgs(argv) {
  const flags = { json: false, store: true, feed: null };
  let positional = null;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--json') flags.json = true;
    else if (a === '--no-store') flags.store = false;
    else if (a === '--feed') {
      flags.feed = argv[++i] || null;
    } else if (a.startsWith('--feed=')) {
      flags.feed = a.slice('--feed='.length);
    } else if (!a.startsWith('--') && positional === null) {
      positional = a;
    }
  }
  return { positional, flags };
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

function emitJson(payload) {
  process.stdout.write(JSON.stringify(payload, null, 2) + '\n');
}

async function runRead(argv) {
  const { url, flags } = parseReadArgs(argv);
  if (!url) {
    console.error('Usage: read <url> [--depth=skim|read|deep] [--force] [--no-store] [--json]');
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

async function runSubscribe(argv) {
  const { positional: input, flags } = parseSimpleArgs(argv);
  if (!input) {
    console.error('Usage: read sub <url> [--no-store] [--json]');
    process.exit(1);
  }
  let result;
  try {
    result = await subscribe(input);
  } catch (err) {
    const payload = { ok: false, error: err.code || 'SUBSCRIBE_FAILED', message: err.message, url: input };
    if (flags.json) emitJson(payload);
    else process.stderr.write(`Error: ${err.message}\n`);
    process.exit(2);
  }
  if (!result.ok && result.error === 'ALREADY_SUBSCRIBED') {
    if (flags.json) emitJson({ ok: false, error: result.error, subscription: result.subscription });
    else process.stdout.write(`Already subscribed: ${result.subscription.name} (${result.subscription.slug})\n`);
    return;
  }
  const sub = result.subscription;
  if (flags.store) {
    const mem = await storeSubscribeMemory({
      name: sub.name,
      feedUrl: sub.feed_url,
      sourceUrl: sub.source_url,
      slug: sub.slug,
      kind: sub.kind,
    });
    sub.memory = mem.stored;
  }
  if (flags.json) emitJson({ ok: true, subscription: sub });
  else {
    process.stdout.write(`Subscribed: ${sub.name}\n`);
    process.stdout.write(`  slug: ${sub.slug}\n`);
    process.stdout.write(`  feed: ${sub.feed_url}\n`);
    process.stdout.write(`  items: ${sub.item_count}\n`);
  }
}

async function runListFeeds(argv) {
  const { flags } = parseSimpleArgs(argv);
  const subs = await listSubscriptions();
  if (flags.json) {
    emitJson({ ok: true, count: subs.length, subscriptions: subs });
    return;
  }
  if (subs.length === 0) {
    process.stdout.write('No subscriptions yet. Add one with: read sub <url>\n');
    return;
  }
  process.stdout.write(`${subs.length} subscription${subs.length === 1 ? '' : 's'}:\n`);
  for (const s of subs) {
    const last = s.last_poll ? ` (last poll: ${s.last_poll})` : ' (never polled)';
    process.stdout.write(`  • ${s.name} [${s.slug}]${last}\n    ${s.feed_url}\n`);
  }
}

async function runRefresh(argv) {
  const { flags } = parseSimpleArgs(argv);
  const result = await refresh({ slug: flags.feed });
  if (!result.ok) {
    if (flags.json) emitJson(result);
    else process.stderr.write(`Error: ${result.error}${result.slug ? ` (${result.slug})` : ''}\n`);
    process.exit(2);
  }
  if (flags.json) {
    emitJson(result);
    return;
  }
  let totalNew = 0;
  for (const r of result.results) {
    if (r.error) {
      process.stdout.write(`✗ ${r.name} [${r.slug}]: ${r.error}\n`);
      continue;
    }
    totalNew += r.new_items.length;
    process.stdout.write(`✓ ${r.name} [${r.slug}]: ${r.new_items.length} new\n`);
    for (const item of r.new_items) {
      process.stdout.write(`    - ${item.title}\n      ${item.url}\n`);
    }
  }
  process.stdout.write(`\n${totalNew} new item${totalNew === 1 ? '' : 's'} across ${result.results.length} feed${result.results.length === 1 ? '' : 's'}.\n`);
}

async function runUnsubscribe(argv) {
  const { positional: input, flags } = parseSimpleArgs(argv);
  if (!input) {
    console.error('Usage: read unsub <slug-or-url> [--json]');
    process.exit(1);
  }
  const result = await unsubscribe(input);
  if (!result.ok) {
    if (flags.json) emitJson(result);
    else process.stderr.write(`Not subscribed: ${input}\n`);
    process.exit(2);
  }
  if (flags.json) emitJson(result);
  else process.stdout.write(`Unsubscribed: ${result.removed.name} [${result.removed.slug}]\n`);
}

async function main() {
  const argv = process.argv.slice(2);
  const first = argv[0];

  if (!first) {
    console.error('Usage:');
    console.error('  read <url> [--depth=skim|read|deep] [--force] [--no-store] [--json]');
    console.error('  read sub <url> [--no-store] [--json]');
    console.error('  read feeds [--json]');
    console.error('  read refresh [--feed <slug>] [--json]');
    console.error('  read unsub <slug-or-url> [--json]');
    process.exit(1);
  }

  if (SUBCOMMANDS.has(first)) {
    const rest = argv.slice(1);
    switch (first) {
      case 'sub':
      case 'subscribe':
        return runSubscribe(rest);
      case 'feeds':
      case 'list':
        return runListFeeds(rest);
      case 'refresh':
        return runRefresh(rest);
      case 'unsub':
      case 'unsubscribe':
        return runUnsubscribe(rest);
    }
  }

  return runRead(argv);
}

const isDirectInvocation = import.meta.url === `file://${process.argv[1]}`;
if (isDirectInvocation) {
  main().catch((err) => {
    process.stderr.write(`Unexpected error: ${err.stack || err.message}\n`);
    process.exit(1);
  });
}
