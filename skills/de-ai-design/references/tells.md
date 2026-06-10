# AI Design Tells Catalog

The convergent design signatures LLM-generated sites default to, with detection patterns and replacement directions. Run the greps against the site's CSS / JS / templates; a tell only goes on the fix list with `file:line` evidence.

Background reading:

- [Why Every AI-Built Website Looks the Same (Blame Tailwind's Indigo-500)](https://dev.to/alanwest/why-every-ai-built-website-looks-the-same-blame-tailwinds-indigo-500-3h2p)
- [Why Every AI-Generated Landing Page Looks the Same (and How to Fix It)](https://dev.to/_46ea277e677b888e0cd13/why-every-ai-generated-landing-page-looks-the-same-and-how-to-fix-it-1kmo)

Detection greps below assume `grep -rn` over the site's asset/template directories. Adjust paths and extensions to the stack (plain CSS, Tailwind classes in markup, CSS-in-JS).

## The big three (the "Purple Problem" core)

### 1. Indigo/violet gradient palette

The single loudest tell. `bg-indigo-500` was Tailwind UI's default button for years; the models learned it as "what buttons look like."

```bash
grep -rniE '#(6366f1|818cf8|8b5cf6|7c3aed|a855f7|c084fc|4f46e5|6d28d9)|indigo|violet-[0-9]|purple-[0-9]' assets/ templates/
```

**Replace with:** a palette chosen from the genre — ink + paper neutrals with one deliberate accent. If the brand has colors, use the brand's.

### 2. Inter (or default sans) for everything

```bash
grep -rniE "font-family[^;]*(inter|plus jakarta|space grotesk|poppins)" assets/
```

**Replace with:** a deliberate pairing. Serif body if the genre supports it; otherwise a system stack or a face someone actually picked. One display face + one text face, max.

### 3. Three feature cards with icons

The icon / bold-title / two-line-blurb card, times three, in a grid.

```bash
grep -rnE 'grid-template-columns:\s*repeat\(3' assets/
grep -rniE 'feature-(card|grid|box)|card-icon' templates/ assets/
```

**Replace with:** ruled rows, a numbered list, an editorial two-column layout — anything where the content's actual shape (3 items? 4? 6?) drives the layout instead of the template.

## Component tells

### 4. Pill/badge chips

Fully-rounded little labels ("NEW", "BETA", category chips) sprinkled everywhere.

```bash
grep -rnE 'border-radius:\s*(999|9999|99)px|rounded-full' assets/ templates/
grep -rniE 'class="[^"]*(chip|pill|badge|tag)' templates/
```

**Replace with:** em-dash run-ins ("Managed hosting — launching now"), parentheticals, or small-caps inline labels.

### 5. Emoji as UI

✓ as bullet glyphs, 🚀 in headings, decorative emoji in buttons and footers.

```bash
grep -rnP '[\x{1F300}-\x{1FAFF}\x{2700}-\x{27BF}\x{2600}-\x{26FF}]' templates/ assets/*.js
```

**Replace with:** typographic structure — real list markers, `Incl. —` ledger prefixes, numbered items. If an icon is genuinely needed, use a drawn icon set, consistently.

### 6. Big-number stat boxes

"10,000+ users" / "99.9% uptime" counters in rounded boxes, often with a count-up animation.

```bash
grep -rniE 'stat-(box|card|grid)|count-?up|data-count' templates/ assets/
```

**Replace with:** a ruled financial-table treatment — figures in columns under a heavy top rule, sourced and captioned. Numbers gain credibility from restraint.

### 7. Marquee / logo ticker

Infinite horizontal scroll of logos or phrases.

```bash
grep -rniE 'marquee|ticker' templates/ assets/
grep -rnE '@keyframes\s+(scroll|slide|marquee)' assets/
```

**Replace with:** a static line. A tombstone-style summary or a plain "as seen in" row reads as confidence; motion reads as filler.

### 8. Mono/uppercase "eyebrow" kickers

Tiny letterspaced all-caps label above every heading.

```bash
grep -rnE 'text-transform:\s*uppercase' assets/ | grep -iE 'eyebrow|kicker|label|overline'
grep -rniE 'class="[^"]*(eyebrow|kicker|overline)' templates/
```

**Replace with:** numbered small-caps section headings ("Section I — Background"), or just delete them — most eyebrows restate the heading below.

## Effect tells

### 9. Gradient glows and gradient text

Radial glow blobs behind heroes; `background-clip: text` gradient headlines.

```bash
grep -rnE '(radial|conic)-gradient|background-clip:\s*text|text-fill-color' assets/
```

**Replace with:** flat color fields and typographic hierarchy. If the hero needs weight, give it scale or contrast, not glow.

### 10. Hover-lift cards

`translateY(-4px)` + grown shadow on every card.

```bash
grep -rnE 'hover[^{]*\{[^}]*translateY\(-|hover:-translate-y' assets/ templates/
```

**Replace with:** no motion, or an honest affordance (underline, background tint) only on elements that are actually links.

### 11. Scroll-triggered fade-up reveals

Sections animate in as you scroll; `IntersectionObserver` + `opacity: 0` initial states.

```bash
grep -rniE 'IntersectionObserver|data-aos|fade-(up|in)|\breveal\b' assets/ templates/
```

**Replace with:** delete it — content should be visible on load. **Verify carefully:** removing the reveal JS while leaving `opacity: 0` initial CSS makes sections permanently invisible. Remove both halves.

### 12. Backdrop-blur sticky header (glassmorphism)

```bash
grep -rnE 'backdrop-filter|bg-opacity|rgba\(255,\s*255,\s*255,\s*0?\.[0-9]' assets/
```

**Replace with:** a solid header with a real border (a double rule, a hairline). Frosted glass is the default; opacity is a choice.

### 13. Border-radius on everything

Not any one radius — the *uniformity*. Cards, buttons, inputs, images, all at 8–16px.

```bash
grep -rcE 'border-radius' assets/*.css   # count per file; high count = tell
```

**Replace with:** square corners as the default; radius only where the genre justifies it (and then one consistent value with a reason).

### 14. Soft shadow on every surface

`box-shadow: 0 4px 6px rgba(0,0,0,0.1)`-style elevation everywhere, making the page float in layers.

```bash
grep -rcE 'box-shadow' assets/*.css
```

**Replace with:** borders and rules for separation. Print genres separate with lines, not depth.

### 15. Generic dark-mode-first slate

`bg-slate-900` / `#0f172a` page background with light text and glowing accents — the default "AI SaaS" night look.

```bash
grep -rniE '#0f172a|#1e293b|slate-(800|900|950)|#111827|gray-900' assets/ templates/
```

**Replace with:** a background someone chose. Paper white, warm off-white, brand-dark — anything with intent. Dark is fine; *default* dark is the tell.

## Out of scope (flag, don't fix)

Copy tells — triad sentences ("Fast. Simple. Secure."), "Built for X. Designed for Y.", relentless em-dashes, "Unlock / Unleash / Elevate" verbs. Note them in the report; fixing copy is a separate pass.
