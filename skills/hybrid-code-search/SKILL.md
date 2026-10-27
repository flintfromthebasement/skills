---
name: hybrid-code-search
description: Build (and teach agents to use) a hosted hybrid search over a codebase and its docs — exact identifier, fuzzy symbol, and embedding lanes merged into one ranked list, served over HTTP + MCP with per-person tokens and a nightly incremental index. Use when agents need to answer questions about code or docs they don't have checked out, when grep-only or embeddings-only search keeps missing, or when choosing an embedding model for code. Ships an eval method, a model bake-off result, and dependency-free reference code for the lanes and merge.
---

# Hybrid Code Search

A recipe for giving agents (and teammates) one search tool over a pile of repos and docs, without everyone cloning everything or running their own indexes. It came out of building the team search for Paid Memberships Pro (one core plugin plus ~140 Add On repos and ~1,600 doc pages). Everything here is general; swap in your own sources.

**The one-line lesson:** neither grep nor embeddings works alone. On 40 known-answer questions about our PHP codebase:

| Search | answer in top 8 |
|---|---|
| grep (the way an agent uses it) | 2 / 40 |
| embeddings only (doc-comment symbols, text-embedding-3-small) | 24 / 40 inside hybrid, 13 / 32 natural-language alone |
| **hybrid: exact + symbol + function-level gemini-embedding-2** | **37 / 40** |

Grep wins only when the user already knows the exact string. Embeddings alone turn "where does `pmpro_after_checkout` fire?" into a whole function that merely *looks* related and never return the one `do_action` line. Hybrid does both.

## When to use

- Agents answer technical questions about code they don't have locally (support, docs writers, customer bots, other teams).
- You have many repos and want one tool instead of "clone X, then grep."
- Your current search is grep-only (can't answer "where do we handle refunds?") or embeddings-only (can't find an exact hook or function name).
- You're picking an embedding model for code and want to measure instead of trusting vendor charts.

If you only have one repo and the agent already has it checked out, plain `rg` plus a good CLAUDE.md is usually enough. Build this when the corpus is bigger than one checkout or the askers don't have the code.

## Architecture

```
            query
              │
   ┌──────────┼───────────────┐
   ▼          ▼               ▼
 exact      symbol         semantic
 (ripgrep)  (name table)   (function vectors)
   │          │               │
   └──── merge + rank ────────┘
              │
   results: path, line range, excerpt, match type
              │
   HTTP /code/search · /docs/search · MCP /mcp (bearer token)
```

### Code: three lanes

1. **Exact lane.** Pull identifier-looking terms out of the query (`snake_case` with an underscore, `CamelCase`, `lowerCamel`), run `rg -F -w` for them over the indexed repos, and classify each hit line. Rank: where a hook/event **fires** (`do_action`, `apply_filters`, `emit(`, `dispatch(` — whatever your stack uses) → where a name is **defined** (`function`, `class`, `def`) → **listeners** (`add_action`, `.on(`) → plain references. Core/primary repo first within a rank.
2. **Symbol lane.** Keep an in-memory table of every defined function/class and every fired hook name (rebuild hourly). Match the query against it for things grep can't do:
   - typos — edit distance ≤ 1–2 (`pmpro_after_chekout` → `pmpro_after_checkout`)
   - partial names — normalized suffix match (`hasMembershipLevel` → `pmpro_hasMembershipLevel`)
   - plain words — runs of 2–5 query words, stopwords dropped and stemmed, joined and compared to normalized names (`change membership level` → `pmpro_changeMembershipLevel`)
3. **Semantic lane.** Embedding search over **every function/method** (not just documented ones). This answers behavior questions ("redirect members after they log in").

**Merge:** exact fires/defines and strong symbol matches lead (cap at ~2 sites per symbol so one hook fired from five places doesn't eat the page), then interleave semantic results with the remaining exact/symbol hits, dedupe by `path:line`. Label every result with `match: exact | symbol | semantic` and a `kind` (`exact:fires`, `exact:defines`, …) so the calling model knows what it's looking at.

Reference implementation of the identifier extraction, symbol matching, line classification, and merge: [`reference/lanes.mjs`](reference/lanes.mjs) (no dependencies).

### Docs: two lanes

Docs are easier: SQLite FTS5 (BM25) plus vectors over ~1,400-char section chunks, fused with Reciprocal Rank Fusion (k = 60). Offer `mode: hybrid | fts | vector` so an agent can force keyword match for an exact hook name.

## Chunking code

One chunk per function/method:

```
// <repo>/<path>
// <Class>::<method>
/** docblock, if any */
function body… (truncate ~2,000 chars)
```

- The path and symbol header lines matter more than you'd think — they're the strongest signal for many questions. The symbol line doubles as the document title for models that take one.
- **Embed everything.** Our original index (codanna) only embedded symbols with doc comments — 18.7k of 79.9k — so half the codebase was invisible to the semantic lane regardless of model. Fixing coverage and the model together took natural-language MRR from 0.22 to 0.78.
- Skip `vendor/`, `node_modules/`, generated and minified files. Bundled SDKs (Stripe, Braintree, Action Scheduler) are real noise; leave them in only if people ask about them.
- Use a brace/indent matcher that skips strings and comments, or a real parser (tree-sitter) if you have one. Regex-only start detection is fine.

## Picking an embedding model: measure, don't guess

Vendor benchmarks (MTEB-Code, CoIR) disagreed with our results. Build a known-answer set and run a bake-off; it costs a few dollars.

Our PHP/WordPress results (27,876 function chunks, 32 natural-language questions + 8 exact/fuzzy, October 2026):

| Model | $/M tokens | NL right answer #1 (/32) | NL in top 8 | hybrid top 8 (/40) | NL MRR |
|---|---|---|---|---|---|
| **gemini-embedding-2 @768** | 0.20 | **22** | 30 | 38 | **0.78** |
| gemini-embedding-2 @3072 | 0.20 | 20 | 30 | 38 | 0.75 |
| gemini-embedding-001 | 0.15 | 18 | 29 | 37 | 0.69 |
| gemini-embedding-2, `taskType` instead of prefixes | 0.20 | 13 | 30 | 39 | 0.60 |
| codestral-embed | 0.15 | 17 | 29 | 36 | 0.63 |
| voyage-4 | 0.06 | 14 | 32 | 39 | 0.62 |
| voyage-code-4 | 0.12 | 12 | 27 | 35 | 0.56 |
| qwen3-embedding-8b | 0.01 | 10 | 27 | 34 | 0.55 |
| nemotron-3.5-embed-8b | free | 12 | 26 | 34 | 0.53 |
| EmbeddingGemma 2 (local, 768) | GPU | 10 | 17 | 27 | 0.38 |
| text-embedding-3-large | 0.13 | 5 | 20 | 29 | 0.34 |
| text-embedding-3-small | 0.02 | 5 | 19 | 27 | 0.32 |
| old index (doc-comment symbols only, 3-small) | — | 4 | 13 | 24 | 0.22 |

Takeaways that probably generalize:

- **Gemini Embedding 2 led**, and truncating to **768 dims** (Matryoshka) cost nothing — a quarter of the storage (~86 MB for 28k vectors) at equal or better quality.
- **gemini-embedding-2 ignores `taskType`** — sending it anyway dropped MRR from 0.78 to 0.60. It wants text prefixes: query `task: code retrieval | query: {q}`, document `title: {symbol} | text: {code}`. `gemini-embedding-001` still uses `taskType: CODE_RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT`.
- Code-specialized ≠ better on your code: voyage-code-4 scored below general voyage-4 here.
- OpenAI's text-embedding-3 models were last on PHP. Fine for prose docs, weak for code.
- Your stack may differ. Re-run the bake-off on your own corpus; 40 cases separate big gaps (Gemini vs OpenAI), not small ones (Gemini vs Voyage).

Operational notes from the bake-off:

- OpenRouter's `/api/v1/embeddings` serves most hosted models (Voyage, Gemini, Codestral, Qwen3, OpenAI, NVIDIA) behind one key; Voyage's `input_type` passes through. Use the Gemini API directly when you need its task types or quotas.
- Gemini paid tier 2 allows **5,000 embeddings per minute per model per project** (a 100-text batch counts as 100). Pace bulk jobs at ~4,000/min.
- NVIDIA's nemotron-3.5-embed is a vision-language embedder: a `data:image/...;base64` string in your code gets parsed as an image and the request 422s. Defang those strings.
- Local option: EmbeddingGemma 2 (Google, Apache-2.0, 768 dims) runs on a consumer GPU via sentence-transformers (needs a recent `transformers` and `torchvision` even for text), but it scored well below the hosted models here. Google's hosted model is the strong one; its small local one is not.

## The eval (do this first)

A known-answer set beats any leaderboard:

```js
{ group: 'natural', query: 'redirect members after they log in',
  file: 'core-plugin/includes/login.php', re: /function pmpro_login_redirect\b/ }
```

- **30–40 cases minimum**, mostly natural-language, phrased the way a user asks — paraphrase, never copy the docblock. Add a handful of exact-identifier and typo/partial cases.
- Ground truth is **file + a regex for the answering line**, located at runtime, so it survives code drift.
- Score a hit when the result is the right file **and its excerpt contains a line matching the regex** — not by line number. Indexes on different machines drift by a few lines.
- Report hit@1, hit@3, hit@8 and MRR, split by group. Score each semantic model **alone and inside the full hybrid**; the hybrid number is what users feel.
- Include the baseline your agents use today (usually grep with the query as the pattern).
- Re-run after every change. Our first hybrid cut regressed a case from #1 to #8 because two-word symbol matches flooded the top; only the eval caught it.

## Serving it

A small HTTP service is enough:

| Method | Path | Body |
|---|---|---|
| `GET` | `/health` | index stats (counts, model, last build) |
| `POST` | `/code/search` | `{ query, repo?, limit? }` |
| `POST` | `/docs/search` | `{ query, mode?, type?, limit? }` |
| `POST` | `/mcp` | MCP Streamable-HTTP: `initialize`, `tools/list`, `tools/call` |

- **Auth:** per-person bearer tokens, stored as SHA-256 hashes, shown once at mint, revocable by id, rate-limited per token. If some users may only see public code, give tokens a scope and filter results to an allowlist of repos — in every lane, including the exact and symbol lanes.
- **Result contract:** `start_line`/`end_line` must span the `content` excerpt (clients number lines from `start_line`); add a separate `match_line` for exact/symbol hits. Breaking this silently mis-numbers every excerpt downstream.
- **Semantic lane at query time:** hold the matrix in memory (brute-force dot product over ~30k × 768 floats is a few ms), embed the query with a short timeout and one retry, and **fall back** to an older lane (or exact-only) when the embedding API is down. One warn line per fallback.
- **Nightly sync:** pull the repos, re-chunk, hash each chunk's text, re-embed only new/changed hashes, write the whole set in one transaction, stamp `built_at`. The server reloads when the stamp changes. A no-change night costs nothing; a full rebuild of ~28k functions is ~7 minutes and ~$1.40 on gemini-embedding-2.
- **Distribution:** for Claude Code, a plugin that bundles the remote MCP (token as a sensitive user-config value, not plaintext in settings) plus a usage skill is the least-friction install. Otherwise `claude mcp add <name> -s user --transport http <url>/mcp --header "Authorization: Bearer <token>"`.

## Make the agent actually use it

Registering the tool isn't enough; models default to answering from memory.

1. **Tool descriptions explain the lanes and fields.** Say that exact names find where a hook fires, that typos and plain words resolve to symbols, and what `match`, `kind`, `match_line` mean. Tell the model to pass the identifier when it knows one — otherwise it clones repos to grep (we watched it happen).
2. **A CLAUDE.md / system-prompt rule:**

```markdown
## <Project> search tools
- `<project>_code_search` — exact names, fuzzy names, and behavior questions over all <project> repos
- `<project>_docs_search` — docs, hook reference, guides
Search before answering any <project> technical question; don't rely on training data.
Cite `path:match_line` (or `path:start_line`). If nothing comes back, say where you looked.
```

3. **Test it the way a new user will.** Run the exact example from your setup instructions against the live server before sending them out.

## Pitfalls we hit

- **Docblock-only embedding indexes** look healthy (thousands of vectors) while missing most of the code. Check `embedded symbols / total symbols`.
- **ripgrep output order is nondeterministic** (multithreaded). Sort anything you cache or rank from it, or results flip between runs.
- **One symbol fired from many sites** floods the top of the list; cap sites per symbol in the leading tier.
- **Hooks are both fired and defined**: a class method named like a hook (`static function pmpro_after_checkout`) must rank below the `do_action` line.
- **Grep tools take the query as a regex.** If you keep a grep tool alongside the hybrid one, append hybrid matches to its output instead of replacing it.
- **Ports between harnesses drop features.** Our chat bot's semantic mode vanished in a repo migration and nobody noticed for four months. Keep the eval in the repo and run it after moves.
