# LLM Cliché Patterns  -  de-AI writing filter

Shared flag list for prose (blog posts, docs, emails, essays). Song lyrics have their own failure modes; see the `write-lyrics` skill in this repo for that filter.

Source: Simon Willison’s [LLM cliché highlighter](https://tools.simonwillison.net/llm-cliche-highlighter) (38 patterns as of 2026-08-28) + Wikipedia [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing). Tweet: https://x.com/simonw/status/2093277255438860358

**How to use:** flag list, not auto-kill. One hit can be coincidence; clusters are the tell. Rewrite the sentence so the claim stands without the tic. Prefer concrete specifics over significance puffery.

Used by Pass 4 (de-fingerprint scrub) and Pass 6 (critic review) in `write-blog-post`. `scripts/scan-draft.py` machine-checks a subset.

---

## Group A  -  Rhetorical / structural tics (Simon’s original set + expansions)

| ID | Pattern | What it looks like |
|---|---|---|
| `no-chain` | “No X, no Y” chains | “No fluff, no filler, no jargon.” Two+ “no …” items in a row. |
| `whole` | “That’s the whole …” | “That’s / this is the whole point / game / thing …” |
| `is-the-entire` | “Is the entire …” | “X is the entire point / game / business model.” |
| `the-entire-is` | “The entire … is” | Flipped twin: “The entire point is …” |
| `is-the-whole` | “Is the whole …” | “is the whole point / trick / pitch / idea”; “here is the whole …” |
| `did-not-chain` | “Did not / didn’t” chains | Two+ “did not …” / “didn’t …” items stacked. |
| `dont-verb-it` | “Don’t VERB it. VERB it.” | “Don’t call it X. Call it Y.” Negated verb+it, then same verb+it. |
| `sit-with` | “Sit with that” | “Sit with that / this / it (for a moment)”, “sit with the discomfort.” |
| `already-know` | “You already know” | Standing alone or before the tidy answer. |
| `is-real` | “Is real … and / not” | “The X is real, and/not …” (skip real estate / real time). |
| `punchline` | “The punchline is” | “The punchline is/:/?” |
| `worth-naming` | “Worth naming” | Therapist-voiced loss-naming; “Worth naming:” openers. |
| `not-nothing` | “That’s not nothing” | “that/this/it is not nothing.” |
| `echo-triad` | Echoing sentence runs | Same skeleton repeated: “A cart is an object… A room is an object…” |
| `performative-honesty` | Performative honesty | “I won’t pretend,” “I’ll be honest,” “let’s be honest,” “to be clear,” sentence-initial “Honestly,” / “Look,”. |
| `thats-the-part` | “That’s the part …” | Gesturing at a detail instead of stating it; “my favourite part…” |
| `the-only-i-trust` | “The only X I trust / that matters” | Narrowing superlative reveal. |
| `take-my-word` | “Don’t take my word for it” | Stock invitation to verify. |
| `turns-out` | “Turns out …” | Casual-revelation opener bolted to a tidy conclusion. |
| `fits-in-your-head` | Dev-blog simplicity boilerplate | “small enough to hold in your head,” “batteries included,” “it just works,” “zero config,” “sane defaults.” |
| `stacked-questions` | Stacked rhetorical questions | Two+ questions in a row (often fragments after the first). |
| `sentence-anaphora` | Repeated sentence openers | 3+ consecutive sentences starting the same way (ignore articles/pronouns). |
| `colon-triple` | Colon into a triple | Colon → 3+ comma-separated items as fake rhythm. |
| `heres-the-twist` | “Here’s the twist / thing / catch / kicker” | Stage-managed reveal. |
| `x-is-dead` | “X is dead” / “long live …” | Obituary headline + sequel. |
| `thats-why-mattered` | “That’s why X mattered” | Retroactive significance assignment. |
| `stranded-auxiliary` | Stranded auxiliary contrast | “The tool died; the data didn’t.” Bare auxiliary reversal. |

Also watch (from replies / related lists, not always in the 38):
- Sentence-initial **“Honestly,”** (Claude tell)  -  covered under performative-honesty; still worth a hard eye.
- Em-dash-for-everything (handled in Pass 4, step 2).
- Rule-of-three everything; false binaries (“The question isn’t X. It’s Y.”).

---

## Group B  -  Wikipedia-adapted “Signs of AI writing”

| ID | Pattern | What it looks like |
|---|---|---|
| `ai-vocab` | AI vocabulary words | delve, tapestry, meticulous, pivotal, intricate, interplay, underscore, garner, bolster, vibrant, bustling, multifaceted, seamless, ever-evolving. One = maybe; several = tell. |
| `not-just` | “Not just X, but Y” | “not just X, but (also) Y,” “not only… but…,” “it’s not X  -  it’s Y.” |
| `note-that` | “It’s important to note” | “it is important/worth noting,” “it should be noted,” “worth pausing/considering.” |
| `testament` | “Stands as a testament” | “stands/serves as a testament/reminder,” “is a testament to.” |
| `crucial-role` | “Plays a crucial role” | crucial / pivotal / vital / key / significant role. |
| `landscape` | “Ever-evolving landscape” | “ever-evolving/changing/shifting landscape,” “in today’s fast-paced world.” |
| `vague-experts` | “Experts argue” | “experts argue,” “some critics have noted,” “observers suggest” (unnamed). |
| `despite-challenges` | “Despite these challenges” | “challenges remain,” “remains to be seen,” “time will tell,” outlook formula. |
| `participle-tail` | Participle sentence tails | “…, highlighting/underscoring/showcasing/reflecting the…” |
| `promo` | Promotional / travel-brochure | “nestled in,” “in the heart of,” “rich tapestry/heritage,” “hidden gem,” “boasts,” “breathtaking.” |
| `ai-leftovers` | Chatbot leftovers | “as an AI language model,” “as of my last update,” “knowledge cutoff,” markup debris (`oaicite`, `contentReference`, `turn0search`, tracking params). |

Related WP:AISIGNS themes (use judgment; not every hit is a kill):
- Significance/legacy puffery without specifics
- Ecosystem/conservation padding on mundane subjects
- Canned notability / media claims
- Excessive boldface, broken citation markup (wiki-specific)

---

## Group C  -  Covered elsewhere in Pass 4 (keep)

- Invisible Unicode watermarks (Layer 1)
- Em-dash overuse → real punctuation (Layer 2)
- Throat-clearing openers, transition glue (Moreover/Furthermore/Additionally…)
- Verb swaps: leverage/utilize/delve/harness/craft/foster/navigate/streamline/elevate
- Filler qualifiers: comprehensive, robust, seamless, cutting-edge
- Structural: identical bullet grammar, “X. Here’s why:” formula
- Prose: medium-length monotony, hedging, abstract over concrete

---

## Rewrite rules (when a pattern hits)

1. **State the claim.** Drop the frame (“Here’s the thing,” “Turns out,” “It’s worth noting”).
2. **One concrete.** Name, number, failure mode, or example beats “pivotal role.”
3. **Break the skeleton.** If three sentences share a shape, wreck one.
4. **Cut the second half of false binaries.** “It’s not X, it’s Y” → just Y (if Y is the point).
5. **Don’t replace a tic with another tic.** “No fluff” → not “Here’s the kicker.”
6. **Clusters > singles.** Three+ Group A/B hits in one graf = rewrite the graf, not the word.

---

## Self-audit (final pass)

- [ ] Any “no X, no Y” / “not just… but…” / “it’s not X - it’s Y”?
- [ ] Any sit-with / turns-out / here’s-the-twist / whole-point / punchline?
- [ ] Performative honesty openers?
- [ ] AI vocab cluster (delve/tapestry/pivotal/seamless/landscape…)?
- [ ] Testament / crucial role / experts argue / despite challenges / participle tails?
- [ ] Chatbot leftovers or tracking debris?
- [ ] 3+ sentences with the same opener or colon-triples as fake rhythm?
- [ ] Could a skeptical peer say this without the scaffolding?

---

## Maintenance

- Upstream tool: https://tools.simonwillison.net/llm-cliche-highlighter  
- Source HTML (patterns array): https://github.com/simonw/tools/blob/main/llm-cliche-highlighter.html  
- When Simon adds patterns, diff the `patterns` array and extend Group A/B here and the regex list in `scripts/scan-draft.py`.
- Related auto-mined lists (optional future): sloptells.com
