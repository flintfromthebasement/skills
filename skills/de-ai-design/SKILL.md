---
name: de-ai-design
description: Audit a Claude/AI-generated web design for the convergent "AI look" (indigo gradients, pill badges, emoji UI, hover-lift cards, scroll reveals, and the newer cream-and-terracotta "editorial" fix) and replace each tell with a deliberate alternative from a chosen design genre. Also covers redesigns of agent-built sites, including what must not be broken (brand assets, content, IA, working interactions). Evidence-based — every tell must be found in the actual CSS/JS/markup before it gets fixed, and the result is checked against a pre-flight list including dark-mode parity.
---

# De-AI Design

Make an AI-generated design look handcrafted. This skill audits a site's actual code for the convergent design signatures LLMs default to, builds a site-specific "top tells" list with file:line evidence, then replaces each tell with a coherent alternative drawn from a real-world design genre, and verifies nothing broke.

The prompt pattern that birthed this skill: *"Find the top 10 Claude design signatures and then remove them from the site."* It works because it forces an audit-then-fix structure instead of a vague "make it less AI."

## Why AI designs converge

Every model-generated page trends toward the same look — purple/indigo gradient, Inter font, three feature cards with icons, rounded everything. This isn't taste; it's training data. Adam Wathan (Tailwind's creator) made `bg-indigo-500` the default button color in Tailwind UI around 2020, the scraped web filled up with it, and LLMs learned "buttons are purple" as a statistical truth. The pattern is called **the Purple Problem**.

It also moves. The published fix for the first wave ("warm it up, make it editorial") was adopted wholesale by models and became the next wave: cream ground, terracotta accent, serif display, hairline rules. Any remedy applied by default becomes the next tell, which is why this skill picks a genre from the *subject* instead of handing out a replacement look.

Sources worth reading before a pass:

- [Why Every AI-Built Website Looks the Same (Blame Tailwind's Indigo-500)](https://dev.to/alanwest/why-every-ai-built-website-looks-the-same-blame-tailwinds-indigo-500-3h2p) — the origin story
- [Why Every AI-Generated Landing Page Looks the Same (and How to Fix It)](https://dev.to/_46ea277e677b888e0cd13/why-every-ai-generated-landing-page-looks-the-same-and-how-to-fix-it-1kmo) — the fix-it companion

## When to use

- A page or site was generated/heavily drafted by an AI agent and "looks like AI"
- A redesign or restyle of an agent-built site, where the content and behavior must survive
- Pre-launch polish pass on agent-built landing pages, dashboards, internal tools
- A client or teammate says "make it less AI" and you need a concrete, checkable plan

## When not to use

- The design is human-made and just needs normal design feedback
- A design system already governs the page (fix the system, not one page)
- You only want copy edits — this skill is visual; AI *writing* tells are a different audit

## Workflow

### 0. Read the brief and the project

Before touching anything, write down (one line each, decide instead of asking unless a missing fact blocks the work):

- **Subject and audience** — what this is, who lands on it, the one thing a visitor should do
- **Mood and mode** — light, dark, or both; quiet or loud; how much motion (none, feedback only, a signature move)
- **Stack** — plain CSS, Tailwind (check v3 vs v4 before touching config), CSS-in-JS; never migrate it
- **Fixed constraints** — brand colors, fonts, logo, an existing design system
- **Real imagery** — the project's own photos, product shots, real UI to show, or nothing. Don't plan around pictures that don't exist.
- **Subject inventory** — 5–8 things that belong to this client and no competitor (its name, place, materials, constraint, printed artifacts, numbers). Step 2 draws on this.

For a redesign, also fix the **preservation list** now (see "Redesign preservation" below). It is the contract for steps 3–4.

### 1. Audit — find the tells in the actual code

Read [`references/tells.md`](./references/tells.md) — the catalog of known tells, each with grep-able detection patterns. Run the detection greps against the site's CSS, JS, and templates.

**The list must be derived from this site, not copied from the catalog.** A tell only goes on the fix list with file:line evidence. Output of this step: the site's own "top N tells" table (typically 8–12), each row = tell, evidence (`file:line`), planned replacement.

Screenshot the current state first (hero, mid-page sections, interactive widgets) at 390, 768 and 1440 wide, and in dark mode if the site has one. You'll want the before/after.

### 2. Pick a replacement genre

Removal alone produces blandness — a page with the tells deleted and nothing added looks unfinished, not handcrafted. The fix is to pick a **real-world design genre** and let it supply the replacement vocabulary:

| Genre | Vocabulary it gives you |
| --- | --- |
| Print prospectus / offering memorandum | Serif body, hairline rules, numbered small-caps sections, navy ink |
| Newspaper / editorial | Column grids, heavy headline contrast, rules between stories, captions |
| Technical manual / spec sheet | Mono labels, ruled tables, figure numbers, no decoration |
| Terminal / utilitarian | System fonts, square corners, visible borders, dense layout |
| Swiss / international style | Strict grid, one accent color, flush-left type, generous whitespace |
| Industrial brutalist | Huge heavy grotesk, tight tracking, hard 1–2px borders, zero radius, one hazard-red accent; commit to light paper or dark phosphor, never both |
| Quiet product / soft modern | One neutral ground, one accent, very large type, big spacing, sections separated by tone steps instead of shadows, a few real-world details |
| Photographic / gallery | One dominant picture per screen, flat color fields sampled from the photos, minimal chrome, captions as content |

Choose from the **subject inventory, not the category**. Competitor test: if the same genre choice would suit the nearest competitor, you picked a category default. Don't reach for print/editorial because it is the safe "not AI" answer; it is now the most recognizable AI answer (tell 16). Commit to one genre and one light/dark mode. Every replacement in step 3 should be answerable with "what would this genre do?"

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

**Fill the space you opened.** Deleting ornament leaves a hole; never refill it with a different ornament. Fill it with scale (make the main thing larger), full real content (no thin sections), a flat field of color, or a real picture of this subject's world. Leave one deliberate rest per page at most.

**If the page keeps motion,** it is chosen, not default: transform and opacity only, one signature move plus feedback on controls, content visible without JS, and a `prefers-reduced-motion` fallback.

### Redesign preservation

When restyling an existing site, these survive unless the user says otherwise:

- **Brand assets** — logo, brand colors and fonts. If the brand itself uses a tell (logo on a gradient, violet accent), keep it, record it as a documented exception, and fix everything around it.
- **Content** — copy, data, images, and section completeness. Restyle presentation; don't rewrite or trim content to fit a layout. Don't invent proof (customers, quotes, stats).
- **Information architecture** — URLs, routes, nav structure, form actions, page titles and meta.
- **Working behavior** — forms, handlers, analytics, auth flows, accessibility features (skip links, ARIA, focus order). Deleting reveal JS or hover states orphans handlers.
- **The stack** — no framework or styling-library migration; check `package.json` before importing anything.

Make small, reviewable changes and re-check after each batch. Order for most impact at least risk: type and palette, then states (hover, focus, loading, empty, error), then layout and spacing, then component swaps, then polish.

### 4. Verify

Pre-flight list. Every line is checked in this session, not assumed:

- Every detection grep from step 1 comes back clean, or has a documented, deliberate exception
- Lint/parse whatever you touched (CSS, JS, PHP templates)
- Screenshots at 390 / 768 / 1440 match the step 1 views; no horizontal scroll at 390
- **Dark-mode parity** — if the site has a dark mode (`prefers-color-scheme`, `.dark`, `data-theme`), re-run the screenshots there: every new color goes through a token with a dark value, no hard-coded light-only colors left behind, muted text still 4.5:1 against its ground, no pure `#000`/`#fff` pairing unless the genre calls for it. If the site has no dark mode, don't add one
- Body text 4.5:1 or better on its ground; large type 3:1
- Interactive elements still work, with visible `:focus-visible` states; keyboard path through nav and forms intact
- No section is invisible: removing scroll-reveal JS while leaving `opacity: 0` initial CSS is the classic failure
- No placeholder content shipped (lorem ipsum, "John Doe", "Acme", `href="#"`, 99.99% figures); content from before is all still present
- Full-height sections use `min-height: 100dvh`, not `100vh`
- Preservation list from step 0 re-read and satisfied

### 5. Report

Deliver the audit table (tell → evidence → replacement), the genre chosen and why (cite the subject inventory), documented exceptions, and before/after screenshots. If the agent's session supports memory, store the site-specific list so the next "make it fun" request starts from a less incriminating baseline.

## Notes

- **Tailwind sites:** the fastest single fix is replacing the indigo/violet palette and Inter with a deliberate palette + type pairing. Half the tells in the catalog are Tailwind defaults wearing a trench coat.
- **Don't over-rotate.** Rounded corners, gradients, and emoji aren't sins — *defaults* are. The question is always "did someone choose this, or did the model?" A deliberate gradient that fits the genre stays.
- **Copy has tells too** (triad sentences, "Built for X. Designed for Y.", relentless em-dashes). Prose rewriting stays out of scope: it is a different audit with different evidence. But placeholder content is greppable markup and is in scope (tells 24–25), and loud copy tells get flagged in the report using the greps at the end of the catalog.

## Credits

The cream/terracotta third-wave tell, the subject-inventory and competitor-test ideas, redesign preservation rules, pre-flight checklist, fill-the-space principle, and several catalog entries are adapted from [Taste Skill](https://github.com/Leonxlnx/taste-skill) by Leon Lin (MIT) — see also [tasteskill.dev](https://www.tasteskill.dev/).
