# Maintaining this repository

- Edit the policy and agent sources here, not the installed copies under
  `~/.codex`, `~/.claude`, `~/.config/opencode`, or `~/.grok`. Then reinstall
  with `python3 install-agents.py --update`.
- When an installed source changes, record the previously released file's
  sha256 in `previous-install-hashes.json` and bump the version in
  `package.json`. `tests/test_release_hashes.py` enforces this.
- Keep the delegation policies project-agnostic: they ship to npm users, so
  name no repo-specific commands or paths.
