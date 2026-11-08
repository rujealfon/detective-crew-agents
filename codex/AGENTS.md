## Delegation

Implement cohesive tasks directly. Delegate substantial independent work when
parallel progress or independent assessment improves the result. Keep scope,
integration, and final verification in the primary agent. Respect requests to work solo.

- runner: bounded read-only lookups; tracker: read-only tracing across files.
- fixer: defined edits and focused checks; inspector: independent diff review.
- consultant: unresolved design trade-offs or a bug surviving two evidence-based attempts.
- default: bounded mixed work with no matching specialist.
- Keep configured models. Default to medium effort; runner and bounded consultant
  tasks use low. Raise effort for a specific difficult decision or defect, or when
  requested; state the reason in the assignment. Routine reviews start at medium.
- Use fresh context (`fork_turns: "none"`) for bounded assignments when supported.
  Supply objective, relevant paths/instructions, ownership or read-only scope,
  acceptance criteria, and expected evidence. Reviewers also need baseline and checks.
- Resolve decisions before dependent implementation. Parallel edits need distinct
  ownership; agents must preserve others' changes. Reuse an agent for related follow-up,
  except for the high-effort review below.
- Integrate before independent review of meaningful changes, especially auth,
  encryption, migrations, and data integrity. Give multiple reviewers distinct scopes.
- Before the PR or final handoff, without asking, spawn a fresh inspector
  (`fork_turns: "none"`, or the closest fresh-context equivalent) once at high
  effort on a settled diff touching migrations, auth, tenant isolation, payment or
  financial records, how audit entries or sensitive data are written or revealed,
  or data deletion. Give it no earlier findings; rerun only if a fix touches those
  types; report that it ran and what it found.
- Workers run focused checks, and data-writing checks only against disposable data
  (the repo's documented test setup when neither shared nor persistent, or a scratch
  database), never shared or persistent databases or one another running worker
  uses; if none is available, report the check as not run. The
  primary runs repository-wide checks. Reuse evidence unless later changes or
  unresolved concerns invalidate it. Resolve confirmed findings.
- Any open question, clarification, or decision raised, by a subagent to the primary
  or by the primary to the user, includes a recommended answer and a one-line reason;
  ask without one only when there is no basis.
- Subagents complete their assignment directly; leave further delegation and
  integration to the primary. Return evidence and missing context rather than expanding scope.

## Context management

Load relevant skills once per agent; reread only changed or lost material. Read
linked references on demand. Keep tool output scoped and summarize large logs.
Follow explicit skills and project verification requirements even when costly.
At a natural boundary before unrelated work or a substantial new phase, offer a
short handoff for a fresh session. Finish authorized work; never silently stop or reset it.
Record the objective, repository/branch/commit, decisions, remaining work, checks
and log paths, and authorization limits. Read the handoff in the new session.
