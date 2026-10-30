import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Loads WIDE_SEARCH_ENV_FILE (default ~/.env) into process.env without overriding values already set.
export function loadEnv(file = process.env.WIDE_SEARCH_ENV_FILE || path.join(os.homedir(), '.env')) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, 'utf8').split('\n')) {
    const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!m || process.env[m[1]] !== undefined) continue;
    let v = m[2].trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    process.env[m[1]] = v;
  }
}
