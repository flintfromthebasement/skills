// Reference implementation of the exact + symbol lanes and the merge for hybrid code search.
// No dependencies. Plug in your own ripgrep runner, symbol table builder, and semantic lane.
//
// Result shape every lane returns (semantic results included):
//   { repo, path, start_line, end_line, match_line?, content, symbols, kind, match: 'exact'|'symbol'|'semantic', rank? }
// start_line/end_line span `content`; match_line is the line that matched (exact/symbol only).

// ---- Stack-specific patterns: edit these for your language/framework ----------------------------

// Calls that fire a hook/event by name (WordPress shown; add emit(, dispatch(, trigger( ... for yours).
export const FIRES = ['do_action', 'do_action_ref_array', 'apply_filters', 'apply_filters_ref_array'];
// Calls that listen to a hook/event by name.
export const LISTENS = ['add_action', 'add_filter', 'remove_action', 'remove_filter', 'has_action', 'has_filter'];
// Keywords that define a named symbol.
export const DEFINES = ['function', 'class', 'interface', 'trait', 'enum'];
// Name prefix your project puts on everything; stripped when normalizing so "change membership level" matches pmpro_changeMembershipLevel.
export const PROJECT_PREFIX = /^pmpro/;
// Primary repo; its hits sort first within a rank.
export const CORE_REPO = 'paid-memberships-pro';

// ---- Identifier extraction ----------------------------------------------------------------------

// snake_case (needs an underscore), CamelCase (MemberOrder, PMPro_Field), lowerCamel (hasMembershipLevel). Max 3.
export function extractIdentifiers(query) {
  const words = String(query).match(/[A-Za-z_][A-Za-z0-9_]*/g) || [];
  const ids = words.filter(
    (w) => (w.length >= 5 && /[a-z0-9]_[a-z0-9]/i.test(w)) || /^[A-Z][a-z0-9]+[A-Z_]/.test(w) || (w.length >= 8 && /^[a-z]+[A-Z]/.test(w)),
  );
  return [...new Set(ids)].slice(0, 3);
}

// ---- Exact lane: classify ripgrep hits ----------------------------------------------------------
// Run: rg -n --no-heading --with-filename -F -w -e <id1> -e <id2> -- <repo dirs>, then classify each line.

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const alt = (list) => list.map(escapeRe).join('|');

// rank 0 fires, 1 defines, 3 listens, 4 references (2 is reserved for strong symbol-lane matches).
export function classifyLine(text, ids) {
  for (const id of ids) {
    if (new RegExp(`\\b(${alt(FIRES)})\\s*\\(\\s*['"]${escapeRe(id)}['"]`).test(text)) return { kind: 'fires', id, rank: 0 };
  }
  for (const id of ids) {
    if (new RegExp(`\\b(${alt(DEFINES)})\\s+&?${escapeRe(id)}\\b`).test(text)) return { kind: 'defines', id, rank: 1 };
  }
  for (const id of ids) {
    if (new RegExp(`\\b(${alt(LISTENS)})\\s*\\(\\s*['"]${escapeRe(id)}['"]`).test(text)) return { kind: 'hooks', id, rank: 3 };
  }
  const id = ids.find((i) => new RegExp(`\\b${escapeRe(i)}\\b`).test(text)) || ids[0];
  return { kind: 'references', id, rank: 4 };
}

// ---- Symbol lane ---------------------------------------------------------------------------------
// Build `table` once an hour: Map(normalize(name) -> [{ path, line, name, kind: 'fires'|'defines' }]),
// from one ripgrep pass for definitions and fired hook names. SORT each list (fires, core repo, path, line):
// ripgrep's multithreaded output order changes run to run.

export const normalize = (name) => name.toLowerCase().replace(/_/g, '').replace(PROJECT_PREFIX, '');
const STOPWORDS = new Set('a an and are as at be by can do does for from how i if in into is it of on or the their them they this to under use user users we what when where which while who why with'.split(' '));
const stem = (w) => (w.length > 4 && w.endsWith('s') && !w.endsWith('ss') ? w.slice(0, -1) : w);

function editDistanceWithin(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return false;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    let best = i;
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      best = Math.min(best, cur[j]);
    }
    if (best > max) return false;
    prev = cur;
  }
  return prev[b.length] <= max;
}

// Names the query points at without spelling exactly. weight >= 3 is strong evidence; 2 (two plain words) is weak.
export function symbolCandidates(query, table) {
  const found = new Map();
  const add = (norm, why, weight) => {
    if (table.has(norm) && !(found.get(norm)?.weight >= weight)) found.set(norm, { norm, why, weight });
  };
  for (const id of extractIdentifiers(query)) {
    const n = normalize(id);
    if (n.length < 6) continue;
    for (const k of table.keys()) {
      if (k === n) add(k, `name: ${id}`, 4);
      else if (k.endsWith(n) && k.length - n.length <= 12) add(k, `partial: ${id}`, 3);
      else if (editDistanceWithin(k, n, n.length >= 12 ? 2 : 1)) add(k, `near: ${id}`, 3);
    }
  }
  const words = (String(query).toLowerCase().match(/[a-z0-9]+/g) || []).filter((w) => !STOPWORDS.has(w)).map(stem);
  for (let size = Math.min(5, words.length); size >= 2; size--) {
    for (let i = 0; i + size <= words.length; i++) {
      const joined = words.slice(i, i + size).join('').replace(PROJECT_PREFIX, '');
      if (joined.length < 8) continue;
      add(joined, `words: ${words.slice(i, i + size).join(' ')}`, size);
      add(`${joined}s`, `words: ${words.slice(i, i + size).join(' ')}`, size);
    }
  }
  return [...found.values()].sort((a, b) => b.weight - a.weight).slice(0, 4);
}

// Turns candidates into ranked hits: at most two sites per symbol lead; the rest go to the tail.
export function symbolHits(query, table, lineHit) {
  const hits = [];
  for (const c of symbolCandidates(query, table)) {
    for (const [i, s] of table.get(c.norm).slice(0, 6).entries()) {
      const rank = i >= 2 ? 4 : c.weight >= 3 ? 2 : 3;
      hits.push(lineHit({ path: s.path, line: s.line, symbols: `${s.kind}: ${s.name} (${c.why})`, kind: `symbol:${s.kind}`, match: 'symbol', rank }));
    }
  }
  return hits;
}

// ---- Merge ---------------------------------------------------------------------------------------

// exact/symbol hits with rank <= 2 lead (core repo first), then semantic and the remaining lexical hits interleave.
export function mergeResults(lexical, semantic, cap) {
  const core = (r) => (r.repo === CORE_REPO ? 0 : 1);
  const sorted = [...lexical].sort((a, b) => a.rank - b.rank || core(a) - core(b));
  const top = sorted.filter((r) => r.rank <= 2);
  const rest = sorted.filter((r) => r.rank > 2);
  const out = [];
  const seen = new Set();
  const push = (r) => {
    const k = `${r.path}:${r.match_line ?? r.start_line}`;
    if (out.length < cap && !seen.has(k)) (seen.add(k), out.push(r));
  };
  top.forEach(push);
  let i = 0;
  let j = 0;
  let semanticTurn = true;
  while (out.length < cap && (i < semantic.length || j < rest.length)) {
    push((semanticTurn && i < semantic.length) || j >= rest.length ? semantic[i++] : rest[j++]);
    semanticTurn = !semanticTurn;
  }
  return out.map(({ rank, ...r }) => r);
}

// ---- Helper: a line hit with an excerpt that keeps the start_line/content contract ----------------

export function makeLineHit(readLines, repoOf = (p) => p.split('/')[0]) {
  return ({ path, line, symbols, kind, match, rank }) => {
    const start = Math.max(1, line - 3);
    const lines = readLines(path).slice(start - 1, line + 3);
    return { repo: repoOf(path), path, start_line: start, end_line: start + Math.max(0, lines.length - 1), match_line: line, symbols, kind, score: 1, content: lines.join('\n'), match, rank };
  };
}
