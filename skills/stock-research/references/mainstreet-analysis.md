# Mainstreet Analysis — Bottom-Up Valuation

A second mode of the `stock-research` skill, for companies where traditional P/E and P/S benchmarks are **misleading**: monopolies, platform companies, and businesses in genuinely new markets with no real peers. Instead of comparing multiples, you understand the business from the ground up — what they sell, who buys it, how many units, how that grows — and build a revenue/profit model, then work backward to today's fair value.

Same data tools as standard mode (`scripts/stock-data.py` for price/fundamentals, your agent's web search for units/TAM/capacity). Different valuation engine.

**When to use this instead of the standard four-question framework:** the company is a near-monopoly, a platform with winner-take-most dynamics, or selling into a market that barely existed five years ago — anywhere a "P/E of 15" benchmark tells you nothing useful.

---

## The Mainstreet Questions

Ask what a smart, curious non-finance person would ask:

1. **What does this company actually sell?** Plain English. One product or a few? What does each cost? What does it do?
2. **Who buys it?** Name the customers. How many are there? Is that number growing?
3. **How many have they sold?** Recent actuals — *units*, not just revenue.
4. **How many will they sell?** Build a unit forecast 3–5 years out, constrained by reality: capacity, customer count, replacement cycles, new-product introductions.
5. **What will revenue and profit look like?** Derive revenue from the unit model. Apply a realistic margin trajectory.
6. **What's the stock worth at those numbers?** Apply P/E and P/S multiples appropriate to that *future* state.
7. **What's fair value today?** Discount the future price back to the present.
8. **What's a good margin-of-safety entry price?** Apply a 20–30% haircut to the conservative fair value.

---

## Research Steps

### Step 1 — Gather the facts

Answer each question with real data. Use your agent's web search (or `scripts/perplexity.sh search ...` if you have a key) for:

- products, unit prices, revenue breakdown
- key customers, revenue concentration
- units shipped/sold in recent full years (annual report / 10-K)
- production capacity, roadmap, future product pipeline
- analyst revenue/earnings estimates for the next 3 years

Pull current price context:

```bash
python3 scripts/stock-data.py quote        TICKER
python3 scripts/stock-data.py fundamentals TICKER
```

### Step 2 — Build the unit model

Start with **units**, not revenue. For each product line:

- units sold in the most recent full year
- ASP (average selling price)
- realistic annual unit growth (constrained by customer count, capacity, penetration, replacement cycles)
- new products that could expand units or ASP

Build a table:

| Year | Product A Units | ASP | Product A Rev | Product B Units | ASP | Product B Rev | Services/Other | Total Rev | Net Margin | Net Income |
|------|-----------------|-----|---------------|-----------------|-----|---------------|----------------|-----------|------------|------------|
| 20XX (actual) | | | | | | | | | | |
| 20XX+1 | | | | | | | | | | |
| 20XX+2 | | | | | | | | | | |
| 20XX+3 | | | | | | | | | | |

Be conservative. **Label every assumption explicitly** and note what has to be true for the model to hold.

### Step 3 — Derive future valuation

At the 3–5 year revenue and profit estimates:

- **P/E based:** at Xx (conservative/mature) → $Y/share; at Xx (growth premium, if warranted) → $Y/share
- **P/S based:** at Xx (conservative) → $Y/share; at Xx (justified by moat) → $Y/share

State the multiple rationale — why is this multiple appropriate for *this* business at *that* stage?

### Step 4 — Discount to today

Using a required annual return (10% is a common hurdle rate; adjust to yours):

- bear-case future price ÷ (1.10)^N = today's bear fair value
- bull-case future price ÷ (1.10)^N = today's bull fair value

State the midpoint fair-value range.

### Step 5 — Margin of safety

Apply to the **bear-case** fair value:

- 20% haircut → first entry target
- 30% haircut → strong-conviction entry target

State what the current price implies: is the market pricing in cycle risk, competitive risk, geopolitical risk?

### Step 6 — Key risks to the unit model

Be specific and rank by probability × impact:

- **Demand** — customers pause capex, market saturates
- **Supply** — can't manufacture fast enough, or a rival appears
- **Geopolitical** — export controls, tariffs, sanctions
- **Technology** — the product gets disrupted/obsoleted
- **Concentration** — too few customers

---

## Output

A single markdown report:

```markdown
# TICKER — Mainstreet Analysis (DATE)

## Built From the Ground Up

**What they sell:** <plain English — products, prices, what they do>
**Who buys:** <named customers, concentration, addressable buyer count>
**How many sold (most recent year):** <units by product line, revenue derived>

### The 3–5 Year Build

| Year | [Product] Units | [Product] Units | Services | Total Rev | Net Margin | Net Income |
|------|-----------------|-----------------|----------|-----------|------------|------------|
| <actuals + projections> |

_Key assumption: X. What needs to be true: Y._

### What's the stock worth then?
At [Year] (~$X net income, ~$X revenue):
- Xx P/E (rationale) → $X/share
- Xx P/E (rationale) → $X/share
- Xx P/S (rationale) → $X/share

[Year] fair-value range: $X–$X

### Fair value today
Discounted back N years at 10%:
- Bear: ~$X
- Bull: ~$X
Midpoint: ~$X–$X
Current price ($X) implies the market is pricing in: <what the discount implies>

### Margin-of-safety entry
- 20% haircut on bear case: ~$X ← first entry
- 30% haircut on bear case: ~$X ← strong conviction

## Bottom Line
<3–4 sentences. Great business at a fair price, fair business at a great price, or
great business still expensive after the pullback? The one number to watch (unit
shipments, capex guidance, a specific customer)? The entry plan?>

> Not financial advice. This is an AI research tool — do your own due diligence.
```

---

## Gotchas

- Don't use this for mature companies — the standard four-question framework in `SKILL.md` is better for those.
- Unit-economics assumptions are highly sensitive. Always show your math and flag which inputs are reported vs. estimated.
- TAM estimates vary wildly across sources. Use the most conservative credible source and note the range.
