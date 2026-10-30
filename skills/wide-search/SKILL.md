---
name: wide-search
description: Fan one web question out to Grok (web + X search), Perplexity sonar-pro, and ChatGPT (via `codex --search exec`) in parallel, merge their sources, and flag the ones two or more engines cited. Use when coverage matters more than speed (discovery lists, events, vendors, comparisons, contested or obscure facts), because each engine misses roughly half of what the others find. Has a `--route` mode that picks engines from the query. Triggers: "wide search", "search everywhere", "ask all the search engines", "cross-check this", "find everything about".
---

# wide-search

One query, several live-search engines, one merged source list. The script does the searching and the source bookkeeping; **the calling agent does the synthesis.**

```bash
node scripts/wide-search.mjs "query"                          # Grok + Perplexity + ChatGPT in parallel
node scripts/wide-search.mjs --route "query"                  # router picks engines (see below)
node scripts/wide-search.mjs --fast "query"                   # drop ChatGPT, the slowest engine
node scripts/wide-search.mjs --engines grok,chatgpt "query"   # explicit engines
node scripts/wide-search.mjs --recent --x --json --effort high "query"
node scripts/wide-search.mjs route "query"                    # print the route, don't search
```

Tip: `ln -s "$PWD/scripts/wide-search.mjs" ~/.local/bin/wide-search` to call it as `wide-search`.

## When to use it (and when not)

| Need | Use |
|---|---|
| Lists, discovery, "everything near X", comparisons, obscure local facts | `wide-search` (all engines) |
| What people on X are saying, reactions, sentiment | `wide-search --route` (goes to Grok with X search) |
| One quick fact | `wide-search --route` (goes to Perplexity), or just your agent's own search |
| Breaking or live news | `wide-search --route` (Grok with X + Perplexity) |
| Reading one known URL | not this; fetch the page |

Why bother with several engines: in one same-prompt bake-off on a local-events discovery task, Grok found 78 events, ChatGPT 64, Claude 52, and Perplexity 36. Only 40 of the 167 distinct events were found by two or more engines. Grok was the strongest single engine, ChatGPT was close and best on niche or online-only items, and Perplexity was fast and cheap but thin. One engine is fine for a single fact; for "find all of X" it leaves a lot on the table.

## Output

Markdown by default:

1. A header line with each engine's time and source count (or `FAILED` / `SKIPPED`).
2. One section per engine with its full answer.
3. **Sources cited by 2+ engines**: the corroborated ones, URLs normalized (no `www.`, tracking params, fragments, or trailing slashes) before matching.
4. A count of distinct sources and domains.

`--json` returns `{ query, engines, route, results: [{ engine, ok, skipped, error, ms, text, citations }], sources: [{ url, title, engines }] }`, with `sources` sorted by how many engines cited them.

When you synthesize: read every section, prefer claims two engines agree on or that cite a primary source, and say where the engines disagree. Don't just paste the first section.

## Flags

| Flag | Effect |
|---|---|
| `--engines a,b` | Pick engines: `grok`, `perplexity`, `chatgpt`, plus opt-in `openai`, `claude` |
| `--route` | Let the regex router pick engines and X search (social → Grok; lists/comparisons → all; live news → Grok + Perplexity; short factual question → Perplexity; else all) |
| `--fast` | Drop `chatgpt` from whatever set was chosen |
| `--x` / `--no-x` | Force Grok's X search on or off (default on, or the router's choice with `--route`) |
| `--recent` | Ask engines to prefer roughly the last two weeks and give dates |
| `--effort low\|medium\|high` | Reasoning effort for Grok, ChatGPT, OpenAI, Claude (defaults: Grok/OpenAI low, ChatGPT/Claude medium) |
| `--json` | Machine-readable output |
| `route "query"` | Print the router's decision as JSON and exit |

The router is a handful of regexes in `scripts/lib/route.js`, so an agent can predict where a query will go.

## Setup

Needs Node 18+. No `npm install` for the default engines. Credentials come from the environment; the script also loads `~/.env` (or the file in `WIDE_SEARCH_ENV_FILE`) without overriding variables already set.

| Engine | What it calls | Auth |
|---|---|---|
| `grok` | xAI Responses API with `web_search` + `x_search` | `XAI_API_KEY`, or (optional fallback) an xAI OAuth login stored by the [pi](https://github.com/earendil-works/pi) coding agent in `~/.pi/agent/auth.json` (`PI_AUTH_PATH` overrides) |
| `perplexity` | Perplexity `sonar-pro` chat completions | `PERPLEXITY_API_KEY` |
| `chatgpt` | `codex --search exec` (read-only sandbox, ephemeral) | The Codex CLI, logged in with `codex login`. Billed to your ChatGPT plan, not the API. Found via `CODEX_BIN`, then `PATH`, then `~/.local/bin` and nvm installs |
| `openai` (opt-in) | OpenAI Responses API with `web_search` | `OPENAI_API_KEY` (paid API) |
| `claude` (opt-in) | Anthropic Messages API with the web search tool | `ANTHROPIC_API_KEY` and `npm install` in `scripts/` (paid API) |

An engine whose credentials are missing is **skipped** with a note saying what's missing; the others still run. An engine that errors shows `FAILED` with the error. The command exits non-zero only if every engine fails or is skipped.

**About the pi OAuth fallback:** xAI rotates the refresh token on every refresh, so two processes refreshing with the same token kill the login. `scripts/lib/xai-oauth.mjs` takes pi's own lock (the `auth.json.lock` directory), re-reads the file, and refreshes only if nobody else just did. That matters here because a wide search can fire several Grok calls at once. It also works standalone: `node scripts/lib/xai-oauth.mjs status|token|keepwarm`.

Model defaults live in `DEFAULT_MODELS` in `scripts/lib/providers.js`; override any of them with `WIDE_SEARCH_MODEL_<ENGINE>` (e.g. `WIDE_SEARCH_MODEL_GROK=grok-4`).

## Cost and latency

- **Latency** is the slowest engine you picked. Perplexity usually answers in a few seconds to ~15s, Grok in ~10–60s, ChatGPT via Codex in ~20–90s. `--fast` drops ChatGPT. Per-engine timeout is 10 minutes.
- **Cost** per query is small for the defaults: a Perplexity `sonar-pro` request plus Grok tokens and search calls on your xAI account (or your plan, with the OAuth login), and ChatGPT counts against your ChatGPT plan's Codex usage. The opt-in API engines cost more; Claude with web search ran about $0.75 per query in our use.
- `--route` is the cheap default for agents that search often: it sends one-line facts to Perplexity alone and saves the full fan-out for queries that need coverage.

## Files

```
scripts/
├── wide-search.mjs     # CLI: args, fan-out, source merge, output
├── package.json        # optional dep for the claude engine only
└── lib/
    ├── env.js          # ~/.env loader
    ├── providers.js    # one function per engine + credential checks
    ├── route.js        # regex router
    └── xai-oauth.mjs   # optional pi OAuth token with locked refresh
```

`providers.js` exports `runEngine(name, { system, prompt, model?, effort?, x? })` if you want a single engine from your own script.
