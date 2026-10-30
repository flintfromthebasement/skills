import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { getXaiOAuthToken, hasXaiOAuthLogin } from './xai-oauth.mjs';

const TIMEOUT_MS = 600000;

// Override any model with WIDE_SEARCH_MODEL_<ENGINE>, e.g. WIDE_SEARCH_MODEL_GROK=grok-4.
const env = (name, fallback) => process.env[`WIDE_SEARCH_MODEL_${name.toUpperCase()}`] || fallback;
export const DEFAULT_MODELS = {
  grok: env('grok', 'grok-4.5'),
  perplexity: env('perplexity', 'sonar-pro'),
  chatgpt: env('chatgpt', 'gpt-6.1-sol'),
  openai: env('openai', 'gpt-6.1-sol'),
  claude: env('claude', 'claude-opus-5-5'),
};

// XAI_API_KEY first; otherwise an optional pi xAI OAuth login, refreshed under pi's lock so parallel searches can't burn the rotating refresh token.
async function grokToken() {
  if (process.env.XAI_API_KEY?.trim()) return process.env.XAI_API_KEY.trim();
  const pi = await getXaiOAuthToken();
  if (!pi) throw new Error('No xAI auth (set XAI_API_KEY or log in to xAI with pi)');
  return pi.token;
}

async function postJson(url, headers, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const raw = await res.text();
  let data;
  try { data = JSON.parse(raw); } catch { throw new Error(`HTTP ${res.status}: ${raw.slice(0, 300)}`); }
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${data?.error?.message || raw.slice(0, 300)}`);
  return data;
}

function addCite(map, url, title = '') {
  if (typeof url !== 'string' || !/^https?:/.test(url) || map.has(url)) return;
  map.set(url, { url, title: title || '' });
}

// Collects output_text and url citations from an OpenAI/xAI Responses API payload.
function readResponses(data) {
  const texts = [];
  const cites = new Map();
  const walk = (node) => {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) return node.forEach(walk);
    if (node.type === 'output_text' && node.text) texts.push(node.text);
    if (node.url) addCite(cites, node.url, node.title);
    for (const [k, v] of Object.entries(node)) if (k !== 'reasoning' && typeof v === 'object') walk(v);
  };
  walk(data.output);
  for (const c of data.citations || []) addCite(cites, typeof c === 'string' ? c : c?.url, c?.title);
  return { text: texts.join('\n').trim(), citations: [...cites.values()] };
}

async function grok({ system, prompt, model, effort = 'low', x = true }) {
  const tools = [{ type: 'web_search' }];
  if (x) tools.push({ type: 'x_search' });
  const data = await postJson('https://api.x.ai/v1/responses', { Authorization: `Bearer ${await grokToken()}` }, {
    model,
    input: [{ role: 'system', content: system }, { role: 'user', content: prompt }],
    tools,
    reasoning: { effort },
  });
  return { ...readResponses(data), usage: data.usage };
}

async function openai({ system, prompt, model, effort = 'low' }) {
  const data = await postJson('https://api.openai.com/v1/responses', { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` }, {
    model,
    instructions: system,
    input: prompt,
    tools: [{ type: 'web_search' }],
    include: ['web_search_call.action.sources'],
    reasoning: { effort },
  });
  return { ...readResponses(data), usage: data.usage };
}

async function perplexity({ system, prompt, model }) {
  const data = await postJson('https://api.perplexity.ai/chat/completions', { Authorization: `Bearer ${process.env.PERPLEXITY_API_KEY}` }, {
    model,
    messages: [{ role: 'system', content: system }, { role: 'user', content: prompt }],
  });
  const cites = new Map();
  for (const r of data.search_results || []) addCite(cites, r.url, r.title);
  for (const c of data.citations || []) addCite(cites, c);
  return { text: data.choices?.[0]?.message?.content || '', citations: [...cites.values()], usage: data.usage };
}

function onPath(name) {
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    const bin = path.join(dir, name);
    try { fs.accessSync(bin, fs.constants.X_OK); return bin; } catch {}
  }
  return null;
}

// CODEX_BIN, then codex on PATH, then common install spots (~/.local/bin, nvm) so it also works under cron's bare PATH.
function codexCommand() {
  if (process.env.CODEX_BIN) return { bin: process.env.CODEX_BIN, env: process.env };
  const found = onPath('codex');
  if (found) return { bin: found, env: process.env };
  const local = path.join(os.homedir(), '.local', 'bin', 'codex');
  if (fs.existsSync(local)) return { bin: local, env: process.env };
  const root = path.join(os.homedir(), '.nvm', 'versions', 'node');
  const versions = fs.existsSync(root) ? fs.readdirSync(root).sort().reverse() : [];
  for (const v of versions) {
    const bin = path.join(root, v, 'bin', 'codex');
    if (fs.existsSync(bin)) return { bin, env: { ...process.env, PATH: `${path.dirname(bin)}:${process.env.PATH || '/usr/bin:/bin'}` } };
  }
  return null;
}

// ChatGPT web search through the Codex CLI, billed to the ChatGPT plan rather than the API.
async function chatgpt({ system, prompt, model, effort = 'medium' }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wide-search-codex-'));
  const outFile = path.join(dir, 'last.txt');
  const full = `${system}\n\nUse live web search only. Do not run shell commands or read local files.\n\n${prompt}`;
  const args = ['--search', 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-m', model,
    '-c', `model_reasoning_effort=${effort}`, '--json', '-o', outFile, full];
  try {
    const stdout = await new Promise((resolve, reject) => {
      const { bin, env } = codexCommand() || { bin: 'codex', env: process.env };
      const { OPENAI_API_KEY, ...childEnv } = env;
      const child = spawn(bin, args, { cwd: dir, env: childEnv, stdio: ['ignore', 'pipe', 'pipe'] });
      let out = '';
      let err = '';
      const timer = setTimeout(() => { child.kill('SIGTERM'); reject(new Error('codex timed out')); }, TIMEOUT_MS);
      child.stdout.on('data', (d) => { out += d; });
      child.stderr.on('data', (d) => { err += d; });
      child.on('error', (e) => { clearTimeout(timer); reject(e); });
      child.on('close', (code) => {
        clearTimeout(timer);
        if (code === 0) resolve(out);
        else reject(new Error(`codex exit ${code}: ${err.trim().split('\n').slice(-3).join(' ').slice(0, 300)}`));
      });
    });
    const cites = new Map();
    let usage = null;
    for (const line of stdout.split('\n')) {
      if (!line.trim()) continue;
      let ev;
      try { ev = JSON.parse(line); } catch { continue; }
      if (ev.type === 'item.completed' && ev.item?.type === 'web_search') for (const r of ev.item.results || []) addCite(cites, r.url, r.title);
      if (ev.type === 'turn.completed') usage = ev.usage;
    }
    const text = fs.existsSync(outFile) ? fs.readFileSync(outFile, 'utf8').trim() : '';
    return { text, citations: [...cites.values()], usage };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

async function claude({ system, prompt, model, effort = 'medium' }) {
  // Lazy so boxes without node_modules can still run the other engines.
  const { default: Anthropic } = await import('@anthropic-ai/sdk');
  const client = new Anthropic({ timeout: TIMEOUT_MS });
  const params = {
    model,
    max_tokens: 16000,
    system,
    tools: [{ type: 'web_search_20260209', name: 'web_search', max_uses: 8 }],
    output_config: { effort },
    betas: ['server-side-fallback-2026-07-01'],
    fallbacks: 'default',
  };
  const messages = [{ role: 'user', content: prompt }];
  const usage = { input_tokens: 0, output_tokens: 0, web_search_requests: 0 };
  let msg;
  for (let i = 0; i < 5; i++) {
    msg = await client.beta.messages.create({ ...params, messages });
    usage.input_tokens += msg.usage?.input_tokens || 0;
    usage.output_tokens += msg.usage?.output_tokens || 0;
    usage.web_search_requests += msg.usage?.server_tool_use?.web_search_requests || 0;
    if (msg.stop_reason !== 'pause_turn') break;
    messages.push({ role: 'assistant', content: msg.content });
  }
  if (msg.stop_reason === 'refusal') throw new Error(`refusal: ${msg.stop_details?.category || 'unknown'}`);
  const cites = new Map();
  const texts = [];
  for (const block of [...messages.filter((m) => m.role === 'assistant').flatMap((m) => m.content), ...msg.content]) {
    if (block.type === 'web_search_tool_result' && Array.isArray(block.content)) for (const r of block.content) addCite(cites, r.url, r.title);
  }
  for (const block of msg.content) {
    if (block.type !== 'text') continue;
    texts.push(block.text);
    for (const c of block.citations || []) addCite(cites, c.url, c.title);
  }
  return { text: texts.join('').trim(), citations: [...cites.values()], usage };
}

export const ENGINES = { grok, perplexity, chatgpt, openai, claude };

// Returns null when an engine has credentials, else a short reason it will be skipped.
export function missingAuth(name) {
  const has = (k) => Boolean(process.env[k]?.trim());
  if (name === 'grok') return has('XAI_API_KEY') || hasXaiOAuthLogin() ? null : 'no XAI_API_KEY and no pi xAI login';
  if (name === 'perplexity') return has('PERPLEXITY_API_KEY') ? null : 'no PERPLEXITY_API_KEY';
  if (name === 'openai') return has('OPENAI_API_KEY') ? null : 'no OPENAI_API_KEY';
  if (name === 'claude') return has('ANTHROPIC_API_KEY') ? null : 'no ANTHROPIC_API_KEY';
  if (name === 'chatgpt') return codexCommand() ? null : 'codex CLI not found (install it and run `codex login`, or set CODEX_BIN)';
  return null;
}

// Runs one engine; opts = { system, prompt, model?, effort?, x? }.
export async function runEngine(name, opts) {
  const fn = ENGINES[name];
  if (!fn) throw new Error(`Unknown engine ${name}`);
  const t0 = Date.now();
  const out = await fn({ ...opts, model: opts.model || DEFAULT_MODELS[name] });
  return { ...out, ms: Date.now() - t0 };
}
