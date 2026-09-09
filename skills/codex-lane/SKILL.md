---
name: codex-lane
description: >
  Session-scoped delegation guidance for Claude-led Codex work and Astra-led Sol
  workers. Use when the user explicitly enables a Codex lane. Delegate bounded
  implementation, investigation, and testing; the lead retains architecture,
  coordination, and final review. Not a blanket instruction to delegate every task
  or change the session's model.
---

# Codex Lane

GPT-5.6 via Codex CLI is a genuinely strong development model — highly steerable,
efficient on well-spec'd work, and good at verification loops. This skill makes it a
first-class execution lane for the current session. Guiding principle: **best model
for the job** — route by what the task needs, not by rate-limit anxiety.

## Session Toggle

- **On:** the user invokes the skill, runs a wired slash command, or explicitly enables
  Codex mode for the session.
- **Off:** default. Without this skill loaded, use the current runtime's normal routing.
- **Astra-led sessions:** the user can enable this lane for Astra to run Sol workers
  while Astra remains the lead. This does not change global model defaults.

## The Lane Split

**Route to the worker lane (`gpt-5.6-sol`):**

| Work | Why worker |
|------|-----------|
| Well-spec'd implementation (clear diff to write, spec exists) | Efficient, steerable execution |
| Token-hungry codebase analysis / investigation | Keeps bulk context out of the session; reports a summary back. (Not free — Codex plans have real usage limits; route for fit, not cost dumping.) |
| UI/UX verification (drive the flow, screenshot, compare against spec) | Strong at verification loops |
| Independent second opinions on plans and PRs | Different vendor = genuinely independent read |
| Data analysis, migrations, mechanical multi-file transforms | Bulk execution on a clear contract |

**Stays with the lead:**

| Work | Why lead |
|------|-----------|
| Orchestration, task decomposition, judgment calls | The lead owns the complete task and integration |
| Ambiguous design work needing back-and-forth with the user | Needs conversation context |
| External tool workflows and authorization-sensitive actions | The lead retains the full context and authorization boundary |
| Anything in your agent's voice (messages, commit text, PR descriptions) | Voice is not delegable |
| Quick reads/searches | Usually cheaper in coordination time to do locally |

**Escalation is standing permission:** if a Codex result doesn't meet the bar, redo it at
higher effort or pull it back to the lead. Announce escalation and judge the output,
not the price tag. After two unsuccessful worker rounds, the lead takes over or surfaces
the unresolved decision instead of cycling workers.

## Model + Reasoning Effort Routing

As of GPT-5.6, Codex ships model variants: a frontier variant (`gpt-5.6-sol`), a
balanced one (`gpt-5.6-terra`), and a fast/cheap one (`gpt-5.6-luna`). Default the lane
to the frontier variant; pass `-m gpt-5.6-luna` for purely mechanical bulk transforms
where frontier reasoning is overkill. Terra has no standing route in this lane; don't
switch to it merely to save money. Otherwise don't override the model.

Pass effort per call with `-c model_reasoning_effort=<level>`. Don't rely on the config
default — pick deliberately. GPT-5.6 is notably stronger at low effort than 5.5 was
(OpenAI's own guidance: start lower, turn it up for harder jobs), so this table sits a
rung lower than a 5.5-era one would:

| Task | Effort |
|------|--------|
| Routine framework/CRUD coding, doc drafts | `low` |
| Most architecture and refactor work | `low` |
| Infrastructure debugging, harder refactors | `medium` |
| Security review | `high` |
| Performance tuning, novel algorithms, research | `high` |
| "I have no idea what's wrong" | `xhigh` |
| `max` / `ultra` | **Only when the user explicitly asks.** `ultra` adds automatic task delegation on top of max reasoning, so its spend is open-ended. |

Low is not a downgrade — GPT-5.6 low covers the whole routine-coding tier and then some.
Reserve `high`+ for work where being wrong is expensive.

Effort multiplies token spend, not per-token price — roughly 1x/2x/4x/8x/16x for
low/medium/high/xhigh/max, while capability gains flatten hard past medium. Codex usage
is a bounded budget (business plans hit limits quickly), so one xhigh run costs about
eight low runs of headroom — spend it where being wrong is expensive. `ultra` spawns
delegated subtasks on top of max reasoning, so its spend is open-ended — hence the
explicit-ask gate on both modes.

## Astra → Sol Delegation

Use Sol when a concrete subtask can run independently while Astra makes useful
progress: an adapter with an agreed interface, a bounded investigation, a test suite,
or an independent diff review. Keep ambiguous architecture and integration with Astra.
Do not delegate merely because slots are available.

When Codex exposes native collaboration tools, prefer them over a nested `codex exec`.
Request `gpt-5.6-sol` explicitly with a self-contained task and an appropriate effort
from the table above. Use `fork_turns="none"` (or a small positive count) when selecting
a worker model; full-history forks inherit the lead model.

Give each worker a compact contract: objective, repository or worktree, owned files,
interface constraints, acceptance tests, forbidden side effects, and reporting format.
Multiple workers share files, so assign non-overlapping ownership and agree on interfaces
before parallel edits. Workers do not commit, push, restart shared services, or modify
active user sessions. The lead owns those decisions.

Use follow-up or steering on the same worker for corrections. If a genuinely ambiguous
decision affects scope or authorization, have it stop and report `QUESTION: ...`. Worker
completion is evidence to review, not proof of success.

## CLI Mechanics

When native collaboration is unavailable, use `codex exec` (non-interactive). Prompts
must be **self-contained**: the worker has no access to the lead conversation. Include
the repo path, file paths, spec, constraints, and house rules in every prompt.

**Implementation (writes to working tree):**

```bash
codex exec -C /path/to/repo \
  -s workspace-write \
  -c model_reasoning_effort=low \
  -o /tmp/codex-out.md \
  "Implement <feature>. Spec: <full spec inline>. Constraints: <house rules>.
   Do not commit — leave changes in the working tree."
```

Then review with `git diff`, run tests, commit yourself. **Never let Codex commit or push.**

**Investigation (read-only, report back):**

```bash
codex exec -C <repo> -s read-only -c model_reasoning_effort=medium \
  "Analyze <question>. Report: findings, file:line references, recommended approach."
```

**PR review handoff:** pipe the exact diff in as the contract — don't let Codex bind to
a branch on its own:

```bash
gh pr diff <number> --repo <owner/repo> > /tmp/pr.diff
codex exec "Review this PR diff for bugs, regressions, security issues. Review only the diff provided." < /tmp/pr.diff
```

**Long tasks:** run in the background with `-o <file>` so the final message lands
somewhere readable; continue other work meanwhile.

**Isolation for big writes:** give Codex a dedicated `git worktree` so it can't collide
with edits you make in the main checkout while it works.

**Under Claude Code's Bash tool:** append `< /dev/null` to sandboxed calls to avoid a
stdin-read hang.

## Sessions — pause/ask/resume

`codex exec` is not fire-and-forget (verified on codex-cli 0.142.x). Every run prints
`session id: <uuid>` in its banner and persists the conversation under
`~/.codex/sessions/`; `codex exec resume <uuid> "<prompt>"` continues it with full
context (also `resume --last` for the most recent). Use this to give Codex the same
escalate-instead-of-guess contract Claude subagents get:

1. In the initial prompt add: *"If you hit a genuinely ambiguous decision, STOP and end
   your reply with a line `QUESTION: <what you need>` instead of guessing."*
2. Parse the output (grep the banner for the session id; or `--json` JSONL events for
   robust parsing). If the last message contains `QUESTION:`, answer it:
   `codex exec resume <uuid> "ANSWER: <answer>. Continue."`
3. Repeat until it ships. Sandbox/effort flags should be re-stated on resume calls.

**Calibration note from live testing:** a soft "if unclear, ask" is often not enough —
GPT-5.6 tends to feel confident and decide anyway, especially at `low` effort. If a
decision genuinely must come back to you, make it a hard gate: *"Do NOT implement
<the ambiguous part> in your first turn. Ask first."*

The sleeper benefit is **post-review fixups**: `codex exec resume <uuid> "your diff has
X wrong, fix it"` beats a fresh call re-explaining the whole task — the session already
knows the files and its own reasoning. This adds a third option to the escalation
ladder: resume-with-correction, then escalate effort, then take it back.

## Verification Contract

Worker output ships only after the lead verifies it. Minimum bar:

1. Read the actual diff (`git diff`), not just Codex's summary of it.
2. Run the tests / drive the affected flow where one exists.
3. Check house conventions (comment density, code style, no stray files).
4. **Live-test external API surfaces it wrote against.** A sandboxed model produces
   documented-API-shaped code; only a real call catches the undocumented behavior.
   (Real example: Trello's `/1/search` silently returns nothing for short board ids —
   plausible code, zero results, found only by a live curl.)
5. Disagreement between Codex and your own read is high-signal — resolve it by reading
   code, not by trusting either model.

## Linux Sandbox Note (Ubuntu 24.04)

Codex's Linux sandbox uses bubblewrap, which Ubuntu 24.04's
`kernel.apparmor_restrict_unprivileged_userns=1` blocks. Failure signature: every tool
call dies instantly with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`.
Fix: an AppArmor profile granting `userns,` to `/usr/bin/bwrap` and Codex's vendored
bwrap path (see `/etc/apparmor.d/unprivileged_userns` for Ubuntu's own mechanism) —
scoped to bwrap so the global mitigation stays on. Fallback:
`-s danger-full-access` skips bwrap entirely; tighten the prompt contract accordingly
and don't use it near credentials.

## Anti-Patterns

- Delegating ambiguous work "to see what it does" — spec first, delegate second. A vague
  prompt produces a confident wrong diff.
- Letting Codex touch git history, remotes, or anything outside the named repo.
- Re-running a failed call at the same effort with a reworded prompt. Resume with a
  correction, escalate effort, or take it back.
- Trusting "verified: script parses" as verification. Parsing is not behavior.
