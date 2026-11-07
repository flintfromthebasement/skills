import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { firecrawlConfigured, scrape } from './firecrawl.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, '..');
const TRANSCRIPT_SCRIPT = path.join(SKILL_ROOT, 'scripts', 'fetch_transcript.py');
const FIRECRAWL_ATTEMPTS = 3;

/** One cache key per video, whatever URL shape it arrived as. */
export function canonicalYouTubeUrl(url) {
  const id = extractVideoId(url);
  return id ? `https://www.youtube.com/watch?v=${id}` : url;
}

export function isYouTubeUrl(url) {
  return Boolean(extractVideoId(url));
}

export function extractVideoId(url) {
  const isId = (s) => /^[A-Za-z0-9_-]{11}$/.test(s);
  try {
    const u = new URL(url);
    if (u.hostname === 'youtu.be') {
      const id = u.pathname.replace(/^\//, '').split('/')[0];
      return isId(id) ? id : null;
    }
    if (!/(^|\.)youtube\.com$/i.test(u.hostname)) return null;
    if (/^\/(shorts|embed|live)\//.test(u.pathname)) {
      const id = u.pathname.split('/')[2] || '';
      return isId(id) ? id : null;
    }
    if (u.pathname !== '/watch') return null;
    const v = u.searchParams.get('v');
    return v && isId(v) ? v : null;
  } catch {
    return null;
  }
}

function findPython() {
  const candidates = [process.env.READ_PYTHON, 'python3', 'python'].filter(Boolean);
  for (const cmd of candidates) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf-8' });
    if (r.status === 0) return cmd;
  }
  return null;
}

/** Direct caption fetch via youtube-transcript-api. Throws with .code on any failure. */
function fetchTranscriptDirect(videoId) {
  const python = findPython();
  if (!python || !existsSync(TRANSCRIPT_SCRIPT)) {
    throw Object.assign(new Error('python3 not available for the direct transcript path'), { code: 'NO_PYTHON' });
  }
  const r = spawnSync(python, [TRANSCRIPT_SCRIPT, videoId], { encoding: 'utf-8', timeout: 60000 });
  const line = (r.stdout || '').trim().split('\n').pop();
  let parsed;
  try {
    parsed = JSON.parse(line || '');
  } catch {
    throw Object.assign(
      new Error(`Transcript fetch produced no usable output (${r.error?.message || r.stderr?.slice(0, 200) || 'unknown'})`),
      { code: 'TRANSCRIPT_ERROR' },
    );
  }
  if (!parsed.success || !parsed.text?.trim()) {
    throw Object.assign(new Error(`Transcript unavailable: ${parsed.error || 'empty'}`), {
      code: parsed.error && /^[A-Z_]+$/.test(parsed.error) ? parsed.error : 'TRANSCRIPT_ERROR',
    });
  }
  const duration = Number(parsed.duration);
  return { text: parsed.text.trim(), durationSeconds: duration > 0 ? duration : null, language: parsed.language || null };
}

/** Video length from a Firecrawl scrape: metadata.duration (ISO 8601), then the **Length** line. */
function scrapedDurationSeconds(markdown, metadata) {
  const iso =
    typeof metadata?.duration === 'string'
      ? /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$/i.exec(metadata.duration.trim())
      : null;
  if (iso && (iso[1] || iso[2] || iso[3])) {
    const s = Number(iso[1] || 0) * 3600 + Number(iso[2] || 0) * 60 + Number(iso[3] || 0);
    if (s > 0) return Math.round(s);
  }
  const line = markdown ? /^\*\*Length\*\*:\s*(\d{1,2}(?::\d{2}){1,2})\s*$/im.exec(markdown) : null;
  if (!line) return null;
  const s = line[1].split(':').reduce((t, p) => t * 60 + Number(p), 0);
  return s > 0 ? s : null;
}

function lastTimestampSeconds(text) {
  let last = null;
  for (const m of text.matchAll(/\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]/g)) {
    last = m[3] !== undefined ? +m[1] * 3600 + +m[2] * 60 + +m[3] : +m[1] * 60 + +m[2];
  }
  return last;
}

function extractTranscriptFromMarkdown(markdown) {
  const match = /^##\s+Transcript\s*$/im.exec(markdown || '');
  if (!match) return null;
  const after = markdown.slice(match.index + match[0].length);
  const text = after
    .replace(/\[\d{1,2}:\d{2}(?::\d{2})?\]\s*/g, '')
    .replace(/\r\n?/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return text ? { text, durationSeconds: lastTimestampSeconds(after) } : null;
}

/**
 * Firecrawl fallback. YouTube intermittently serves it an "Error 401" shell with no
 * transcript; stealth proxy + waitFor + uncached retries get captions most tries.
 */
async function fetchTranscriptViaFirecrawl(videoId) {
  const watchUrl = `https://www.youtube.com/watch?v=${videoId}`;
  let durationSeconds = null;
  let sawRealPage = false;
  let lastErr = null;
  for (let attempt = 1; attempt <= FIRECRAWL_ATTEMPTS; attempt++) {
    let scraped;
    try {
      scraped = await scrape(watchUrl, {
        formats: ['markdown'],
        onlyMainContent: true,
        proxy: 'stealth',
        waitFor: 5000,
        maxAge: 0,
      });
    } catch (e) {
      lastErr = e;
      continue;
    }
    const md = scraped.markdown || '';
    const extracted = extractTranscriptFromMarkdown(md);
    durationSeconds = scrapedDurationSeconds(md, scraped.metadata) ?? durationSeconds ?? extracted?.durationSeconds ?? null;
    if (extracted) return { text: extracted.text, durationSeconds };
    if (md && !md.trimStart().startsWith('Error 401')) sawRealPage = true;
  }
  const why = sawRealPage
    ? 'video has no transcript'
    : lastErr
      ? lastErr.message
      : `YouTube blocked all ${FIRECRAWL_ATTEMPTS} attempts`;
  throw Object.assign(new Error(`Firecrawl: ${why}`), { code: 'NO_TRANSCRIPT', durationSeconds });
}

export async function fetchOembed(videoId) {
  const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
  try {
    const res = await fetch(oembedUrl, { signal: AbortSignal.timeout(10000) });
    if (!res.ok) return { title: `YouTube ${videoId}`, author: 'YouTube' };
    const data = await res.json();
    return { title: data.title || `YouTube ${videoId}`, author: data.author_name || 'YouTube' };
  } catch {
    return { title: `YouTube ${videoId}`, author: 'YouTube' };
  }
}

/**
 * Transcript chain: youtube-transcript-api direct → Firecrawl (stealth, retried).
 * Never throws for a missing transcript: returns transcript=null with the errors,
 * so the watch pass can still cover a captionless video.
 */
export async function readYouTube(url) {
  const videoId = extractVideoId(url);
  if (!videoId) throw Object.assign(new Error(`Could not extract video ID from URL: ${url}`), { code: 'NO_VIDEO_ID' });
  const meta = await fetchOembed(videoId);
  const base = { title: meta.title, byline: meta.author, source: meta.author, video_id: videoId };
  const errors = [];

  try {
    const direct = fetchTranscriptDirect(videoId);
    return {
      ...base,
      body: direct.text,
      transcript_via: 'direct',
      duration_seconds: direct.durationSeconds,
      transcript_language: direct.language,
    };
  } catch (e) {
    errors.push(`direct: ${e.message}`);
  }

  let durationSeconds = null;
  if (firecrawlConfigured()) {
    try {
      const fc = await fetchTranscriptViaFirecrawl(videoId);
      return { ...base, body: fc.text, transcript_via: 'firecrawl', duration_seconds: fc.durationSeconds };
    } catch (e) {
      durationSeconds = e.durationSeconds ?? null;
      errors.push(e.message);
    }
  } else {
    errors.push('firecrawl: FIRECRAWL_API_KEY not set, fallback skipped');
  }

  return { ...base, body: '', transcript_via: null, duration_seconds: durationSeconds, transcript_errors: errors };
}
