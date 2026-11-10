## Delegation

Apply this delegation policy in Claude Code sessions.

When acting as the primary agent, delegate independent work when it materially
improves speed or quality. Handle small tasks directly and keep orchestration,
scope decisions, integration, and final verification in the primary agent. For
non-trivial changes, plan and delegate rather than implementing them yourself.
A change is non-trivial when it spans more than one module or touches public
interfaces, access checks, persisted data shapes, or tests. Short wording edits
the user dictates, and wording fixes that make no claim about code, are small
tasks.

- Use `runner` for bounded read-only lookups, file discovery, and factual checks.
- Use `Explore` (the crew's custom agent) for tracing behavior across the
  codebase and the built-in `Plan` for research during plan mode. Include
  relevant project constraints in a `Plan` assignment because it skips CLAUDE.md.
- Use `fixer` to implement a defined change within assigned files and verify it.
- Use `inspector` for independent assessment of a supplied diff for correctness,
  regressions, security issues, and missing validation.
  Pass the diff or artifacts, requirements, and check results, not the author's
  reasoning, so the review stays independent.
- Always review high-risk changes with the default inspector: renames that reach
  persisted names or codes, removing endpoints or access checks, anything
  without a rollback, and the Opus types. A user's approval of a plan does not
  replace review.
- Opus types: migrations, including squashing or rewriting history;
  authentication or authorization, including sessions, tokens, and crypto;
  tenant isolation; payment, billing, or financial records, such as balances or
  closed periods; changes to how audit entries are written or which fields they
  record, but not features that only add one; changes to how sensitive or
  personal data is encrypted, masked, or revealed, or new paths that could copy
  it into logs, errors, or audit entries; and data deletion. For a diff touching
  one, also run one Opus review:
  1. On the settled diff before the PR or final handoff, without asking the
     user, spawn `inspector` with the Agent tool's `model: "opus"`
     override at high effort. Use the default inspector until then.
  2. Give it the usual inspector inputs, including the baseline, but not earlier
     inspector findings.
  3. Review fix diffs with the default inspector; rerun the Opus review only if
     a fix itself touches an Opus type.
  4. Report in your summary that the Opus review ran and what it found.
- Use `consultant` before recommending on any architecture or design question: a
  choice between viable options, a data model, API, or integration decision, or a
  change that is hard to reverse, such as rewriting migration history or renaming
  domain concepts across packages. Skip it only when the answer is obvious or the
  question is a small lookup. Also use it for a bug that has climbed the
  escalation ladder below without a fix. It runs at its configured high effort.
  If a high answer did not fix the bug, first run the cheapest check the
  consultant named and resume it at high with the result. Pass `effort: "xhigh"`
  only when no new evidence can be gathered, or for a hard-to-reverse decision;
  its turn limit may cut an xhigh run short, so narrow the question for it.
  Gather the relevant files and findings first and put them in the assignment, so
  it reasons over them instead of searching. Include the project instruction
  sections (CLAUDE.md, AGENTS.md) and specs that state a rule on the topic (grep
  for it), because a consultant that sees only code argues from a stale comment.
  State a tighter tool-call budget for a narrow question.
- When a fixer's result fails its checks, escalate in this order:
  1. Give it a way to verify its own work, such as a failing test, a build, or a
     script. This is a precondition, not an attempt; if the assignment already
     had one, go straight to the reruns.
  2. Rerun it one effort level higher, capped at high. If the fixer already ran
     at high, skip to the next step.
  3. Rerun it with the Agent tool's `model: "opus"` override at medium effort.
     The drop to medium is intentional: a bigger model starts at a lower effort.
  4. Only then go to `consultant`.

  Each rerun is a fresh spawn with a short brief: the failed diff, the failing
  check output, and whether to keep or discard the earlier edits (prompt caches
  belong to the model that wrote them). For a fixer assignment that touches an
  Opus type and has no automated outcome check, start the fixer with
  `model: "opus"` at medium instead of Sonnet. If that fixer fails (a failed
  manual or review check counts), step 1 still applies; then rerun it on Opus
  at high, skip step 3, and go to `consultant`.
- Give a `fixer` that writes docs, ADRs, or API descriptions the implementing diff
  or file paths, and have it check each claim against that code. A brief alone
  yields unverified prose.
- Prefer the configured `inspector` over plugin reviewer agents; use a plugin
  agent only when its specialty (for example security audit or test design) is
  what the task needs.
- Use the built-in `general-purpose` agent for mixed investigation and action
  when no specialist fits. It can spawn agents, so tell it in the assignment not
  to delegate further.
- Use each agent's configured model unless this policy names another. Choose a
  supported reasoning effort for its task: low for simple lookups, medium for
  routine implementation and tracing, and high for complex investigation or
  review. Respect explicit user requests for effort.
- Pass the chosen effort through the Agent tool's per-invocation effort parameter
  for non-fork subagents. Respect the `CLAUDE_CODE_EFFORT_LEVEL` environment
  override when set.
- Give each assignment its objective, relevant context, file ownership or
  read-only scope, acceptance criteria, and expected evidence. Each fixer
  assignment names the check that proves the change works, so verification comes
  before effort. Give inspectors the diff,
  baseline, requirements, and available test results; their tools cannot run git
  or tests. State a tighter tool-call budget for a narrow review.
- Resolve required investigation and decisions before starting dependent fixers.
  Parallelize independent work with distinct file ownership to avoid edit conflicts:
  list the owned files in each assignment, make sure no two fixers share one, and
  run work that must touch the same file sequentially.
- Tell each `fixer` to run only the checks for its owned files (lint those paths
  with the repo's own linter, autofixing only those paths, not its repo-wide
  lint or fix command). State that this overrides the project's pre-handoff
  checks; the primary runs those. Tell it to also run the type-check for its
  owned paths and the repo's fast structural or guard checks when the repo names
  them, using the command the repo documents. Tell it to run data-writing checks
  only against a disposable environment (the repo's documented test setup when it
  is neither shared nor persistent, or a scratch database it creates and tears
  down), never shared or persistent data or a database another running fixer
  uses, so data and its safeguards
  (audit logs, triggers, constraints) stay untouched; if none is available,
  report the check as not run. For rename and move assignments, grep the repo's
  test directories, including cross-cutting guard or architecture specs, for the
  old paths and names first, and list each matching spec as an owned file,
  because such specs hard-code paths and fixtures. For rename assignments, tell
  it to change prose and identifiers only and to leave persisted codes (enum
  values, audit action names, table or column names), import paths, and query
  literals unchanged unless the assignment lists them. Run the full lint,
  type-check, and test suites once yourself, after integration, and never two
  test runs at once.
- Integrate changes before reviewing the combined result. Use independent review
  for meaningful changes and handle trivial edits directly.
- Resolve missing context and scope dependencies in the primary agent, then resume
  `runner`, `Explore`, `inspector`, `consultant`, `fixer`, or `general-purpose`
  with `SendMessage` and the additional context. A foreground result may omit
  the agent ID; use the ID that sent the report. The built-in `Plan` is
  one-shot; start a new one. When a subagent returns partial, hits its turn
  limit, or returns no report, resume it and ask it to report now from what it
  has, listing what it did not verify. Do not restart it.
  Verify returned work and review findings, fix confirmed defects, and rerun the
  checks affected by each fix.
- Any open question, clarification, or decision you raise, whether a subagent
  reporting to the primary or the primary asking the user, includes a recommended
  answer and a one-line reason. Ask without a recommendation only when you have
  no basis for one.

When acting as a delegated subagent, complete the assigned task directly and
return the result to the primary agent. Leave further delegation to the primary.

## Tool economy

Search with Grep/Glob, not shell grep/find (zsh errors on unquoted globs). When
Grep is unavailable, use `git grep`, which skips untracked build output. Edit files with Edit, not `sed -i` (BSD sed on macOS differs) or scripted string replacement: a pattern that no longer matches changes nothing and reports success, while Edit fails loudly.

In zsh, quote words that start with `=` (`echo '====='`), which zsh otherwise
expands as a command path. Write temporary files to the session scratchpad, never
to a relative path outside the repository.
