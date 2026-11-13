# Detective Crew Agents

Detective Crew agents for Codex, Claude Code, OpenCode, and Grok Build.
Subagent definitions and delegation rules, installed with one command, that
apply across every project on your machine.

```sh
npx @rujealfon/detective-crew-agents
```

## Meet the Detective Crew

![The Detective Crew](assets/detective-crew/detective-crew.png)

Your main agent is the Chief: it coordinates the case, makes the decisions,
integrates changes, and verifies the outcome. The crew does the legwork.

| | Crew member | Question it answers | Expected result |
| --- | --- | --- | --- |
| <img src="assets/detective-crew/runner.svg" alt="Runner" width="72"> | **Runner** | Where is it, and what are the facts? | A concise answer with file or source references |
| <img src="assets/detective-crew/fixer.svg" alt="Fixer" width="72"> | **Fixer** | Can you implement the agreed solution? | Scoped changes, relevant checks, and their outcomes |
| <img src="assets/detective-crew/inspector.svg" alt="Inspector" width="72"> | **Inspector** | Does this change work correctly, and what did we miss? | Concrete findings with impact and evidence, or no findings with verification limits |
| <img src="assets/detective-crew/consultant.svg" alt="Consultant" width="72"> | **Consultant** | Which approach should we take, and why? | A recommendation, alternatives, trade-offs, risks, and supporting evidence |
| <img src="assets/detective-crew/tracker.svg" alt="Tracker" width="72"> | **Tracker** (Codex only) | How does this work, and what caused the problem? | Execution paths, likely causes, evidence, and remaining uncertainty |

### Models per tool

| Tool | `runner` | `fixer` | `inspector` | `consultant` | `tracker` | `default` | `explore` | `general` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Codex | `gpt-6-luna` | `gpt-6.1-terra` | `gpt-6.1-sol` | `gpt-6-astra` | `gpt-6-luna` | `gpt-6.1-sol` | N/A | N/A |
| Claude Code | `claude-haiku-5-5`, medium | `claude-sonnet-5-5`, medium | `claude-sonnet-5-5`, high | `claude-opus-5-5`, high | N/A | N/A | `claude-sonnet-5-5`, medium | N/A |
| OpenCode | `opencode-go/deepseek-v4.1-flash`, high | `opencode-go/deepseek-v4.1-flash`, max | `opencode-go/glm-5.3-flash`, high | `opencode-go/glm-5.3-flash`, max | N/A | N/A | `opencode-go/deepseek-v4.1-flash`, high | `opencode-go/deepseek-v4.1-flash`, max |
| Grok Build | `grok-4.7`, low | `grok-4.7`, medium | `grok-4.7`, high | `grok-4.7`, xhigh | N/A | N/A | N/A | N/A |

N/A means the tool doesn't get that role. Codex leaves effort to the Chief at
spawn time, so its row lists models only. `default` (Codex) and `general`
(OpenCode) handle mixed work; `explore` (Claude Code, OpenCode) traces code.

## How a case runs

Use only the stages a task needs. Small tasks stay with the Chief.

1. **Gather evidence**: Runner looks things up; Tracker (or `explore`, or Claude Code's custom `Explore`) traces deeper.
2. **Consult**: Consultant weighs in on an unresolved design decision, or after two failed bug-fix attempts (Claude Code and OpenCode climb an escalation ladder first).
3. **Implement**: Fixer makes the agreed change in the files it owns.
4. **Inspect**: Inspector reviews the combined diff against the requirements.

A failing test with a clear cause can go straight to Fixer, then Inspector.
Read-only roles can't run shell commands or tests, so hand them the diff and
test output.

## The crew in each tool

Each tool gets its own delegation policy. Full per-tool rules, permissions, and
effort levels are in [docs/orchestration.md](docs/orchestration.md).

### Claude orchestration

| Agent | Assignment | Configuration |
| --- | --- | --- |
| `runner` | Bounded factual lookup or file discovery with references | Haiku 5.5, medium; max 15 turns, reports from 12 tool calls; Read, Glob, Grep, WebFetch, WebSearch |
| `fixer` | Implement an agreed change within owned files and verify it | Sonnet 5.5, medium; no turn limit; inherited tools, including shell, editing, skills, and MCP; Agent disabled |
| `inspector` | Review a supplied diff for concrete defects and explain their impact | Sonnet 5.5, high; max 60 turns, reports from 50 tool calls; Read, Glob, Grep, WebFetch, WebSearch |
| `consultant` | Advise on architecture, design trade-offs, and stubborn bugs; use sparingly | Opus 5.5, high; max 30 turns, reports from 24 tool calls; Read, Glob, Grep, WebFetch, WebSearch |
| `Explore` | Trace behavior and dependencies across the codebase; overrides the built-in | Sonnet 5.5, medium; max 40 turns, reports from 32 tool calls; Read, Glob, Grep |
| `Plan` built-in | Gather research during plan mode | Built-in read-only tools |
| `general-purpose` built-in | Mixed investigation and action without a matching specialist | Built-in available tools |

High-risk changes get an Inspector review. Opus types get that review from
Opus at high effort, with a budget of about 30 tool calls, instead of the
default Inspector. The delegation rule
([claude/rules/delegation.md](claude/rules/delegation.md)) lists which changes
qualify and the steps.

### Codex orchestration

| Agent | Assignment | Configuration |
| --- | --- | --- |
| `runner` | Bounded factual lookup or file discovery with references | Luna; read-only sandbox |
| `fixer` | Implement an agreed change within owned files and verify it | Terra; inherited permissions |
| `inspector` | Review a specified diff for concrete defects and explain their impact | Sol; read-only sandbox |
| `consultant` | Advise on architecture, difficult trade-offs, and stubborn bugs | Astra; read-only sandbox |
| `tracker` | Trace behavior, dependencies, and likely causes across files | Luna; read-only sandbox |
| `default` | Bounded mixed investigation and implementation without a matching specialist | Sol; inherited permissions |

Read-only roles run with `sandbox_mode = "read-only"`. Effort isn't fixed: the
Chief picks it for each task when spawning.

### OpenCode orchestration

| Agent | Assignment | Configuration |
| --- | --- | --- |
| `runner` | Bounded factual lookup or file discovery | DeepSeek V4.1 Flash, high; max 15 steps; inherited permissions |
| `fixer` | Implement an agreed change and verify it | DeepSeek V4.1 Flash, max; inherited permissions |
| `inspector` | Review a supplied diff for concrete defects | GLM-5.3-Flash, high; max 60 steps; inspection tools |
| `consultant` | Advise on architecture, design trade-offs, and stubborn bugs | GLM-5.3-Flash, max; max 30 steps; inspection tools |
| `explore` | Trace behavior and dependencies across files | DeepSeek V4.1 Flash, high; max 40 steps; built-in exploration permissions |
| `general` | Mixed investigation and implementation | DeepSeek V4.1 Flash, max; built-in general permissions |

Inspector and Consultant can only read, search, and fetch. `explore` and
`general` are OpenCode's built-in agents with this setup's models.

OpenCode uses only two models. DeepSeek V4.1 Flash does the lookups and
implementation, and GLM-5.3-Flash reviews and advises, so Inspector never
reviews code written by its own model. High-risk changes always get an
Inspector review. The riskiest also get one deep review from a fresh Inspector
session at max with a focus brief;
[opencode/AGENTS.md](opencode/AGENTS.md) lists which changes qualify and the
steps.

### Grok orchestration

| Agent | Assignment | Configuration |
| --- | --- | --- |
| `runner` | Bounded factual lookup or file discovery | Grok 4.7, low; inherited capabilities |
| `fixer` | Implement an agreed change and verify it | Grok 4.7, medium; inherited capabilities |
| `inspector` | Review a supplied diff for concrete defects | Grok 4.7, high; read-only capability mode |
| `consultant` | Advise on unresolved design choices and stubborn bugs | Grok 4.7, xhigh; read-only capability mode |

All roles use Grok 4.7 at different efforts. Inspector and Consultant run in
read-only capability mode.

## Install, update, uninstall

Needs Node.js 18+ and Python 3. It installs configuration only, not the tools
themselves or credentials.

```sh
npx @rujealfon/detective-crew-agents                  # choose tools from a menu
npx @rujealfon/detective-crew-agents --tool claude    # skip the menu (repeatable)
npx @rujealfon/detective-crew-agents --dry-run        # preview changes
npx @rujealfon/detective-crew-agents --update         # upgrade an earlier install
npx @rujealfon/detective-crew-agents --uninstall      # remove recognized files
```

Files you've customized are never overwritten: the installer stops and reports
them. `--update` backs up each file it replaces. Start a fresh tool session
afterward.

| Tool | Delegation policy | Agents |
| --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `~/.codex/agents/` |
| Claude Code | `~/.claude/rules/delegation.md` | `~/.claude/agents/` |
| OpenCode v2 | `~/.config/opencode/AGENTS.md` | `~/.config/opencode/agents/`, `opencode.jsonc` |
| Grok Build | `~/.grok/rules/delegation.md` | `~/.grok/agents/` |

All options, upgrade behavior, and project-level instructions:
[docs/install.md](docs/install.md).

## More docs

- [Orchestration details](docs/orchestration.md): per-tool rules, permissions, effort, and the fixer benchmark
- [Install reference](docs/install.md): menus, flags, upgrades, uninstall, instruction paths
- [Repository layout and testing](docs/repository.md): file map, CI, and tests
- [Local Codex usage reports](docs/session-usage.md): token usage per agent from Codex session logs

Run the tests:

```sh
python3 -B -m unittest discover -s tests -v
```

## License

[MIT](LICENSE), copyright 2026 Ruje Alfon.

Codex also installs [context and token-use guidance](codex/docs/token-usage.md)
to `~/.codex/docs/token-usage.md` as a standalone reference for manual use.
Token measurement and audits are separate from the delegation policy.
