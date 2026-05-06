---
name: context-window
description: Generate a single-file HTML report visualizing what's in an LLM session's context window — system prompt, tool schemas, recall, hooks, conversation turns — color-coded by source type with token estimates. Use when someone asks "what's in your context?" / "show me your system prompt" / "make a context map of this session." Works for the calling agent's own session (Claude Code), for bots whose source you can read (Slack/Discord/Forge/Maurice/etc.), and best-effort for black-box bots you only chat with. Output is a self-contained .html file you open in a browser.
---

# Context Window

A skill that turns "what's actually in this LLM's context window" into a single-file HTML report. Color-coded by source, collapsible per-block, click to read the verbatim text.

## When to use

- "What's in your context window right now?" / "Show me your system prompt."
- "Map out the context of my Claude Code session."
- "What does the bot in #dev see when I ask it something?"
- Debugging context burn — why is this session at 60% already?
- Onboarding a new bot — making the prompt structure legible to a teammate.
- Comparing two sessions side-by-side (CLI vs. bot, work mode vs. conversation mode).

## When **not** to use

- You just want a token count — the model's status bar already shows that.
- The user wants a transcript dump — `claude --resume` or the chat log is simpler.
- You can't see any of the bot's prompt or its replies in this conversation. Then the report has nothing to render.

## What the output looks like

A single `.html` file. Open it in any browser — no build step, no server, no JS deps. Contains:

- Tab bar (one tab per session being visualized; most reports have one).
- Header: status line, model, token limit, runtime, turn count.
- Stats row: tokens used / remaining / capacity %, block count, window limit.
- Capacity progress bar.
- Color legend across 8 source types.
- Stack of collapsible blocks — one per logical chunk of context. Each block shows its type badge, label, source, token count, and (when expanded) the literal text.
- Token breakdown grid by type.
- Footer note explaining provenance ("approximate," "reconstructed," etc.).

See [`examples/blank-project.html`](examples/blank-project.html) for a working example: a Claude Code session in a directory with no CLAUDE.md and three turns of conversation.

## How the calling agent uses this skill

There's no executable. The skill is a template + a thinking framework. The flow:

1. **Confirm scope.** Ask the user 2–3 short questions if they haven't already answered them:
   - **Which session?** Current Claude Code session, a bot whose code you have access to, or a black-box bot the user chats with?
   - **Where to save the .html?** Default: `./context-window-YYYYMMDD-HHMM.html` in the current working directory.
   - **Sensitive content?** If the prompt or messages contain API keys, customer names, ticket bodies, etc., either redact them or stop and ask before pasting them into the artifact.

2. **Read [`reference/data-model.md`](reference/data-model.md)** to lock in the 8 type buckets and the block schema.

3. **Read the runtime recipe** that matches the target session in [`reference/runtime-recipes.md`](reference/runtime-recipes.md). It tells you where to look for context in each runtime and how to bucket the chunks you find.

4. **Estimate tokens** per [`reference/token-estimation.md`](reference/token-estimation.md). Default: `chars / 4`. Cite the rule in the footer so readers know it's approximate.

5. **Copy the template:**
   ```bash
   bash skills/context-window/scripts/new.sh ./context-window-$(date +%Y%m%d-%H%M).html
   ```
   Or just `cp template.html <dest>`. The script does that plus the timestamped default filename.

6. **Fill in the TODO markers** in the copied file:
   - One `TABS[]` entry per session, with `meta`, `tokensUsed`, `tokensLimit`, `caption`, `footer`.
   - One `<script type="text/plain" id="...">` block per content chunk, holding the raw text.
   - One `blocks[]` entry per content chunk inside the tab, with id, type, label, source, tokens.

7. **Print the path** of the saved file so the user can open it. On macOS: `open <file>`. On Linux: `xdg-open <file>`.

## Output location

Default: current working directory, named `context-window-<YYYYMMDD-HHMM>.html`.

That puts it next to whatever the user is working on, makes it easy to clean up, and avoids cluttering home directories. If the user wants a different path, take theirs verbatim.

## Honesty rules — non-negotiable

These are the rules that keep the artifact useful instead of a confidently wrong picture:

1. **Never fabricate prompt text.** If a block's content isn't available, leave the script body empty (`[content not available]` will show) and note it in the footer. Don't invent plausible system-prompt text from training data.
2. **Mark token counts approximate.** Unless you ran a real tokenizer, the footer must say something like "Token counts are approximate — derived from `chars / 4`."
3. **Mark reconstructed content.** If you reconstructed any block from indirect evidence (running source code rather than reading the prompt verbatim, inferring from observed behavior), say so in the footer.
4. **Don't claim to see what you can't.** For black-box bots, you can only render what you've actually exchanged in the conversation. Anything claimed about the bot's hidden side (system prompt, tool schemas, internal recall) must be flagged "estimated" or omitted.

## Layout

```
skills/context-window/
├── SKILL.md                      # this file
├── template.html                 # the renderable single-file template (copy this)
├── examples/
│   └── blank-project.html        # synthetic Claude Code session, 3 turns
├── reference/
│   ├── data-model.md             # 8 type buckets + block schema
│   ├── runtime-recipes.md        # how to extract context per runtime
│   └── token-estimation.md       # chars/4 rule + when to caveat
└── scripts/
    └── new.sh                    # cp template.html <dest> with a sensible default
```

No setup script and no install receipt — there's nothing to install. Just copy `template.html` and edit it.
