## Delegation

Apply this delegation policy in OpenCode sessions.

When acting as the primary agent, use subagents when independent work can run
in parallel and delegation would materially improve speed or quality. Handle
small tasks directly. Keep orchestration, scope and design decisions, integration,
and final verification in the primary agent.

- Use `runner` for simple lookups, targeted searches, and mechanical checks.
- Use the built-in `explore` agent for investigation across files without code edits.
- Use `fixer` to implement a defined change within assigned files and verify it.
- Use `inspector` for independent assessment of correctness, regressions, security
  issues, and missing validation. Supply its diff, baseline, and test results;
  its inspection permissions exclude shell execution and edits.
- For high-risk changes, also request one deeper review of the final diff from
  `consultant`, which reasons at a higher effort than `inspector`. High-risk
  changes include authentication, authorization, sessions, tokens, or crypto;
  migrations or schema changes; data deletion; payment or billing logic;
  secrets, CI/CD, or infrastructure; removing routes or guards; untrusted input
  reaching SQL, shell, templates, deserialization, redirects, or server-side
  fetches; and any change whose failure would be silent or irreversible.
  Supply the diff, baseline, requirements, and test results, but not
  `inspector`'s findings, so the review stays independent. Ask for concrete
  defects with severity, file and line, and evidence. Reconcile both reviews in
  the primary agent.
- Use `consultant` before dependent implementation when architecture or design
  trade-offs remain unresolved, or when two evidence-based attempts have not fixed
  a difficult bug. Provide relevant context, constraints, options, and previous
  attempts. Use sparingly for decisions requiring deeper reasoning; the primary
  agent resolves the recommendation before assigning dependent work. Its inspection
  permissions exclude shell execution and edits.
- Use the built-in `general` agent for mixed investigation and implementation
  when no specialist fits.
- For `explore`, require execution paths, evidence with file and symbol references,
  and a distinction between observed behavior and likely causes. For `general`,
  specify file ownership or read-only scope and require changed files, source
  references, checks with outcomes, and unresolved questions. Include these output
  requirements and the instruction to leave further delegation to the primary
  agent in their assignments; their built-in system prompts are retained.
- Use each agent's configured model and effort variant.
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

When acting as a delegated subagent, complete the assigned task directly and
return the result to the primary agent. Leave integration, commits, and further
delegation to the primary agent unless the assignment explicitly authorizes commits.
