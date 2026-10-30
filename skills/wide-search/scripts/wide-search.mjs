#!/usr/bin/env node
/**
 * wide-search — one query, several live-search engines (Grok, Perplexity, ChatGPT via Codex), merged sources.
 *
 *   wide-search "query"                       # all three engines in parallel
 *   wide-search --route "query"               # let the router pick engines (social → grok, quick fact → perplexity, ...)
 *   wide-search --engines grok,chatgpt "query"
 *   wide-search --fast "query"                # skip ChatGPT (slowest, ~20-90s)
 *   wide-search --x --recent --json --effort high "query"
 *   wide-search route "query"                 # print the route only, no search
 */
import { loadEnv } from './lib/env.js';
import { runEngine, ENGINES, missingAuth } from './lib/providers.js';
import { ALL, route } from './lib/route.js';

loadEnv();

const SYSTEM =
  'You are a research assistant with live web search. Answer with specific, sourced findings and cite URLs inline. ' +
  'Prefer primary sources. Say plainly when you could not find something. Never invent facts, dates, or URLs.';

const LABEL = { grok: 'Grok', perplexity: 'Perplexity', chatgpt: 'ChatGPT', openai: 'OpenAI API', claude: 'Claude' };

function usage(code) {
  console.log(`Usage: wide-search [--route] [--engines a,b] [--fast] [--x] [--recent] [--effort low|medium|high] [--json] "query"
       wide-search route "query"
Engines: ${Object.keys(ENGINES).join(', ')} (default: ${ALL.join(', ')}; openai and claude are paid API, opt-in only)`);
  process.exit(code);
}

function parseArgs(argv) {
  const a = { engines: null, route: false, fast: false, x: null, recent: false, effort: null, json: false, words: [] };
  for (let i = 0; i < argv.length; i++) {
    const v = argv[i];
    if (v === '--route') a.route = true;
    else if (v === '--fast') a.fast = true;
    else if (v === '--x') a.x = true;
    else if (v === '--no-x') a.x = false;
    else if (v === '--recent') a.recent = true;
    else if (v === '--json') a.json = true;
    else if (v === '--engines') a.engines = argv[++i].split(',').map((s) => s.trim()).filter(Boolean);
    else if (v.startsWith('--engines=')) a.engines = v.slice(10).split(',').map((s) => s.trim()).filter(Boolean);
    else if (v === '--effort') a.effort = argv[++i];
    else if (v === '-h' || v === '--help') usage(0);
    else if (v.startsWith('--')) { console.error(`Unknown flag ${v}`); usage(1); }
    else a.words.push(v);
  }
  return a;
}

function domainOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
}

function canon(url) {
  try {
    const u = new URL(url);
    for (const k of [...u.searchParams.keys()]) if (/^utm_|^fbclid$|^gclid$/.test(k)) u.searchParams.delete(k);
    u.hash = '';
    return `${u.hostname.replace(/^www\./, '')}${u.pathname.replace(/\/+$/, '')}${u.search}`;
  } catch { return url; }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const routeOnly = args.words[0] === 'route';
  if (routeOnly) args.words.shift();
  const query = args.words.join(' ').trim();
  if (!query) usage(1);

  const routed = route(query);
  if (routeOnly) {
    console.log(JSON.stringify(routed));
    return;
  }
  let engines = args.engines || (args.route ? routed.engines : ALL);
  if (args.fast) engines = engines.filter((e) => e !== 'chatgpt');
  if (!engines.length) engines = ['perplexity'];
  const bad = engines.filter((e) => !ENGINES[e]);
  if (bad.length) { console.error(`Unknown engine(s): ${bad.join(', ')}`); usage(1); }
  const x = args.x ?? (args.route ? routed.x : true);
  const prompt = args.recent ? `${query}\n\nPrefer sources from roughly the last two weeks and give dates.` : query;
  if (args.route) console.error(`route: ${routed.reason}`);
  console.error(`searching: ${engines.join(', ')}…`);

  const results = await Promise.all(engines.map(async (engine) => {
    const missing = missingAuth(engine);
    if (missing) return { engine, ok: false, skipped: true, error: `skipped: ${missing}`, text: '', citations: [], ms: null };
    try {
      const r = await runEngine(engine, { system: SYSTEM, prompt, x, ...(args.effort ? { effort: args.effort } : {}) });
      return { engine, ok: true, ...r };
    } catch (err) {
      return { engine, ok: false, error: err.message, text: '', citations: [], ms: null };
    }
  }));

  const bySource = new Map();
  for (const r of results) for (const c of r.citations) {
    const key = canon(c.url);
    if (!bySource.has(key)) bySource.set(key, { url: c.url, title: c.title, engines: new Set() });
    bySource.get(key).engines.add(r.engine);
  }
  const sources = [...bySource.values()].map((s) => ({ ...s, engines: [...s.engines] }))
    .sort((a, b) => b.engines.length - a.engines.length);

  if (args.json) {
    console.log(JSON.stringify({ query, engines, route: args.route ? routed : null, results: results.map(({ engine, ok, skipped, error, text, citations, ms }) => ({ engine, ok, skipped: Boolean(skipped), error, ms, text, citations })), sources }, null, 2));
  } else {
    const head = results.map((r) => `${LABEL[r.engine]} ${r.ok ? `${Math.round(r.ms / 1000)}s, ${r.citations.length} sources` : r.skipped ? 'SKIPPED' : 'FAILED'}`).join(' · ');
    const out = [`# wide-search: ${query}`, '', head, ''];
    for (const r of results) {
      out.push(`## ${LABEL[r.engine]}`, '', r.ok ? (r.text || '_(empty answer)_') : r.skipped ? `_${r.error}_` : `_Error: ${r.error}_`, '');
    }
    const shared = sources.filter((s) => s.engines.length > 1);
    out.push('## Sources cited by 2+ engines', '');
    out.push(...(shared.length ? shared.slice(0, 25).map((s) => `- ${s.title ? `${s.title} — ` : ''}${s.url} (${s.engines.map((e) => LABEL[e]).join(', ')})`) : ['_none_']));
    const domains = [...new Set(sources.map((s) => domainOf(s.url)))];
    out.push('', `${sources.length} distinct sources across ${domains.length} domains.`);
    console.log(out.join('\n'));
  }
  if (results.every((r) => !r.ok)) process.exit(1);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
