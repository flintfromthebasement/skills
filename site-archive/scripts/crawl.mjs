import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { execFile as execFileCb } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';

import { Readability } from '@mozilla/readability';
import { XMLParser } from 'fast-xml-parser';
import { JSDOM, VirtualConsole } from 'jsdom';
import TurndownService from 'turndown';

import { detectBlocker, fingerprintBlocker } from './detect-blockers.mjs';

const execFile = promisify(execFileCb);

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SKILL_ROOT = path.dirname(__dirname);
const WORKSPACE_ROOT = '/home/flint';
const DEFAULT_ARCHIVE_ROOT = path.join(WORKSPACE_ROOT, 'data', 'site-archives');
const FETCH_HEADERS = {
  'user-agent':
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
  accept:
    'text/html,application/xhtml+xml,application/xml;q=0.9,text/markdown;q=0.8,text/plain;q=0.7,*/*;q=0.5',
  'accept-language': 'en-US,en;q=0.9',
  'cache-control': 'no-cache',
  pragma: 'no-cache'
};
const DEFAULT_SITEMAP_TYPES = ['page', 'post', 'download', 'documentation', 'addons'];
const CONTENT_SITEMAP_EXCLUDES = [
  /category/i,
  /tag/i,
  /author/i,
  /taxonomy/i,
  /image/i,
  /video/i,
  /news-sitemap\.xml$/i
];
const DEFAULT_EXCLUDE_PATTERNS = [
  /^\/wp-login\.php$/i,
  /^\/wp-admin(?:\/|$)/i,
  /^\/feed\/?$/i,
  /^\/comments\/feed\/?$/i,
  /^\/cart\/?$/i,
  /^\/checkout\/?$/i,
  /^\/my-account\/?$/i
];

function parseArgs(argv) {
  const args = {
    site: null,
    minDelayMs: 700,
    maxDelayMs: 1800,
    limit: null,
    dryRun: false,
    includePosts: false,
    onlyPosts: false,
    includePagination: false,
    includeSearch: false,
    skipExisting: false,
    sinceLastmod: false,
    retryBlocked: false,
    fetchEngine: 'auto',
    outputDir: null,
    sitemapTypes: [...DEFAULT_SITEMAP_TYPES],
    includePatterns: [],
    excludePatterns: [],
    linkDepth: 1,
    maxPagesFromLinks: 100,
    maxBlockerStreak: 3
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];

    if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    }
    if (arg === '--dry-run') {
      args.dryRun = true;
      continue;
    }
    if (arg === '--include-posts') {
      args.includePosts = true;
      continue;
    }
    if (arg === '--only-posts') {
      args.onlyPosts = true;
      continue;
    }
    if (arg === '--include-pagination') {
      args.includePagination = true;
      continue;
    }
    if (arg === '--include-search') {
      args.includeSearch = true;
      continue;
    }
    if (arg === '--skip-existing') {
      args.skipExisting = true;
      continue;
    }
    if (arg === '--since-lastmod') {
      args.sinceLastmod = true;
      continue;
    }
    if (arg === '--retry-blocked') {
      args.retryBlocked = true;
      continue;
    }
    if (arg === '--site') {
      args.site = argv[++i];
      continue;
    }
    if (arg === '--output-dir') {
      args.outputDir = path.resolve(argv[++i]);
      continue;
    }
    if (arg === '--limit') {
      args.limit = Number(argv[++i]);
      continue;
    }
    if (arg === '--min-delay-ms') {
      args.minDelayMs = Number(argv[++i]);
      continue;
    }
    if (arg === '--max-delay-ms') {
      args.maxDelayMs = Number(argv[++i]);
      continue;
    }
    if (arg === '--fetch-engine') {
      args.fetchEngine = String(argv[++i]).toLowerCase();
      continue;
    }
    if (arg === '--sitemap-types') {
      args.sitemapTypes = String(argv[++i])
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      continue;
    }
    if (arg === '--include-pattern') {
      args.includePatterns.push(argv[++i]);
      continue;
    }
    if (arg === '--exclude-pattern') {
      args.excludePatterns.push(argv[++i]);
      continue;
    }
    if (arg === '--link-depth') {
      args.linkDepth = Number(argv[++i]);
      continue;
    }
    if (arg === '--max-pages-from-links') {
      args.maxPagesFromLinks = Number(argv[++i]);
      continue;
    }
    if (arg === '--max-blocker-streak') {
      args.maxBlockerStreak = Number(argv[++i]);
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  if (!args.site) {
    throw new Error('Missing required --site <url>.');
  }
  if (args.includePosts && !args.sitemapTypes.includes('post')) {
    args.sitemapTypes.push('post');
  }
  if (args.onlyPosts) {
    args.sitemapTypes = ['post'];
  }
  if (!['auto', 'node', 'curl'].includes(args.fetchEngine)) {
    throw new Error('Fetch engine must be one of: auto, node, curl.');
  }
  if (!Number.isFinite(args.minDelayMs) || !Number.isFinite(args.maxDelayMs)) {
    throw new Error('Delay values must be numbers.');
  }
  if (args.minDelayMs < 0 || args.maxDelayMs < 0 || args.maxDelayMs < args.minDelayMs) {
    throw new Error('Delay bounds are invalid.');
  }
  if (args.limit !== null && (!Number.isInteger(args.limit) || args.limit <= 0)) {
    throw new Error('Limit must be a positive integer.');
  }
  if (!Number.isInteger(args.linkDepth) || args.linkDepth < 0) {
    throw new Error('Link depth must be a non-negative integer.');
  }
  if (!Number.isInteger(args.maxPagesFromLinks) || args.maxPagesFromLinks <= 0) {
    throw new Error('max-pages-from-links must be a positive integer.');
  }
  if (!Number.isInteger(args.maxBlockerStreak) || args.maxBlockerStreak <= 0) {
    throw new Error('max-blocker-streak must be a positive integer.');
  }

  return args;
}

function printHelp() {
  console.log(`Usage: node crawl.mjs --site <url> [options]

Options:
  --site <url>                 Starting URL or site root
  --output-dir <path>          Output directory (default: /home/flint/data/site-archives/<domain>)
  --include-posts              Include post sitemap entries
  --only-posts                 Crawl only post sitemap entries
  --include-pagination         Include paginated index pages like /page/2/
  --include-search             Include search result pages
  --skip-existing              Skip URLs whose markdown file already exists
  --since-lastmod              Skip URLs unchanged since archived lastmod
  --retry-blocked              Retry URLs recorded as blocked in state/blocklist.json
  --fetch-engine <mode>        auto | node | curl (default: auto)
  --sitemap-types <list>       Comma-separated sitemap types to prefer
  --include-pattern <regex>    Include only matching URLs (repeatable)
  --exclude-pattern <regex>    Exclude matching URLs (repeatable)
  --link-depth <n>             Fallback link crawl depth when sitemaps unavailable
  --max-pages-from-links <n>   Fallback link crawl page cap
  --max-blocker-streak <n>     Abort after n consecutive blocker pages
  --limit <n>                  Limit target count
  --min-delay-ms <n>           Minimum randomized delay between requests
  --max-delay-ms <n>           Maximum randomized delay between requests
  --dry-run                    Build target list without fetching content pages
  --help                       Show this help
`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomBetween(min, max) {
  if (min === max) return min;
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function ensureArray(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function slugifySegment(segment) {
  return segment
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'index';
}

function slugifyHost(host) {
  return host.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

function resolveSiteConfig(siteInput, explicitOutputDir) {
  const startUrl = new URL(siteInput);
  const origin = startUrl.origin;
  const domainSlug = slugifyHost(startUrl.hostname);
  const outputDir = explicitOutputDir || path.join(DEFAULT_ARCHIVE_ROOT, domainSlug);
  return { startUrl, origin, domainSlug, outputDir };
}

function urlToRelativePath(urlString) {
  const url = new URL(urlString);
  const segments = url.pathname.split('/').filter(Boolean).map(slugifySegment);
  return segments.length === 0 ? path.join('home', 'index.md') : path.join(...segments, 'index.md');
}

function blockedUrlToRelativePath(urlString) {
  return urlToRelativePath(urlString).replace(/\.md$/, '.json');
}

function yamlValue(value) {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(String(value));
}

function toFrontMatter(data) {
  const lines = ['---'];
  for (const [key, value] of Object.entries(data)) {
    if (Array.isArray(value)) {
      lines.push(`${key}:`);
      for (const item of value) {
        lines.push(`  - ${yamlValue(item)}`);
      }
      continue;
    }
    lines.push(`${key}: ${yamlValue(value)}`);
  }
  lines.push('---', '');
  return `${lines.join('\n')}`;
}

function parseFrontMatter(content) {
  if (!content.startsWith('---\n')) return null;
  const endIndex = content.indexOf('\n---\n', 4);
  if (endIndex === -1) return null;

  const block = content.slice(4, endIndex);
  const parsed = {};
  let currentArrayKey = null;

  for (const rawLine of block.split('\n')) {
    const line = rawLine.trimEnd();
    if (!line.trim()) continue;

    const arrayMatch = line.match(/^([A-Za-z0-9_]+):\s*$/);
    if (arrayMatch) {
      currentArrayKey = arrayMatch[1];
      parsed[currentArrayKey] = [];
      continue;
    }

    const itemMatch = line.match(/^\s*-\s+(.*)$/);
    if (itemMatch && currentArrayKey) {
      parsed[currentArrayKey].push(parseFrontMatterScalar(itemMatch[1]));
      continue;
    }

    const fieldMatch = line.match(/^([A-Za-z0-9_]+):\s+(.*)$/);
    if (fieldMatch) {
      currentArrayKey = null;
      parsed[fieldMatch[1]] = parseFrontMatterScalar(fieldMatch[2]);
    }
  }

  return parsed;
}

function parseFrontMatterScalar(value) {
  const trimmed = value.trim();
  if (trimmed === 'null') return null;
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    try {
      return JSON.parse(trimmed.replace(/^'|'$/g, '"'));
    } catch {
      return trimmed.slice(1, -1);
    }
  }
  return trimmed;
}

function normalizeWhitespace(value) {
  return String(value || '')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

function extractMeta(document, selectors) {
  for (const selector of selectors) {
    const node = document.querySelector(selector);
    if (!node) continue;
    const content = node.getAttribute('content') || node.getAttribute('href') || node.textContent;
    const normalized = normalizeWhitespace(content);
    if (normalized) return normalized;
  }
  return null;
}

function createPatternList(patterns) {
  return patterns.map((pattern) => (pattern instanceof RegExp ? pattern : new RegExp(pattern, 'i')));
}

function shouldIncludeUrl(urlString, includePatterns, excludePatterns) {
  const url = new URL(urlString);
  const asString = url.toString();
  const pathname = url.pathname;

  for (const pattern of createPatternList(DEFAULT_EXCLUDE_PATTERNS)) {
    if (pattern.test(pathname)) {
      return { keep: false, reason: 'default excluded path' };
    }
  }

  for (const pattern of excludePatterns) {
    if (pattern.test(asString) || pattern.test(pathname)) {
      return { keep: false, reason: 'excluded by pattern' };
    }
  }

  if (includePatterns.length > 0) {
    const matched = includePatterns.some((pattern) => pattern.test(asString) || pattern.test(pathname));
    if (!matched) {
      return { keep: false, reason: 'outside include patterns' };
    }
  }

  return { keep: true, reason: null };
}

function shouldSkipByDefault(urlString, args) {
  const url = new URL(urlString);
  const pathname = url.pathname;
  const hasSearchQuery =
    url.searchParams.has('s') || url.searchParams.has('search') || url.searchParams.has('query');
  const searchPath = /^\/search\/?$/i.test(pathname) || /^\/search\//i.test(pathname);

  if (!args.includePagination && /\/page\/\d+\/?$/i.test(pathname)) {
    return { skip: true, reason: 'pagination page' };
  }

  if (!args.includeSearch && (hasSearchQuery || searchPath)) {
    return { skip: true, reason: 'search results page' };
  }

  return { skip: false, reason: null };
}

function rulePatternToRegex(value) {
  const escaped = value
    .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
    .replace(/\*/g, '.*')
    .replace(/\$/g, '$');
  return new RegExp(`^${escaped}`);
}

function parseRobots(robotsText) {
  const lines = robotsText
    .split('\n')
    .map((line) => line.replace(/#.*$/, '').trim())
    .filter(Boolean);

  const groups = [];
  const sitemaps = [];
  let currentGroup = null;

  for (const line of lines) {
    const [rawKey, ...rawRest] = line.split(':');
    if (!rawKey || rawRest.length === 0) continue;

    const key = rawKey.trim().toLowerCase();
    const value = rawRest.join(':').trim();

    if (key === 'sitemap') {
      sitemaps.push(value);
      continue;
    }

    if (key === 'user-agent') {
      if (!currentGroup || currentGroup.closed) {
        currentGroup = {
          userAgents: [],
          allow: [],
          disallow: [],
          crawlDelay: null,
          closed: false
        };
        groups.push(currentGroup);
      }
      currentGroup.userAgents.push(value.toLowerCase());
      continue;
    }

    if (!currentGroup) continue;
    currentGroup.closed = true;

    if (key === 'allow') currentGroup.allow.push(value);
    if (key === 'disallow') currentGroup.disallow.push(value);
    if (key === 'crawl-delay') currentGroup.crawlDelay = Number(value);
  }

  return { groups, sitemaps };
}

function selectRobotsGroup(parsedRobots) {
  const specific = parsedRobots.groups.find((group) =>
    group.userAgents.some((agent) => agent.includes('flint') || agent.includes('mozilla'))
  );
  if (specific) return specific;
  return parsedRobots.groups.find((group) => group.userAgents.includes('*')) || null;
}

function isRobotsAllowed(pathname, robotsGroup) {
  if (!robotsGroup) return true;

  const matches = [];
  for (const value of robotsGroup.allow) {
    if (!value) continue;
    const regex = rulePatternToRegex(value);
    if (regex.test(pathname)) {
      matches.push({ type: 'allow', length: value.length });
    }
  }
  for (const value of robotsGroup.disallow) {
    if (!value) continue;
    const regex = rulePatternToRegex(value);
    if (regex.test(pathname)) {
      matches.push({ type: 'disallow', length: value.length });
    }
  }

  if (matches.length === 0) return true;
  matches.sort((left, right) => right.length - left.length);
  return matches[0].type === 'allow';
}

async function readJson(filePath, fallback) {
  try {
    const content = await fs.readFile(filePath, 'utf8');
    return JSON.parse(content);
  } catch (error) {
    if (error && typeof error === 'object' && error.code === 'ENOENT') {
      return fallback;
    }
    throw error;
  }
}

async function readExistingMetadata(filePath) {
  try {
    const content = await fs.readFile(filePath, 'utf8');
    return parseFrontMatter(content);
  } catch (error) {
    if (error && typeof error === 'object' && error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

function getContentFilePath(outputDir, urlString) {
  return path.join(outputDir, 'content', 'pages', urlToRelativePath(urlString));
}

function getBlockedFilePath(outputDir, urlString) {
  return path.join(outputDir, 'blocked', blockedUrlToRelativePath(urlString));
}

function compareIsoLikeStrings(left, right) {
  if (!left || !right) return null;
  const leftTime = Date.parse(left);
  const rightTime = Date.parse(right);
  if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) return null;
  return leftTime - rightTime;
}

async function fetchWithNode(url) {
  const response = await fetch(url, {
    redirect: 'follow',
    headers: FETCH_HEADERS
  });
  const text = await response.text();
  return {
    engine: 'node',
    ok: response.ok,
    statusCode: response.status,
    finalUrl: response.url,
    text
  };
}

async function fetchWithCurl(url) {
  const args = [
    '-sSL',
    '--compressed',
    '-A',
    FETCH_HEADERS['user-agent'],
    '-H',
    `Accept: ${FETCH_HEADERS.accept}`,
    '-H',
    `Accept-Language: ${FETCH_HEADERS['accept-language']}`,
    '-H',
    `Cache-Control: ${FETCH_HEADERS['cache-control']}`,
    '-H',
    `Pragma: ${FETCH_HEADERS.pragma}`,
    '-w',
    '\n__CURL_STATUS__:%{http_code}\n__CURL_FINAL_URL__:%{url_effective}\n',
    url
  ];
  const { stdout } = await execFile('curl', args, {
    maxBuffer: 10 * 1024 * 1024
  });

  const statusMatch = stdout.match(/\n__CURL_STATUS__:(\d+)\n__CURL_FINAL_URL__:(.+)\n?$/);
  if (!statusMatch) {
    throw new Error(`Unable to parse curl response metadata for ${url}`);
  }

  const text = stdout.slice(0, statusMatch.index);
  const statusCode = Number(statusMatch[1]);
  const finalUrl = statusMatch[2].trim();
  return {
    engine: 'curl',
    ok: statusCode >= 200 && statusCode < 300,
    statusCode,
    finalUrl,
    text
  };
}

function shouldFallbackToCurl(result) {
  if (!result) return true;
  if ([403, 406, 409, 429, 503].includes(result.statusCode)) return true;
  return Boolean(detectBlocker(result.text, result.statusCode, result.finalUrl));
}

async function fetchText(url, args) {
  if (args.fetchEngine === 'curl') {
    return fetchWithCurl(url);
  }
  if (args.fetchEngine === 'node') {
    return fetchWithNode(url);
  }

  const nodeResult = await fetchWithNode(url);
  if (!shouldFallbackToCurl(nodeResult)) {
    return nodeResult;
  }

  try {
    return await fetchWithCurl(url);
  } catch {
    return nodeResult;
  }
}

async function fetchRobots(siteConfig, args) {
  const robotsUrl = new URL('/robots.txt', siteConfig.origin).toString();
  const result = await fetchText(robotsUrl, args);
  if (result.statusCode === 404) {
    return {
      robotsUrl,
      text: '',
      parsed: { groups: [], sitemaps: [] },
      selectedGroup: null
    };
  }
  if (!result.ok) {
    throw new Error(`HTTP ${result.statusCode} for ${robotsUrl}`);
  }
  const parsed = parseRobots(result.text);
  return {
    robotsUrl,
    text: result.text,
    parsed,
    selectedGroup: selectRobotsGroup(parsed)
  };
}

function inferCandidateSitemapUrls(siteConfig, robotsInfo) {
  const fromRobots = robotsInfo.parsed.sitemaps;
  const candidates = [
    ...fromRobots,
    new URL('/sitemap_index.xml', siteConfig.origin).toString(),
    new URL('/sitemap.xml', siteConfig.origin).toString()
  ];
  return [...new Set(candidates)];
}

async function fetchSitemap(url, args) {
  const result = await fetchText(url, args);
  if (!result.ok) {
    throw new Error(`HTTP ${result.statusCode} for ${url}`);
  }

  const parser = new XMLParser({
    ignoreAttributes: false,
    removeNSPrefix: true,
    trimValues: true
  });
  const data = parser.parse(result.text);

  if (data.sitemapindex?.sitemap) {
    return {
      type: 'index',
      items: ensureArray(data.sitemapindex.sitemap).map((entry) => ({
        loc: entry.loc,
        lastmod: entry.lastmod || null
      }))
    };
  }

  if (data.urlset?.url) {
    return {
      type: 'urlset',
      items: ensureArray(data.urlset.url).map((entry) => ({
        loc: entry.loc,
        lastmod: entry.lastmod || null
      }))
    };
  }

  return { type: 'unknown', items: [] };
}

function isSelectedSitemap(sitemapUrl, args) {
  if (args.sitemapTypes.length === 0) {
    return !CONTENT_SITEMAP_EXCLUDES.some((pattern) => pattern.test(sitemapUrl));
  }

  const filename = path.basename(new URL(sitemapUrl).pathname).toLowerCase();
  if (CONTENT_SITEMAP_EXCLUDES.some((pattern) => pattern.test(filename))) {
    return false;
  }

  return args.sitemapTypes.some((type) => filename.startsWith(`${type.toLowerCase()}-sitemap`));
}

async function discoverSitemapTargets(siteConfig, robotsInfo, args) {
  const candidates = inferCandidateSitemapUrls(siteConfig, robotsInfo);
  const selectedSitemaps = [];
  const targets = [];
  const seenTargets = new Set();
  let foundSitemapData = false;

  for (const candidate of candidates) {
    try {
      const payload = await fetchSitemap(candidate, args);
      if (payload.type === 'index') {
        foundSitemapData = true;
        for (const sitemap of payload.items) {
          if (!isSelectedSitemap(sitemap.loc, args)) {
            continue;
          }
          selectedSitemaps.push(sitemap);
        }
      } else if (payload.type === 'urlset') {
        foundSitemapData = true;
        if (isSelectedSitemap(candidate, args) || candidates.length === 1) {
          selectedSitemaps.push({ loc: candidate, lastmod: null, inline: true, inlineItems: payload.items });
        }
      }
    } catch {
      // Ignore unavailable candidates and continue.
    }
  }

  const dedupedSitemaps = [];
  const seenSitemaps = new Set();
  for (const sitemap of selectedSitemaps) {
    if (seenSitemaps.has(sitemap.loc)) continue;
    seenSitemaps.add(sitemap.loc);
    dedupedSitemaps.push(sitemap);
  }

  for (const sitemap of dedupedSitemaps) {
    const urlItems = sitemap.inlineItems || (await fetchSitemap(sitemap.loc, args)).items;
    for (const entry of urlItems) {
      if (seenTargets.has(entry.loc)) continue;
      seenTargets.add(entry.loc);
      targets.push({
        url: entry.loc,
        lastmod: entry.lastmod,
        sitemap: sitemap.loc,
        sourceType: deriveSourceType(sitemap.loc, entry.loc)
      });
    }
  }

  return { foundSitemapData, selectedSitemaps: dedupedSitemaps, targets };
}

function deriveSourceType(sitemapUrl, pageUrl) {
  const sitemapName = path.basename(new URL(sitemapUrl).pathname, '.xml').toLowerCase();
  if (sitemapName.endsWith('-sitemap')) {
    return sitemapName.replace(/-sitemap$/, '');
  }
  const pathname = new URL(pageUrl).pathname.toLowerCase();
  if (pathname.startsWith('/documentation/')) return 'documentation';
  if (pathname.startsWith('/addons/')) return 'addons';
  if (pathname.startsWith('/blog/')) return 'post';
  return 'page';
}

function extractSameOriginLinks(html, baseUrl, siteConfig) {
  const dom = new JSDOM(html, { url: baseUrl });
  const urls = [];
  for (const node of dom.window.document.querySelectorAll('a[href]')) {
    try {
      const url = new URL(node.getAttribute('href'), baseUrl);
      if (url.origin !== siteConfig.origin) continue;
      if (!['http:', 'https:'].includes(url.protocol)) continue;
      urls.push(url.toString());
    } catch {
      // Ignore malformed hrefs.
    }
  }
  return [...new Set(urls)];
}

async function discoverByLinks(siteConfig, robotsInfo, args) {
  const seen = new Set();
  const queue = [{ url: siteConfig.startUrl.toString(), depth: 0 }];
  const targets = [];
  const selectedSitemaps = [];

  while (queue.length > 0 && targets.length < args.maxPagesFromLinks) {
    const current = queue.shift();
    if (seen.has(current.url)) continue;
    seen.add(current.url);

    const robotsGroup = robotsInfo.selectedGroup;
    const currentPath = new URL(current.url).pathname;
    if (!isRobotsAllowed(currentPath, robotsGroup)) {
      continue;
    }

    const result = await fetchText(current.url, args);
    const blocker = detectBlocker(result.text, result.statusCode, result.finalUrl);
    if (result.ok && !blocker) {
      targets.push({
        url: current.url,
        lastmod: null,
        sitemap: 'link-discovery',
        sourceType: current.depth === 0 ? 'page' : 'linked-page'
      });
    }

    if (!result.ok || blocker || current.depth >= args.linkDepth) {
      continue;
    }

    const links = extractSameOriginLinks(result.text, current.url, siteConfig);
    for (const link of links) {
      if (!seen.has(link)) {
        queue.push({ url: link, depth: current.depth + 1 });
      }
    }
  }

  return { selectedSitemaps, targets };
}

function prepareStatePaths(outputDir) {
  return {
    summaryPath: path.join(outputDir, 'summary.md'),
    manifestPath: path.join(outputDir, 'manifest.json'),
    logsDir: path.join(outputDir, 'logs'),
    stateDir: path.join(outputDir, 'state'),
    blocklistPath: path.join(outputDir, 'state', 'blocklist.json'),
    lastRunPath: path.join(outputDir, 'state', 'last-run.json')
  };
}

async function loadState(paths) {
  await fs.mkdir(paths.logsDir, { recursive: true });
  await fs.mkdir(paths.stateDir, { recursive: true });
  return {
    blocklist: await readJson(paths.blocklistPath, {
      blockedUrls: {},
      fingerprints: {},
      hostBlockedAt: null,
      hostBlockReason: null
    })
  };
}

function isKnownBlocked(targetUrl, blocklist) {
  return Boolean(blocklist.blockedUrls?.[targetUrl]);
}

function noteBlockedUrl(blocklist, targetUrl, blocker) {
  if (!blocklist.blockedUrls) blocklist.blockedUrls = {};
  if (!blocklist.fingerprints) blocklist.fingerprints = {};

  blocklist.blockedUrls[targetUrl] = {
    detectedAt: new Date().toISOString(),
    blocker
  };

  const key = blocker.fingerprint || fingerprintBlocker(blocker);
  blocklist.fingerprints[key] = (blocklist.fingerprints[key] || 0) + 1;
  return blocklist.fingerprints[key];
}

function maybeEscalateHostBlock(blocklist, blockerFingerprint, timesSeen) {
  if (timesSeen >= 3) {
    blocklist.hostBlockedAt = new Date().toISOString();
    blocklist.hostBlockReason = `repeated blocker fingerprint ${blockerFingerprint}`;
  }
}

async function filterTargets(rawTargets, siteConfig, robotsInfo, args, state) {
  const includePatterns = createPatternList(args.includePatterns);
  const excludePatterns = createPatternList(args.excludePatterns);
  const filteredTargets = [];
  const skipped = [];

  for (const target of rawTargets) {
    const targetUrl = new URL(target.url);

    if (targetUrl.origin !== siteConfig.origin) {
      skipped.push({ url: target.url, sitemap: target.sitemap, reason: 'cross-origin' });
      continue;
    }

    if (!isRobotsAllowed(targetUrl.pathname, robotsInfo.selectedGroup)) {
      skipped.push({ url: target.url, sitemap: target.sitemap, reason: 'disallowed by robots.txt' });
      continue;
    }

    const importance = shouldIncludeUrl(target.url, includePatterns, excludePatterns);
    if (!importance.keep) {
      skipped.push({ url: target.url, sitemap: target.sitemap, reason: importance.reason });
      continue;
    }

    const defaultSkip = shouldSkipByDefault(target.url, args);
    if (defaultSkip.skip) {
      skipped.push({ url: target.url, sitemap: target.sitemap, reason: defaultSkip.reason });
      continue;
    }

    if (!args.retryBlocked && isKnownBlocked(target.url, state.blocklist)) {
      skipped.push({ url: target.url, sitemap: target.sitemap, reason: 'known blocked URL' });
      continue;
    }

    const filePath = getContentFilePath(siteConfig.outputDir, target.url);
    const existingMetadata = await readExistingMetadata(filePath);

    if (args.skipExisting && existingMetadata) {
      skipped.push({ url: target.url, sitemap: target.sitemap, reason: 'already archived' });
      continue;
    }

    if (args.sinceLastmod && existingMetadata && existingMetadata.lastmod && target.lastmod) {
      const delta = compareIsoLikeStrings(existingMetadata.lastmod, target.lastmod);
      if (delta !== null && delta >= 0) {
        skipped.push({ url: target.url, sitemap: target.sitemap, reason: 'unchanged since lastmod' });
        continue;
      }
    }

    filteredTargets.push(target);
  }

  if (args.limit !== null) {
    return { targets: filteredTargets.slice(0, args.limit), skipped };
  }

  return { targets: filteredTargets, skipped };
}

function createTurndown() {
  const service = new TurndownService({
    headingStyle: 'atx',
    codeBlockStyle: 'fenced',
    bulletListMarker: '-'
  });

  service.remove(['script', 'style', 'noscript', 'iframe']);

  service.addRule('trimLinks', {
    filter: 'a',
    replacement(content, node) {
      const href = node.getAttribute('href');
      const text = normalizeWhitespace(content);
      if (!href) return text;
      if (!text) return href;
      return `[${text}](${href})`;
    }
  });

  service.addRule('preformattedCode', {
    filter(node) {
      return node.nodeName === 'PRE';
    },
    replacement(content, node) {
      const code = node.textContent || content || '';
      const language = node.querySelector('code')?.className?.match(/language-([\w-]+)/)?.[1] || '';
      return `\n\n\`\`\`${language}\n${code.trim()}\n\`\`\`\n\n`;
    }
  });

  return service;
}

function removeJunk(document) {
  const selectors = [
    'script',
    'style',
    'noscript',
    'iframe',
    '.cky-consent-container',
    '.cookie-law-info-bar',
    '.grecaptcha-badge',
    '.sharedaddy',
    '.jp-relatedposts'
  ];

  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      node.remove();
    }
  }
}

async function renderPage(target, args) {
  const fetchedAt = new Date().toISOString();
  const response = await fetchText(target.url, args);
  const blocker = detectBlocker(response.text, response.statusCode, response.finalUrl);

  if (blocker) {
    return {
      status: 'blocked',
      blocker: {
        ...blocker,
        fingerprint: fingerprintBlocker(blocker)
      },
      fetchedAt,
      fetchEngine: response.engine,
      statusCode: response.statusCode,
      finalUrl: response.finalUrl
    };
  }

  if (!response.ok) {
    throw new Error(`HTTP ${response.statusCode} for ${target.url}`);
  }

  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', () => {});
  const dom = new JSDOM(response.text, {
    url: response.finalUrl,
    virtualConsole
  });
  const { document } = dom.window;
  removeJunk(document);

  const canonicalUrl = extractMeta(document, ['link[rel="canonical"]']) || response.finalUrl || target.url;
  const description =
    extractMeta(document, [
      'meta[name="description"]',
      'meta[property="og:description"]',
      'meta[name="twitter:description"]'
    ]) || '';

  const title =
    extractMeta(document, [
      'meta[property="og:title"]',
      'meta[name="twitter:title"]',
      'title'
    ]) || normalizeWhitespace(document.title) || target.url;

  const readability = new Readability(document.cloneNode(true), {
    keepClasses: false
  }).parse();

  let contentHtml = '';
  let contentTitle = title;

  if (readability?.content) {
    contentHtml = readability.content;
    contentTitle = normalizeWhitespace(readability.title) || title;
  } else {
    const main =
      document.querySelector('main') ||
      document.querySelector('article') ||
      document.querySelector('.entry-content') ||
      document.body;
    contentHtml = main?.innerHTML || '';
  }

  const markdown = normalizeWhitespace(createTurndown().turndown(contentHtml));
  const finalTitle = contentTitle || title;
  const wordCount = markdown ? markdown.split(/\s+/).filter(Boolean).length : 0;

  return {
    status: 'archived',
    title: finalTitle,
    description,
    canonicalUrl,
    fetchedAt,
    markdown,
    wordCount,
    fetchEngine: response.engine,
    statusCode: response.statusCode,
    finalUrl: response.finalUrl
  };
}

async function writeArchivedPage(outputDir, target, page) {
  const filePath = getContentFilePath(outputDir, target.url);
  await fs.mkdir(path.dirname(filePath), { recursive: true });

  const frontMatter = toFrontMatter({
    source_url: target.url,
    source_path: new URL(target.url).pathname,
    source_type: target.sourceType,
    sitemap: target.sitemap,
    title: page.title,
    description: page.description,
    lastmod: target.lastmod,
    canonical_url: page.canonicalUrl,
    fetched_at: page.fetchedAt,
    fetch_engine: page.fetchEngine,
    http_status: page.statusCode,
    final_url: page.finalUrl,
    status: 'archived',
    word_count: page.wordCount
  });

  const body = page.markdown ? `# ${page.title}\n\n${page.markdown}\n` : `# ${page.title}\n`;
  await fs.writeFile(filePath, `${frontMatter}${body}`, 'utf8');
  return filePath;
}

async function writeBlockedDiagnostic(outputDir, target, blocked) {
  const filePath = getBlockedFilePath(outputDir, target.url);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(
    filePath,
    JSON.stringify(
      {
        url: target.url,
        sitemap: target.sitemap,
        detectedAt: blocked.fetchedAt,
        fetchEngine: blocked.fetchEngine,
        statusCode: blocked.statusCode,
        finalUrl: blocked.finalUrl,
        blocker: blocked.blocker
      },
      null,
      2
    ),
    'utf8'
  );
  return filePath;
}

async function writeSummary(outputDir, summary) {
  const lines = [
    '# Site Archive Summary',
    '',
    `- Generated at: ${summary.generatedAt}`,
    `- Site: ${summary.site}`,
    `- Output: ${outputDir}`,
    `- Included sitemap types: ${summary.sitemapTypes.join(', ') || '(auto)'}`,
    `- Selected sitemaps: ${summary.selectedSitemaps.length}`,
    `- Archived pages: ${summary.archived.length}`,
    `- Blocked pages: ${summary.blocked.length}`,
    `- Skipped pages: ${summary.skipped.length}`,
    `- Failed pages: ${summary.failed.length}`,
    ''
  ];

  if (summary.blocked.length > 0) {
    lines.push('## Blocked', '');
    for (const blocked of summary.blocked.slice(0, 50)) {
      lines.push(`- ${blocked.url}: ${blocked.blocker.reason}`);
    }
    if (summary.blocked.length > 50) {
      lines.push(`- ... ${summary.blocked.length - 50} more`);
    }
    lines.push('');
  }

  if (summary.failed.length > 0) {
    lines.push('## Failures', '');
    for (const failure of summary.failed) {
      lines.push(`- ${failure.url}: ${failure.error}`);
    }
    lines.push('');
  }

  if (summary.skipped.length > 0) {
    lines.push('## Skipped', '');
    for (const skipped of summary.skipped.slice(0, 50)) {
      lines.push(`- ${skipped.url}: ${skipped.reason}`);
    }
    if (summary.skipped.length > 50) {
      lines.push(`- ... ${summary.skipped.length - 50} more`);
    }
    lines.push('');
  }

  await fs.writeFile(path.join(outputDir, 'summary.md'), lines.join('\n'), 'utf8');
}

async function writeState(paths, blocklist, manifest) {
  await fs.writeFile(paths.blocklistPath, JSON.stringify(blocklist, null, 2), 'utf8');
  await fs.writeFile(
    paths.lastRunPath,
    JSON.stringify(
      {
        generatedAt: manifest.generatedAt,
        site: manifest.site,
        archived: manifest.archived.length,
        blocked: manifest.blocked.length,
        skipped: manifest.skipped.length,
        failed: manifest.failed.length
      },
      null,
      2
    ),
    'utf8'
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const siteConfig = resolveSiteConfig(args.site, args.outputDir);
  const paths = prepareStatePaths(siteConfig.outputDir);
  await fs.mkdir(siteConfig.outputDir, { recursive: true });
  const state = await loadState(paths);

  const robotsInfo = await fetchRobots(siteConfig, args);
  if (state.blocklist.hostBlockedAt && !args.retryBlocked) {
    throw new Error(
      `Host marked as blocked on ${state.blocklist.hostBlockedAt}: ${state.blocklist.hostBlockReason}`
    );
  }

  let effectiveMinDelay = args.minDelayMs;
  const crawlDelaySeconds = robotsInfo.selectedGroup?.crawlDelay;
  if (Number.isFinite(crawlDelaySeconds) && crawlDelaySeconds > 0) {
    effectiveMinDelay = Math.max(effectiveMinDelay, Math.ceil(crawlDelaySeconds * 1000));
    args.maxDelayMs = Math.max(args.maxDelayMs, effectiveMinDelay);
  }

  const sitemapDiscovery = await discoverSitemapTargets(siteConfig, robotsInfo, args);
  const discovery =
    sitemapDiscovery.foundSitemapData && sitemapDiscovery.targets.length > 0
      ? sitemapDiscovery
      : await discoverByLinks(siteConfig, robotsInfo, args);

  const filtered = await filterTargets(discovery.targets, siteConfig, robotsInfo, args, state);
  const generatedAt = new Date().toISOString();

  if (args.dryRun) {
    const report = {
      generatedAt,
      site: siteConfig.origin,
      startUrl: siteConfig.startUrl.toString(),
      outputDir: siteConfig.outputDir,
      sitemapTypes: args.sitemapTypes,
      options: {
        includePosts: args.includePosts,
        onlyPosts: args.onlyPosts,
        includePagination: args.includePagination,
        includeSearch: args.includeSearch,
        skipExisting: args.skipExisting,
        sinceLastmod: args.sinceLastmod,
        retryBlocked: args.retryBlocked,
        fetchEngine: args.fetchEngine
      },
      crawlDelayMs: effectiveMinDelay,
      selectedSitemaps: discovery.selectedSitemaps,
      targetCount: filtered.targets.length,
      skippedCount: filtered.skipped.length,
      sampleTargets: filtered.targets.slice(0, 25),
      sampleSkipped: filtered.skipped.slice(0, 25)
    };
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  const archived = [];
  const blocked = [];
  const failed = [];
  let blockerStreak = 0;
  let abortedReason = null;

  for (let index = 0; index < filtered.targets.length; index += 1) {
    const target = filtered.targets[index];
    const delayMs = index === 0 ? 0 : randomBetween(effectiveMinDelay, args.maxDelayMs);
    if (delayMs > 0) {
      await sleep(delayMs);
    }

    try {
      const result = await renderPage(target, args);
      if (result.status === 'blocked') {
        blockerStreak += 1;
        const diagnosticPath = await writeBlockedDiagnostic(siteConfig.outputDir, target, result);
        const timesSeen = noteBlockedUrl(state.blocklist, target.url, result.blocker);
        maybeEscalateHostBlock(state.blocklist, result.blocker.fingerprint, timesSeen);
        blocked.push({
          url: target.url,
          sitemap: target.sitemap,
          diagnostic: diagnosticPath,
          blocker: result.blocker,
          statusCode: result.statusCode
        });
        console.error(`[${index + 1}/${filtered.targets.length}] blocked ${target.url}`);

        if (blockerStreak >= args.maxBlockerStreak) {
          abortedReason = `Aborted after ${blockerStreak} consecutive blocker pages`;
          break;
        }
        continue;
      }

      blockerStreak = 0;
      const filePath = await writeArchivedPage(siteConfig.outputDir, target, result);
      archived.push({
        url: target.url,
        file: filePath,
        title: result.title,
        sourceType: target.sourceType,
        sitemap: target.sitemap,
        wordCount: result.wordCount,
        lastmod: target.lastmod,
        fetchEngine: result.fetchEngine
      });
      console.log(`[${index + 1}/${filtered.targets.length}] archived ${target.url}`);
    } catch (error) {
      blockerStreak = 0;
      failed.push({
        url: target.url,
        sitemap: target.sitemap,
        error: error instanceof Error ? error.message : String(error)
      });
      console.error(`[${index + 1}/${filtered.targets.length}] failed ${target.url}`);
    }
  }

  const manifest = {
    generatedAt,
    site: siteConfig.origin,
    startUrl: siteConfig.startUrl.toString(),
    skillRoot: SKILL_ROOT,
    outputDir: siteConfig.outputDir,
    sitemapTypes: args.sitemapTypes,
    options: {
      includePosts: args.includePosts,
      onlyPosts: args.onlyPosts,
      includePagination: args.includePagination,
      includeSearch: args.includeSearch,
      skipExisting: args.skipExisting,
      sinceLastmod: args.sinceLastmod,
      retryBlocked: args.retryBlocked,
      fetchEngine: args.fetchEngine,
      includePatterns: args.includePatterns,
      excludePatterns: args.excludePatterns,
      linkDepth: args.linkDepth
    },
    delay: {
      minMs: effectiveMinDelay,
      maxMs: args.maxDelayMs,
      randomized: true,
      concurrency: 1
    },
    selectedSitemaps: discovery.selectedSitemaps,
    archived,
    blocked,
    skipped: filtered.skipped,
    failed,
    abortedReason
  };

  await fs.writeFile(paths.manifestPath, JSON.stringify(manifest, null, 2), 'utf8');
  await writeSummary(siteConfig.outputDir, {
    generatedAt,
    site: siteConfig.origin,
    sitemapTypes: args.sitemapTypes,
    selectedSitemaps: discovery.selectedSitemaps,
    archived,
    blocked,
    skipped: filtered.skipped,
    failed
  });
  await writeState(paths, state.blocklist, manifest);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack : String(error));
  process.exitCode = 1;
});
