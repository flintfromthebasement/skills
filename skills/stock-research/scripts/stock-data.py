#!/usr/bin/env python3
"""stock-data.py — CLI tool for live stock fundamentals via yfinance.

Usage:
  stock-data.py quote NVDA              # Current price, change, volume
  stock-data.py fundamentals NVDA       # P/E, market cap, revenue, EPS, margins
  stock-data.py earnings NVDA           # Recent + upcoming earnings, EPS estimates
  stock-data.py analysts NVDA           # Analyst ratings, price targets, recommendations
  stock-data.py compare NVDA,AMD,TSM    # Side-by-side comparison table
  stock-data.py sector "semiconductors" # Top stocks in a sector

Options:
  --json    Output as JSON instead of formatted text
"""

import sys
import json
import argparse
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print("Error: yfinance not installed. Run: pip install yfinance", file=sys.stderr)
    sys.exit(1)


def fmt_num(n, prefix="", suffix="", decimals=2):
    """Format a number with optional prefix/suffix, handling None."""
    if n is None:
        return "N/A"
    if abs(n) >= 1e12:
        return f"{prefix}{n/1e12:.{decimals}f}T{suffix}"
    if abs(n) >= 1e9:
        return f"{prefix}{n/1e9:.{decimals}f}B{suffix}"
    if abs(n) >= 1e6:
        return f"{prefix}{n/1e6:.{decimals}f}M{suffix}"
    if abs(n) >= 1e3:
        return f"{prefix}{n/1e3:.{decimals}f}K{suffix}"
    return f"{prefix}{n:.{decimals}f}{suffix}"


def fmt_pct(n):
    """Format as percentage."""
    if n is None:
        return "N/A"
    return f"{n * 100:.2f}%"


def fmt_price(n):
    """Format as dollar price."""
    if n is None:
        return "N/A"
    return f"${n:.2f}"


def safe_get(info, *keys, default=None):
    """Safely get nested dict values."""
    for key in keys:
        if isinstance(info, dict):
            info = info.get(key, default)
        else:
            return default
    return info if info is not None else default


def cmd_quote(ticker_str, as_json=False):
    """Current price, change, volume."""
    ticker = yf.Ticker(ticker_str)
    info = ticker.info

    data = {
        "symbol": ticker_str.upper(),
        "name": safe_get(info, "shortName", default=ticker_str.upper()),
        "price": safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice"),
        "previous_close": safe_get(info, "previousClose") or safe_get(info, "regularMarketPreviousClose"),
        "open": safe_get(info, "open") or safe_get(info, "regularMarketOpen"),
        "day_high": safe_get(info, "dayHigh") or safe_get(info, "regularMarketDayHigh"),
        "day_low": safe_get(info, "dayLow") or safe_get(info, "regularMarketDayLow"),
        "volume": safe_get(info, "volume") or safe_get(info, "regularMarketVolume"),
        "market_cap": safe_get(info, "marketCap"),
        "52w_high": safe_get(info, "fiftyTwoWeekHigh"),
        "52w_low": safe_get(info, "fiftyTwoWeekLow"),
        "exchange": safe_get(info, "exchange"),
        "currency": safe_get(info, "currency", default="USD"),
    }

    # Calculate change
    if data["price"] and data["previous_close"]:
        data["change"] = data["price"] - data["previous_close"]
        data["change_pct"] = data["change"] / data["previous_close"]
    else:
        data["change"] = None
        data["change_pct"] = None

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    change_str = ""
    if data["change"] is not None:
        sign = "+" if data["change"] >= 0 else ""
        change_str = f"  {sign}{data['change']:.2f} ({sign}{data['change_pct']*100:.2f}%)"

    print(f"{'='*50}")
    print(f"  {data['name']} ({data['symbol']})")
    print(f"{'='*50}")
    print(f"  Price:        {fmt_price(data['price'])}{change_str}")
    print(f"  Open:         {fmt_price(data['open'])}")
    print(f"  Day Range:    {fmt_price(data['day_low'])} - {fmt_price(data['day_high'])}")
    print(f"  52W Range:    {fmt_price(data['52w_low'])} - {fmt_price(data['52w_high'])}")
    print(f"  Volume:       {fmt_num(data['volume'])}")
    print(f"  Market Cap:   {fmt_num(data['market_cap'], prefix='$')}")
    print(f"  Exchange:     {data['exchange'] or 'N/A'}")


def cmd_fundamentals(ticker_str, as_json=False):
    """P/E, market cap, revenue, EPS, margins."""
    ticker = yf.Ticker(ticker_str)
    info = ticker.info

    data = {
        "symbol": ticker_str.upper(),
        "name": safe_get(info, "shortName", default=ticker_str.upper()),
        "sector": safe_get(info, "sector"),
        "industry": safe_get(info, "industry"),
        "market_cap": safe_get(info, "marketCap"),
        "enterprise_value": safe_get(info, "enterpriseValue"),
        "trailing_pe": safe_get(info, "trailingPE"),
        "forward_pe": safe_get(info, "forwardPE"),
        "peg_ratio": safe_get(info, "pegRatio"),
        "price_to_book": safe_get(info, "priceToBook"),
        "price_to_sales": safe_get(info, "priceToSalesTrailing12Months"),
        "ev_to_ebitda": safe_get(info, "enterpriseToEbitda"),
        "ev_to_revenue": safe_get(info, "enterpriseToRevenue"),
        "revenue": safe_get(info, "totalRevenue"),
        "revenue_growth": safe_get(info, "revenueGrowth"),
        "gross_margins": safe_get(info, "grossMargins"),
        "operating_margins": safe_get(info, "operatingMargins"),
        "profit_margins": safe_get(info, "profitMargins"),
        "ebitda": safe_get(info, "ebitda"),
        "net_income": safe_get(info, "netIncomeToCommon"),
        "eps_trailing": safe_get(info, "trailingEps"),
        "eps_forward": safe_get(info, "forwardEps"),
        "dividend_yield": safe_get(info, "dividendYield"),
        "dividend_rate": safe_get(info, "dividendRate"),
        "payout_ratio": safe_get(info, "payoutRatio"),
        "beta": safe_get(info, "beta"),
        "shares_outstanding": safe_get(info, "sharesOutstanding"),
        "float_shares": safe_get(info, "floatShares"),
        "short_ratio": safe_get(info, "shortRatio"),
        "debt_to_equity": safe_get(info, "debtToEquity"),
        "current_ratio": safe_get(info, "currentRatio"),
        "return_on_equity": safe_get(info, "returnOnEquity"),
        "return_on_assets": safe_get(info, "returnOnAssets"),
        "free_cash_flow": safe_get(info, "freeCashflow"),
    }

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"{'='*60}")
    print(f"  {data['name']} ({data['symbol']}) — Fundamentals")
    print(f"{'='*60}")
    print(f"  Sector:       {data['sector'] or 'N/A'}")
    print(f"  Industry:     {data['industry'] or 'N/A'}")
    print()
    print(f"  --- Valuation ---")
    print(f"  Market Cap:       {fmt_num(data['market_cap'], prefix='$')}")
    print(f"  Enterprise Value: {fmt_num(data['enterprise_value'], prefix='$')}")
    print(f"  Trailing P/E:     {fmt_num(data['trailing_pe']) if data['trailing_pe'] else 'N/A'}")
    print(f"  Forward P/E:      {fmt_num(data['forward_pe']) if data['forward_pe'] else 'N/A'}")
    print(f"  PEG Ratio:        {fmt_num(data['peg_ratio']) if data['peg_ratio'] else 'N/A'}")
    print(f"  P/B:              {fmt_num(data['price_to_book']) if data['price_to_book'] else 'N/A'}")
    print(f"  P/S:              {fmt_num(data['price_to_sales']) if data['price_to_sales'] else 'N/A'}")
    print(f"  EV/EBITDA:        {fmt_num(data['ev_to_ebitda']) if data['ev_to_ebitda'] else 'N/A'}")
    print(f"  EV/Revenue:       {fmt_num(data['ev_to_revenue']) if data['ev_to_revenue'] else 'N/A'}")
    print()
    print(f"  --- Income ---")
    print(f"  Revenue (TTM):    {fmt_num(data['revenue'], prefix='$')}")
    print(f"  Revenue Growth:   {fmt_pct(data['revenue_growth'])}")
    print(f"  EBITDA:           {fmt_num(data['ebitda'], prefix='$')}")
    print(f"  Net Income:       {fmt_num(data['net_income'], prefix='$')}")
    print(f"  EPS (TTM):        {fmt_price(data['eps_trailing']) if data['eps_trailing'] else 'N/A'}")
    print(f"  EPS (Fwd):        {fmt_price(data['eps_forward']) if data['eps_forward'] else 'N/A'}")
    print()
    print(f"  --- Margins ---")
    print(f"  Gross:            {fmt_pct(data['gross_margins'])}")
    print(f"  Operating:        {fmt_pct(data['operating_margins'])}")
    print(f"  Profit:           {fmt_pct(data['profit_margins'])}")
    print()
    print(f"  --- Returns & Health ---")
    print(f"  ROE:              {fmt_pct(data['return_on_equity'])}")
    print(f"  ROA:              {fmt_pct(data['return_on_assets'])}")
    print(f"  Free Cash Flow:   {fmt_num(data['free_cash_flow'], prefix='$')}")
    print(f"  Debt/Equity:      {fmt_num(data['debt_to_equity']) if data['debt_to_equity'] else 'N/A'}")
    print(f"  Current Ratio:    {fmt_num(data['current_ratio']) if data['current_ratio'] else 'N/A'}")
    print(f"  Beta:             {fmt_num(data['beta']) if data['beta'] else 'N/A'}")
    print()
    print(f"  --- Dividends ---")
    div_yield = f"{data['dividend_yield']:.2f}%" if data['dividend_yield'] is not None else "N/A"
    print(f"  Yield:            {div_yield}")
    print(f"  Annual Rate:      {fmt_price(data['dividend_rate']) if data['dividend_rate'] else 'N/A'}")
    print(f"  Payout Ratio:     {fmt_pct(data['payout_ratio'])}")
    print()
    print(f"  --- Shares ---")
    print(f"  Outstanding:      {fmt_num(data['shares_outstanding'])}")
    print(f"  Float:            {fmt_num(data['float_shares'])}")
    print(f"  Short Ratio:      {fmt_num(data['short_ratio']) if data['short_ratio'] else 'N/A'}")


def cmd_earnings(ticker_str, as_json=False):
    """Recent + upcoming earnings, EPS estimates."""
    ticker = yf.Ticker(ticker_str)
    info = ticker.info

    data = {
        "symbol": ticker_str.upper(),
        "name": safe_get(info, "shortName", default=ticker_str.upper()),
        "earnings_history": [],
        "next_earnings_date": None,
    }

    # Get earnings history
    try:
        earnings_df = ticker.earnings_dates
        if earnings_df is not None and not earnings_df.empty:
            for date_idx, row in earnings_df.head(8).iterrows():
                entry = {
                    "date": str(date_idx.date()) if hasattr(date_idx, 'date') else str(date_idx),
                    "eps_estimate": None,
                    "eps_actual": None,
                    "surprise_pct": None,
                }
                if "EPS Estimate" in row:
                    v = row["EPS Estimate"]
                    entry["eps_estimate"] = float(v) if v == v else None  # NaN check
                if "Reported EPS" in row:
                    v = row["Reported EPS"]
                    entry["eps_actual"] = float(v) if v == v else None
                if "Surprise(%)" in row:
                    v = row["Surprise(%)"]
                    entry["surprise_pct"] = float(v) if v == v else None
                data["earnings_history"].append(entry)
    except Exception:
        pass

    # Next earnings date
    try:
        cal = ticker.calendar
        if cal is not None:
            if isinstance(cal, dict) and "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                if dates:
                    data["next_earnings_date"] = str(dates[0]) if isinstance(dates, list) else str(dates)
    except Exception:
        pass

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"{'='*60}")
    print(f"  {data['name']} ({data['symbol']}) — Earnings")
    print(f"{'='*60}")

    if data["next_earnings_date"]:
        print(f"  Next Earnings: {data['next_earnings_date']}")
        print()

    if data["earnings_history"]:
        print(f"  {'Date':<14} {'Estimate':>10} {'Actual':>10} {'Surprise':>10}")
        print(f"  {'-'*14} {'-'*10} {'-'*10} {'-'*10}")
        for e in data["earnings_history"]:
            est = fmt_price(e["eps_estimate"]) if e["eps_estimate"] is not None else "N/A"
            act = fmt_price(e["eps_actual"]) if e["eps_actual"] is not None else "—"
            surp = f"{e['surprise_pct']:+.2f}%" if e["surprise_pct"] is not None else "—"
            print(f"  {e['date']:<14} {est:>10} {act:>10} {surp:>10}")
    else:
        print("  No earnings data available.")


def cmd_analysts(ticker_str, as_json=False):
    """Analyst ratings, price targets, recommendations."""
    ticker = yf.Ticker(ticker_str)
    info = ticker.info

    data = {
        "symbol": ticker_str.upper(),
        "name": safe_get(info, "shortName", default=ticker_str.upper()),
        "recommendation": safe_get(info, "recommendationKey"),
        "recommendation_mean": safe_get(info, "recommendationMean"),
        "num_analysts": safe_get(info, "numberOfAnalystOpinions"),
        "target_high": safe_get(info, "targetHighPrice"),
        "target_low": safe_get(info, "targetLowPrice"),
        "target_mean": safe_get(info, "targetMeanPrice"),
        "target_median": safe_get(info, "targetMedianPrice"),
        "current_price": safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice"),
    }

    # Calculate upside/downside
    if data["target_mean"] and data["current_price"]:
        data["upside_pct"] = (data["target_mean"] - data["current_price"]) / data["current_price"]
    else:
        data["upside_pct"] = None

    # Get recommendation trends
    data["trends"] = []
    try:
        recs = ticker.recommendations
        if recs is not None and not recs.empty:
            for _, row in recs.tail(6).iterrows():
                trend = {}
                for col in recs.columns:
                    val = row[col]
                    trend[col] = int(val) if isinstance(val, (int, float)) and val == val else str(val)
                data["trends"].append(trend)
    except Exception:
        pass

    # Get upgrades/downgrades
    data["upgrades_downgrades"] = []
    try:
        ud = ticker.upgrades_downgrades
        if ud is not None and not ud.empty:
            for date_idx, row in ud.head(10).iterrows():
                entry = {
                    "date": str(date_idx.date()) if hasattr(date_idx, 'date') else str(date_idx),
                    "firm": str(row.get("Firm", "")) if "Firm" in row else "",
                    "to_grade": str(row.get("ToGrade", "")) if "ToGrade" in row else "",
                    "from_grade": str(row.get("FromGrade", "")) if "FromGrade" in row else "",
                    "action": str(row.get("Action", "")) if "Action" in row else "",
                }
                data["upgrades_downgrades"].append(entry)
    except Exception:
        pass

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"{'='*60}")
    print(f"  {data['name']} ({data['symbol']}) — Analyst Consensus")
    print(f"{'='*60}")
    print(f"  Consensus:     {(data['recommendation'] or 'N/A').upper()}")
    print(f"  Mean Rating:   {fmt_num(data['recommendation_mean']) if data['recommendation_mean'] else 'N/A'} (1=Strong Buy, 5=Sell)")
    print(f"  # Analysts:    {data['num_analysts'] or 'N/A'}")
    print()
    print(f"  --- Price Targets ---")
    print(f"  Current:       {fmt_price(data['current_price'])}")
    print(f"  Mean Target:   {fmt_price(data['target_mean'])}")
    print(f"  Median Target: {fmt_price(data['target_median'])}")
    print(f"  Low Target:    {fmt_price(data['target_low'])}")
    print(f"  High Target:   {fmt_price(data['target_high'])}")
    if data["upside_pct"] is not None:
        sign = "+" if data["upside_pct"] >= 0 else ""
        label = "Upside" if data["upside_pct"] >= 0 else "Downside"
        print(f"  {label}:       {sign}{data['upside_pct']*100:.1f}% to mean target")

    if data["upgrades_downgrades"]:
        print()
        print(f"  --- Recent Upgrades/Downgrades ---")
        for ud in data["upgrades_downgrades"][:8]:
            action = ud["action"]
            firm = ud["firm"]
            to_g = ud["to_grade"]
            from_g = ud["from_grade"]
            date = ud["date"]
            grade_change = f"{from_g} → {to_g}" if from_g else to_g
            print(f"  {date}  {firm:<20} {action:<12} {grade_change}")


def cmd_compare(tickers_str, as_json=False):
    """Side-by-side comparison table."""
    symbols = [t.strip().upper() for t in tickers_str.split(",")]

    rows = []
    for sym in symbols:
        ticker = yf.Ticker(sym)
        info = ticker.info
        rows.append({
            "symbol": sym,
            "name": safe_get(info, "shortName", default=sym),
            "price": safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice"),
            "market_cap": safe_get(info, "marketCap"),
            "trailing_pe": safe_get(info, "trailingPE"),
            "forward_pe": safe_get(info, "forwardPE"),
            "peg_ratio": safe_get(info, "pegRatio"),
            "revenue": safe_get(info, "totalRevenue"),
            "revenue_growth": safe_get(info, "revenueGrowth"),
            "gross_margins": safe_get(info, "grossMargins"),
            "operating_margins": safe_get(info, "operatingMargins"),
            "profit_margins": safe_get(info, "profitMargins"),
            "eps_trailing": safe_get(info, "trailingEps"),
            "eps_forward": safe_get(info, "forwardEps"),
            "roe": safe_get(info, "returnOnEquity"),
            "debt_to_equity": safe_get(info, "debtToEquity"),
            "free_cash_flow": safe_get(info, "freeCashflow"),
            "dividend_yield": safe_get(info, "dividendYield"),
            "beta": safe_get(info, "beta"),
            "recommendation": safe_get(info, "recommendationKey"),
            "target_mean": safe_get(info, "targetMeanPrice"),
        })

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return

    # Build table
    col_width = max(14, max(len(r["symbol"]) + 2 for r in rows))

    def row_line(label, key, fmt_fn=str):
        vals = []
        for r in rows:
            v = r.get(key)
            vals.append(fmt_fn(v) if v is not None else "N/A")
        cols = "".join(f"{v:>{col_width}}" for v in vals)
        return f"  {label:<20}{cols}"

    header_cols = "".join(f"{r['symbol']:>{col_width}}" for r in rows)
    print(f"{'='*(22 + col_width * len(rows))}")
    print(f"  {'Metric':<20}{header_cols}")
    print(f"{'='*(22 + col_width * len(rows))}")
    print(row_line("Price", "price", fmt_price))
    print(row_line("Market Cap", "market_cap", lambda v: fmt_num(v, prefix="$")))
    print(row_line("Trailing P/E", "trailing_pe", lambda v: f"{v:.1f}"))
    print(row_line("Forward P/E", "forward_pe", lambda v: f"{v:.1f}"))
    print(row_line("PEG Ratio", "peg_ratio", lambda v: f"{v:.2f}"))
    print(row_line("Revenue (TTM)", "revenue", lambda v: fmt_num(v, prefix="$")))
    print(row_line("Rev Growth", "revenue_growth", fmt_pct))
    print(row_line("Gross Margin", "gross_margins", fmt_pct))
    print(row_line("Op Margin", "operating_margins", fmt_pct))
    print(row_line("Profit Margin", "profit_margins", fmt_pct))
    print(row_line("EPS (TTM)", "eps_trailing", fmt_price))
    print(row_line("EPS (Fwd)", "eps_forward", fmt_price))
    print(row_line("ROE", "roe", fmt_pct))
    print(row_line("D/E Ratio", "debt_to_equity", lambda v: f"{v:.1f}"))
    print(row_line("FCF", "free_cash_flow", lambda v: fmt_num(v, prefix="$")))
    print(row_line("Div Yield", "dividend_yield", lambda v: f"{v:.2f}%"))
    print(row_line("Beta", "beta", lambda v: f"{v:.2f}"))
    print(row_line("Consensus", "recommendation", lambda v: v.upper()))
    print(row_line("Target Price", "target_mean", fmt_price))


def cmd_sector(sector_query, as_json=False):
    """Top stocks in a sector via predefined mappings."""
    # Sector -> representative tickers mapping
    sector_map = {
        "semiconductors": ["NVDA", "AMD", "TSM", "AVGO", "INTC", "QCOM", "MU", "ASML", "TXN", "MRVL"],
        "semis": ["NVDA", "AMD", "TSM", "AVGO", "INTC", "QCOM", "MU", "ASML", "TXN", "MRVL"],
        "cloud": ["AMZN", "MSFT", "GOOGL", "SNOW", "NET", "DDOG", "MDB", "CRWD"],
        "ai": ["NVDA", "MSFT", "GOOGL", "META", "AMZN", "AMD", "PLTR", "AI", "PATH", "SMCI"],
        "ai infrastructure": ["NVDA", "AMD", "AVGO", "MRVL", "ANET", "VRT", "SMCI", "DELL", "EQIX", "DLR"],
        "big tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
        "faang": ["META", "AAPL", "AMZN", "NFLX", "GOOGL"],
        "mag7": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
        "magnificent 7": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
        "cybersecurity": ["CRWD", "PANW", "ZS", "FTNT", "S", "OKTA", "CYBR"],
        "ev": ["TSLA", "RIVN", "LCID", "NIO", "LI", "XPEV", "GM", "F"],
        "electric vehicles": ["TSLA", "RIVN", "LCID", "NIO", "LI", "XPEV", "GM", "F"],
        "fintech": ["SQ", "PYPL", "COIN", "AFRM", "SOFI", "NU", "HOOD"],
        "banks": ["JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "PNC"],
        "healthcare": ["UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT"],
        "biotech": ["AMGN", "GILD", "REGN", "VRTX", "MRNA", "BIIB", "ILMN"],
        "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PXD", "OXY"],
        "renewable energy": ["ENPH", "SEDG", "FSLR", "NEE", "BEP", "PLUG", "RUN"],
        "defense": ["LMT", "RTX", "NOC", "GD", "BA", "LHX", "HII"],
        "reits": ["PLD", "AMT", "EQIX", "DLR", "PSA", "SPG", "O", "WELL"],
        "retail": ["WMT", "AMZN", "COST", "TGT", "HD", "LOW", "TJX"],
        "saas": ["CRM", "ADBE", "NOW", "SHOP", "WDAY", "ZM", "TEAM", "HUBS"],
        "social media": ["META", "SNAP", "PINS", "RDDT"],
        "streaming": ["NFLX", "DIS", "WBD", "PARA", "ROKU"],
        "crypto": ["COIN", "MSTR", "MARA", "RIOT", "CLSK", "HUT"],
    }

    key = sector_query.lower().strip()
    if key not in sector_map:
        # Try partial match
        matches = [k for k in sector_map if key in k]
        if len(matches) == 1:
            key = matches[0]
        elif matches:
            if as_json:
                print(json.dumps({"error": "ambiguous", "matches": matches}))
            else:
                print(f"Ambiguous sector. Did you mean: {', '.join(matches)}?")
            return
        else:
            if as_json:
                print(json.dumps({"error": "unknown_sector", "available": sorted(sector_map.keys())}))
            else:
                print(f"Unknown sector: {sector_query}")
                print(f"Available: {', '.join(sorted(set(sector_map.keys())))}")
            return

    tickers = sector_map[key]
    print(f"Sector: {key.title()} — {len(tickers)} stocks")
    print()
    cmd_compare(",".join(tickers), as_json=as_json)


def cmd_options(ticker_str, expiry=None, moneyness="wide", opt_type="both", as_json=False):
    """Options chain with IV, OI, volume. Default: next expiry, ±15% strikes, both sides."""
    ticker = yf.Ticker(ticker_str)
    expiries = list(ticker.options or [])
    if not expiries:
        msg = {"error": "no_options", "symbol": ticker_str.upper()}
        if as_json:
            print(json.dumps(msg))
        else:
            print(f"No options available for {ticker_str.upper()}.")
        return

    if expiry and expiry not in expiries:
        msg = {"error": "invalid_expiry", "requested": expiry, "available": expiries}
        if as_json:
            print(json.dumps(msg))
        else:
            print(f"Expiry {expiry} not available. Available: {', '.join(expiries[:10])}"
                  + (f" (+{len(expiries)-10} more)" if len(expiries) > 10 else ""))
        return

    chosen_expiry = expiry or expiries[0]
    chain = ticker.option_chain(chosen_expiry)

    # Get current spot to filter by moneyness
    info = ticker.info
    spot = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice") or safe_get(info, "previousClose")

    # moneyness window
    if moneyness == "near":
        band = 0.10
    elif moneyness == "all":
        band = None
    else:  # "wide" default
        band = 0.15

    def filter_strikes(df):
        if band is None or spot is None:
            return df
        lo, hi = spot * (1 - band), spot * (1 + band)
        return df[(df["strike"] >= lo) & (df["strike"] <= hi)]

    cols = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility", "inTheMoney"]

    result = {
        "symbol": ticker_str.upper(),
        "expiry": chosen_expiry,
        "spot": spot,
        "moneyness": moneyness,
        "available_expiries": expiries[:20],
    }

    if opt_type in ("calls", "both"):
        calls = filter_strikes(chain.calls)[cols].copy()
        calls["impliedVolatility"] = (calls["impliedVolatility"] * 100).round(2)
        result["calls"] = calls.to_dict(orient="records")

    if opt_type in ("puts", "both"):
        puts = filter_strikes(chain.puts)[cols].copy()
        puts["impliedVolatility"] = (puts["impliedVolatility"] * 100).round(2)
        result["puts"] = puts.to_dict(orient="records")

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    print(f"{'='*70}")
    print(f"  {ticker_str.upper()} OPTIONS — expiry {chosen_expiry}")
    print(f"  Spot: {fmt_price(spot)} | Moneyness: {moneyness} | {len(expiries)} expiries available")
    print(f"{'='*70}")

    def print_side(label, rows):
        if not rows:
            print(f"\n  {label}: none in window")
            return
        print(f"\n  {label}")
        print(f"  {'Strike':>8} {'Last':>8} {'Bid':>8} {'Ask':>8} {'Vol':>8} {'OI':>8} {'IV%':>7} {'ITM':>5}")
        for r in rows:
            print(f"  {r['strike']:>8.2f} {r['lastPrice']:>8.2f} {r['bid']:>8.2f} {r['ask']:>8.2f} "
                  f"{int(r.get('volume') or 0):>8} {int(r.get('openInterest') or 0):>8} "
                  f"{r['impliedVolatility']:>7.2f} {'Y' if r.get('inTheMoney') else 'N':>5}")

    if "calls" in result:
        print_side("CALLS", result["calls"])
    if "puts" in result:
        print_side("PUTS", result["puts"])


def main():
    parser = argparse.ArgumentParser(
        description="Stock data CLI — live fundamentals via yfinance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # quote
    p_quote = subparsers.add_parser("quote", help="Current price, change, volume")
    p_quote.add_argument("ticker", help="Stock ticker symbol")

    # fundamentals
    p_fund = subparsers.add_parser("fundamentals", help="P/E, market cap, revenue, EPS, margins")
    p_fund.add_argument("ticker", help="Stock ticker symbol")

    # earnings
    p_earn = subparsers.add_parser("earnings", help="Recent + upcoming earnings")
    p_earn.add_argument("ticker", help="Stock ticker symbol")

    # analysts
    p_anal = subparsers.add_parser("analysts", help="Analyst ratings, price targets")
    p_anal.add_argument("ticker", help="Stock ticker symbol")

    # compare
    p_comp = subparsers.add_parser("compare", help="Side-by-side comparison")
    p_comp.add_argument("tickers", help="Comma-separated ticker symbols")

    # sector
    p_sect = subparsers.add_parser("sector", help="Top stocks in a sector")
    p_sect.add_argument("sector", help="Sector name (e.g. semiconductors, ai, cloud)")

    # options
    p_opt = subparsers.add_parser("options", help="Options chain with IV, OI, volume")
    p_opt.add_argument("ticker", help="Stock ticker symbol")
    p_opt.add_argument("--expiry", help="Expiry date YYYY-MM-DD (default: nearest)")
    p_opt.add_argument("--moneyness", choices=["near", "wide", "all"], default="wide",
                       help="Strike filter: near=±10%%, wide=±15%% (default), all=full chain")
    p_opt.add_argument("--type", dest="opt_type", choices=["calls", "puts", "both"], default="both",
                       help="calls, puts, or both (default)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "quote":
            cmd_quote(args.ticker, as_json=args.json)
        elif args.command == "fundamentals":
            cmd_fundamentals(args.ticker, as_json=args.json)
        elif args.command == "earnings":
            cmd_earnings(args.ticker, as_json=args.json)
        elif args.command == "analysts":
            cmd_analysts(args.ticker, as_json=args.json)
        elif args.command == "compare":
            cmd_compare(args.tickers, as_json=args.json)
        elif args.command == "sector":
            cmd_sector(args.sector, as_json=args.json)
        elif args.command == "options":
            cmd_options(args.ticker, expiry=args.expiry, moneyness=args.moneyness,
                        opt_type=args.opt_type, as_json=args.json)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
