# Orchestration details

How each tool delegates to the [Detective
Crew](../README.md#meet-the-detective-crew): handoffs, permissions, effort
levels, and the fixer benchmark.

## Roles at a glance

- `runner` performs simple lookups, targeted searches, and mechanical checks.
- `fixer` implements defined changes within clear file ownership and verifies
  the affected behavior.
- `inspector` independently assesses correctness, regressions, security issues,
  and missing validation with read-only tools.
- `consultant` (all four providers) advises on architecture, design trade-offs,
  and stubborn bugs with inspection tools. It uses Astra in Codex, Opus at high
  effort in Claude Code, GLM-5.3-Flash at max in OpenCode, and Grok 4.7 at xhigh
  in Grok Build; the primary agent stays on your main model. See [consultation
  and handoffs](#consultation-and-handoffs) for when to call it.
- `tracker` (Codex only) traces behavior, dependencies, and likely causes across
  files without editing code.
- `default` is Codex's subagent for bounded mixed investigation and
  implementation when no specialist fits. Prefer Fixer for a defined change and
  Tracker for tracing.
- `explore` is OpenCode's built-in subagent for tracing behavior, dependencies,
  and likely causes without code edits. Prefer Runner for bounded factual
  lookups. Claude Code's custom `Explore` fills the same role on Sonnet 5.5.
- `general` is OpenCode's built-in subagent for bounded mixed investigation and
  implementation when no specialist fits. Prefer Fixer for a defined change and
  Explore for tracing.

N/A means this setup does not provide that role for the tool. The model table
shows configured defaults; for the riskiest change types, Claude runs the
Inspector review on Opus and OpenCode adds a deep review from a fresh Inspector
session at max, as described below.

Each provider has its own delegation policy. Those policies route deeper
investigation to Codex `tracker`, OpenCode `explore`, or Claude Code's custom
`Explore`. Mixed work goes to Codex `default`, OpenCode
`general`, or Claude Code's built-in `general-purpose` when available. Claude's
`Explore` is a custom agent that overrides the built-in; the other Claude
built-ins keep their own model settings. For tools without a matching
specialist, the primary agent handles the work or splits it into scoped
assignments for available agents.

## Consultation and handoffs

Use the stages the case needs: gather evidence → consult when needed → implement
→ inspect. The primary agent handles small tasks directly and selects
specialists when delegation improves speed or quality.

Call Consultant before dependent implementation when an architecture or design
decision remains unresolved. Examples include choosing a module boundary,
deciding where state should live, or comparing migration strategies with
different risks. Claude reserves that call for decisions that are hard to
reverse and answers the rest in the primary agent; the types are under
[Claude orchestration](#claude-orchestration). Architecture consultation can
happen immediately; the two-attempt threshold applies to stubborn bugs in
Codex and Grok. For those
bugs, consult after two evidence-based attempts have failed, supplying each
hypothesis, attempted fix, and observed result. Claude Code and OpenCode instead
climb a fixer escalation ladder, described under [Claude
orchestration](#claude-orchestration) and [OpenCode
orchestration](#opencode-orchestration), before they consult.

Give Consultant a specific decision or diagnostic question, relevant code and
evidence, constraints, viable options, and previous attempts when applicable. It
returns a recommendation with alternatives, risks, and supporting evidence. For
a bug, it also identifies the likely cause, evidence for and against it, and the
cheapest check that would confirm it. The primary agent resolves open questions
and decides the approach before assigning dependent implementation.

All four policies share one rule for questions. A subagent that returns an open
question, clarification, or decision to the primary agent, and a primary agent
that asks the user, includes a recommended answer and a one-line reason. It asks
without one only when it has no basis for a recommendation. The rule is global;
project conventions that sharpen the recommendation belong in the project's own
`AGENTS.md`.

Tracker gathers and traces evidence; Consultant uses that evidence to evaluate
an uncertain approach. Inspector reviews the implemented change against its
requirements. An inspector finding may expose a design question that the primary
agent routes back to Consultant.

Use the corresponding investigation role for each provider: Codex `tracker`,
OpenCode `explore`, or Claude's `Explore`. Grok delegates bounded
lookups to Runner and keeps deeper tracing in the primary agent. Its Consultant
advises on unresolved design choices; the primary agent makes the final
decision.

For example, a failing test with a clear cause can go directly to Fixer and then
Inspector. A change with competing designs may need Tracker to map the current
behavior, Consultant to compare options, Fixer to implement the chosen approach,
and Inspector to review the combined diff. Give Fixer file ownership and
acceptance criteria; give Inspector the baseline, diff, requirements, and
validation results.

## Claude orchestration

The five custom roles complement Claude's built-in agents. Keep coordination,
scope decisions, integration, and final verification in the primary
conversation.

The Claude role table lives in the [README](../README.md#claude-orchestration).

Use only the stages the task needs. For a change that needs investigation,
gather evidence first, then assign fixers distinct file ownership and acceptance
criteria. Integrate their changes before reviewing the combined diff. Give the
inspector the baseline, diff, requirements, and test output: its inspection-only
tools cannot run git or tests. The primary agent validates findings, coordinates
fixes, and checks the result. Independent lookups or fixers can run in parallel;
work that depends on their output waits for it.

Each read-only agent starts writing its report at a tool-call budget, even if
incomplete, and names what it did not verify; the turn limits in the table are
the hard stop. The policy has the primary agent state a tighter budget for a
narrow review or consultation. When a subagent returns partial, hits its turn
limit, or returns no report, resume it with `SendMessage` and ask it to report
now rather than restarting it. Claude Code's custom `Explore` can be resumed
like the other crew agents; a foreground result may omit the agent ID, so use
the ID that sent the report. The built-in `Plan` is one-shot, so start a new
one instead.

Fixers lint only their owned files with the repo's own linter, run data-writing
checks only against a disposable environment (reporting the check as not run
when none is available), and leave the full lint, type-check, and test suites to
the primary agent, which runs them once after integration and never two test
runs at once. This overrides a project's pre-handoff checks. A fixer that writes
docs, ADRs, or API descriptions gets the implementing diff or file paths and
checks each claim against that code. The policy also prefers the configured
`inspector` over plugin reviewer agents, and tells agents to search with Grep
and Glob and edit with Edit rather than shell `grep`/`find`, `sed -i`, or
scripted replacement.

The built-in Plan skips CLAUDE.md, so include relevant project constraints in
its assignments. Fixers retain inherited tools for project-specific workflows
but cannot spawn further subagents through Agent. Runner, Explore, inspector, and
consultant use explicit inspection tool lists, which also exclude shell, edits,
and MCP tools. Send work requiring those tools to the primary agent or a
suitably scoped fixer. The five custom agents have configured model and effort
defaults. High-risk changes get a review from the default Inspector. Opus
types get one Opus Inspector review at high effort, with a budget of about 30
tool calls, instead of that default review. The delegation rule
([claude/rules/delegation.md](../claude/rules/delegation.md)) lists the Opus
types and the four review steps (settled diff, no earlier findings, default
inspector for fix diffs, report that it ran) right after the high-risk bullet.
Approving a plan does not replace review. Other custom agents use their
configured models.

The delegation rule is a standing request to start the agents it names
(`runner`, `Explore`, `fixer`, `inspector`, `consultant`) without waiting to be
asked again. If a session instruction still blocks one, the primary agent says
so and names the agent it would have used.

Delegate implementation to `fixer` when the change splits into independent
pieces that can each be built against a written spec, such as a feature built
to a spec, a well-scoped bug fix, or mechanical edits across many files.
Implement it in the primary agent when it is one chain of dependent steps, fits
in context, or turns on a judgment call: public interfaces, access checks,
persisted data shapes, and the Opus types. Short wording edits the user
dictates, and wording fixes that make no claim about code, are small tasks.

Claude's policy consults before recommending on an architecture or design
decision that is hard to reverse: a data model, a public API or integration
contract, rewriting migration history, or renaming domain concepts across
packages. The primary agent answers other design questions. Consultant runs at
its configured high effort. If a high answer did not fix the bug, the primary
agent first runs the cheapest check it named and resumes the consultant at
high. Do not raise it past high; narrow the question instead.

When a fixer's result fails its checks, escalate in order: give the fixer a
way to verify its own work (a precondition, skipped when the assignment already
had one), rerun one effort level higher (capped at high), take the change over
in the primary agent, then consult. Each rerun is a fresh spawn with the failed
diff, the failing check output, and a keep-or-discard instruction for earlier
edits. Implement a change that touches an Opus type in the primary agent. If
that check fails, go to the consultant.
Include the instruction to leave further delegation to the primary agent when
assigning Claude's built-in `general-purpose` agent. The built-in `Plan` and
`general-purpose` still inherit the session model; `CLAUDE_CODE_SUBAGENT_MODEL`
sets the default model for subagents that have none.

Add another custom role only for a recurring task with distinct tools or
instructions that these roles and the built-ins do not cover. [Claude routing
and tools](https://code.claude.com/docs/en/sub-agents)

## OpenCode orchestration

The six roles combine four custom agents with the built-in `explore` and
`general` subagents. Keep coordination, decisions, integration, and final
verification in the primary agent.

The role table lives in the [README](../README.md#opencode-orchestration).

Follow the [consultation and handoff guidance](#consultation-and-handoffs),
using `explore` for codebase tracing. OpenCode uses two models. DeepSeek V4.1
Flash runs Runner and `explore` at high, and Fixer and `general` at max.
GLM-5.3-Flash runs Inspector at high and Consultant at max, so reviews always
come from a different model than the one that wrote the code. Watch
GLM-5.3-Flash usage in the console. Keep Inspector on GLM: the deep review is an
Inspector session, so moving Inspector to DeepSeek would review the riskiest
diffs with the model that wrote them. Revisit the split based on the quality of
findings and recommendations on your projects.

The OpenCode policy plans and delegates non-trivial changes, consults before
recommending on architecture or design questions, scopes each fixer's checks to
its owned files, and has the primary agent run full suites once after
integration.
High-risk changes always get a review from the default Inspector. For the
riskiest of them, the deep-review types, the primary agent also runs one deep
review on the settled diff, without asking first and without passing the
earlier findings, and reports that it ran and what it found. The deep review is
a fresh Inspector session, never a continuation of the iteration review, whose
assignment carries a focus brief: look for subtle defects an earlier pass could
miss, such as interleavings, edge-case states, bypasses of checks, and silent or
irreversible failures. The `subagent` tool takes a per-call `model` override
with a variant (`provider/model#variant`), so the policy launches it with
`opencode-go/glm-5.3-flash#max` and no separate max-variant agent is needed.
The tool's own guidance says to set `model` only when the user asks; the policy
names the exact ID, which counts as that request. If you change Inspector's
model, update the ID in the policy too.
[opencode/AGENTS.md](../opencode/AGENTS.md) lists the types and the four steps
right after the high-risk bullet. They match Claude's Opus
types, plus secrets, CI/CD, or infrastructure changes and new paths for
untrusted input. When a fixer's result fails its checks, the policy escalates in
order: give it a way to verify its own work, rerun it once as a fresh fixer with
the failed diff and failing output, then consult. Fixer already runs at its
top variant, and moving it to GLM would leave reviews on the model that wrote
the code, so that one rerun stands in for Claude's effort step and the primary
agent's takeover. When a subagent returns partial
results, the primary agent continues it through its `sessionID` instead of
starting over.

Runner, Inspector, and Consultant set `steps` limits of 15, 60, and 30, and the `explore` override sets 40. On the last step OpenCode
removes tools and asks the agent to summarize, so a long task still ends with a
report; continuing the agent through its `sessionID` resets the allowance. Fixer
and `general` have no step limit, so an edit is never cut off halfway.

Inspector and Consultant deny all permissions, then allow only
`read`, `glob`, `grep`, `webfetch`, and `websearch`. Shell execution, edits, and
further subagents stay denied. Supply relevant command output with their
assignments and run validation through the primary agent or Fixer. Every role
runs on its configured model and variant. Runner
uses inspection operations by instruction but inherits permissions; its prompt
is not a permission boundary.

The `explore` and `general` overrides set only model, description, and for
`explore` a step limit, retaining their built-in system prompts and permissions.
Their assignments carry evidence, ownership, validation, and handoff
requirements from the delegation policy. Further delegation stays with the
primary agent; OpenCode's built-in `general` also blocks child delegation. Start
a fresh OpenCode session after installing. [OpenCode V2 agents and
permissions](https://opencode.ai/v2/docs/agents)

## Grok orchestration

The four custom agents use the same model with different reasoning efforts.
Consultant reserves xhigh reasoning for unresolved architecture or design
decisions and bugs that survive two evidence-based attempts; Inspector keeps
high effort for independent review. The primary agent gathers any deeper tracing
evidence, resolves recommendations, assigns implementation, and verifies the
combined result.

The role table lives in the [README](../README.md#grok-orchestration).

Follow the [consultation and handoff guidance](#consultation-and-handoffs).
Supply Inspector and Consultant with relevant command output, since their
capability mode excludes shell execution and edits. Runner uses inspection
operations by instruction but inherits capabilities. All roles leave integration
and further delegation to the primary agent. The installer preserves your main
model and Grok settings. Start a fresh Grok session after installing. [Grok
subagent
configuration](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/16-subagents.md)
[Grok 4.7 reasoning efforts](https://docs.x.ai/developers/grok-4-7)

## Codex orchestration

The six roles cover narrow lookup, codebase investigation, implementation,
independent review, consultation, and mixed work. Keep coordination and final
verification in the primary agent; these custom agents return their assigned
work directly.

The role table lives in the [README](../README.md#codex-orchestration).

Implement cohesive tasks in the primary agent. Delegate substantial independent
workstreams when parallel progress or separate assessment earns the overhead.
Use independent review for meaningful changes, including authentication,
authorization, encryption, migrations, and data integrity; solo implementation
can still receive a scoped Inspector review.

Prefer fresh, bounded assignments containing the relevant project instructions,
requirements, and evidence. Keep responsibilities distinct when project rules
require multiple reviews. Workers run focused checks; the primary agent owns
repository-wide verification after integration and review fixes, repeating
checks when later changes or unresolved concerns justify it.

Give each assignment its objective, relevant context, file ownership or
read-only scope, acceptance criteria, and expected evidence. Gather any required
investigation before starting fixers. Parallelize independent work with distinct
file ownership, then integrate before reviewing the combined change. Supply
inspectors with the baseline, requirements, and validation results. The primary
agent verifies findings, coordinates fixes, and reruns affected checks. Use only
the stages a task needs.

Follow the [consultation and handoff guidance](#consultation-and-handoffs) when
choosing between Fixer, Inspector, Consultant, and Tracker.

Runner, tracker, inspector, and consultant are configured with `sandbox_mode =
"read-only"`. Codex can reapply parent runtime permission overrides when
spawning, so these are sandbox defaults rather than an unconditional guarantee.
A filesystem sandbox also does not make external connector tools read-only.
Their prompts require inspection operations across tools. An inspector can
inspect git history or diffs through available read-only commands; send checks
that need writes to the primary agent or a fixer.

Fixers and default agents retain inherited project tools. Further delegation is
left to the primary agent by instruction, rather than a Claude-style Agent tool
restriction. All six roles retain their configured models and omit fixed effort.
An ambiguous task or weak result should return to the primary agent for a
clearer assignment or different specialist, rather than spawning an additional
hierarchy. [Codex agent configuration and
permissions](https://learn.chatgpt.com/docs/agent-configuration/subagents)

Edit the provider-specific policies listed below to change how each tool
delegates work; the Codex policy defaults to solo implementation for cohesive
tasks.

These definitions configure subagents. Select your daily main model separately
in the tool's model selector or settings. The installer does not set the main
model, main effort, or default primary agent. The Codex `default` definition is
a subagent role.

Codex agent files omit `model_reasoning_effort` so the primary agent can select
an effort when spawning each subagent. The Codex policy uses these
task-selection targets, with escalation for more demanding work:

| Role | Usual effort | Escalation |
| --- | --- | --- |
| `runner` | Low | Medium for ambiguous lookups |
| `tracker` | Medium | High for complex investigation |
| `fixer`, `default` | Medium | High for difficult implementation or persistent failures |
| `inspector` | Medium | High for complex or security-sensitive review |
| `consultant` | Low for bounded advice | Medium or high for consequential unresolved decisions |

The fixer trials GPT-6.1 Terra for defined changes, usually at medium effort.
Keep Sol for the default and inspector roles, and Astra for consultation. Route
complex implementation back to the primary agent for reassignment when Terra
cannot complete it reliably. A role consumes tokens only when invoked. Compare
uncached input, cached input, output, elapsed time, findings, and corrective
work on matched tasks. Different-task token totals do not establish causal
savings, and usage records are not a final bill.

Run a local comparison from this checkout with an authenticated Codex CLI (add
`--provider claude` to compare Claude Code models with your Claude login
instead):

```sh
python3 tools/benchmark-fixer.py --dry-run
python3 tools/benchmark-fixer.py --limit 1
python3 tools/benchmark-fixer.py
```

The benchmark compares Terra and Sol at medium effort on five seeded regressions
in the session-usage tool, each in a fresh temporary workspace. It runs the
original regression tests after each attempt and records elapsed time, reported
token usage, patches, and failures. It uses hosted models through your existing
Codex login and consumes your account allowance. Results default to a temporary
directory; pass `--output PATH` to retain them somewhere specific.
```sh
python3 tools/benchmark-fixer.py --provider claude --dry-run
python3 tools/benchmark-fixer.py --provider claude --limit 1
python3 tools/benchmark-fixer.py --provider claude
```

With `--provider claude` it compares Sonnet 5.5 and Opus 5.5 at medium effort on
the same five regressions, using `claude -p` with the body of `claude/fixer.md`
written to the workspace as `CLAUDE.md`. Claude Code has no workspace-write
sandbox, so isolation relies on a temporary directory plus a restricted tool
list (Read, Edit, Write, Glob, Grep, and python3 through Bash; Agent
disallowed). Usage is taken from the final `result` event. [Initial Claude trial
results](../benchmarks/sonnet-opus-2026-10-28.md).

This is a repeatable smoke benchmark for scoped fixes. Use matched real project
tasks and independent diff review before drawing broader quality conclusions.
[Initial local trial results](../benchmarks/terra-sol-2026-10-28.md). [OpenAI
model comparison guidance](https://learn.chatgpt.com/docs/model-selection)

Use effort levels supported by the selected model. This is a choice made at
spawn time. Omitting the field alone uses Codex's resolved default or inherited
effort; it does not enable automatic task-based selection. Custom agent files
that explicitly set effort override spawn settings. [Codex subagent
settings](https://learn.chatgpt.com/docs/agent-configuration/subagents)

For existing installations, run `npx @rujealfon/detective-crew-agents --update`
to replace the earlier definitions and delegation policy with backups. The
installer leaves `~/.codex/config.toml` unchanged. If you want the model default
as the fallback when no effort is selected at spawn time, omit
`default_subagent_reasoning_effort` from its `[agents]` table. For the
recommended medium fallback, set it to `"medium"`. Explicit spawn effort takes
precedence over that global default either way. Routine reviews start at medium;
state a concrete reason when escalating effort. A settled diff that touches the
high-risk types (migrations, auth, tenant isolation, payment or financial
records, how audit entries or sensitive data are written or revealed, or data
deletion) gets one fresh inspector (`fork_turns: "none"`, no earlier findings)
at high effort before the PR, and the primary agent reports that it ran and what
it found. See the installable [context and token-use
reference](../codex/docs/token-usage.md) for matched-task measurement. Session
handoffs and skill reuse are covered in the Codex policy.

Claude agent files set a default `effort` in their frontmatter: medium for
`runner`, `fixer`, and `Explore`, and high for `inspector` and `consultant`.
The delegation policy also asks the primary agent to pass a supported effort
level through the Agent tool for each non-fork subagent invocation: medium for
lookups, routine implementation, and tracing, and high for complex
investigation or review. `CLAUDE_CODE_EFFORT_LEVEL`, if set, overrides per-invocation choices.
Unset that environment variable to let the primary agent choose effort. The
installer leaves Claude settings and shell environment variables unchanged.
Restart Claude Code after updating to load the new agent definitions. [Claude
subagent
effort](https://code.claude.com/docs/en/sub-agents#choose-an-effort-level)

Claude uses explicit `claude-haiku-5-5`, `claude-sonnet-5-5`, and
`claude-opus-5-5` model IDs. OpenCode uses the `opencode-go` provider and
encodes effort as a model variant, such as `#medium`, `#high`, or `#max`. Access
to these models and variants depends on your account and provider. Check that
they are available before using the agents. OpenCode Go blocks DeepSeek until
the workspace allows the Global region; see [install](install.md). [Claude
models](https://platform.claude.com/docs/en/models/overview), [OpenAI
models](https://developers.openai.com/api/docs/models), and [OpenCode model
variants](https://opencode.ai/v2/docs/models#variants).

Grok Build uses `grok-4.7` for all four native agents, with low effort for
`runner`, medium for `fixer`, high for `inspector`, and xhigh for `consultant`.
Inspector and Consultant set `capabilityMode: read-only`, which excludes file
edits and shell execution. These fields follow the [Grok agent
schema](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-agent/src/config.rs).
