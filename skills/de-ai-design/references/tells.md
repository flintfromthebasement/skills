# AI Design Tells Catalog

The convergent design signatures LLM-generated sites default to, with detection patterns and replacement directions. Run the greps against the site's CSS / JS / templates; a tell only goes on the fix list with `file:line` evidence.

Tells 1-15 are the classic set; 16-23 are second/third-wave and structural tells (the "fix" that became the look); 24-27 are content and craft defects. Several entries adapted from [Taste Skill](https://github.com/Leonxlnx/taste-skill) (MIT, Leon Lin).

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
grep -rnE 'blur-(2xl|3xl)|filter:\s*blur\([0-9]{2,}|(orb|blob|glow)' assets/ templates/   # decorative blobs
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

**Replace with:** delete it — content should be visible on load. (If the genre wants motion, keep one signature move; see tell 27.) **Verify carefully:** removing the reveal JS while leaving `opacity: 0` initial CSS makes sections permanently invisible. Remove both halves.

### 12. Backdrop-blur sticky header (glassmorphism)

```bash
grep -rnE 'backdrop-filter|bg-opacity|rgba\(255,\s*255,\s*255,\s*0?\.[0-9]' assets/
grep -rniE 'backdrop-blur|(fixed|sticky)[^"]*rounded-full' templates/ assets/   # floating pill nav
```

**Replace with:** a solid header with a real border (a double rule, a hairline), or a plain bar: wordmark, a few links, one action. Frosted glass and the floating pill nav are the defaults; opacity is a choice.

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
grep -rniE '#0{3}(0{3})?\b|background(-color)?:\s*black' assets/   # pure black ground
```

**Replace with:** a background someone chose. Paper white, warm off-white, brand-dark — anything with intent. Dark is fine; *default* dark is the tell. On dark: a slightly tinted deep ground (not pure `#000`), soft-light ink, depth from a lighter surface step rather than glows, and `color-scheme: dark` on the root so controls follow.

## Second- and third-wave tells

The first-wave fixes ("make it warm, make it editorial, make it premium") became the next look. These are common in sites that were already "improved" once.

### 16. Cream ground + terracotta accent ("the editorial remedy")

Yellow-cream or parchment background with rust / terracotta / clay accent, usually with a serif display face. The most recognizable AI look of 2025-26 because it was the published cure for the indigo one.

```bash
grep -rniE '#(faf[0-9a-f]{3}|f[5-9][0-9a-f]{2}e[0-9a-f]|fdf[0-9a-f]{3}|f5f0e8|f4ecd8|faf7f2)\b|\b(cream|parchment|bone|ivory)\b' assets/ templates/
grep -rniE '#(c2410c|c4623b|b45309|c1440e|d9622b|c65d3b|bc5a45|a0522d)|terracotta|\b(rust|clay)\b|burnt-?orange|amber-(600|700)|orange-(700|800)' assets/ templates/
```

Both a cream ground and a terracotta accent hitting together is the tell; either alone is a note. **Replace with:** a palette derived from the subject (its materials, its street, its landscape), a full saturated field, a cool stone, or a deep ink. Warmth from a photograph beats warmth from a hex code.

### 17. Accent word in the headline

One word in a headline set in italic serif, a different color, or underlined: "Build *better* products."

```bash
grep -rniE '<h[1-3][^>]*>[^<]*<(em|i|span)[ >]' templates/
grep -rnE 'h[1-3][^{]*(em|i|span)[^{]*\{[^}]*(font-style:\s*italic|color:|text-decoration)' assets/
```

**Replace with:** one face and one color per headline; let the words carry the emphasis.

### 18. Index numbering as decoration

01 / 02 / 03 on cards and sections, "Step 02", (001), "No. 3" with no real sequence behind it.

```bash
grep -rnE '>\s*0[1-9]\s*<|counter-increment|content:\s*"0[1-9]|Step 0?[1-9]\b' templates/ assets/
```

**Replace with:** a real `<ol>` when order matters; otherwise position, scale, or the words themselves. (A genre that actually numbers things, such as the prospectus or the manual, keeps real section numbers: the test is whether the numbers carry information.)

### 19. Status dots and agency micro-meta

"Available for work" with a pulsing green dot, local time, coordinates, version stamps, "Scroll" cues, middle-dot strings of metadata.

```bash
grep -rniE 'status-?dot|pulse|available for|now (open|booking)|local time|scroll\s*(down|↓)|©\s*20[0-9]{2}\s*[—–·]' templates/ assets/
```

**Replace with:** delete it unless the information is real and useful to a visitor (opening hours that are actually live belong; decoration doesn't).

### 20. Fake dashboard / fake product shot

Hero image built from grey bars, donut charts, and lorem-labelled widgets in a browser frame.

```bash
grep -rniE 'mock(up)?|fake-?(chart|dash)|dashboard-(preview|mock)|browser-frame|window-chrome|traffic-?lights?' templates/ assets/
```

**Replace with:** a real screenshot or a cropped real interface fragment, or no image. Never draw a product that doesn't exist.

### 21. Bento tiles and nested "double-bezel" shells

Rounded tile grid of mixed sizes as the feature section; cards wrapped in an outer shell plus an inner core with concentric radii; arrow icons nested in their own circle inside the button. The "premium" fix that became the look.

```bash
grep -rniE 'bento|col-span-[0-9]+\s+row-span' templates/ assets/
grep -rnE 'border-radius:\s*calc\(|rounded-\[calc|inset\s+0\s+1px\s+[0-9]+px\s+rgba\(255' assets/ templates/
```

**Replace with:** a composition shaped by the content (ruled rows, a split, one large item plus a list). One surface level, not a tray inside a tray.

### 22. Centered formula hero and the stock section order

Centered headline, subtitle, two buttons, screenshot below; then logo strip, three features, testimonial, pricing, CTA in that order, every section its own centered block.

```bash
grep -rcE 'text-align:\s*center|text-center|justify-center' assets/ templates/
grep -rniE 'trusted by|as seen (in|on)|logo-(strip|cloud)|testimonial' templates/
```

A high centered-count across most sections is the signal. **Replace with:** left-anchored layouts with one centered moment at most, section order that follows the argument (claim then proof), and neighbouring sections that do not share a layout.

### 23. Invented social proof

Logo walls of companies that are not clients, quoted reviews with stock names, star rows, "10,000+ teams".

```bash
grep -rniE '10,?000\+|trusted by [0-9]|★{3,}|star-rating|"[^"]{20,}"\s*[—–-]\s*[A-Z][a-z]+ [A-Z][a-z]+' templates/
```

**Replace with:** real proof the client can source, or none. If the original brief supplied it, keep it (see preservation rules); if an agent invented it, flag it in the report and remove it.

## Content and craft tells

Greppable defects that signal unfinished agent output. In scope: they are markup, not prose style.

### 24. Placeholder content

```bash
grep -rniE 'lorem ipsum|john doe|jane (doe|smith)|acme|99\.99%|\$100\.00|example\.com|picsum\.photos|placehold(er)?\.(co|com)|via\.placeholder|your (company|name) here' templates/ assets/
```

**Replace with:** real or realistic draft content, with every sample detail listed in the report for the client to confirm. Unsplash/picsum stand-ins get replaced with real pictures or removed.

### 25. Dead and default interaction states

```bash
grep -rnE 'href="#"|href="javascript:void' templates/
grep -rnE 'outline:\s*(none|0)' assets/                       # needs a :focus-visible replacement
grep -rnE 'transition:\s*all|ease-in-out|transition[^;]*linear' assets/
grep -rnE '(100vh|h-screen)' assets/ templates/
grep -rnP '<img(?![^>]*\balt=)' templates/                    # images with no alt
```

**Replace with:** real destinations (or visibly disabled controls), a visible `:focus-visible` style, specific transition properties with a chosen easing, `min-height: 100dvh`, and meaningful alt text. Also check there is a current-page state in nav and no `alert()` for errors.

### 26. Default iconography

Lucide/Feather everywhere at default stroke, rocketship for "launch", shield for "security", stock "diverse team" photos.

```bash
grep -rniE 'lucide|feather|fa-rocket|rocket|🚀|data-lucide' templates/ assets/ package.json
```

**Replace with:** one consistent icon set at one stroke weight, used only where an icon carries meaning, or no icons; real team photos or none.

### 27. Motion without a point

Identical fade-up on every block, a dozen staggered hero entrances, bounce easing, infinite loops that mean nothing, animation on `top`/`left`/`width`/`height`, no reduced-motion fallback.

```bash
grep -rnE 'animation:[^;]*infinite' assets/
grep -rnE '(transition|animation)[^;]*(top|left|width|height)\b' assets/
grep -rL 'prefers-reduced-motion' assets/*.css                  # files with no fallback (check they animate at all)
```

**Replace with:** one signature move, feedback on controls, transform and opacity only, reduced-motion fallback that keeps content and drops travel, content visible if JS fails.

## Out of scope (flag, don't fix)

Prose rewriting. Copy tells are a separate audit with different evidence, but loud ones are cheap to spot and belong in the report:

```bash
grep -rniE '\b(unlock|unleash|elevate|supercharge|seamless(ly)?|effortless(ly)?|next-gen|game-?changer|cutting-edge|delve|tapestry|all-in-one|revolutionize)\b' templates/
grep -rnoE '\b[A-Z][a-z]+\. [A-Z][a-z]+\. [A-Z][a-z]+\.' templates/    # "Fast. Simple. Secure."
grep -rniE "not just [^.]{3,40}, (it's|but) |Built for .{3,30}\. Designed for" templates/
grep -rniE 'oops!|get started|learn more' templates/
grep -rco '—' templates/ | sort -t: -k2 -nr | head -5            # em-dash density
```

Triad sentences, "Built for X. Designed for Y.", the "not just X, it's Y" correction, relentless em-dashes, exclamation marks in success messages, Title Case On Every Header. Note them in the report; fixing prose is a separate pass.
