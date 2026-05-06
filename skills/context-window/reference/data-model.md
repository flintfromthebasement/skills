# Data model

Everything in the artifact reduces to: **tabs** (one per session being visualized) → **blocks** (one per logical chunk of context inside that session) → **raw content** (the literal text of that chunk).

## Tab

```js
{
  id:          'snake-case-id',         // also the URL hash
  label:       'Display name',          // shown in tab bar
  icon:        '⚡',                    // single emoji or character
  title:       'Context Window',
  subtitle:    'runtime · session label',
  statusText:  'Live status line shown above the title',
  meta: [                                // key/value pairs, top-right
    ['Model',   'claude-opus-4-7'],
    ['Limit',   '200,000 tokens'],
    ['Runtime', 'Claude Code CLI'],
    ['Turns',   '3 conversation turns'],
  ],
  tokensUsed:  12500,                    // estimated total tokens in window
  tokensLimit: 200000,                   // model context window size
  caption:     'One-line orientation for the reader',
  footer:      'HTML allowed. Use this to explain provenance.',
  blocks: [ /* see below */ ],
}
```

## Block

```js
{
  id:     'cc-harness',                 // matches a <script type="text/plain" id="...">
  type:   'system',                     // one of the 8 types below
  label:  'Harness system prompt',      // human-readable name
  source: 'Claude Code CLI default',    // where this content came from
  tokens: 5500,                         // estimated tokens (chars / 4)
}
```

The id must match a `<script type="text/plain">` element somewhere in the HTML body. The renderer reads the script's `textContent` directly — HTML special chars in the content don't need escaping.

## The 8 type buckets

Pick the type by **where the content originated**, not by what it talks about. A long memory entry that happens to discuss tools is still `memory`, not `tool`.

| Type | Color | What goes here |
|---|---|---|
| `system` | purple | The harness's persistent system prompt. Tool schemas. Skill listings. @-imported instruction files (CLAUDE.md, AGENTS.md, etc.). Any block the model sees on every turn before any user input. |
| `workspace` | pink | Project / channel / chat-scoped context. Workspace-specific markdown. Channel topic + metadata. Per-thread state. Things that change when you switch projects but not when you switch turns. |
| `memory` | green | Recall results. Context cache. Semantic memory hits. Anything that came out of a memory store (AutoMem, vector DB, keyword index) and got injected into the prompt. |
| `hook` | teal | Output injected by harness hooks: SessionStart banners, UserPromptSubmit recall blocks, Stop hooks. Conversation history stitched in by the runtime. The distinguishing feature is that a piece of code outside the model added this on the model's behalf. |
| `skill` | amber | Skill instructions surfaced into the prompt. Either the skill listing (still kind of system) or, when a skill has been invoked, its full instruction body. |
| `user` | blue | A user-authored message. One block per turn, even if the user pasted a wall of text. |
| `assist` | lavender | An assistant-authored reply. One block per turn. |
| `tool` | red | A turn's tool calls plus their results. Group both call and result into one block per turn — separating them adds clutter without insight. |

If a chunk genuinely doesn't fit any of these — for example, a raw API trace dump — bucket it as `system` and explain in the source field.

## Why this taxonomy

The colors map cleanly to the question "who controls this?":

- **system** + **workspace** + **skill** = the harness operator (whoever runs the bot or CLI configured these).
- **memory** + **hook** = automated runtime injection (a hook script or a memory service decided to add this).
- **user** + **assist** = the conversation itself.
- **tool** = the model's own actions and their effects.

When you look at a context-burn problem, that grouping is what you actually need: "is the harness too heavy?" vs. "is the conversation too long?" vs. "are tool results eating the window?"

## Conversation ordering

Render blocks **top-down chronologically**. System and workspace first (they were there before any turn started). Then the first turn (user → optional hook → tool → assist). Then the second turn. Etc.

For Claude Code with hook-based recall (UserPromptSubmit hook fires per turn), the per-turn order is:

```
user → hook (recall) → tool (calls + results) → assist
```

That matches what the model actually sees in its messages array.

## Raw content (`<script type="text/plain">`)

Three rules:

1. **The id must match the block id.** No exceptions.
2. **Don't pre-escape HTML.** The renderer pulls `.textContent`, so `<`, `>`, `&` are safe inside the script. Escaping them double-escapes when the block is opened.
3. **Don't fabricate.** If you can't find the actual content, leave the script empty. The renderer will show `[content not found]` — that's the right behavior, not a bug to paper over.

## Tokens vs. characters

`tokens` on each block is your best estimate. The header `tokensUsed` is the sum of all block tokens. See [`token-estimation.md`](token-estimation.md) for how to estimate.
