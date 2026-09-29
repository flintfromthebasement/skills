# Editorial Notes: "I Wiped My Own Memory Testing a WordPress Plugin"

- **Mode:** Draft (personal, deep-read). Voice profile built in Phase 0 from the blog's editorial doc + corpus.
- **Corpus:** crown-molding dispatch, agent-tooling-pile, approval-theater. Corpus scan found 11-17 em-dashes per older post plus "worth sitting with," "here's the part…," "this is not a thought experiment" → moved to Never list / banned.txt.

## Passes
1. **Substance:** cut "recall kept answering" (unverified); replaced a guess at what Jason was thinking; "that night" → "afterward" (not in the record); fixed "the part that connects things" (the nodes were wiped too). Verified the plugin's flush() falls through to flushdb() in source.
2. **Structure:** 4 H2s, hook first, single CTA (validate restore output same day). No TOC (~1,100 words).
3. **Voice:** removed "Not the count. The shape.", a vague mic-drop ("I had the whole thing backwards"), an invented "field 7". Style fix introduced a new claim ("spent May worrying…") → caught and replaced.
4. **Scrub:** scanner clean (0 flags) before the critic, which still found 5 stated-then-flipped binaries in the last section.
5. **Style:** Title Case label headings, sentence case for sentence headings; real links only (5, all 200).
6. **Critic (fresh context, different model):** loop 1: 6/10 REVISE (voice 5). Accepted 11/12 notes, rejected heading-case note (conflicts with style guide). Loop 2: 7/10 PUBLISH after one fix ("was written on" → "dated from", a claim the revision itself introduced).

## Publishing
- A stale local checkout would have deleted 4 newer posts on a sync-with-delete deploy; the push was rejected non-fast-forward; republished from the up-to-date checkout.

## Needs author
- None. Coda (`tags.join` recall error) is honestly untraced.

## Round 2 (human editor, after publish)
The editor flagged lines that the scanner and critic had both passed: the heading "The Part Where Nobody Noticed", "Nothing crashed, and that's what still bothers me," "which is boring and correct:", and a coda confessing a bug found while writing. Changes:
- Scanner: `nobody-noticed`, `emotional-residue`, `self-rated-setup`, and a `watch-words` density check (notice/noticing…). All four now flag on the v1 text.
- Pass 1 rules: don't narrate the writing session; chase the primary record. Chasing the raw heartbeat data corrected the date by a day and supplied the post's best detail (the count went from ~70,200 to 7 under "all systems nominal").
- The coda became a resolved third act instead of a confession. Critic v2: 8/10 PUBLISH.
