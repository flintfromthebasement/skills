/**
 * Firecrawl /v2/scrape — the fallback for bot-blocked or JS-only pages and for
 * YouTube transcripts when the direct caption path fails. Every call needs
 * FIRECRAWL_API_KEY; without it callers skip the fallback.
 */

const DEFAULT_BASE_URL = 'https://api.firecrawl.dev';
const SCRAPE_TIMEOUT_MS = 90000;

export function firecrawlConfigured() {
  return Boolean(process.env.FIRECRAWL_API_KEY?.trim());
}

export async function scrape(url, opts = {}) {
  const key = process.env.FIRECRAWL_API_KEY?.trim();
  if (!key) throw Object.assign(new Error('FIRECRAWL_API_KEY not set'), { code: 'FIRECRAWL_MISSING_KEY' });
  const base = (process.env.FIRECRAWL_BASE_URL || DEFAULT_BASE_URL).replace(/\/+$/, '');
  const body = {
    url,
    formats: opts.formats || ['markdown'],
    onlyMainContent: opts.onlyMainContent !== false,
    ...(opts.proxy ? { proxy: opts.proxy } : {}),
    ...(typeof opts.waitFor === 'number' ? { waitFor: opts.waitFor } : {}),
    ...(typeof opts.maxAge === 'number' ? { maxAge: opts.maxAge } : {}),
  };
  const res = await fetch(`${base}/v2/scrape`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${key}` },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(SCRAPE_TIMEOUT_MS),
  });
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw Object.assign(new Error(`Firecrawl HTTP ${res.status}: ${text.slice(0, 200)}`), { code: 'FIRECRAWL_FAILED' });
  }
  if (!res.ok || !json.success || !json.data) {
    throw Object.assign(
      new Error(`Firecrawl scrape failed (HTTP ${res.status}): ${json.error || 'no data'}`),
      { code: 'FIRECRAWL_FAILED' },
    );
  }
  return json.data;
}

export async function readArticleViaFirecrawl(url) {
  const scraped = await scrape(url, { formats: ['markdown'], onlyMainContent: true });
  const body = (scraped.markdown || '').trim();
  if (!body) throw Object.assign(new Error('Firecrawl returned no markdown'), { code: 'FIRECRAWL_EMPTY' });
  let source = '';
  try {
    source = new URL(url).host;
  } catch {
    // ignore
  }
  const title = typeof scraped.metadata?.title === 'string' ? scraped.metadata.title : '';
  return { title: title || 'Untitled', byline: '', source, body, via: 'firecrawl' };
}
