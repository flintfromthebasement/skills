---
name: write-blog-post
description: "Write or edit a long-form blog post in a specific author's voice, then run it through six editorial passes (substance, structure, human voice, de-AI scrub, house style + O'Reilly word list, fresh-context critic) before delivering. Handles drafting from a brief, filling an outline, editing a draft, refreshing an old post, and applying revision notes. Use when the user wants a blog post that sounds like a real person wrote it, not a one-shot generation."
---

# Write Blog Post

Write blog posts the way a good editorial team does: calibrate to the author's voice, draft, then run the draft through a series of editorial passes before anyone sees it. One-shot generation produces the same competent, faintly robotic post every time. The passes are the product.

The skill runs in two halves:

1. **Write** (Phases 0-3): voice setup, mode detection, corpus calibration, drafting.
2. **Edit** (Phase 4): six editorial passes, in order, every time. Then deliver (Phase 5).

Works in three environments:

| Environment | How to run |
| --- | --- |
| **Chat only** (Claude.ai, ChatGPT, any paste-the-skill chat) | Paste the reference files or keep their rules in mind. Run the phases in conversation. Deliver in the [chat output block](#chat-only-output). |
| **Coding agent with a workspace** (Claude Code, Codex, Cursor, etc.) | Same phases. Work in a project folder: `blog-post.md` for the post, `editorial-notes.md` for the pass log. |
| **This repo checked out** | Also run `scripts/scan-draft.py` during Pass 4 for a mechanical tells check. |

## Reference Files

Load these at Phase 2. They're the rules the passes enforce.

| File | What it's for |
| --- | --- |
| [`references/human-voice-guide.md`](./references/human-voice-guide.md) | Structural AI tells (clipped antithesis, triads, mic-drop closers) and what a human voice does instead |
| [`references/llm-cliche-patterns.md`](./references/llm-cliche-patterns.md) | Phrase-level catalog: Simon Willison's LLM cliché list + Wikipedia's Signs of AI Writing, with rewrite rules |
| [`references/style-guide.md`](./references/style-guide.md) | House style: punctuation, contractions, naming, heading case, UI paths, personal vs. company posts |
| [`references/oreilly-word-list.md`](./references/oreilly-word-list.md) | Preferred spelling and term conventions (backend, codebase, email, login vs. log in…) |
| [`references/structure.md`](./references/structure.md) | Brief template, openings, TOC, body, closings, content types, SEO |
| [`references/editorial-review.md`](./references/editorial-review.md) | The Pass 6 critic rubric, verdicts, and scorecard format |
| [`references/voice-profile-template.md`](./references/voice-profile-template.md) | Template for the author's voice profile + target reader persona |

**Precedence when rules conflict:** the user's explicit instruction > the project's voice profile > the corpus > these reference files. If the author genuinely writes "honestly" a lot, it stays, even though it's on a filler list.

---

## Phase 0: Voice Setup (Context Gate)

The generic guides only tell the model what *not* to sound like. To sound like a specific person, you need the person.

Look for, in the project folder:

- `voice/voice.md` or `blog-voice.md`: the voice profile (author, target reader, tics, never-list, style overrides)
- `voice/corpus/*.md`: 3+ real posts by the author
- `voice/banned.txt`: extra banned phrases for the scanner

**If they exist,** move on.

**If they don't,** ask for, in one message:

1. Who's the author (a person, or the company)? Personal post or company post?
2. Who's the reader? One or two sentences is enough to start.
3. 2-5 posts the author has written that sound like them (files, pasted text, or URLs you can fetch).

With samples in hand, offer to draft a voice profile from them using [`references/voice-profile-template.md`](./references/voice-profile-template.md) and save it for next time. The author's corrections to that draft are the most valuable part of the file.

If the user wants to skip this and just get a post, say plainly that you're writing without a voice sample, so the result will be de-AI'd and clean but generic, and proceed.

## Phase 1: Detect Mode and Confirm

Figure out what state the work is in before touching it.

| Mode | Signal | Phases |
|---|---|---|
| **Draft** | No draft yet, or `blog-post.md` has only a brief/topic/notes | 0, 1, 2, 3, 4, 5 |
| **Outline-fill** | Headings exist with no prose between them | 0, 1, 2, 3, 4, 5 |
| **Edit** | A full draft exists; no rewrite signal | 0, 1, 2, 4, 5 (edit plan first) |
| **Rewrite / Refresh** | An existing *published* post is being updated: a live URL, a `current-post.md`, `rewrite_of:` / `post_id:` in frontmatter, or the user says "refresh" | 0, 1, 2, rewrite plan, 3, 4, 5 |
| **Apply revision spec** *(modifier)* | A `revision-notes.md` (or similar) exists, or notes are pasted in | Stacks on Edit or Rewrite |

Modes stack. "Refresh this old post and apply these notes" is Rewrite + Apply revision spec.

**State what you found and confirm in one short message**, then proceed:

> Detected **Edit** + **Apply revision spec**. `blog-post.md` has a full draft, and `revision-notes.md` has 6 numbered changes. Run it that way, or did you want a fresh draft?

If the user already told you exactly what they want ("write a post about X"), skip the confirmation and go.

**Draft mode inputs.** If there's no brief, fill the brief template in [`references/structure.md`](./references/structure.md) with what you can infer, mark gaps `[?]`, and ask for the gaps that matter (topic, reader, key message, CTA, sources) in one message. Don't interrogate. Default the rest.

## Phase 2: Voice and Corpus Calibration (Every Mode)

Before writing or editing a line:

1. Read the reference files above.
2. Read the voice profile (if any).
3. **Read 2-3 corpus posts closest to this one** in topic and type (a how-to next to other how-tos, a personal essay next to other personal essays). Weight newer posts heavier. Note: how they open, paragraph rhythm, how they address the reader, heading style, how they close, pet phrases.
4. **Edit / Rewrite / Revision modes:** diff the existing draft against the corpus. List where it diverges on word choice, AI tells, sentence-length monotony, voice (passive, "users" instead of "you," "let's explore" filler), and structure the corpus uses that the draft lacks. These findings feed the edit plan.

Skipping this phase is the single most common cause of voice drift. Don't.

## Phase 3: Draft

Runs in Draft, Outline-fill, and (after the plan is approved) Rewrite.

1. **Write the brief** at the top of `blog-post.md` (template in `structure.md`).
2. **Personal posts:** outline first (headings + bullets), then convert to flowing prose in the same phase. Formal headings come out, lists become sentences, and a bolded standalone sentence marks a key idea. **Company posts** keep headings and lists.
3. **Draft the whole thing in one go**, following `structure.md` for the content type: hook, context, promise; TOC over 1,000 words; H2 sections; one primary CTA.
4. **Write like the corpus, not like the reference files.** The references are filters for Phase 4. While drafting, the voice profile and corpus lead.
5. **Never invent facts, stats, quotes, anecdotes, or URLs.** Where the post needs something you don't have, leave a visible placeholder:
   - `[SOURCE: claim that needs a citation]`
   - `[DETAIL: a real example from the author about X]`
   - `[LINK: what this should link to]`
   - `[IMAGE: what this should show]`

   A placeholder costs the author thirty seconds. A fabricated anecdote in their voice costs them credibility.

**Outline-fill:** keep the user's headings and order. Fill between them.

### Rewrite plan (Rewrite mode, before Phase 3)

1. **Keep the URL.** The slug doesn't change; that's how a refresh keeps its search ranking and backlinks.
2. Read the current post. Classify each section: **keep** (still accurate, light voice pass), **rewrite** (stale facts, retired products, old terminology), or **cut** (no longer fits the angle).
3. **Audit every link.** Flag renamed, redirected, or dead ones.
4. Fold in any revision spec.
5. Surface the plan, with **open decisions** (new title, structural cuts, new images) listed separately as questions. **Get approval**, then draft.

### Edit plan (Edit mode, before Phase 4)

**Don't redraft an edit-mode project.** "Edit this" means improve it, not replace it.

1. Combine the revision spec (in its own order, applied verbatim) with the Phase 2 diff findings into one plan, grouped by section.
2. Put open decisions in a separate list.
3. **Get approval.** Then run the Phase 4 passes as targeted edits, not a full-file rewrite.

---

## Phase 4: Editorial Passes

The core of the skill. Run all six, **in order**, on the full draft. Each pass has one job. Doing them separately is the point: a single "make it better" pass fixes the easy stuff and misses the rest.

**Ground rule for every pass after Pass 1:** style passes never add claims, facts, or examples. They change how things are said, not what is said. If a pass wants new substance, it leaves a placeholder or a note.

Log what each pass changed in `editorial-notes.md` (or a short running list in chat). One line per meaningful change is enough.

### Pass 1: Substance and Honesty

*Is it true, is it useful, does it deliver?*

- **Every statistic, quote, and factual claim** traces to a named source, the provided material, or the author's own experience. "Studies show," "experts agree," and aggregator-of-aggregator stats get a real citation or get cut. If you can't source it, cut the sentence; most sections are stronger without the unsourced number.
- **No fabricated links.** Every URL came from the user, the sources, or a tool result.
- **Case studies and customer stories:** every result and quote traces to the customer. No invented outcomes.
- **Promise kept.** Does the body deliver what the intro promised? Does the post say something the reader couldn't get from the first search result?
- **Cut what doesn't earn its place:** sections that restate earlier ones, integration lists that should be one example plus a link, generic FAQs nobody actually asks.
- **One primary CTA.** Demote extras to one supporting sentence.
- **Is anything outdated?** Product names, features, prices, versions.

### Pass 2: Structure and Flow

*Can a skimmer get 80% of the value?*

- Hook first. No "In this post…" opener. The key insight shows up early.
- Heading hierarchy is clean and the headings make sense in a TOC.
- Paragraphs 2-4 sentences, with some variation. No walls of text.
- Lists where the content is a list; prose where it's an argument. Personal posts: mostly prose.
- Numbered lists are honestly sequential (an "ongoing" state isn't step 4).
- Transitions between sections carry the reader instead of announcing the next section.
- Length matches depth. Cut padding.

### Pass 3: Human Voice

*Would the author say this to one person across a table?* Apply [`references/human-voice-guide.md`](./references/human-voice-guide.md).

- Kill the structural tells: clipped antithesis ("Not X. It's Y."), rule-of-three fragment triads, "X isn't about Y, it's about Z," the tidy mic-drop closer, explained metaphors.
- Put the author back in: their pet phrases, their kind of aside, their way of opening and closing (from the voice profile and corpus).
- Real specifics over abstractions. **Only real ones.** Placeholders for anything you'd have to make up.
- Endings invite or point somewhere (a real question, an admission, a next step) instead of concluding with a fortune cookie.
- Read it aloud (or simulate it). Anything that sounds like a slogan, a caption, or a keynote gets pulled back.

### Pass 4: De-AI Scrub

*Mechanical and phrase-level fingerprints.* Apply [`references/llm-cliche-patterns.md`](./references/llm-cliche-patterns.md).

1. **Invisible characters.** Strip zero-width spaces, BOMs, joiners, soft hyphens, and other Unicode format characters (`scan-draft.py --fix-invisible` does this).
2. **Em-dashes.** Replace every `—` with a period, comma, colon, parentheses, or an ellipsis, whichever the sentence actually wants. Watch for `--` and spaced en-dashes doing the same job.
3. **Phrase catalog.** Hedging throat-clearing, stage-managed reveals ("here's the thing," "turns out"), performative honesty, false binaries, significance puffery ("plays a crucial role," "a testament to"), AI vocabulary (delve, leverage, seamless, robust…), stiff transitions (Moreover, Furthermore), chatbot leftovers.
4. **Prose naturalization.** Vary sentence length (AI defaults to medium). Break parallel runs. A fragment or a sentence starting with "And" or "But" is fine. Cut hedges unless the uncertainty matters.
5. **Clusters over singles.** One hit might be coincidence. Three in a paragraph means rewrite the paragraph, not the word.
6. **Don't swap tic for tic.** Killing "no fluff" to write "here's the kicker" fails the pass.

Then run the scanner if you can:

```bash
python3 scripts/scan-draft.py blog-post.md --ban voice/banned.txt
```

Fix or consciously keep every flag. Kept flags get a one-line reason in the notes (e.g., "'honestly' is the author's real tic, per voice profile"). `--allow <id-or-word>` silences an accepted pattern. `examples/sloppy-draft.md` is a smoke test that should light up with ~19 flags.

### Pass 5: House Style and Word List

*Consistency.* Apply [`references/style-guide.md`](./references/style-guide.md) and [`references/oreilly-word-list.md`](./references/oreilly-word-list.md), plus any overrides in the voice profile.

- Heading case: Title Case for labels, sentence case for complete sentences, no punctuation on label headings or titles.
- Exclamation marks: one per post, max.
- Links close before punctuation. Descriptive anchor text.
- Official product and feature names, full name before abbreviation, consistent brand casing.
- Double quotes for highlighted UI terms. `**Term**: description` for settings. Bold each segment of a menu path, with `>` outside the bold.
- Spelling and term conventions from the word list (e.g., "backend," "codebase," "checkbox," "backup" as a noun vs. "back up" as a verb).
- Contractions by register: kept in conversational prose, considered for expansion in formal docs.
- SEO (if it applies): keyword in title, first 100 words, one H2, one alt text.

### Pass 6: Critic Review

*Should this be published?* Apply [`references/editorial-review.md`](./references/editorial-review.md).

- **Run it in a fresh context if your environment allows** (a subagent, a new session, ideally a different model). Give the critic only the brief, the voice profile, and the draft. The model that wrote the post is a soft grader of its own work.
- Score seven dimensions (interest, title/hook, self-indulgence, structure, shareability, voice, accuracy). Verdict: **PUBLISH**, **REVISE**, or **KILL**. Accuracy under 8 forces REVISE on its own.
- **REVISE:** apply the revision notes, then re-run Passes 3-5 on the changed sections only, then re-score. **Max two revise loops.** If it's still REVISE after two, stop and hand the author the scorecard and the remaining notes; the missing ingredient is usually something only they have (a real story, a real number, a sharper opinion).
- **KILL:** don't polish it. Tell the user, and say what could be salvaged as a different piece.

---

## Phase 5: Deliver

### Workspace / coding-agent output

- `blog-post.md`: the brief, then the post.
- `editorial-notes.md`: mode, corpus posts used, what each pass changed (short), scanner summary with any kept flags and why, the critic scorecard, **open decisions**, and **every placeholder** that needs the author.

Edit and Rewrite modes edit `blog-post.md` in place.

Then post a short chat summary: the verdict and score, the 2-3 most important changes, the placeholders that need the author, and the open decisions. Don't paste the whole post into chat unless asked.

### Chat-only output

```
## Brief
[brief]

## Post
[the post]

## Editorial Notes
- Verdict: [PUBLISH/REVISE] ([score]/10)
- Passes: [one line per pass on what changed]
- Needs you: [placeholders + open decisions]
```

---

## Model Notes

Nothing here requires a particular model, but the phases have different needs:

- **Drafting and Passes 1-3** reward your strongest writing model. Voice is where cheaper models fall down first.
- **Passes 4-5** are rule application. A mid-tier model does them fine, and the scanner catches what it misses.
- **Pass 6** benefits most from independence: a fresh context beats a better model grading its own draft. A different model family is better still.

## Checklist Before Delivering

- [ ] Mode confirmed (or the user was explicit)
- [ ] Voice profile and 2-3 corpus posts read (or "writing without a voice sample" stated)
- [ ] Revision spec applied verbatim, if one existed
- [ ] Rewrite: slug unchanged, links audited
- [ ] All six passes run, in order
- [ ] No em-dashes, no invisible characters
- [ ] Every stat and quote sourced; no invented anecdotes; no fabricated URLs
- [ ] Placeholders listed for the author
- [ ] Open decisions surfaced as questions, not silently decided
- [ ] Critic verdict recorded

## Notes

- **The passes are the product.** If you only have time for one, it's Pass 1 (a false claim is worse than a clunky sentence). If you have time for two, add Pass 3.
- **Substance and style are separate jobs.** Style passes never invent. That one rule prevents most of the ways editing makes a post worse.
- **Open decisions belong to the user.** New titles, structural cuts, image placement: propose options, let them pick.
- **Voice profile over generic lists.** The filters catch defaults; the author's real habits win when they conflict.
- **This skill stops at a reviewed draft.** Publishing, images, and platform formatting are separate jobs.
