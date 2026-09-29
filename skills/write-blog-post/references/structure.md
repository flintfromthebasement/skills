# Post Structure, Content Types, and SEO

The structural playbook for a long-form blog post. Personal posts loosen most of this during polish (see "Personal vs. Company Posts" in `style-guide.md`).

## The Brief

Every draft opens with an internal brief. It's the contract for the post, and every editorial pass checks the draft against it.

```markdown
## Brief

**Post Type**: [Personal (author's voice) | Company]
**Author**: [Name, or the company]
**Target Reader**: [Persona name or one-line description, from the voice profile]
**Primary Keyword**: [One SEO keyword, or "none" for non-search posts]
**Content Type**: [How-To | Comparison | Strategy | Release Notes | Best Practices | Case Study | Conceptual | Personal Essay]
**Key Message**: [Main takeaway in 1-2 sentences]
**Tone**: [e.g., Conversational and practical]
**Length**: [Short 800-1,200 | Medium 1,500-2,500 | Long 3,000+]
**CTA**: [The ONE thing the reader should do next]
**Sources**: [Links, docs, notes, interviews the post is built from]
**Notes**:
- [Angle, must-include points, things to avoid]
```

If the user gives you a topic and nothing else, fill what you can infer, mark the rest `[?]`, and ask for the gaps in one message.

## Opening (First 100-200 Words)

Three jobs, in order:

1. **Hook:** a relevant problem, a question, a specific moment, or a bold claim.
2. **Context:** why it matters to this reader now.
3. **Promise:** what they'll get from reading.

**Never open with "In this post…"** Hook first, then promise.

**Pattern 1: Problem, Stakes, Promise**
```
[State the problem]
[Show what's at stake]
[What this post will help them do]
```

**Pattern 2: Context, Contrast, Promise**
```
[Establish the trend or situation]
[Contrast two approaches]
[What this post breaks down and helps them decide]
```

For personal posts, a specific scene or moment usually beats both patterns.

## Table of Contents

Include one for posts over 1,000 words (or 3+ major sections).

```markdown
## Table of Contents

* [Section Title One](#section-title-one)
  + [Subsection Title](#subsection-title)
* [Section Title Two](#section-title-two)
```

Anchors are lowercase, hyphenated slugs of the heading text. Match whatever your platform generates.

## Body

**Headings**
- H2 for major sections (4-8 per post).
- H3 for subsections. H4 sparingly.
- Case rules live in `style-guide.md`.

**Paragraphs**
- 2-4 sentences. Vary it; a one-sentence paragraph now and then is good.
- Bulleted lists for options, features, and non-sequential items. Numbered lists for steps.
- Keep list items grammatically parallel, but don't let every list in the post share the same shape.

**Emphasis**
- **Bold** for key terms and the one sentence per section a skimmer must not miss.
- *Italics* for titles of works, new terms, gentle emphasis.
- No ALL CAPS outside code.

**Links**
- Descriptive anchor text, never "click here."
- 3-5 internal links for a site with an archive. Every 300-500 words is a good rhythm.
- **Never fabricate a URL.** Only link to URLs you got from the user, the source material, or a tool result. If you need a link you don't have, leave `[LINK: what it should point to]`.

**Images**
- Tutorials: one every 300-500 words.
- Always alt text. Caption where it helps.
- If you can't produce the image, leave `[IMAGE: what it should show]`.

**Code**
- Inline code for short references, fenced blocks with a language hint for anything multi-line.
- Explain what the code does before showing it.

## Closing

1. **Summary:** the takeaways, briefly (and not as a tidy aphorism).
2. **Recommendation:** what to do next, concretely.
3. **One primary CTA.** Other options get demoted to a single supporting sentence. Three CTAs in three sentences reads like a menu, not a next step.
4. **Related reading** (optional): 3-6 links to related posts you actually have URLs for.

## FAQ Sections

Include only when the questions are ones real readers actually ask (from support, search queries, comments, the user). A generic, competently written FAQ adds length without adding value. When in doubt, cut it.

```markdown
## Frequently Asked Questions

**[Real question]?** [Answer in 1-3 sentences.]
```

---

## Content Types

| Type | Structure | Tone |
|---|---|---|
| **How-To Guide** | Goal, TOC, prerequisites, numbered steps, troubleshooting, related | Patient, instructional. Assume they're following along. |
| **Comparison** | Why it matters, overview table, each option, feature-by-feature, decision framework, verdict | Balanced. Acknowledge competitor strengths honestly. |
| **Strategy / Business** | Scenario hook, context, core framework, examples, action steps, encouraging close | Experienced, advisory. Draw on real experience. |
| **Release Notes** | Opening, TOC, major features (with screenshots), migration notes, before-you-update, changelog | Enthusiastic but thorough. Honest about risk. |
| **Best Practices** | Actionable advice, examples, what not to do, recommendations | Clear, authoritative, practical. |
| **Case Study** | Open in the customer's world, how they got here, the problem, why this solution, how it works now, results, what's next, CTA | Story-first. The customer is the hero. |
| **Conceptual** | Plain definition, why it matters, how it works, examples, misconceptions, next step | Explanatory, analogy-light. |
| **Personal Essay** | A moment, what it made you notice, the tension, where you've landed (or haven't) | First person, specific, unresolved is fine. |

**Case studies and customer stories:** every result, number, and quote must trace back to the source material (questionnaire, interview, the customer's own words). Never invent an outcome or a quote, even when filling in context from public research. If the source is thin, say so and propose options (research around it, follow up with the customer, or go shorter) before drafting.

## Relationship to the Product

When the post is on a company blog:
- The product supports the reader. The reader is the hero.
- Product mentions should serve the reader's goal.
- No over-promising, no hype.
- The CTA is relevant and helpful, not pushy.

---

## SEO

- One primary keyword per post (skip SEO entirely for personal essays if the user doesn't care).
- Put it naturally in: the title, the first 100 words, at least one H2, one image's alt text.
- Title patterns that work:
  - How-to: "How to [Achieve Result] with [Tool or Method]"
  - List: "[Number] [Things] for [Audience or Goal]"
  - Comparison: "[Option A] vs. [Option B]: [Key Question]"
  - Guide: "[Topic]: The Basics and Beyond"
  - Best practices: "Best Practices for [Topic]"
- Length only helps when the topic justifies it. Padding to hit a word count is a critic-pass fail.

## Common Mistakes

1. Opening with "In this post…"
2. Walls of text.
3. Vague advice. Be specific with examples and numbers.
4. Burying the lede.
5. Weak closings, or three CTAs where one belongs.
6. Over-promotion. Reader first, product second.
7. Assuming knowledge. Define terms, link prerequisites.
8. Unsourced stats ("studies show…"). Name the source or cut the claim.
9. Redrafting when an edit was asked for.
10. Silently deciding things that belong to the user (new title, structural cuts, image choices).
