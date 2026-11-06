# Install, upgrade, and uninstall

Full reference for the installer. The [README](../README.md#install-update-uninstall) has the short version.

## Global instructions and installation paths

`~` means your home directory. These paths are personal configuration and apply
across projects; they are separate from instruction files inside a repository.

| Tool | Policy source in this repo | Installed policy |
| --- | --- | --- |
| Codex | [codex/AGENTS.md](../codex/AGENTS.md) | `~/.codex/AGENTS.md` |
| Claude Code | [claude/rules/delegation.md](../claude/rules/delegation.md) | `~/.claude/rules/delegation.md` |
| OpenCode v2 | [opencode/AGENTS.md](../opencode/AGENTS.md) | `~/.config/opencode/AGENTS.md` |
| Grok Build | [grok/rules/delegation.md](../grok/rules/delegation.md) | `~/.grok/rules/delegation.md` |

Each policy contains only its provider's roles, effort controls, and delegation
instructions. These destinations match the tools' global instruction discovery:
[Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[Claude user-level rules](https://code.claude.com/docs/en/memory#user-level-rules),
[OpenCode instructions](https://opencode.ai/v2/docs/instructions), and
[Grok rules directories](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/12-project-rules.md#rules-directories).

The former root `delegation.md` has been replaced by these four source files.
Installed paths are unchanged. Run `npx @rujealfon/detective-crew-agents --update` to replace
recognized shared policies with the provider-specific versions and retain backups.
Customized instructions still stop the update before any files are changed.

Claude's Opus review steps install into `~/.claude/docs/opus-review.md`, outside
`~/.claude/rules/`, so they load only when the delegation rule points to them.
OpenCode's deep-review steps install into `~/.config/opencode/docs/deep-review.md`
for the same reason: OpenCode always loads `AGENTS.md`, but reads the doc only
when the policy points to it.

Agent definitions install into `~/.codex/agents/`, `~/.claude/agents/`,
`~/.config/opencode/agents/`, and `~/.grok/agents/`, respectively. OpenCode's
built-in role overrides also install into `~/.config/opencode/opencode.jsonc`.

Claude Code supports `~/.claude/CLAUDE.md` as global personal instructions.
It also loads global rules from `~/.claude/rules/`. This setup uses the separate
`delegation.md` rule so you can keep other personal instructions in `CLAUDE.md`.
An empty global `CLAUDE.md` is fine: the delegation rule still loads. There is no
need to duplicate the policy in both files. [Claude global instructions](https://code.claude.com/docs/en/memory#choose-where-to-put-claudemd-files)
and [global rules](https://code.claude.com/docs/en/memory#user-level-rules).

OpenCode's `runner`, `fixer`, `inspector`, `consultant`, and `deep-inspector` definitions live in
`~/.config/opencode/agents/*.md`. Its `explore` and `general` model and description overrides
live in `~/.config/opencode/opencode.jsonc`.

The OpenCode agents use two [OpenCode Go](https://opencode.ai/docs/go/) models:
DeepSeek V4.1 Flash for `runner`, `explore`, `fixer`, and `general`, and
GLM-5.3-Flash for `inspector`, `deep-inspector`, and `consultant`. By default, Go allows only the Europe and
United States regions, which blocks DeepSeek. Before you use the agents, have a
workspace owner or admin open **Settings › Privacy** in the
[OpenCode Console](https://opencode.ai/console) and select **Global** under
**Regions**. If you skip this, every agent except the three GLM agents fails. GLM-5.3-Flash
needs no privacy change. DeepSeek requests count double against your Go
allowance during peak hours: 01:00–04:00 and 06:00–10:00 UTC, Monday through
Friday.

For project-specific instructions, put `AGENTS.md` or `CLAUDE.md` inside the
repository. Claude Code v2.1.277 and later can load project `AGENTS.md`, with
loading determined by its Project instructions setting and existing project
`CLAUDE.md` files. To share a project `AGENTS.md` through `CLAUDE.md`, add this
line to the project's `CLAUDE.md`:

```markdown
@AGENTS.md
```

That import is a Claude-specific feature. OpenCode v2 reads `AGENTS.md` directly
and does not use `CLAUDE.md` as a fallback. [Claude project instruction loading](https://code.claude.com/docs/en/memory#agentsmd)
and [OpenCode v2 instructions](https://opencode.ai/v2/docs/instructions).

Grok Build loads global rules from `~/.grok/rules/` and project `AGENTS.md`
files. This setup installs native Grok agents and a separate delegation rule;
it does not change `~/.grok/config.toml` or your main model. Project agents under
`.grok/agents/` can override the global agents with the same names. Grok may also
load Claude instruction files and global rules when its compatibility settings
enable them. Each policy states which provider session it applies to. This
installer leaves compatibility settings unchanged.
Use `grok inspect --json` to inspect discovered configuration and `/config-agents`
to check the available agents. See
[Grok instructions](https://docs.x.ai/build/features/project-rules) and
[Grok subagents](https://docs.x.ai/build/features/subagents).

## Install or upgrade

Install the tools you intend to use. You also need Node.js 18 or newer, for
`npx`, and Python 3. The installer uses only Python's standard library. It
installs configuration and does not install the tools or configure credentials.

Run this from any directory:

```sh
npx @rujealfon/detective-crew-agents
```

On a terminal, that opens a checkbox menu titled `Install scope`. Every tool
starts checked, so `All` and each tool are highlighted. The arrow keys move,
Space toggles the current row, and Enter confirms every checked tool. Choosing
`All` checks or clears Codex, Claude, OpenCode, and Grok together. Any
combination can stay checked. A piped or other non-interactive run installs all
four tools.

At least one tool must stay checked, and Ctrl-C cancels with exit status 130.
Pass `--tool` once per tool to choose without the menu, or `--tool all` for every
tool (it cannot be combined with a specific tool). Preview first with `--dry-run`:

```sh
npx @rujealfon/detective-crew-agents --dry-run
npx @rujealfon/detective-crew-agents --tool grok
npx @rujealfon/detective-crew-agents --tool codex --tool grok
```

The custom roles are now named `runner` (formerly `fast`), `fixer` (`worker`),
`inspector` (`reviewer`), and Codex `tracker` (`explorer`). `consultant` replaces
Claude's former `oracle` and is new in the other tools.
Codex `default` and OpenCode’s built-in `explore` and `general` keep their names.
An update backs up and removes recognized old agent files as it installs the new
names. Customized old agents stop the update for manual review.

To upgrade an earlier version of this setup, preview and then apply the update.
`--update` opens an `Update scope` menu on a terminal when you omit `--tool`:

```sh
npx @rujealfon/detective-crew-agents --update --dry-run
npx @rujealfon/detective-crew-agents --update
npx @rujealfon/detective-crew-agents --tool codex --update
```

The installer checks the selected destinations before writing. Identical files stay as
they are. Without `--update`, a recognized earlier version stops the install with
exit status `1` and asks you to rerun with `--update`. With `--update`, it
replaces only files that match recorded earlier versions in [previous-install-hashes.json](../previous-install-hashes.json) and saves
a backup beside each changed file as `<filename>.bak-<UTC timestamp>`. Customized
instructions or agents cause it to stop before changing any files. `--update`
does not force replacement of unrecognized files.

If you have existing personal instructions, review the reported conflict and
merge the delegation policy into the appropriate instruction file manually.
Keep your existing instructions. The installer does not perform this merge.

If your customized `~/.config/opencode/opencode.jsonc` uses plain JSON and
already contains all the specified `explore` and `general` agent fields, the
installer preserves the entire file and continues. Extra settings, agents,
and agent fields stay intact. Uninstall still preserves this customized file.
Otherwise, unless it matches a recorded earlier version that `--update` replaces
with a backup, it reports a conflict before changing any files. Merge the entries
under `agents` from [opencode/opencode.jsonc](../opencode/opencode.jsonc) manually.
Configs with JSONC comments or trailing commas still require manual review.

Start fresh tool sessions after installing. To preview installation under another
home directory, add `--target-home /path/to/home --dry-run`. This option is also
useful for testing the installer without changing your personal configuration.

Inside a clone of this repository, `npx` finds this package locally and
runs the `detective-crew-agents` command from `node_modules/.bin`. That link
is included in the clone. The same flags also work through
`python3 install-agents.py`.

## Uninstall

`--uninstall` opens an `Uninstall scope` menu on a terminal when you omit
`--tool`. Preview which installed files would be removed, then remove the
recognized agent definitions and delegation rules:

```sh
npx @rujealfon/detective-crew-agents --uninstall --dry-run
npx @rujealfon/detective-crew-agents --uninstall
npx @rujealfon/detective-crew-agents --tool claude --uninstall
```

Add `--tool opencode` to remove one tool, repeat `--tool` for several, or check
any combination in the menu. Choosing `All` checks every tool.
Uninstall checks the same destinations as installation, limited to the tools you
selected. It removes files that match the current definitions or recorded earlier
versions of this setup.
Customized files, empty personal instruction files, symlinks, and directories
are preserved and reported for manual review. Recognized files are still removed
when other files need manual review; the command exits with status `1` if any
destination was preserved. Missing files are harmless, so you can rerun it.

Customized app settings, credentials, other agents, and upgrade backups stay in place.
The setup-owned OpenCode `opencode.jsonc` is removed when its contents match
the current setup or a recorded earlier version.
Backups are not restored automatically. To recover an earlier instruction file,
review its `.bak-<UTC timestamp>` copy and restore or merge it manually. Start
fresh tool sessions after uninstalling.

Use `--target-home /path/to/home` to uninstall from another home directory.
`--uninstall` and `--update` cannot be combined.
