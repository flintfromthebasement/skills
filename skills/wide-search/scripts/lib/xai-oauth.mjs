#!/usr/bin/env node
/**
 * xai-oauth.mjs — optional fallback: a locked refresh path for the xAI (Grok) OAuth token in pi's auth.json.
 * Only used when XAI_API_KEY is unset and you've logged in to xAI with the pi coding agent.
 *
 * xAI rotates the refresh token on every refresh, so two processes refreshing with the same
 * token kill the login. Every refresher takes pi's own lock (proper-lockfile's `auth.json.lock`
 * directory), re-reads the file, and only refreshes if nobody else just did.
 *
 *   import { getXaiOAuthToken } from './lib/xai-oauth.mjs';
 *   const { token } = await getXaiOAuthToken();          // null when there's no pi xAI login
 *
 *   node xai-oauth.mjs token [--min-valid MIN]            # print a token valid for MIN minutes
 *   node xai-oauth.mjs keepwarm [--min-valid MIN]         # refresh if under MIN (default 120)
 *   node xai-oauth.mjs status                             # JSON: key, minutes left
 *
 * Auth path: PI_AUTH_PATH or ~/.pi/agent/auth.json. Keys: grok-build (pi-xai <=0.15) or xai.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const XAI_TOKEN_URL = process.env.XAI_OAUTH_TOKEN_URL || 'https://auth.x.ai/oauth2/token';
const XAI_CLIENT_ID = 'b1a00492-073a-47ea-816f-4c329264a828';
const KEYS = ['grok-build', 'xai'];
// Stored `expires` is the real expiry minus an hour, same as pi-xai.
const STORED_EXPIRY_SKEW_MS = 60 * 60 * 1000;
// proper-lockfile defaults: a lock untouched for 10s is stale.
const LOCK_STALE_MS = 10_000;
const LOCK_WAIT_MS = 60_000;

export function piAuthPath() {
  return process.env.PI_AUTH_PATH || path.join(os.homedir(), '.pi', 'agent', 'auth.json');
}

function readAuth(authPath) {
  return JSON.parse(fs.readFileSync(authPath, 'utf8'));
}

function findEntry(auth) {
  const key = KEYS.find((k) => auth?.[k]?.access || auth?.[k]?.key);
  return key ? { key, entry: auth[key] } : null;
}

function writeAuth(authPath, auth) {
  const tmp = `${authPath}.tmp-${process.pid}`;
  fs.writeFileSync(tmp, `${JSON.stringify(auth, null, 2)}\n`, { mode: 0o600 });
  fs.renameSync(tmp, authPath);
}

function relogin(authPath, key) {
  return `re-login: run pi, then /login ${key} (${authPath})`;
}

async function withAuthLock(authPath, fn) {
  const lockPath = `${authPath}.lock`;
  const deadline = Date.now() + LOCK_WAIT_MS;
  for (;;) {
    try {
      fs.mkdirSync(lockPath);
      break;
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      try {
        if (Date.now() - fs.statSync(lockPath).mtimeMs > LOCK_STALE_MS) {
          fs.rmdirSync(lockPath);
          continue;
        }
      } catch {}
      if (Date.now() > deadline) throw new Error(`timed out waiting for ${lockPath}`);
      await new Promise((resolve) => setTimeout(resolve, 150 + Math.random() * 250));
    }
  }
  // Keep the lock fresh so pi doesn't treat it as stale during a slow refresh.
  const touch = setInterval(() => {
    try {
      const now = new Date();
      fs.utimesSync(lockPath, now, now);
    } catch {}
  }, LOCK_STALE_MS / 2);
  try {
    return await fn();
  } finally {
    clearInterval(touch);
    try {
      fs.rmdirSync(lockPath);
    } catch {}
  }
}

async function refresh(refreshToken) {
  const res = await fetch(XAI_TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'refresh_token', client_id: XAI_CLIENT_ID, refresh_token: refreshToken }),
    signal: AbortSignal.timeout(30_000),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw Object.assign(new Error(`xAI token refresh failed (${res.status}) ${text.slice(0, 160)}`.trim()), { status: res.status });
  }
  const data = await res.json();
  if (!data?.access_token) throw new Error('xAI token refresh returned no access_token');
  return data;
}

function fresh(entry, minValidMs) {
  if (entry.type === 'api_key' || !entry.expires) return true;
  return Number(entry.expires) - Date.now() > minValidMs;
}

// True when pi's auth.json holds an xAI login (no network, no refresh).
export function hasXaiOAuthLogin(authPath = piAuthPath()) {
  try { return Boolean(findEntry(readAuth(authPath))); } catch { return false; }
}

/**
 * Returns { token, key, expires, refreshed } or null when there's no pi xAI login.
 * Throws when the token needs a refresh and xAI rejects it (dead login).
 */
export async function getXaiOAuthToken({ authPath = piAuthPath(), minValidMs = 5 * 60 * 1000 } = {}) {
  if (!fs.existsSync(authPath)) return null;
  const found = findEntry(readAuth(authPath));
  if (!found) return null;
  const tokenOf = ({ key, entry }, refreshed) => ({
    token: entry.type === 'api_key' ? entry.key : entry.access,
    key,
    expires: entry.expires ? Number(entry.expires) : null,
    refreshed,
  });
  if (fresh(found.entry, minValidMs)) return tokenOf(found, false);

  return withAuthLock(authPath, async () => {
    // Another process may have refreshed while we waited for the lock.
    const auth = readAuth(authPath);
    const current = findEntry(auth);
    if (!current) return null;
    if (fresh(current.entry, minValidMs)) return tokenOf(current, false);
    if (!current.entry.refresh) throw new Error(`xAI token expired with no refresh token; ${relogin(authPath, current.key)}`);
    let data;
    try {
      data = await refresh(current.entry.refresh);
    } catch (error) {
      if (error.status === 400 || error.status === 401) error.message += `; ${relogin(authPath, current.key)}`;
      throw error;
    }
    auth[current.key] = {
      ...current.entry,
      type: 'oauth',
      access: data.access_token,
      refresh: data.refresh_token || current.entry.refresh,
      expires: Date.now() + (data.expires_in || 3600) * 1000 - STORED_EXPIRY_SKEW_MS,
    };
    writeAuth(authPath, auth);
    return tokenOf({ key: current.key, entry: auth[current.key] }, true);
  });
}

async function main(argv) {
  const [cmd, ...rest] = argv;
  const i = rest.indexOf('--min-valid');
  const minValidMin = i >= 0 ? Number(rest[i + 1]) : cmd === 'keepwarm' ? 120 : 5;
  const authPath = piAuthPath();
  if (cmd === 'status') {
    const found = fs.existsSync(authPath) ? findEntry(readAuth(authPath)) : null;
    const left = found?.entry.expires ? Math.round((Number(found.entry.expires) - Date.now()) / 60000) : null;
    console.log(JSON.stringify({ authPath, key: found?.key ?? null, minutes_left: left }));
    return;
  }
  if (cmd !== 'token' && cmd !== 'keepwarm') {
    console.error('Usage: xai-oauth.mjs token|keepwarm|status [--min-valid MIN]');
    process.exit(2);
  }
  const result = await getXaiOAuthToken({ authPath, minValidMs: minValidMin * 60 * 1000 });
  if (!result) {
    console.error(`No pi xAI login in ${authPath}`);
    process.exit(3);
  }
  if (cmd === 'token') {
    process.stdout.write(`${result.token}\n`);
    return;
  }
  const left = result.expires ? Math.round((result.expires - Date.now()) / 60000) : null;
  console.log(`${result.key}: ${result.refreshed ? 'refreshed' : 'ok'}, ${left ?? '∞'} min left`);
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
}
