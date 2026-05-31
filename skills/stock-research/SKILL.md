---
name: stock-research
description: End-to-end stock analysis for long-term investors — pulls live fundamentals/quote/earnings/analyst data (yfinance, no API key), generates public technical-analysis chart URLs (StockCharts + Finviz, no image downloads, no auth), and walks a four-question quality+valuation framework to a buy/watch/avoid verdict. Includes a second "Mainstreet" bottom-up mode (references/mainstreet-analysis.md) for monopoly / novel-business-model companies where P/E benchmarks don't apply. Use when asked to research, analyze, chart, or get a technical read on a ticker.
---

# Stock Research

A research workflow for **long-term investors** (3–5 year minimum horizon) — not traders. The edge this skill assumes is patience: accumulating shares of good companies when they're on sale and riding out volatility.

It bundles the data and chart tools, then walks a repeatable framework to a verdict. The calling agent does the analysis and synthesis — the scripts just deliver data and URLs.

## When to Use

- "research TICKER" / "analyze TICKER" / "what do you think of TICKER"
- "TA on TICKER" / "technical read on TICKER" / "chart TICKER"
- "is TICKER a buy?" / "is TICKER on sale?"
- Comparing a stock against peers
- For **monopoly / platform / brand-new-market** companies where P/E and P/S benchmarks mislead → use **Mainstreet Mode** (see below).

## Setup

```bash
bash scripts/setup.sh
```

Installs `yfinance` (the only hard dependency) and verifies Node is present. Perplexity is optional — the skill works fine with your agent's own web search.

## The Framework

Four questions, in order. The first three decide quality and price; the fourth keeps you honest about your edge.

1. **Is this an exceptional company?** Durable moat (network effects, switching costs, cost advantage, brand, IP), growing/stable revenue, no structural threat (disruption, commoditization, regulation, patent cliff).
2. **Is management good?** Capital allocation track record, guidance accuracy, insider alignment, no dilution/empire-building red flags.
3. **Is it on sale?** Default benchmarks for a *mature* company: P/E ~15, P/S ~2x. High, durable growth justifies a higher multiple — say why. Compare to the stock's own history and to peers.
4. **Is it in your circle of competence?** Do you have real domain knowledge here, or are you guessing? Outside-your-lane plays deserve small positions at most. *(Customize this to your own expertise — it's the question that's personal to the investor.)*

---

## Part 1 — Data Collection

Run these (in parallel where your harness allows). All use `yfinance`, no API key.

```bash
python3 scripts/stock-data.py quote        TICKER     # price, change, volume
python3 scripts/stock-data.py fundamentals TICKER     # P/E, P/S, market cap, margins, revenue
python3 scripts/stock-data.py earnings     TICKER     # recent + upcoming earnings, EPS estimates
python3 scripts/stock-data.py analysts     TICKER     # ratings, price targets, recommendations
python3 scripts/stock-data.py compare      TICKER,PEER1,PEER2   # side-by-side table
```

Add `--json` to any command for structured output.

**News & recent context:** use your agent's web search for recent news, the latest earnings reaction, and sector trends. If you have a Perplexity key, `scripts/perplexity.sh search --recent=week "TICKER stock news earnings"` is a convenient shortcut (optional).

**Gotchas:**
- `stock-data.py` can return stale/cached data. If a quote shows `$0` or fundamentals come back empty, re-run.
- Cross-check analyst price targets against the fundamentals — don't trust a single scraped number.
- If no peers are obvious, identify 2–3 real competitors yourself; never fabricate tickers.

---

## Part 2 — Charts (URLs, not downloads)

Generate public chart URLs — nothing is fetched. Open them, or paste them into a chat client that unfurls images.

```bash
node scripts/chart-urls.mjs TICKER            # 1yr + 3yr StockCharts + Finviz + interactive link
node scripts/chart-urls.mjs TICKER --yr=1,3,5 # pick timeframes
node scripts/chart-urls.mjs TICKER --mn=3     # 3-month zoom
node scripts/chart-urls.mjs TICKER --style=10dma   # add a 10-day MA (3yr)
node scripts/chart-urls.mjs BTC               # crypto maps to $BTCUSD
```

The StockCharts URLs use **public** chart-layout style IDs that bake in RSI(14), MACD(12,26,9), and 50/200-day MAs. Finviz is included as an independent daily cross-check. The interactive link is for a human to open and customize.

> If you want vision analysis of the chart, fetch the StockCharts image URL with a browser `User-Agent` header (it 404s on a bare request). Otherwise just emit the URLs and read the data instead.

### Reading the chart (think like an accumulator, not a day-trader)

- **Trend (the three MAs).** 50-day = medium-term, 200-day = long-term. Above both = uptrend; below 50 but above 200 = pullback in an uptrend (often good entry territory); below both = downtrend (thesis may hold, but size down). Is price bouncing off the 200-day (bullish), grinding under it (bearish), or deeply extended below it (oversold/opportunity)?
- **Support & resistance.** Current price position defines the role: a level is *support* if price is above it, *resistance* if below. A months-long support level flips to overhead resistance the moment price closes under it. Look for consolidation zones, prior swing highs/lows (3+ touches = significant), volume confirmation, gaps, and round numbers. Name **3–5 specific price levels** and what role each plays now.
- **Momentum.** RSI: oversold (<30), overbought (>70), or neutral. MACD direction and any recent crossover.

---

## Part 3 — Fundamental Research

Work the four questions using the Part 1 data plus news/filings. For each, land a verdict:

- **Exceptional company?** Strong / OK / Weak / Uncertain — moat, durability, revenue trend.
- **Good management?** Strong / OK / Weak / Unknown — capital allocation, guidance accuracy, alignment, red flags.
- **On sale?** Cheap / Fair / Expensive — P/E vs ~15, P/S vs ~2x, vs history, vs peers; if it sold off, is the thesis broken or is it an overreaction?
- **In your lane?** High / Medium / Low conviction — honest read on your domain edge.

Then:
- **Catalysts (next 12–18 months):** specific dated events — launches, earnings inflections, regulatory decisions.
- **Risks:** what breaks the thesis, ranked by probability × impact.
- **The 3–5 year thesis:** one paragraph. If you're right, where is this company in 3–5 years, and what has to be true?

---

## Output

Produce a single markdown report. (No chat-platform-specific formatting — this is portable.)

```markdown
# TICKER — Stock Research (DATE)

## Technical Read
- Charts: <1yr URL> · <3yr URL> · <Finviz URL>
- Price: $X | Mkt Cap: $X | Rev: $X (P/S X) | Net income: $X (P/E X)
- Trend: short [↑/↓] · medium [↑/↓] · long [↑/↓]
- 200-day MA: [above $X — floor] / [below $X — accumulation, X% extended]
- Key levels: $X (role), $Y (role), $Z (role)   ← 3–5, labeled support/resistance by current price
- Momentum: RSI X (state); MACD (state)
- Where I'd look to add: $X, $Y, $Z — (prior consolidation / 200-day / prior support)

## Research Brief
- 3–5yr verdict: Strong Buy / Accumulate / Watch / Avoid
- Company: [Strong/OK/Weak] — <moat / business quality, one line>
- Management: [Strong/OK/Unknown] — <one line>
- Valuation: [Cheap/Fair/Expensive] — P/E X (benchmark ~15), P/S X (benchmark ~2x)
- Trend: [Uptrend/Pullback/Downtrend] — price vs 50-day ($X) and 200-day ($X)
- In your lane: [High/Medium/Low conviction] — <domain edge, one line>
- Thesis (3–5yr): <2–3 sentences>
- Catalysts: <top 1–2 dated events>
- Main risk: <the thing most likely to break the thesis>

## Bottom Line
<3–5 sentences synthesizing charts + fundamentals. Good company at a bad price,
bad company at a good price, or something worth accumulating now? The single
most important thing to watch?>

> Not financial advice. This is an AI research tool — do your own due diligence.
```

Always include the disclaimer on substantive output.

---

## Mainstreet Mode (bottom-up valuation)

For **monopolies, platform companies, and genuinely new markets** where P/E and P/S benchmarks are misleading, switch to the bottom-up framework in [`references/mainstreet-analysis.md`](references/mainstreet-analysis.md): what they sell → who buys → units sold → unit forecast → revenue/profit model → future valuation → discount to today → margin-of-safety entry. Same data tools (`stock-data.py`, web search for TAM/units), different valuation engine.

## Tool Routing

| Need | Tool |
|------|------|
| Current price, volume | `stock-data.py quote` |
| Valuation, margins, financials | `stock-data.py fundamentals` |
| Earnings history & estimates | `stock-data.py earnings` |
| Analyst consensus, price targets | `stock-data.py analysts` |
| Compare multiple stocks | `stock-data.py compare` |
| Technical chart (URLs) | `chart-urls.mjs` |
| Recent news / earnings reaction / macro | your agent's web search (or optional `perplexity.sh`) |

## Uninstall

This skill writes no state outside its folder except the install receipt and the pip package. To remove:

```bash
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/stock-research/.installed"
pip uninstall yfinance   # only if nothing else needs it
```
