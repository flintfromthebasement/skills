#!/usr/bin/env node

/**
 * chart-urls.mjs — Generate public stock-chart URLs (no image fetching).
 *
 * Emits ready-to-open chart URLs for a ticker. Nothing is downloaded — the
 * calling agent (or a human) opens the URLs, or pastes them into a chat client
 * that unfurls them as inline images.
 *
 * Two providers, no API keys, no auth:
 *   - StockCharts SharpCharts image endpoint (daily, RSI + MACD + 50/200-day MA)
 *   - Finviz daily candle image (with overlays) as an independent cross-check
 *   - StockCharts interactive page (for a human to open and customize)
 *
 * The StockCharts style IDs below are PUBLIC chart-layout configs — they
 * reference a saved indicator set (RSI, MACD, 50/200-day MAs), not an account.
 * Anyone can open them. Swap in your own saved SharpCharts style ID via
 * --style-id=... if you have a layout you prefer.
 *
 * Usage (CLI):
 *   node chart-urls.mjs AAPL                  → 1yr + 3yr URLs (default)
 *   node chart-urls.mjs AAPL --yr=1,3,5       → those timeframes
 *   node chart-urls.mjs AAPL --mn=3           → 3-month zoom
 *   node chart-urls.mjs AAPL --style=10dma    → add a 10-day MA (3yr style)
 *   node chart-urls.mjs AAPL --style-id=xxxxx → use your own SharpCharts style ID
 *   node chart-urls.mjs AAPL --json           → structured output
 *   node chart-urls.mjs BTC                   → crypto: maps to $BTCUSD
 *
 * Usage (module):
 *   import { buildStockChartsUrl, buildFinvizUrl, buildChartSet } from './chart-urls.mjs';
 */

// --- Public StockCharts style presets (RSI, MACD, 50/200-day MAs baked in) ---
const STYLE_PRESETS = {
  default: {
    1: 'p41790266871',   // 1yr: RSI, MACD, 50/200-day MAs
    3: 't7707536376c',   // 3yr: RSI, MACD, 50/200-day MAs
    fallback: 'p41790266871',
  },
  '10dma': {
    3: 't2518728970c',   // 3yr: RSI, MACD, 50/200/10-day MAs
    fallback: 't2518728970c',
  },
};

// Crypto and other symbols that differ on StockCharts vs standard notation.
const TICKER_OVERRIDES = {
  BTC: '$BTCUSD',
  BTCUSD: '$BTCUSD',
  ETH: '$ETHUSD',
  ETHUSD: '$ETHUSD',
};

function resolveTicker(ticker) {
  const key = ticker.toUpperCase();
  return TICKER_OVERRIDES[key] || key;
}

/**
 * Build a StockCharts SharpCharts image URL.
 * @param {string} ticker
 * @param {object} opts
 * @param {number} [opts.yr=1]  years of history
 * @param {number} [opts.mn=0]  months (use with yr=0 for sub-year views)
 * @param {string} [opts.style='default']  preset name
 * @param {string} [opts.styleId]  explicit SharpCharts style ID (overrides preset)
 * @param {number} [opts.cacheBust]  optional r= value (defaults to a fixed value)
 */
export function buildStockChartsUrl(ticker, { yr = 1, mn = 0, style = 'default', styleId, cacheBust } = {}) {
  const sc = resolveTicker(ticker);
  const preset = STYLE_PRESETS[style] || STYLE_PRESETS.default;
  const id = styleId || preset[yr] || preset.fallback;
  const useMonths = mn > 0 && yr === 0;
  const yrParam = useMonths ? 0 : yr;
  const mnParam = useMonths ? mn : 0;
  const r = cacheBust ?? 1; // r= just busts caches; a constant is fine for a URL you paste
  return `https://stockcharts.com/c-sc/sc?s=${encodeURIComponent(sc)}&p=D&yr=${yrParam}&mn=${mnParam}&dy=0&i=${id}&r=${r}`;
}

/**
 * Build a Finviz daily candle image URL (independent cross-check chart).
 * ty=c candles, ta=1 technical overlays (MAs, RSI, MACD), p=d daily.
 */
export function buildFinvizUrl(ticker) {
  const t = ticker.toUpperCase();
  return `https://charts2.finviz.com/chart.ashx?t=${encodeURIComponent(t)}&ty=c&ta=1&p=d&s=l`;
}

/** Build the StockCharts interactive page URL (for a human to open + customize). */
export function buildStockChartsPageUrl(ticker) {
  return `https://stockcharts.com/h-sc/ui?s=${encodeURIComponent(resolveTicker(ticker))}`;
}

/**
 * Build a full set of chart URLs for a ticker across the requested timeframes.
 * @returns {{ticker, resolved, charts: Array<{label, stockcharts, finviz?}>, interactive, finvizPage}}
 */
export function buildChartSet(ticker, { years = [1, 3], mn = 0, style = 'default', styleId } = {}) {
  const charts = [];
  if (mn > 0) {
    charts.push({
      label: `${mn}mo`,
      stockcharts: buildStockChartsUrl(ticker, { yr: 0, mn, style, styleId }),
    });
  }
  for (const yr of years) {
    charts.push({
      label: `${yr}yr`,
      stockcharts: buildStockChartsUrl(ticker, { yr, style, styleId }),
    });
  }
  return {
    ticker: ticker.toUpperCase(),
    resolved: resolveTicker(ticker),
    charts,
    finviz: buildFinvizUrl(ticker),
    interactive: buildStockChartsPageUrl(ticker),
  };
}

// --- CLI ---
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const ticker = args.find(a => !a.startsWith('--'));
  if (!ticker) {
    console.error('Usage: node chart-urls.mjs <TICKER> [--yr=1,3] [--mn=N] [--style=default|10dma] [--style-id=ID] [--json]');
    process.exit(1);
  }
  const yrArg = args.find(a => a.startsWith('--yr='))?.split('=')[1];
  const years = yrArg ? yrArg.split(',').map(n => parseInt(n, 10)).filter(Boolean) : [1, 3];
  const mn = parseInt(args.find(a => a.startsWith('--mn='))?.split('=')[1] ?? '0', 10);
  const style = args.find(a => a.startsWith('--style='))?.split('=')[1] ?? 'default';
  const styleId = args.find(a => a.startsWith('--style-id='))?.split('=')[1];
  const asJson = args.includes('--json');

  const set = buildChartSet(ticker, { years, mn, style, styleId });

  if (asJson) {
    console.log(JSON.stringify(set, null, 2));
  } else {
    console.log(`${set.ticker}${set.resolved !== set.ticker ? ` (StockCharts: ${set.resolved})` : ''} — chart URLs\n`);
    for (const c of set.charts) {
      console.log(`  ${c.label.padEnd(5)} StockCharts: ${c.stockcharts}`);
    }
    console.log(`\n  Finviz (daily, cross-check): ${set.finviz}`);
    console.log(`  Interactive (open + customize): ${set.interactive}`);
  }
}
