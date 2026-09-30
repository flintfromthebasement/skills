---
name: codex-lane
description: >
  Session-scoped guidance for Claude-led Codex work and Sol-led or Astra-led
  Codex sessions. Use when the user explicitly enables a Codex lane. Delegate bounded
  implementation, investigation, and testing; the lead retains architecture,
  coordination, and final review. Not a blanket instruction to delegate every task
  or change the session's model.
---

# Codex Lane

GPT-6.1 Sol is the default Codex model for substantial work, as a lead or worker.
It replaces GPT-6 Sol and GPT-5.6 Terra's default budget role in this lane. GPT-6
Luna handles narrow work with easy acceptance checks. Route by task fit; cost is
a tie-breaker rather than a reason to accept worse output.

## Session Toggle

- **On:** the user invokes the skill, runs a wired slash command, or explicitly enables
  Codex mode for the session.
- **Off:** default. Without this skill loaded, use the current runtime's normal routing.
- **Astra-led sessions:** the user can enable this lane for Astra to run Sol workers
  while an explicitly selected Astra remains the lead.
- **Sol-led sessions:** Sol owns orchestration, architecture, conversation, and
  final integration. The lane split describes responsibilities, not a requirement
  that Astra lead every Codex session. Enabling the lane does not change the
  current session model.

## The Lane Split

**Route to the worker lane (`gpt-6.1-sol` unless the task fits Luna):**

| Work | Why worker |
|------|-----------|
| Well-spec'd implementation (clear diff to write, spec exists) | Efficient, steerable execution |
| Token-hungry codebase analysis / investigation | Keeps bulk context out of the session; reports a summary back. (Not free — Codex plans have real usage limits; route for fit, not cost dumping.) |
| UI/UX verification (drive the flow, screenshot, compare against spec) | Strong at verification loops |
| Independent second opinions on plans and PRs | An independent review can expose missed assumptions |
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
higher permitted effort or pull it back to the lead. This never authorizes
`max`/`ultra` without the user explicitly requesting that level. Announce escalation
and judge the output, not the price tag. After two unsuccessful worker rounds, the lead takes over or surfaces
the unresolved decision instead of cycling workers.

## Model + Reasoning Effort Routing

Choose the model and effort together; pass both explicitly in worker calls. Start
with `gpt-6.1-sol` at `medium`; your installed client and account determine availability.

| Worker task | Model | Effort |
|-------------|-------|--------|
| Extraction, file inventory, mechanical edits with exact acceptance checks | `gpt-6-luna` | `low` |
| Bounded code tracing, investigation, or small coordinated edits requiring reasoning | `gpt-6-luna` | `high`, if acceptance is easy to verify |
| Focused docs, review notes, tightly specified code edits | `gpt-6.1-sol` | `low` |
| Everyday framework feature work, refactors, investigations, UI verification | `gpt-6.1-sol` | `medium` |
| Security/performance review, difficult debugging, multi-file refactors | `gpt-6.1-sol` | `high` |
| Mystery debugging and `/plan-check` critical review | `gpt-6.1-sol` | `xhigh` |
| Verified Sol miss that warrants a different model, or the user selects Astra | `gpt-6-astra` | `high`; `xhigh` for mystery debugging or critical plan review |
| `max` or Codex `ultra`, including inherited worker settings | Any model | Only when the user explicitly asks for that level; check current runtime support |

Use `-m <model> -c model_reasoning_effort=<level>` with `codex exec`. Luna low is
for mechanical work where speed matters; Luna high is the starting point for
bounded work that needs actual reasoning. Medium is an optional latency compromise,
not a mandatory rung. If Luna misses a requirement, move to Sol rather than
walking through every effort setting. Escalate Sol effort only when the task or
observed result warrants it. The lead keeps ambiguous
architecture and final integration; an Astra-led session need not spawn Astra workers.

**Effort boundary:** normal routing stops at `xhigh`. A difficult task, a failed
run, `/plan-check`, or a benchmark measured at `max` does not authorize `max`.
Pass an allowed effort explicitly to workers rather than inheriting a lead's
`max` setting. GPT-6.1 Sol supports `low`, `medium`, `high`, `xhigh`, and `max`;
`none`/`minimal` are unsupported. Codex `ultra` is runtime orchestration, not an
API reasoning effort, and needs a separate explicit request and support check.

### Luna effort and harness defaults

Keep routing simple: low for mechanical work, high for bounded reasoning, Sol
for substantial or ambiguous work. Higher effort can reduce mistakes or repeated
tool calls, so cost per successful task need not track reasoning tokens directly.
Check elapsed time and acceptance quality as well as cost.

[CursorBench 4.0](https://cursor.com/evals) currently reports **5.6 Luna**, not
6 Luna: low 16.0%/$0.03/3,288 tokens; medium 22.2%/$0.08/7,642; high
29.4%/$0.25/23,368. High improves quality, but costs and tokens increase; the
plot's scale can obscure that. These results motivate a reasoning rung, not
a claim that 6 Luna high is free or always faster.

[Codex subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents)
recommends high for explicit Luna agents and low for straightforward work where
speed matters. Codex resolves configured/spawned model and effort defaults;
[models adapt reasoning within the chosen effort](https://developers.openai.com/api/docs/guides/reasoning).
This does not establish automatic selection of an optimal effort for each task.
Use these starting points without building another router or retry ladder. Set
effort explicitly when task fit or the max/ultra boundary matters.

### Evidence and model choice — checked 2026-09-30

OpenAI describes 6.1 Sol as near-Astra capability and recommends comparing on
representative tasks. Sol costs $2/$10 per million input/output tokens versus
Astra's $10/$50; Sol cached input is $0.10. Tool calling requires Responses.
Sources: [Sol model](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[model comparison](https://developers.openai.com/api/docs/models/compare),
[GPT-6 guide](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra).

Artificial Analysis's rounded Intelligence Index snapshot:

| Model / effort | Index | API cost per index task |
|----------------|-------|-------------------------|
| GPT-6 Sol / max (comparison only) | 48 | $1.05 |
| GPT-6.1 Sol / medium | 48 | $0.21 |
| GPT-6.1 Sol / high | 50 | $0.32 |
| GPT-6 Astra / medium | 50 | $1.54 |
| GPT-6.1 Sol / xhigh | 51 | $0.39 |
| GPT-6 Astra / high | 51 | $1.73 |

These aggregate results support medium for everyday work and high for demanding
review. They do not prove equal coding quality or latency on your projects.
Published max results are comparison evidence only. Source:
[AA leaderboard](https://artificialanalysis.ai/leaderboards/models).

Theo's [OpenAI fights back](https://www.youtube.com/watch?v=vu8X3YroB-w)
(transcript reviewed) favors 6.1 Sol for scoped work, investigations, root-cause
analysis, audits, and review. He reports less erratic behavior than Astra, but
keeps Opus 5.5 for collaboration and long rewrites; Sol still got stuck on his
compiler port. His early max runs were incomplete and partly backfilled from
xhigh, so they do not establish an effort winner. His subscription economics
do not transfer to your subscription plan.

**Routing judgment:** use 6.1 Sol instead of 6.0 and for most work previously
assigned to Astra, including leading ordinary Codex sessions. Keep Astra as a
selective escalation after a verified Sol gap, or when the user chooses it. Keep
Opus 5.5 available for long, ambiguous implementation and rewrites in Claude
sessions; Sol investigation and independent review complement that work.
Monitor real task results before changing these starting points.

## Codex Lead → Worker Delegation

Use a worker when a concrete subtask can run independently while the lead makes
useful progress: an adapter with an agreed interface, a bounded investigation, a test suite,
or an independent diff review. Keep ambiguous architecture and integration with
the lead. A Sol lead can use Luna for mechanical work or Sol for bounded independent work; an Astra lead
normally uses Sol workers. Do not delegate merely because slots are available.

When Codex exposes native collaboration tools, prefer them over a nested `codex exec`.
Request `gpt-6.1-sol` explicitly with a self-contained task and an appropriate effort
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
  -m gpt-6.1-sol \
  -s workspace-write \
  -c model_reasoning_effort=low \
  -o /tmp/codex-out.md \
  "Implement <feature>. Spec: <full spec inline>. Constraints: <house rules>.
   Do not commit — leave changes in the working tree."
```

Then review with `git diff`, run tests, commit yourself. **Never let Codex commit or push.**

**Investigation (read-only, report back):**

```bash
codex exec -C <repo> -m gpt-6.1-sol -s read-only -c model_reasoning_effort=medium \
  "Analyze <question>. Report: findings, file:line references, recommended approach."
```

**PR review handoff:** pipe the exact diff in as the contract — don't let Codex bind to
a branch on its own:

```bash
gh pr diff <number> --repo <owner/repo> > /tmp/pr.diff
codex exec -m gpt-6.1-sol -c model_reasoning_effort=high "Review this PR diff for bugs, regressions, security issues. Review only the diff provided." < /tmp/pr.diff
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

**Historical calibration (not yet retested on GPT-6.1 Sol):** a soft "if unclear,
ask" was often insufficient on older models at low effort. If a
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
