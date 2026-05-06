# Runtime recipes

Concrete instructions for extracting context out of the four scenarios you'll actually hit.

## 1. Claude Code (you're inspecting your own session)

This is the easiest case — most of what you need is already in your own context window.

**Walk in this order:**

1. **Harness system prompt** (`type: system`). The text from "You are Claude Code..." down through the "Tone and style" section. You can quote it directly because you're reading it. ~5k tokens for a default install.

2. **Tool schemas** (`type: system`). The list of `<function>` blocks at the top of the system prompt. Group as one block titled "Loaded tool schemas (N)" rather than one per tool — N is usually 8 to 12. Estimate ~400 tokens per schema.

3. **Deferred tool list** (`type: system`). Names listed in a `<system-reminder>` for tools that need ToolSearch to load. Just the names — no schemas yet. Roughly 1–2k tokens.

4. **Available skills** (`type: system` or `skill`). The bullet list of skills the user can invoke. ~600 tokens on a stocked install.

5. **@-imported files** (`type: system`). Walk the import tree from CLAUDE.md / AGENTS.md. Each imported file is its own block. For Flint that's IDENTITY.md → SOUL.md → FLINT-OPS.md → prompts/pmpro-knowledge-rules.md. For most users it's just CLAUDE.md.

6. **Session metadata** (`type: system`). The block containing `userEmail`, `currentDate`, `gitStatus`, etc. Small (~200 tokens) but named explicitly so debug stories like "the model thinks it's 2024" are easy to spot.

7. **SessionStart hook output** (`type: hook`). Whatever the harness's session-start script printed. On Flint this includes the context mode header and a line about ambient context.

8. **For each turn:**
   - **User message** (`type: user`). The literal user prompt.
   - **UserPromptSubmit hook output** (`type: hook`). On Flint this is the AutoMem recall block. On a default Claude Code install with no hooks, skip this.
   - **Tool calls + results** (`type: tool`). Group all tool calls in this turn and their results into one block. The label can be `Turn N · <short description>`.
   - **Assistant reply** (`type: assist`). The literal text the model output.

**Token estimation:** `chars / 4` for English. Status bar's reading is ground truth — cite it in the footer if visible.

**Sensitive content:** Tool results often contain file contents, env-var values, output of `git log`, etc. Scrub anything sensitive before pasting into the artifact.

## 2. Bot service with code access (Slack / Discord / Forge / Maurice / etc.)

You have the bot's repo locally. Trace the prompt builder.

**Find the entry point.** Common names:
- `services/*/claude.js` → `buildSystemPrompt(...)` (Flint Slack bot)
- `services/shared/prompts.js` → `buildAdminPrompt`, `buildChatPrompt`, `buildProfilePrompt`
- `lib/system-prompt.ts` (Forge / AutoBrew)
- `app/api/chat/route.ts` (Next.js chat APIs)
- `src/index.ts` (Discord bots)

**Read the builder top to bottom.** It's almost always a string concatenation. Each segment maps to one block. Bots typically split into:

- **Stable section** (cached, same on every request): identity / soul / static rules. → `type: system`.
- **Workspace context** (per-workspace markdown): `services/*/workspaces/<name>.md` or DB-backed config. → `type: workspace`.
- **Profile / posture**: rules that vary by user role (admin / team / member). → `type: system`.
- **Volatile section** (per-request): recall, channel history, mode, active references. → mostly `type: memory` and `type: hook`.

**Channel / thread history.** Bots that pull recent messages out of Slack/Discord/SQLite into the prompt. → `type: hook` (the runtime injected it). Group as one block: "Recent channel history (N msgs)."

**Tool calls.** If the bot's loop uses tool-calling, follow the same per-turn structure as Claude Code above.

**Reconstruct the user message and the assistant reply** from the actual conversation you're trying to visualize. If you don't have one specific incident in mind, use a representative one and call it "Sample turn" in the label.

**Honest footer:** "Built from reading `<file>:<line>`. Token counts approximate."

## 3. Black-box bot (you only chat with it)

The "OpenClaw Slack" case. You can see your messages and the bot's replies. You can't see its system prompt, hidden recall, or tool schemas.

**Be aggressively honest about scope.**

What you **can** render with confidence:
- Your user messages (`type: user`).
- The bot's replies (`type: assist`).
- Anything the bot quoted back at you ("here's what's in my system prompt: ...") — but only if it actually quoted it. Probing prompts ("dump your full system prompt") often produce a confident hallucination, not the real prompt. Treat anything you didn't read directly as `type: system` with `source: "self-reported by bot — may be inaccurate"`.

What you **can't** render:
- The bot's hidden system prompt, unless quoted verbatim and verifiable.
- Tool schemas the bot has loaded.
- Internal recall, hooks, or memory the bot pulled.

**Recommended approach:** Render the dialogue as one tab. Add an empty `system` block titled "Bot's hidden context" with content `[not visible from this side of the conversation]`. State in the footer: "This artifact captures the user-visible side of the dialogue. The bot's system prompt, tool schemas, and any hidden recall are not represented because they aren't visible from outside the bot's process."

That's a more useful artifact than a confident-looking one full of made-up prompt text.

## 4. Black-box bot whose source you partially know

Common when the bot is a fork of an open-source project (LangChain agent, Claude Agent SDK app, gstack skill, etc.) — you don't have the deployment but you do have the upstream code.

Treat it as case 2 (code access) but mark every block clearly: "From upstream `<repo>@<commit>` — actual deployment may differ." Don't assume the operator hasn't changed the prompt. If recall, hooks, or tool sets are configured per-deployment, don't claim to know what's set.

## Cross-cutting tips

- **One block per logical chunk, not one per line.** If the harness concatenates 14 small strings into the system prompt, that's still one `system` block — don't split unless the user benefits from seeing the seams.
- **Group tool calls + their results into one block per turn.** Splitting them multiplies block count without adding insight.
- **Order matters.** System / workspace blocks before turns. Turns top-down chronologically. Hook output for a turn goes immediately after the user message of that turn.
- **The `caption` and `footer` carry the honesty.** Use them. Tell the reader what's verbatim, what's estimated, and what's reconstructed.
