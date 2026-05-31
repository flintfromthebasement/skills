# stock-research

Long-term-investor stock analysis for agents. Two modes, shared tools.

- **Standard** ([`SKILL.md`](SKILL.md)) — four-question quality + valuation framework → buy/watch/avoid verdict. Best for ordinary companies with comparable peers.
- **Mainstreet** ([`references/mainstreet-analysis.md`](references/mainstreet-analysis.md)) — bottom-up unit-economics model → discounted fair value → margin-of-safety entry. Best for monopolies / platforms / brand-new markets where P/E benchmarks mislead.

## What's bundled

| File | What it is | Needs |
|------|------------|-------|
| `scripts/stock-data.py` | Live quote / fundamentals / earnings / analysts / compare via **yfinance** | `python3`, `yfinance` |
| `scripts/chart-urls.mjs` | Generates **public** technical-analysis chart URLs (StockCharts + Finviz). No downloads, no auth. | `node` |
| `scripts/perplexity.sh` | *Optional* news/context shortcut | `PERPLEXITY_API_KEY`, `curl`, `jq` |
| `scripts/setup.sh` | Idempotent installer (install receipt) | — |

No API keys are required for the core workflow — `yfinance` is free and the chart URLs are public. Perplexity is a convenience only; the skill otherwise uses the calling agent's own web search for news.

## Quick start

```bash
bash scripts/setup.sh

python3 scripts/stock-data.py fundamentals NVDA
node    scripts/chart-urls.mjs NVDA --yr=1,3
```

Then work the framework in `SKILL.md` and emit the markdown report.

## Notes on the chart URLs

The StockCharts URLs reference **public** chart-layout style IDs that include RSI(14), MACD(12,26,9), and 50/200-day moving averages — anyone can open them, no account needed. Finviz is included as an independent daily cross-check, and an interactive StockCharts link lets a human customize. Pass `--style-id=<your-id>` to use your own saved SharpCharts layout.

To fetch a StockCharts image for vision analysis, send a browser `User-Agent` header (a bare request 404s). For most uses, just emit the URLs.

> Not financial advice. This is an AI research tool — do your own due diligence.
