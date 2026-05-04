import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, '..');
const TRANSCRIPT_SCRIPT = path.join(SKILL_ROOT, 'scripts', 'fetch_transcript.py');
const PYTHON_CANDIDATES = ['python3', 'python'];

export function isYouTubeUrl(url) {
  return /(?:youtube\.com\/(?:watch|shorts)|youtu\.be\/)/i.test(url);
}

export function extractVideoId(url) {
  try {
    const u = new URL(url);
    if (u.hostname.includes('youtu.be')) {
      const id = u.pathname.replace(/^\//, '').split('/')[0];
      return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
    }
    if (u.pathname.startsWith('/shorts/')) {
      const id = u.pathname.split('/')[2] || '';
      return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
    }
    const v = u.searchParams.get('v');
    return v && /^[A-Za-z0-9_-]{11}$/.test(v) ? v : null;
  } catch {
    return null;
  }
}

function findPython() {
  for (const cmd of PYTHON_CANDIDATES) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf-8' });
    if (r.status === 0) return cmd;
  }
  throw new Error('No python3/python interpreter found on PATH');
}

export function fetchTranscript(videoId) {
  if (!existsSync(TRANSCRIPT_SCRIPT)) {
    throw new Error(`fetch_transcript.py missing at ${TRANSCRIPT_SCRIPT}`);
  }
  const python = findPython();
  const r = spawnSync(python, [TRANSCRIPT_SCRIPT, videoId], { encoding: 'utf-8', timeout: 60000 });
  if (!r.stdout) {
    throw new Error(`Transcript fetch produced no output (${r.error?.message || 'unknown error'})`);
  }
  let parsed;
  try {
    parsed = JSON.parse(r.stdout);
  } catch {
    throw new Error(`Transcript fetch produced non-JSON output: ${r.stdout.slice(0, 200)}`);
  }
  if (!parsed.success) {
    const err = new Error(`Transcript unavailable: ${parsed.error || 'unknown'}`);
    err.code = parsed.error || 'TRANSCRIPT_ERROR';
    throw err;
  }
  return (parsed.text || '').trim();
}

export async function fetchOembed(videoId) {
  const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
  try {
    const res = await fetch(oembedUrl, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) return { title: `YouTube ${videoId}`, author: 'YouTube' };
    const data = await res.json();
    return {
      title: data.title || `YouTube ${videoId}`,
      author: data.author_name || 'YouTube',
    };
  } catch {
    return { title: `YouTube ${videoId}`, author: 'YouTube' };
  }
}

export async function readYouTube(url) {
  const videoId = extractVideoId(url);
  if (!videoId) throw new Error(`Could not extract video ID from URL: ${url}`);
  const transcript = fetchTranscript(videoId);
  if (!transcript) throw new Error('Transcript fetch returned empty text');
  const meta = await fetchOembed(videoId);
  return {
    title: meta.title,
    byline: meta.author,
    source: meta.author,
    body: transcript,
    video_id: videoId,
  };
}
