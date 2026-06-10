---
name: de-ai-design
description: Audit a Claude/AI-generated web design for the convergent "AI look" (indigo gradients, pill badges, emoji UI, hover-lift cards, scroll reveals) and replace each tell with a deliberate alternative from a chosen design genre. Evidence-based — every tell must be found in the actual CSS/JS/markup before it gets fixed.
---

# De-AI Design

Make an AI-generated design look handcrafted. This skill audits a site's actual code for the convergent design signatures LLMs default to, builds a site-specific "top tells" list with file:line evidence, then replaces each tell with a coherent alternative drawn from a real-world design genre.

The prompt pattern that birthed this skill: *"Find the top 10 Claude design signatures and then remove them from the site."* It works because it forces an audit-then-fix structure instead of a vague "make it less AI."

## Why AI designs converge

Every model-generated page trends toward the same look — purple/indigo gradient, Inter font, three feature cards with icons, rounded everything. This isn't taste; it's training data. Adam Wathan (Tailwind's creator) made `bg-indigo-500` the default button color in Tailwind UI around 2020, the scraped web filled up with it, and LLMs learned "buttons are purple" as a statistical truth. The pattern is now recognizable enough that it's called **the Purple Problem**.

Sources worth reading before a pass:

- [Why Every AI-Built Website Looks the Same (Blame Tailwind's Indigo-500)](https://dev.to/alanwest/why-every-ai-built-website-looks-the-same-blame-tailwinds-indigo-500-3h2p) — the origin story
- [Why Every AI-Generated Landing Page Looks the Same (and How to Fix It)](https://dev.to/_46ea277e677b888e0cd13/why-every-ai-generated-landing-page-looks-the-same-and-how-to-fix-it-1kmo) — the fix-it companion

## When to use

- A page or site was generated/heavily drafted by an AI agent and "looks like AI"
- Pre-launch polish pass on agent-built landing pages, dashboards, internal tools
- A client or teammate says "make it less AI" and you need a concrete, checkable plan

## When not to use

- The design is human-made and just needs normal design feedback
- A design system already governs the page (fix the system, not one page)
- You only want copy edits — this skill is visual; AI *writing* tells are a different audit

## Workflow

### 1. Audit — find the tells in the actual code

Read [`references/tells.md`](./references/tells.md) — the catalog of known tells, each with grep-able detection patterns. Run the detection greps against the site's CSS, JS, and templates.

**The list must be derived from this site, not copied from the catalog.** A tell only goes on the fix list with file:line evidence. Output of this step: the site's own "top N tells" table (typically 8–12), each row = tell, evidence (`file:line`), planned replacement.

Screenshot the current state first (hero, mid-page sections, any interactive widgets). You'll want the before/after.

### 2. Pick a replacement genre

Removal alone produces blandness — a page with the tells deleted and nothing added looks unfinished, not handcrafted. The fix is to pick a **real-world design genre** and let it supply the replacement vocabulary:

| Genre | Vocabulary it gives you |
| --- | --- |
| Print prospectus / offering memorandum | Serif body, hairline rules, numbered small-caps sections, navy ink |
| Newspaper / editorial | Column grids, heavy headline contrast, rules between stories, captions |
| Technical manual / spec sheet | Mono labels, ruled tables, figure numbers, no decoration |
| Terminal / utilitarian | System fonts, square corners, visible borders, dense layout |
| Swiss / international style | Strict grid, one accent color, flush-left type, generous whitespace |

Pick one that fits the page's content and commit to it. Every replacement in step 3 should be answerable with "what would this genre do?"

### 3. Replace each tell

Work through the audit table. Each tell gets a deliberate genre-consistent replacement, not just deletion. Examples from a real pass (offering-memorandum genre):

| Tell found | Replacement shipped |
| --- | --- |
| Pill/badge chips | Em-dash run-ins: "Managed hosting — launching now" |
| Emoji as UI (✓ bullets, 🤝) | Plain ledger lists prefixed `Incl. —` |
| Radial-gradient hero glow | Flat navy; typography does the work |
| Hover-lift card grid | Ruled grid cells, hairline borders, no motion |
| Border-radius everywhere | Square corners throughout |
| Scroll-triggered fade-ups | Deleted from JS and CSS |
| Marquee ticker | Static tombstone-style summary line |
| Mono uppercase eyebrows | Small-caps serif "Section I — Background" |
| Big-number stat boxes | Ruled columns under a heavy top rule, like a financial table |
| Backdrop-blur sticky header | Solid header with a double-rule border |

### 4. Verify

- Re-run every detection grep from step 1 — each must come back clean (or have a documented, deliberate exception)
- Lint/parse whatever you touched (CSS, JS, PHP templates)
- Screenshot the same views as step 1 and compare side by side
- Check interactive elements still work — deleting scroll-reveal JS or hover states can orphan event handlers and `opacity: 0` initial states (the classic failure: sections invisible because the reveal class never gets added)

### 5. Report

Deliver the audit table (tell → evidence → replacement), the genre chosen and why, and the before/after screenshots. If the agent's session supports memory, store the site-specific list so the next "make it fun" request starts from a less incriminating baseline.

## Notes

- **Tailwind sites:** the fastest single fix is replacing the indigo/violet palette and Inter with a deliberate palette + type pairing. Half the tells in the catalog are Tailwind defaults wearing a trench coat.
- **Don't over-rotate.** Rounded corners, gradients, and emoji aren't sins — *defaults* are. The question is always "did someone choose this, or did the model?" A deliberate gradient that fits the genre stays.
- **Copy has tells too** (triad sentences, "Built for X. Designed for Y.", relentless em-dashes). Out of scope here, but flag them in the report if they're loud.
