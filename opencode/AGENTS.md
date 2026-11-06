## Delegation

Apply this delegation policy in OpenCode sessions.

When acting as the primary agent, delegate independent work when it materially
improves speed or quality. Handle small tasks directly and keep orchestration,
scope and design decisions, integration, and final verification in the primary
agent. For non-trivial changes, plan and delegate rather than implementing them
yourself. A change is non-trivial when it spans more than one module or touches
routing, guards, schema, or tests. Short wording edits the user dictates, and
wording fixes that make no claim about code, are small tasks.

- Use `runner` for bounded lookups, file discovery, and factual checks.
- Use the built-in `explore` agent for tracing behavior and dependencies across
  files without code edits. Require execution paths, evidence with file and
  symbol references, and a distinction between observed behavior and likely
  causes.
- Use `fixer` to implement a defined change within assigned files and verify it.
- Use `inspector` for independent assessment of a supplied diff for correctness,
  regressions, security issues, and missing validation. Pass the diff or
  artifacts, requirements, and check results, not the author's reasoning, so the
  review stays independent. Always review high-risk changes with the default
  inspector: renames that reach the schema or stored codes, removing routes or
  guards, anything without a rollback, and the deep-review types (migrations,
  authentication or authorization, tenant isolation, payment, billing, or
  financial records, changes to how audit entries are written but not features
  that only add one, changes to how sensitive data is encrypted, masked, or
  revealed or new paths that could leak it, secrets, CI/CD, or infrastructure,
  new paths for untrusted input into SQL, shell or template construction,
  deserialization, uploads, redirects, or server-side fetches, and data
  deletion). When a diff touches a deep-review type, read
  `~/.config/opencode/docs/deep-review.md` and run the `deep-inspector` review it
  describes. Use `deep-inspector` for nothing else.
  A user's approval of a plan does not replace review.
- Use `consultant` before recommending on any architecture or design question: a
  choice between viable options, a data model, API, or integration decision, or a
  change that is hard to reverse, such as rewriting migration history or renaming
  domain concepts across packages. Skip it only when the answer is obvious or the
  question is a small lookup. Also use it for a bug that two attempts have not
  fixed. Gather the relevant files and findings first and put them in the
  assignment, so it reasons over them instead of searching. Include the AGENTS.md
  sections and specs that state a rule on the topic (grep for it), because a
  consultant that sees only code argues from a stale comment. State a tighter
  tool-call budget for a narrow question. The primary agent resolves the
  recommendation before assigning dependent work.
- Give a `fixer` that writes docs, ADRs, or API descriptions the implementing diff
  or file paths, and have it check each claim against that code. A brief alone
  yields unverified prose.
- Prefer the configured `inspector` over reviewer agents added by plugins or
  other configuration; use one only when its specialty (for example security
  audit or test design) is what the task needs.
- Use the built-in `general` agent for mixed investigation and implementation
  when no specialist fits. Specify file ownership or read-only scope and require
  changed files, source references, checks with outcomes, and unresolved
  questions. Include these output requirements and the instruction to leave
  further delegation to the primary agent in the assignments for `explore` and
  `general`; their built-in system prompts are retained.
- Use each agent's configured model and effort variant. Respect explicit user requests for a model or effort.
- Give each assignment its objective, relevant context, file ownership or read-only
  scope, acceptance criteria, and expected evidence. Give inspectors the diff,
  baseline, requirements, and available test results; their permissions exclude
  shell execution and edits, so they cannot run git or tests. State a tighter
  tool-call budget for a narrow review.
- Resolve required investigation and decisions before starting dependent fixers.
  Parallelize independent work with distinct file ownership to avoid edit conflicts:
  list the owned files in each assignment, make sure no two fixers share one, and
  run work that must touch the same file sequentially.
- Tell each `fixer` to run only the checks for its owned files (lint those paths
  with the repo's own linter, autofixing only those paths, not its repo-wide
  lint or fix command), and never a test project that shares a database with
  another running fixer. State that this overrides the project's pre-handoff
  checks; the primary runs those. Tell it to also run the type-check for its
  owned paths and the project's database-free guard specs when the repo names
  them (for example `pnpm test:guards`). For rename and move assignments, grep the
  repo's root `test/` for the old paths and names first, and list each matching
  spec as an owned file, because guard specs hard-code paths and fixtures. For
  rename assignments, tell it to change prose and identifiers only and to leave
  stored codes (audit actions, module keys, table names), import paths, and SQL
  literals unchanged unless the assignment lists them. Run the full lint,
  type-check, and test suites once yourself, after integration, and never two
  test runs at once.
- Integrate changes before reviewing the combined result. Use independent review
  for meaningful changes and handle trivial edits directly.
- Resolve missing context and scope dependencies in the primary agent, then
  continue the same subagent by passing its `sessionID` with the additional
  context. When a subagent returns partial, reaches its step limit, or returns no
  report, continue it and ask it to report now from what it has, listing what it
  did not verify. Do not restart it. Verify returned work and review findings, fix
  confirmed defects, and rerun the checks affected by each fix.
- Any open question, clarification, or decision you raise, whether a subagent
  reporting to the primary or the primary asking the user, includes a recommended
  answer and a one-line reason. Ask without a recommendation only when you have
  no basis for one.

When acting as a delegated subagent, complete the assigned task directly and
return the result to the primary agent. Leave integration, commits, and further
delegation to the primary agent unless the assignment explicitly authorizes commits.

## Tool economy

Search with the grep and glob tools, not shell `grep` or `find` (zsh errors on
unquoted globs). When those tools are unavailable, use `git grep`, which skips
untracked build output. Edit files with the edit tool, not `sed -i` (BSD sed on
macOS differs) or scripted string replacement: a pattern that no longer matches
changes nothing and reports success, while the edit tool fails loudly.

In zsh, quote words that start with `=` (`echo '====='`), which zsh otherwise
expands as a command path. Write temporary files to the system temporary
directory, never to a relative path outside the repository.
