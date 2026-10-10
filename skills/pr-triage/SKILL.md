---
name: pr-triage
description: Audit every open PR and issue on a GitHub repo with parallel subagents and hand the maintainer a ranked list of what to look at first, with a merge verdict and confidence per PR and a keep/close call per issue. Use when a repo has accumulated open PRs or issues and someone asks "what should I merge, what should I close, what first?"
---

# PR Triage

Answer one question for a maintainer: **what should I look at first, and how safe is it to merge?** One subagent per open PR, one subagent per ~10 open issues, then a synthesis table. Read-only against GitHub: the skill never merges, comments, labels, or closes anything. Those are the human's calls; the output tells them which calls to make.

Inputs: `REPO` (`owner/name`), `BASE` (the integration branch, often `dev` or `main`), and a local clone whose `origin` points at the repo. The clone's working tree is never modified; all work happens in throwaway worktrees.

Requires `gh` authenticated with read access, and an agent runtime that can run subagents in parallel (Claude Code's Agent tool, Codex workers, or equivalent).

## Procedure

### 1. Inventory

```bash
gh pr list --repo $REPO --state open --limit 100 \
  --json number,title,author,headRefName,baseRefName,updatedAt,isDraft,mergeable
gh issue list --repo $REPO --state open --limit 200 --json number,title,author,createdAt,updatedAt,labels
git -C <clone> fetch origin $BASE
```

Record the `origin/$BASE` SHA in the report header. Every verdict is relative to that SHA; a report without it goes stale invisibly.

### 2. Fan out: one PR audit subagent per PR

Use a strong model for this (mergeability is a judgment call; never the cheapest tier). Launch all PR agents at once so they run concurrently. Each agent gets a self-contained contract:

- Read `gh pr view --json title,body,author,baseRefName,headRefOid,updatedAt,isDraft,mergeable,mergeStateStatus,reviews,comments,statusCheckRollup,files,additions,deletions` and the full `gh pr diff`.
- Fetch the head (`git fetch origin pull/N/head:audit/pr-N`), measure distance (`git log --oneline origin/$BASE..audit/pr-N` and the reverse), and detect conflicts with `git merge-tree --write-tree origin/$BASE audit/pr-N`.
- **Superseded check**: search `origin/$BASE` for the same functionality landing another way (`git log --oneline --since=<PR created>` grepped for the feature's keywords; `git grep` the tree for identifiers the PR introduces). A PR whose feature already shipped is `close-superseded`, however clean it is.
- **Run the tests twice**: on the PR head in a throwaway worktree, then again after a trial merge of `origin/$BASE` into it. Reuse an installed `node_modules` (or the language's equivalent) by symlink; never install into the main clone. Report exact pass/fail counts. Name environment-only failures (DNS, sockets, missing system binaries) separately from real ones.
- Code review on the diff: correctness, security (secrets, injection, permission bypass), data integrity (migrations), tests for new behavior, house style, and whether it follows how the codebase already does that kind of thing.
- Clean up: remove the worktree and the audit branch. Never comment, approve, merge, or push.

Required output per PR (≤ 60 lines): header facts (SHA, size, CI, review state, behind-base count, conflicts), **Verdict** from the fixed vocabulary, **Confidence the maintainer can merge as-is** (0–100% plus one sentence), **Tests** (both runs), **Findings** (3–8 bullets, each `file:line` + severity blocker / should-fix / nit), **What it needs** before merge, **Superseded by**. Facts only from tool output; `UNVERIFIED` where a check could not run.

Verdict vocabulary (use exactly these):

| Verdict | Meaning |
|---|---|
| `merge-now` | Clean merge, tests green on branch and on trial merge, no blockers |
| `rebase-first` | Conflicts or stale enough that a trial merge fails; content is fine |
| `needs-work` | Blockers or should-fix findings the author must address |
| `close-superseded` | The feature landed another way on `$BASE` |
| `close-stale` | Abandoned, no path to merge |

### 3. Fan out: issue triage subagents, ~10 issues each

A mid-tier model is enough here. Each agent reads every issue in its batch (`gh issue view --json title,body,author,createdAt,updatedAt,labels,comments`) and hunts `origin/$BASE` for evidence the work landed (`git log --since=<created>` grepped for keywords, `git grep` for named identifiers). Give each batch the hints you already have (a commit you remember, a directory to look in): it halves the search time.

Classes: `done-close` (evidence it shipped; cite the commit), `obsolete-close` (premise no longer applies), `valid-now` (real, actionable, do soon), `valid-backlog` (real, low urgency), `needs-info`. Priority for valid ones: P1 bug or user-facing harm, P2 clear bounded value, P3 idea.

Required output: one table row per issue, `| # | Title | Age | Class | Priority | Evidence |`, where evidence is a commit SHA, a `file:line`, or the literal "no evidence found on `$BASE`". Then ≤ 3 cross-cutting observations (an epic hiding as five issues, a cheap batch, a keystone that unblocks the rest).

### 4. Synthesize (the lead does this, not a subagent)

Read every report in full. Disagreement between an agent's verdict and your own read of the diff is the signal to open the diff yourself; do not average confidences.

Write the report in this order:

1. **Header**: repo, `origin/$BASE` SHA, date, counts (PRs by verdict, issues by class).
2. **Merge order**: a numbered list of PRs the maintainer should look at first, each with verdict, confidence, one line on why that position, and the one thing to check before clicking merge. Order by: blockers for a release first, then highest-confidence clean merges, then rebase-first, then needs-work. A `merge-now` PR that another PR depends on goes before its dependents.
3. **Close list**: PRs and issues to close, each with the commit or PR that makes it moot. Closing with a citation is a gift to the next person who searches the tracker.
4. **Issues worth doing now**: the P1/P2 `valid-now` rows, grouped when several are one PR's worth of work.
5. **Everything else**: the full PR and issue tables, so the ranking can be audited.
6. **Unverified**: anything the agents could not check, in one list. Never let an `UNVERIFIED` become a confident verdict in the summary.

Confidence is the probability the maintainer can merge as-is without a regression, not a vibe. A clean trial merge with green tests and no should-fix findings is 85–95%. A should-fix finding caps it around 80%. Any blocker, conflict, or failed test run caps it at 50%.

### 5. Deliver

Save the report where your team keeps reports (a notes folder, a wiki page, a published artifact) and put the merge order inline in the reply, because the table is the deliverable and the link is the archive. If your runtime has persistent memory, store the verdict counts and the link so the next triage can diff against this one instead of starting over.

## Anti-patterns

- Judging mergeability from the PR description. The verdict comes from the trial merge and the test run, nothing else.
- One agent for all PRs. Context fills, the later PRs get a skim, and the ranking is worthless exactly where it matters.
- Auditing without the superseded check. Two months of merges make half the open PRs moot; a clean diff of a shipped feature is still a close.
- Letting an agent comment on or approve the PR "to save a step". The maintainer asked for a list, not for the tracker to change under them.
- Averaging confidences across agents. Read the disagreement instead.
