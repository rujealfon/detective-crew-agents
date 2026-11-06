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
  ownership; agents must preserve others' changes. Reuse an agent for related follow-up.
- Integrate before independent review of meaningful changes, especially auth,
  encryption, migrations, and data integrity. Give multiple reviewers distinct scopes.
- Workers run focused checks; the primary runs repository-wide checks. Reuse evidence
  unless later changes or unresolved concerns invalidate it. Resolve confirmed findings.
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

Keep changes to this delegation setup synchronized with its detective-crew-agents source clone.
