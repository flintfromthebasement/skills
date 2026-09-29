# Voice Profile Template

The generic guides tell the model what *not* to sound like. The voice profile tells it who to sound like. Without one, the best you get is "competent, not obviously AI." With one plus a corpus, you get the author.

Save a filled-in copy in the project as `voice/voice.md` (or `blog-voice.md` at the project root). Put 3+ of the author's real posts in `voice/corpus/` as markdown. The skill reads both in Phase 2 of every run.

Don't have one yet? Hand the skill 3-5 past posts and ask it to draft this file from them (Phase 0). Then have the author correct it. Their corrections are the most valuable lines in the file.

---

```markdown
# Voice Profile: [Author or Brand]

## Who's Writing
- **Author:** [Name, role. Or "the company, first-person plural."]
- **Default post type:** [Personal | Company]
- **Platforms:** [Company blog, personal site, LinkedIn, newsletter]
- **Bio line:** [One or two sentences for bylines and author boxes]

## Target Reader
- **Persona name:** [Give them a name. It makes "would Sam care?" a usable test.]
- **Who they are:** [Role, situation, what they're trying to get done]
- **Skill level:** [e.g., comfortable with the tools, not a developer]
- **Mindset and values:** [What they care about, what they resent]
- **How they decide:** [Research-heavy? Try-before-buy? Trust docs and community?]
- **Pain points:** [What makes them lose trust or give up]
- **Things they'd actually say:** ["I know just enough to get myself in trouble."]
- **What they don't need:** [e.g., a sales pitch, theory without examples]

## How the Author Sounds
- **Register:** [Casual / conversational / formal. Contractions yes/no.]
- **Sentence habits:** [Long rambly sentences with asides? Short and blunt?]
- **Pet phrases and tics:** [Real ones, quoted from their writing. These are protected from the filler filters.]
- **Humor:** [Dry, self-deprecating, none?]
- **How they open:** [Scene, question, blunt claim]
- **How they close:** [Question to the reader, admission, next step]
- **Opinions:** [How strongly they commit, how they frame uncertainty]
- **Lived details they reuse:** [Real stories, objects, numbers the author has told before and is okay repeating]

## Never
- [Words, phrases, or moves this author never uses]
- [Topics or claims to avoid]

## House Style Overrides
- [Anything that differs from `style-guide.md`: brand casing, product names, "we" vs "I", allowed em-dashes (if you must)]
- **Official names:** [Product/feature names and exactly how to write them]
- **Extra banned phrases:** [Also add these to `voice/banned.txt`, one per line, so `scan-draft.py --ban` catches them]

## Corpus
- `voice/corpus/[slug].md`: [one line on why it's representative]
- (Weight newer posts heavier if the voice has evolved.)
```
