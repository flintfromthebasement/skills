import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

const USER_AGENT = 'Mozilla/5.0 (compatible; MauriceRead/0.1; +https://maurice.lifterlms.com)';
const FETCH_TIMEOUT_MS = 20000;

export async function fetchArticle(url) {
  const response = await fetch(url, {
    headers: { 'User-Agent': USER_AGENT },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`);
  }
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/pdf') || url.toLowerCase().endsWith('.pdf')) {
    throw new Error('PDF reading not supported in v1');
  }
  const html = await response.text();
  const dom = new JSDOM(html, { url });
  const reader = new Readability(dom.window.document);
  const article = reader.parse();
  if (!article || !article.textContent) {
    throw new Error('Readability could not extract article content');
  }
  let host = '';
  try {
    host = new URL(url).host;
  } catch {
    // ignore
  }
  return {
    title: (article.title || dom.window.document.title || 'Untitled').trim(),
    byline: (article.byline || '').trim(),
    source: host,
    body: article.textContent.trim(),
    excerpt: (article.excerpt || '').trim(),
    length: article.length || 0,
  };
}
