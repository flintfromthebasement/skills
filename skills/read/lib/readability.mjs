import { JSDOM, VirtualConsole } from 'jsdom';
import { Readability } from '@mozilla/readability';
import { firecrawlConfigured, readArticleViaFirecrawl } from './firecrawl.mjs';

const USER_AGENT = 'Mozilla/5.0 (compatible; ReadSkill/0.3; +https://github.com/flintfromthebasement/skills)';
const FETCH_TIMEOUT_MS = 20000;
const MIN_WORDS = 50;

class ReadError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

// Bot blocks (401/403/429/451), server blips (5xx), and network errors are worth a Firecrawl retry.
function fallbackWorthy(err) {
  if (err.code === 'NETWORK' || err.code === 'EXTRACT_FAILED' || err.code === 'THIN_CONTENT') return true;
  const s = err.status;
  return s === 401 || s === 403 || s === 429 || s === 451 || (s >= 500 && s < 600);
}

function countWords(text) {
  return text ? text.trim().split(/\s+/).filter(Boolean).length : 0;
}

async function fetchDirect(url) {
  let response;
  try {
    response = await fetch(url, {
      headers: { 'User-Agent': USER_AGENT },
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
      redirect: 'follow',
    });
  } catch (e) {
    throw new ReadError(`Network error fetching ${url}: ${e.message}`, 'NETWORK');
  }
  if (!response.ok) {
    throw new ReadError(`HTTP ${response.status} ${response.statusText}`, `HTTP_${response.status}`, response.status);
  }
  const finalUrl = response.url || url;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/pdf') || finalUrl.toLowerCase().endsWith('.pdf')) {
    throw new ReadError('PDF reading not supported', 'UNSUPPORTED_TYPE');
  }
  const html = await response.text();
  const dom = new JSDOM(html, { url: finalUrl, virtualConsole: new VirtualConsole() });
  const article = new Readability(dom.window.document).parse();
  if (!article || !article.textContent) {
    throw new ReadError('Readability could not extract article content', 'EXTRACT_FAILED');
  }
  const body = article.textContent.trim();
  if (countWords(body) < MIN_WORDS) {
    throw new ReadError(`Extracted only ${countWords(body)} words (JS-rendered or blocked page?)`, 'THIN_CONTENT');
  }
  let host = '';
  try {
    host = new URL(finalUrl).host;
  } catch {
    // ignore
  }
  return {
    title: (article.title || dom.window.document.title || 'Untitled').trim(),
    byline: (article.byline || '').trim(),
    source: host,
    body,
    via: 'direct',
  };
}

/** Direct fetch + Readability, then Firecrawl when the page is blocked, broken, or JS-only. */
export async function fetchArticle(url) {
  try {
    return await fetchDirect(url);
  } catch (err) {
    if (!fallbackWorthy(err) || !firecrawlConfigured()) throw err;
    try {
      return await readArticleViaFirecrawl(url);
    } catch (fbErr) {
      throw new ReadError(`${err.message}; Firecrawl fallback also failed: ${fbErr.message}`, err.code, err.status);
    }
  }
}
