## Delegation

Apply this delegation policy in Grok Build sessions.

When acting as the primary agent, use subagents when independent work can run
in parallel and delegation would materially improve speed or quality. Handle
small tasks directly. Keep orchestration, scope and design decisions, integration,
and final verification in the primary agent.

- Use `runner` for simple lookups, targeted searches, and mechanical checks.
- Use `fixer` to implement a defined change within assigned files and verify it.
- Use `inspector` for independent assessment of correctness, regressions, security
  issues, and missing validation. Supply its diff, baseline, and test results;
  its read-only capability mode excludes edits and shell execution.
- Use `consultant` before dependent implementation when architecture or design
  trade-offs remain unresolved, or when two evidence-based attempts have not fixed
  a difficult bug. Provide relevant context, constraints, options, and previous
  attempts. Use sparingly for decisions requiring deeper reasoning; the primary
  agent resolves the recommendation before assigning dependent work. Its read-only
  capability mode excludes edits and shell execution.
- For deeper investigation or mixed work without a matching specialist, handle
  the task in the primary agent or split it into bounded assignments for the
  available roles.
- Use each agent's configured model and effort settings.
- Give each agent a bounded task, relevant context, constraints, acceptance
  criteria, and expected output.
- Run dependent tasks in order and parallelize only independent work. Assign
  file edits to agents with distinct ownership to avoid overlapping changes.
- Resolve required investigation and decisions before assigning dependent fixes.
  Integrate changes before reviewing the combined diff. Use independent review
  for meaningful changes and handle trivial edits directly.
- Verify returned work and review findings. Resolve scope dependencies and missing
  context before continuing dependent work; fix confirmed defects and rerun the
  affected checks.
- Any open question, clarification, or decision you raise, whether a subagent
  reporting to the primary or the primary asking the user, includes a recommended
  answer and a one-line reason. Ask without a recommendation only when you have
  no basis for one.

When acting as a delegated subagent, complete the assigned task directly and
return the result to the primary agent. Leave integration, commits, and further
delegation to the primary agent unless the assignment explicitly authorizes commits.
