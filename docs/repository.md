# Repository layout and testing


```text
detective-crew-agents/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── publish.yml
├── assets/
│   └── detective-crew/
├── bin/
│   └── detective-crew-agents
├── node_modules/
│   └── .bin/
│       └── detective-crew-agents
├── docs/
├── codex/
│   ├── AGENTS.md
│   ├── consultant.toml
│   ├── default.toml
│   ├── fixer.toml
│   ├── inspector.toml
│   ├── runner.toml
│   └── tracker.toml
├── claude/
│   ├── consultant.md
│   ├── fixer.md
│   ├── inspector.md
│   ├── runner.md
│   └── rules/
│       └── delegation.md
├── opencode/
│   ├── AGENTS.md
│   ├── consultant.md
│   ├── deep-inspector.md
│   ├── fixer.md
│   ├── inspector.md
│   ├── opencode.jsonc
│   └── runner.md
├── grok/
│   ├── consultant.md
│   ├── fixer.md
│   ├── inspector.md
│   ├── runner.md
│   └── rules/
│       └── delegation.md
├── tests/
│   ├── fixtures/
│   │   ├── pre-consultant-codex.json
│   │   ├── pre-consultant-grok.json
│   │   ├── pre-consultant-opencode.json
│   │   ├── pre-detective-install.json
│   │   ├── pre-revert-chief-inspector.json
│   │   ├── pre-two-model-opencode.json
│   │   └── shared-delegation.md
│   ├── test_session_usage.py
│   └── test_uninstall.py
├── tools/
│   └── session-usage.py
├── install-agents.py
├── install-claude-opencode.py
├── package.json
├── previous-install-hashes.json
├── README.md
└── LICENSE
```

| Path | Purpose |
| --- | --- |
| `codex/*.toml` | Codex agent definitions |
| `codex/docs/token-usage.md` | Installable context, delegation effort, and usage guidance |
| `claude/*.md` | Claude Code agent definitions |
| `opencode/{runner,fixer,inspector,consultant,deep-inspector}.md` | OpenCode v2 agent definitions |
| `opencode/opencode.jsonc` | OpenCode v2 built-in `explore` and `general` model, description, and step-limit overrides |
| `grok/*.md` | Grok Build agent definitions |
| `codex/AGENTS.md`, `opencode/AGENTS.md` | Provider-specific global delegation instructions |
| `claude/rules/delegation.md`, `grok/rules/delegation.md` | Provider-specific global delegation rules |
| `docs/*.md` | Detailed orchestration, install, repository, and usage-report docs |
| `assets/detective-crew/` | Crew poster and portraits used in the README |
| `package.json` | npm package `@rujealfon/detective-crew-agents` |
| `bin/detective-crew-agents` | `npx` entry point that runs `install-agents.py` |
| `install-agents.py` | Combined installer and uninstaller for all four tools, or a selected combination |
| `install-claude-opencode.py` | Compatibility entry point that calls the combined installer |
| `previous-install-hashes.json` | Fingerprints of recognized earlier configurations for safe upgrades |
| `.github/workflows/ci.yml` | Installer tests on Ubuntu for pushes, pull requests, and manual runs |
| `.github/workflows/publish.yml` | Runs those tests on `main`, then publishes when the version is not already on npm |
| `tools/session-usage.py` | Read-only local Codex session usage report; not installed or published |
| `tests/test_uninstall.py` | Tests installation, upgrades, removal, and preservation in temporary home directories |
| `tests/test_session_usage.py` | Synthetic tests for the local Codex usage report |
| `tests/fixtures/shared-delegation.md` | Frozen shared policy for upgrade regression tests |
| `tests/fixtures/pre-*.json` | Recorded earlier installs for upgrade regression tests |

The installer resolves source files relative to its own location, so the clone
can live anywhere. Repository files are the editable source; installed copies
are the configuration each tool reads.

Configuration syntax and installer behavior have been checked locally. Live
delegation and access to every configured model have not been verified.
Grok Build 1.0.46 discovers the native agents and delegation rule in a temporary
home directory with `grok inspect --json`.

[CI](../.github/workflows/ci.yml) runs the installer tests on Ubuntu with Python 3.13
for pushes, pull requests, and manual runs. The suite uses only the standard
library and installs into temporary home directories.
[Publish](../.github/workflows/publish.yml) runs the same tests after a push to
`main`, then publishes the package when its version is not already on npm.

Run the tests with Python's standard library:

```sh
python3 -B -m unittest discover -s tests -v
```

Agent format references: [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[Claude subagents](https://code.claude.com/docs/en/sub-agents), and
[OpenCode v2 agents](https://opencode.ai/v2/docs/agents). Grok Build references:
[subagents](https://docs.x.ai/build/features/subagents) and
[agent definitions](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-agent/README.md).
