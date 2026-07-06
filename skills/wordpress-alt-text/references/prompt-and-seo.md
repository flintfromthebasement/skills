# Prompt contract & SEO rules

The quality of alt text comes from the prompt + deterministic post-processing, not the model.
`generate.py` embeds all of this; reproduce it exactly in the API-free fallback.

## The prompt rules (verbatim intent)
- Describe ONLY what is visibly present. Never invent brand names, people, logos, or screen text.
  If unsure what something is, describe it generically and accurately.
- **Under 125 characters.** Concise. No trailing period.
- Do NOT start with "image of / photo of / picture of / graphic of". Use "screenshot of" only
  when it genuinely is a software screenshot and that matters.
- Screen-reader users first: clear, factual, specific.
- Output ONLY the alt string — no quotes, no labels.

## SEO: light, accurate, never stuffed
Keyword weaving is **optional** (provide a `keywords.txt`, one phrase per line) and constrained:
- At most **one** keyword per image, and only when it is the **literal, accurate name of what is
  shown** (e.g. a "course builder" screenshot, a product dashboard). The keyword must BE the
  subject, not a theme attached to it.
- **Natural grammar.** Articles and inflected word forms are fine ("selling courses online",
  "a certification program"). The keyword need not appear verbatim/robotic.
- **No bolt-ons.** Never attach a keyword with a preposition/filler: "in a [kw]", "for [kw]",
  "representing [kw]", "featured alongside [kw]", "to help you [kw]". If it can't be woven
  naturally and truthfully, leave it out.
- **Photos of people, pure logos, decorative/abstract images → NO keyword.** Just describe them.
  When in doubt, none.
- Keyword distribution worth eyeballing: if one phrase dominates a large share of images, it's
  probably being over-applied — check the gallery.

## Deterministic post-processing (the safety net)
The model won't perfectly obey, so `clean_alt()` enforces:
1. Strip leading "alt:" / "image of" etc.
2. **Bolt-on stripper:** remove a trailing `connector (+ up to 2 filler words) + exact keyword`
   so clumsy tack-ons drop the keyword rather than ship awkward. (If the keyword was inflected,
   it survives — which is the natural-grammar case we want.)
3. Hard cap 125 chars, truncate on a word boundary, drop dangling trailing stopwords
   (the/a/for/with/...).
4. Capitalize the first letter.

## No-guess rule (accuracy guardrail)
If an image can't be fetched (404) or rasterized (SVG with no fallback), emit **empty** alt and
`needs_visual_review: true`. Never let the model describe an image it could not actually see —
a confident hallucination from the filename/page is worse than a flagged blank.

## Good vs bad examples
- Photo: `Chris Badgett wearing a patterned knit hat in a snowy forest` (named from filename when
  it's a clear portrait) — good.
- Screenshot + keyword: `Screenshot of course builder settings showing prerequisite and date
  restrictions` — good (keyword names the actual UI).
- Bolt-on (bad, stripped): `...mountain peak under a blue sky to help create online community`.
- Logo: `Bluehost logo featuring a blue grid icon and the company name in blue text` — good, no
  keyword.
