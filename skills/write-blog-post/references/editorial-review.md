# Editorial Critic Review (Pass 6)

A brutally honest pre-publish critic. No loyalty to the writer, no concern for their feelings. Loyalty to the reader.

**Run this in a fresh context if you can** (a subagent, a new session, or a different model). The model that wrote the draft grades its own homework generously. Give the critic only: the brief, the voice profile, the reader persona, and the draft. Not the drafting conversation.

## Score Each Dimension 1-10

### 1. Interest
- Would a stranger in the target audience stop scrolling for this?
- Is there a genuine insight, or a status update wearing a trench coat?
- Does it say something that hasn't been said a thousand times?
- The "so what?" test: if the reader finishes and shrugs, it fails.

### 2. Title and Hook
- Would you click this title in a feed?
- Does the first paragraph earn the second?
- Specific enough to create curiosity, not so specific it gives everything away. Clickbait is bad. Boring is worse.

### 3. Self-Indulgence (scored inversely)
- Is the author's process there to teach, or just to document?
- "I built X" isn't interesting. "I built X and here's the non-obvious thing I learned" might be.
- 10 = entirely for the reader. 1 = diary entry.

### 4. Structure
- Can a skimmer get 80% of the value?
- Does every section earn its place, or is there filler between the good parts?
- Does it know when to end?
- Are headings, lists, and code blocks doing work, or decoration?

### 5. Shareability
- Is there one takeaway worth texting to a friend?
- Does the reader come away smarter, better equipped, or entertained?
- Would sharing it reflect well on the person who shares it?

### 6. Voice
- Does it sound like the author in the voice profile, or like any model could have written it?
- Personality, opinions, specific details: signs of life.
- Flag clusters from `llm-cliche-patterns.md` and the structural tells in `human-voice-guide.md`. One hit is noise; a cluster is a voice fail.

### 7. Accuracy and Honesty
- Every stat, quote, and claim traceable to a named source or the author's own experience?
- Any "studies show," vague experts, or invented anecdotes?
- Any link that wasn't provided by the user, the sources, or a tool? (Flag as fabricated.)
- Does it over-promise?

## Verdicts

- **PUBLISH**: overall >= 7, and Accuracy >= 8. Worth a reader's time.
- **REVISE**: overall 4-6, or Accuracy < 8. Something's here; give specific revision notes.
- **KILL**: overall <= 3. Kill it clean, and say what (if anything) could be salvaged as a different piece.

Accuracy gates the verdict on its own. A beautifully written post with an invented statistic is a REVISE.

## Output

First the critique in plain language: quote the lines that work and the lines that don't. Then the scorecard:

```json
{
  "score": 7,
  "verdict": "publish",
  "dimensions": {"interest": 7, "title_hook": 6, "self_indulgence": 8, "structure": 7, "shareability": 6, "voice": 8, "accuracy": 9},
  "strengths": ["..."],
  "weaknesses": ["..."],
  "revision_notes": ["..."],
  "one_line": "Single-sentence verdict summary."
}
```

**Revision notes must be actionable without follow-up questions.** "Make it better" is not a note. "The third paragraph repeats the first; cut it and use the space to expand the pricing example" is.
