from pathlib import Path
import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
POLICIES = {
    ".codex/AGENTS.md": "codex/AGENTS.md",
    ".claude/rules/delegation.md": "claude/rules/delegation.md",
    ".config/opencode/AGENTS.md": "opencode/AGENTS.md",
    ".grok/rules/delegation.md": "grok/rules/delegation.md",
}
PRE_DETECTIVE = json.loads((ROOT / "tests/fixtures/pre-detective-install.json").read_text())
PRE_REVERT = json.loads((ROOT / "tests/fixtures/pre-revert-chief-inspector.json").read_text())
LEGACY_POLICY = (ROOT / "tests/fixtures/shared-delegation.md").read_bytes()


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="agent-uninstall-test-")
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name).resolve() / "home"
        installed = self.run_command()
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.installed_files = [path for path in self.home.rglob("*") if path.is_file()]
        self.assertEqual(len(self.installed_files), 26)

    def test_codex_token_reference_is_installed_and_removed(self):
        reference = self.home / ".codex/docs/token-usage.md"
        self.assertEqual(reference.read_bytes(), (ROOT / "codex/docs/token-usage.md").read_bytes())
        policy = (self.home / ".codex/AGENTS.md").read_text()
        self.assertNotIn("docs/token-usage.md", policy)
        result = self.run_command("--tool", "codex", "--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(reference.exists())
        self.assertTrue((self.home / ".claude/rules/delegation.md").exists())

    def test_codex_consultant_upgrade_backs_up_previous_files(self):
        previous = json.loads((ROOT / "tests/fixtures/pre-consultant-codex.json").read_text())
        consultant = self.home / ".codex/agents/consultant.toml"
        consultant.unlink()
        for name, contents in previous.items():
            (self.home / name).write_text(contents)
        config = self.home / ".codex/config.toml"
        config.write_text('model = "personal-model"\n')
        before = {path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}

        preview = self.run_command("--tool", "codex", "--update", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse(consultant.exists())
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(list(self.home.rglob("*.bak-*")), [])

        updated = self.run_command("--tool", "codex", "--update")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(consultant.read_bytes(), (ROOT / "codex/consultant.toml").read_bytes())
        for name, contents in previous.items():
            installed = self.home / name
            source = "codex/AGENTS.md" if name.endswith("AGENTS.md") else "codex/inspector.toml"
            self.assertEqual(installed.read_bytes(), (ROOT / source).read_bytes())
            backups = list(installed.parent.glob(installed.name + ".bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), contents)
        self.assertEqual(config.read_bytes(), before[config])

        removed = self.run_command("--tool", "codex", "--uninstall")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(consultant.exists())
        self.assertEqual(config.read_bytes(), before[config])
        self.assertEqual(len(list(self.home.rglob("*.bak-*"))), 2)

    def write_pre_revert_install(self):
        for name, contents in PRE_REVERT.items():
            target = self.home / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)

    def test_chief_inspector_release_updates_back_with_exact_backups(self):
        self.write_pre_revert_install()
        retired = [name for name in PRE_REVERT if "chief-inspector" in name]
        self.assertEqual(len(retired), 4)
        runner = ".claude/agents/runner.md"
        sources = {**POLICIES, runner: "claude/runner.md"}
        # A file whose current source matches the old release is left in place without a backup.
        replaced = {name: source for name, source in sources.items() if (ROOT / source).read_text() != PRE_REVERT[name]}
        unchanged = [name for name in sources if name not in replaced]
        before = self.snapshot(self.home)

        preview = self.run_command("--update", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.snapshot(self.home), before)
        self.assertEqual(list(self.home.rglob("*.bak-*")), [])

        updated = self.run_command("--update")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        for name in retired:
            self.assertFalse((self.home / name).exists(), name)
        for name, source in replaced.items():
            self.assertEqual((self.home / name).read_bytes(), (ROOT / source).read_bytes(), name)
        for name in [*retired, *replaced]:
            installed = self.home / name
            backups = list(installed.parent.glob(installed.name + ".bak-*"))
            self.assertEqual(len(backups), 1, name)
            self.assertEqual(backups[0].read_text(), PRE_REVERT[name], name)
        for name in unchanged:
            self.assertEqual((self.home / name).read_text(), PRE_REVERT[name], name)
        self.assertEqual(len(list(self.home.rglob("*.bak-*"))), len(retired) + len(replaced))

    def test_customized_chief_inspector_blocks_update_without_mutation(self):
        self.write_pre_revert_install()
        custom = self.home / ".claude/agents/chief-inspector.md"
        custom.write_text("my own chief inspector\n")
        before = self.snapshot(self.home)

        updated = self.run_command("--update")
        self.assertEqual(updated.returncode, 1)
        self.assertIn("Unrecognized existing instructions or agent", updated.stderr)
        self.assertIn(str(custom), updated.stderr)
        self.assertEqual(self.snapshot(self.home), before)
        self.assertEqual(list(self.home.rglob("*.bak-*")), [])

    def test_personal_explore_override_blocks_update_without_mutation(self):
        home = Path(self.directory.name).resolve() / "explore-home"
        custom = home / ".claude/agents/explore.md"
        custom.parent.mkdir(parents=True)
        custom.write_text("---\nname: Explore\nmodel: haiku\n---\nmy own explore\n")
        before = self.snapshot(home)

        for arguments in ((), ("--update",)):
            result = self.run_in_home(home, *arguments)
            self.assertEqual(result.returncode, 1, arguments)
            self.assertIn("Unrecognized existing instructions or agent", result.stderr)
            self.assertIn(str(custom), result.stderr)
            self.assertEqual(self.snapshot(home), before)
            self.assertEqual(list(home.rglob("*.bak-*")), [])

    def test_tool_update_retires_only_that_tools_chief_inspector(self):
        self.write_pre_revert_install()
        updated = self.run_command("--tool", "claude", "--update")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        retired = self.home / ".claude/agents/chief-inspector.md"
        self.assertFalse(retired.exists())
        backups = list(retired.parent.glob(retired.name + ".bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), PRE_REVERT[".claude/agents/chief-inspector.md"])
        for name, contents in PRE_REVERT.items():
            if name.startswith(".claude/"):
                continue
            installed = self.home / name
            self.assertEqual(installed.read_text(), contents, name)
            self.assertEqual(list(installed.parent.glob(installed.name + ".bak-*")), [], name)

    def test_uninstall_removes_chief_inspector_files(self):
        self.write_pre_revert_install()
        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        for name in PRE_REVERT:
            self.assertFalse((self.home / name).exists(), name)

    def test_opencode_consultant_upgrade_backs_up_previous_files(self):
        previous = json.loads((ROOT / "tests/fixtures/pre-consultant-opencode.json").read_text())
        consultant = self.home / ".config/opencode/agents/consultant.md"
        consultant.unlink()
        for name, contents in previous.items():
            (self.home / name).write_text(contents)
        config = self.home / ".config/opencode/opencode.jsonc"
        personal = json.loads(config.read_text())
        personal["mcp"] = {"personal": {"type": "local", "command": ["my-mcp"]}}
        personal["agents"]["personal"] = {"model": "my-provider/my-model"}
        config.write_text(json.dumps(personal, indent=4) + "\n\n")
        before = self.snapshot(self.home)

        preview = self.run_command("--tool", "opencode", "--update", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.snapshot(self.home), before)

        updated = self.run_command("--tool", "opencode", "--update")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(consultant.read_bytes(), (ROOT / "opencode/consultant.md").read_bytes())
        backups = {}
        for name, contents in previous.items():
            installed = self.home / name
            source = "opencode/AGENTS.md" if name.endswith("AGENTS.md") else "opencode/inspector.md"
            self.assertEqual(installed.read_bytes(), (ROOT / source).read_bytes())
            matches = list(installed.parent.glob(installed.name + ".bak-*"))
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].read_bytes(), contents.encode())
            backups[str(matches[0].relative_to(self.home))] = contents.encode()
        upgraded = self.snapshot(self.home)
        self.assertEqual({name: data for name, data in upgraded.items() if ".bak-" in name}, backups)
        self.assertEqual(config.read_bytes(), before[str(config.relative_to(self.home))])
        self.assertEqual({name: data for name, data in upgraded.items()
                          if not name.startswith(".config/opencode/")},
                         {name: data for name, data in before.items()
                          if not name.startswith(".config/opencode/")})

        removed = self.run_command("--tool", "opencode", "--uninstall")
        self.assertEqual(removed.returncode, 1, removed.stderr)
        self.assertFalse(consultant.exists())
        self.assertEqual(self.snapshot(self.home), {
            **{name: data for name, data in before.items()
               if not name.startswith(".config/opencode/") or name.endswith("opencode.jsonc")},
            **backups,
        })

    def test_opencode_consultant_and_inspector_models_and_permissions(self):
        expected_permissions = ['  - action: "*"', '    resource: "*"', '    effect: deny']
        for action in ("read", "glob", "grep", "webfetch", "websearch"):
            expected_permissions.extend((f"  - action: {action}", '    resource: "*"', '    effect: allow'))
        for agent, model in (("consultant", "glm-5.3-flash#max"),
                             ("inspector", "glm-5.3-flash#high"),
                             ("deep-inspector", "glm-5.3-flash#max")):
            with self.subTest(agent=agent):
                installed = self.home / f".config/opencode/agents/{agent}.md"
                self.assertEqual(installed.read_bytes(), (ROOT / f"opencode/{agent}.md").read_bytes())
                frontmatter = installed.read_text().split("---\n", 2)[1]
                self.assertIn(f"model: opencode-go/{model}\n", frontmatter)
                self.assertIn("mode: subagent\n", frontmatter)
                # Exact allowlist plus the deny-all rule excludes shell, edits, and subagents.
                self.assertEqual(frontmatter.split("permissions:\n", 1)[1].splitlines(), expected_permissions)

    def test_opencode_deep_review_is_inlined_in_policy(self):
        policy = (self.home / ".config/opencode/AGENTS.md").read_text()
        self.assertIn("launch `deep-inspector`", policy)
        self.assertIn("Use `deep-inspector` for nothing else.", policy)
        self.assertNotIn("deep-review.md", policy)
        self.assertFalse((self.home / ".config/opencode/docs").exists())
        self.assertFalse((self.home / ".claude/docs").exists())

    def test_update_retires_and_uninstall_removes_old_review_docs(self):
        old_docs = {
            ".claude/docs/opus-review.md": (ROOT / "tests/fixtures/old-opus-review.md").read_bytes(),
            ".config/opencode/docs/deep-review.md": (ROOT / "tests/fixtures/old-deep-review.md").read_bytes(),
        }
        for name, contents in old_docs.items():
            (self.home / name).parent.mkdir(parents=True, exist_ok=True)
            (self.home / name).write_bytes(contents)

        uninstalled_home = self.fresh_home("old-docs-uninstall")
        for name, contents in old_docs.items():
            (uninstalled_home / name).parent.mkdir(parents=True, exist_ok=True)
            (uninstalled_home / name).write_bytes(contents)
        result = self.run_in_home(uninstalled_home, "--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in old_docs:
            self.assertFalse((uninstalled_home / name).exists(), name)

        updated = self.run_command("--update")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        for name, contents in old_docs.items():
            installed = self.home / name
            self.assertFalse(installed.exists(), name)
            backups = list(installed.parent.glob(installed.name + ".bak-*"))
            self.assertEqual(len(backups), 1, name)
            self.assertEqual(backups[0].read_bytes(), contents)

    def test_claude_uninstall_leaves_the_old_opencode_review_doc(self):
        home = self.fresh_home("old-docs-claude-uninstall")
        claude_doc = home / ".claude/docs/opus-review.md"
        opencode_doc = home / ".config/opencode/docs/deep-review.md"
        opencode_contents = (ROOT / "tests/fixtures/old-deep-review.md").read_bytes()
        for doc, fixture in ((claude_doc, "old-opus-review.md"), (opencode_doc, "old-deep-review.md")):
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_bytes((ROOT / "tests/fixtures" / fixture).read_bytes())
        result = self.run_in_home(home, "--tool", "claude", "--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(claude_doc.exists())
        self.assertEqual(opencode_doc.read_bytes(), opencode_contents)

    def test_opencode_agent_step_limits(self):
        for agent, steps in (("runner", "15"), ("inspector", "60"), ("deep-inspector", "60"),
                             ("consultant", "30")):
            with self.subTest(agent=agent):
                frontmatter = (self.home / f".config/opencode/agents/{agent}.md").read_text().split("---\n", 2)[1]
                self.assertIn(f"steps: {steps}\n", frontmatter)
        fixer = (self.home / ".config/opencode/agents/fixer.md").read_text().split("---\n", 2)[1]
        self.assertNotIn("steps:", fixer)
        agents = json.loads((self.home / ".config/opencode/opencode.jsonc").read_text())["agents"]
        self.assertEqual(agents["explore"]["steps"], 40)
        self.assertNotIn("steps", agents["general"])

    def test_opencode_uses_only_deepseek_and_glm(self):
        allowed = {"opencode-go/deepseek-v4.1-flash", "opencode-go/glm-5.3-flash"}
        models = []
        for agent in ("runner", "fixer", "inspector", "consultant", "deep-inspector"):
            text = (self.home / f".config/opencode/agents/{agent}.md").read_text()
            models.append(text.split("model: ", 1)[1].split("\n", 1)[0])
        config = json.loads((self.home / ".config/opencode/opencode.jsonc").read_text())
        models.extend(settings["model"] for settings in config["agents"].values())
        self.assertEqual({model.split("#", 1)[0] for model in models}, allowed)
        self.assertEqual(models[0], "opencode-go/deepseek-v4.1-flash#high")
        self.assertEqual(models[1], "opencode-go/deepseek-v4.1-flash#max")
        self.assertEqual(models[2], "opencode-go/glm-5.3-flash#high")
        self.assertEqual(config["agents"]["explore"]["model"], "opencode-go/deepseek-v4.1-flash#high")

    def test_opencode_two_model_upgrade_backs_up_muse_spark_files(self):
        previous = json.loads((ROOT / "tests/fixtures/pre-two-model-opencode.json").read_text())
        sources = {
            ".config/opencode/agents/runner.md": "opencode/runner.md",
            ".config/opencode/opencode.jsonc": "opencode/opencode.jsonc",
            ".config/opencode/AGENTS.md": "opencode/AGENTS.md",
            ".config/opencode/agents/inspector.md": "opencode/inspector.md",
        }
        for name, contents in previous.items():
            (self.home / name).write_text(contents)
        before = self.snapshot(self.home)

        blocked = self.run_command("--tool", "opencode")
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("--update", blocked.stderr)
        self.assertEqual(self.snapshot(self.home), before)

        updated = self.run_command("--tool", "opencode", "--update")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        for name, contents in previous.items():
            installed = self.home / name
            self.assertEqual(installed.read_bytes(), (ROOT / sources[name]).read_bytes())
            backups = list(installed.parent.glob(installed.name + ".bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), contents)

    def test_customized_opencode_consultant_blocks_upgrade_without_mutation(self):
        previous = json.loads((ROOT / "tests/fixtures/pre-consultant-opencode.json").read_text())
        for name, contents in previous.items():
            (self.home / name).write_text(contents)
        consultant = self.home / ".config/opencode/agents/consultant.md"
        consultant.write_text("My personal consultant\n")
        before = self.snapshot(self.home)

        result = self.run_command("--tool", "opencode", "--update")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(str(consultant), result.stderr)
        self.assertEqual(self.snapshot(self.home), before)

    def test_grok_consultant_upgrade_preserves_backup_and_personal_settings(self):
        previous = json.loads((ROOT / "tests/fixtures/pre-consultant-grok.json").read_text())
        consultant = self.home / ".grok/agents/consultant.md"
        consultant.unlink()
        for name, contents in previous.items():
            (self.home / name).write_text(contents)
        personal = {
            ".grok/config.toml": b'model = "personal-model"\n',
            ".grok/credentials.json": b'{"apiKey": "dummy-test-key"}\n',
        }
        for name, contents in personal.items():
            (self.home / name).write_bytes(contents)
        before = self.snapshot(self.home)

        preview = self.run_command("--tool", "grok", "--update", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.snapshot(self.home), before)

        updated = self.run_command("--tool", "grok", "--update")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(consultant.read_bytes(), (ROOT / "grok/consultant.md").read_bytes())
        policy = self.home / ".grok/rules/delegation.md"
        self.assertEqual(policy.read_bytes(), (ROOT / "grok/rules/delegation.md").read_bytes())
        backups = list(self.home.rglob("*.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].parent, policy.parent)
        self.assertTrue(backups[0].name.startswith(policy.name + ".bak-"))
        self.assertEqual(backups[0].read_bytes(), previous[str(policy.relative_to(self.home))].encode())
        upgraded = self.snapshot(self.home)
        self.assertEqual({name: data for name, data in upgraded.items()
                          if not name.startswith(".grok/") or name in personal},
                         {name: data for name, data in before.items()
                          if not name.startswith(".grok/") or name in personal})

        removed = self.run_command("--tool", "grok", "--uninstall")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(consultant.exists())
        self.assertEqual(self.snapshot(self.home), {
            **{name: data for name, data in before.items()
               if not name.startswith(".grok/") or name in personal},
            str(backups[0].relative_to(self.home)): previous[str(policy.relative_to(self.home))].encode(),
        })

    def test_grok_consultant_and_inspector_models_and_capabilities(self):
        for agent, effort in (("consultant", "xhigh"), ("inspector", "high")):
            with self.subTest(agent=agent):
                installed = self.home / f".grok/agents/{agent}.md"
                self.assertEqual(installed.read_bytes(), (ROOT / f"grok/{agent}.md").read_bytes())
                frontmatter = installed.read_text().split("---\n", 2)[1]
                self.assertIn(f"name: {agent}\n", frontmatter)
                self.assertIn("model: grok-4.7\n", frontmatter)
                self.assertIn(f"effort: {effort}\n", frontmatter)
                self.assertIn("capabilityMode: read-only\n", frontmatter)

    def test_customized_grok_consultant_blocks_upgrade_without_mutation(self):
        previous = json.loads((ROOT / "tests/fixtures/pre-consultant-grok.json").read_text())
        for name, contents in previous.items():
            (self.home / name).write_text(contents)
        consultant = self.home / ".grok/agents/consultant.md"
        consultant.write_text("My personal consultant\n")
        before = self.snapshot(self.home)

        result = self.run_command("--tool", "grok", "--update")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(str(consultant), result.stderr)
        self.assertEqual(self.snapshot(self.home), before)

    def run_command(self, *arguments):
        return subprocess.run(
            [sys.executable, str(ROOT / "install-agents.py"), "--target-home", str(self.home), *arguments],
            capture_output=True,
            text=True,
        )

    def run_in_home(self, home, *arguments):
        return subprocess.run(
            [sys.executable, str(ROOT / "install-agents.py"), "--target-home", str(home), *arguments],
            capture_output=True,
            text=True,
        )

    def fresh_home(self, name):
        home = self.home.parent / name
        home.mkdir()
        return home

    def installed_relative_paths(self, home):
        return {
            str(path.relative_to(home))
            for path in home.rglob("*")
            if path.is_file()
        }

    def run_with_terminal_input(self, home, keystrokes, *arguments, wait_for=None):
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [sys.executable, str(ROOT / "install-agents.py"), "--target-home", str(home), *arguments],
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )
        os.close(slave)
        output = bytearray()

        def read_for(timeout):
            ready, _, _ = select.select([master], [], [], timeout)
            if not ready:
                return "timeout"
            try:
                chunk = os.read(master, 4096)
            except OSError:
                return "eof"
            if not chunk:
                return "eof"
            output.extend(chunk)
            return "data"

        def fail_after_close(message):
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            os.close(master)
            self.fail(f"{message}\n{output.decode()}")

        if wait_for is None:
            if keystrokes:
                os.write(master, keystrokes)
        else:
            marker = wait_for.encode()
            while marker not in output:
                if read_for(5) == "data":
                    continue
                fail_after_close(f"timed out waiting for {wait_for!r}")
            os.write(master, keystrokes)
        while True:
            event = read_for(5)
            if event == "data":
                continue
            if event == "eof" or process.poll() is not None:
                break
            fail_after_close("timed out waiting for installer")
        process.wait(timeout=10)
        os.close(master)
        return process.returncode, output.decode()

    def pre_detective_home(self, name="pre-detective"):
        home = self.fresh_home(name)
        for relative, contents in PRE_DETECTIVE.items():
            path = home / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        return home

    def snapshot(self, home):
        return {str(path.relative_to(home)): path.read_bytes()
                for path in home.rglob("*") if path.is_file()}

    def test_rename_upgrade_requires_update_and_dry_run_preserves_old_install(self):
        home = self.pre_detective_home()
        before = self.snapshot(home)
        result = self.run_in_home(home)
        self.assertEqual(result.returncode, 1)
        self.assertIn("--update", result.stderr)
        self.assertEqual(self.snapshot(home), before)
        preview = self.run_in_home(home, "--update", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("Would retire:", preview.stdout)
        self.assertEqual(self.snapshot(home), before)

    def test_rename_upgrade_replaces_all_active_names_and_preserves_exact_backups(self):
        home = self.pre_detective_home()
        result = self.run_in_home(home, "--update")
        self.assertEqual(result.returncode, 0, result.stderr)
        current = self.snapshot(self.home)
        upgraded = self.snapshot(home)
        active = {name: contents for name, contents in upgraded.items() if ".bak-" not in name}
        self.assertEqual(active, current)
        changed = {name: contents for name, contents in PRE_DETECTIVE.items()
                   if name not in current or contents.encode() != current[name]}
        backups = {name.split(".bak-", 1)[0]: contents for name, contents in upgraded.items()
                   if ".bak-" in name}
        self.assertEqual(backups, {name: contents.encode() for name, contents in changed.items()})
        self.assertEqual(self.run_in_home(home, "--update").returncode, 0)
        self.assertEqual(self.snapshot(home), upgraded)
        self.assertEqual(self.run_in_home(home, "--uninstall").returncode, 0)
        self.assertEqual(self.snapshot(home), {name: contents for name, contents in upgraded.items()
                                               if ".bak-" in name})

    def test_old_customized_or_nonregular_agent_blocks_entire_upgrade(self):
        for kind in ("customized", "symlink", "directory"):
            with self.subTest(kind=kind):
                home = self.pre_detective_home(kind)
                path = home / ".grok/agents/worker.md"
                path.unlink()
                if kind == "customized":
                    path.write_text("Personal agent\n")
                elif kind == "symlink":
                    path.symlink_to(home / ".claude/agents/worker.md")
                else:
                    path.mkdir()
                before = self.snapshot(home)
                result = self.run_in_home(home, "--update")
                self.assertEqual(result.returncode, 1)
                self.assertIn(str(path), result.stderr)
                self.assertEqual(self.snapshot(home), before)
                self.assertEqual(path.is_symlink(), kind == "symlink")
                self.assertEqual(path.is_dir(), kind == "directory")

    def test_old_customized_and_symlink_agents_survive_uninstall(self):
        home = self.pre_detective_home()
        custom = home / ".codex/agents/worker.toml"
        custom.write_text("Personal old agent\n")
        link = home / ".claude/agents/oracle.md"
        external = home.parent / "personal-oracle.md"
        external.write_bytes(link.read_bytes())
        link.unlink()
        link.symlink_to(external)
        result = self.run_in_home(home, "--uninstall")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(custom.read_text(), "Personal old agent\n")
        self.assertTrue(link.is_symlink())
        self.assertTrue(external.is_file())
        self.assertFalse((home / ".codex/agents/fast.toml").exists())

    def test_customized_replacement_blocks_rename_upgrade(self):
        home = self.pre_detective_home()
        replacement = home / ".codex/agents/fixer.toml"
        replacement.write_text("Personal replacement\n")
        before = self.snapshot(home)
        result = self.run_in_home(home, "--update")
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(replacement), result.stderr)
        self.assertEqual(self.snapshot(home), before)

    def test_rename_migration_and_uninstall_respect_tool_scope(self):
        home = self.pre_detective_home()
        before = self.snapshot(home)
        result = self.run_in_home(home, "--tool", "codex", "--update")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((home / ".codex/agents/tracker.toml").is_file())
        self.assertFalse((home / ".codex/agents/explorer.toml").exists())
        self.assertEqual({name: data for name, data in self.snapshot(home).items()
                          if not name.startswith(".codex/")},
                         {name: data for name, data in before.items() if not name.startswith(".codex/")})
        preview = self.run_in_home(home, "--tool", "claude", "--uninstall", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertTrue((home / ".claude/agents/oracle.md").is_file())
        result = self.run_in_home(home, "--tool", "claude", "--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((home / ".claude/agents/oracle.md").exists())
        self.assertTrue((home / ".grok/agents/worker.md").is_file())
        self.assertTrue((home / ".codex/agents/fixer.toml").is_file())

    def test_dry_run_preserves_every_file_and_real_uninstall_is_idempotent(self):
        preferences = self.home / ".claude/CLAUDE.md"
        preferences.write_text("My personal instructions\n")
        backup = self.home / ".codex/AGENTS.md.bak-example"
        backup.write_text("Earlier instructions\n")
        before = {path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}

        preview = self.run_command("--uninstall", "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertTrue(all(not path.exists() for path in self.installed_files))
        self.assertEqual(preferences.read_text(), "My personal instructions\n")
        self.assertEqual(backup.read_text(), "Earlier instructions\n")
        self.assertTrue((self.home / ".claude/agents").is_dir())

        repeated = self.run_command("--uninstall")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)

    def test_grok_native_agents_and_policy_are_installed_exactly(self):
        expected = {
            ".grok/agents/runner.md": "grok/runner.md",
            ".grok/agents/fixer.md": "grok/fixer.md",
            ".grok/agents/inspector.md": "grok/inspector.md",
            ".grok/agents/consultant.md": "grok/consultant.md",
            ".grok/rules/delegation.md": "grok/rules/delegation.md",
        }
        installed = {
            str(path.relative_to(self.home))
            for path in (self.home / ".grok").rglob("*")
            if path.is_file()
        }
        self.assertEqual(installed, set(expected))
        for target, source in expected.items():
            with self.subTest(target=target):
                self.assertEqual((self.home / target).read_bytes(), (ROOT / source).read_bytes())

    def test_provider_policies_are_installed_exactly(self):
        for target, source in POLICIES.items():
            with self.subTest(target=target):
                self.assertEqual((self.home / target).read_bytes(), (ROOT / source).read_bytes())
        self.assertEqual(len({(self.home / target).read_bytes() for target in POLICIES}), 4)

    def install_legacy_policies(self):
        for target in POLICIES:
            (self.home / target).write_bytes(LEGACY_POLICY)

    def test_shared_legacy_policies_require_update_without_mutation(self):
        self.install_legacy_policies()
        before = {path: path.read_bytes() for path in self.installed_files}

        result = self.run_command()
        self.assertEqual(result.returncode, 1)
        self.assertIn("--update", result.stderr)
        self.assertEqual({path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}, before)

    def test_shared_legacy_policy_update_dry_run_preserves_every_file(self):
        self.install_legacy_policies()
        before = {path: path.read_bytes() for path in self.installed_files}
        entries = set(self.home.rglob("*"))

        result = self.run_command("--update", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({path: path.read_bytes() for path in self.installed_files}, before)
        self.assertEqual(set(self.home.rglob("*")), entries)
        for target in POLICIES:
            self.assertIn(f"Update: {self.home / target}", result.stdout)

    def test_shared_legacy_policies_upgrade_with_exact_backups(self):
        self.install_legacy_policies()
        result = self.run_command("--update")
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = []
        for target, source in POLICIES.items():
            policy = self.home / target
            with self.subTest(target=target):
                self.assertEqual(policy.read_bytes(), (ROOT / source).read_bytes())
                matches = list(policy.parent.glob(policy.name + ".bak-*"))
                self.assertEqual(len(matches), 1)
                self.assertEqual(matches[0].read_bytes(), LEGACY_POLICY)
                backups.extend(matches)
        self.assertEqual(set(self.home.rglob("*.bak-*")), set(backups))

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertTrue(all(not path.exists() for path in self.installed_files))
        self.assertTrue(all(path.read_bytes() == LEGACY_POLICY for path in backups))

    def test_customized_legacy_policy_blocks_all_updates_and_survives_uninstall(self):
        for target in POLICIES:
            with self.subTest(target=target):
                installed = self.run_command()
                self.assertEqual(installed.returncode, 0, installed.stderr)
                self.install_legacy_policies()
                custom = self.home / target
                custom.write_bytes(LEGACY_POLICY + b"\nMy personal delegation rule\n")
                before = {path: path.read_bytes() for path in self.installed_files}

                result = self.run_command("--update")
                self.assertEqual(result.returncode, 1)
                self.assertIn(str(custom), result.stderr)
                self.assertEqual({path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}, before)

                removed = self.run_command("--uninstall")
                self.assertEqual(removed.returncode, 1)
                self.assertEqual(custom.read_bytes(), before[custom])
                self.assertTrue(all(not path.exists() for path in self.installed_files if path != custom))
                custom.unlink()

    def test_uninstall_recognizes_shared_legacy_policies(self):
        self.install_legacy_policies()
        result = self.run_command("--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(not path.exists() for path in self.installed_files))

    def test_update_replaces_previous_opencode_agents_and_backs_them_up(self):
        earlier = {}
        for name, current, previous in (
            ("fast", "#high", "#xhigh"),
            ("reviewer", "glm-5.3-flash#max", "glm-5.3#max"),
        ):
            agent = self.home / f".config/opencode/agents/{name}.md"
            old_description = {
                "fast": "Handles focused exploration and straightforward independent tasks.",
                "reviewer": "Reviews complex logic, bugs, and security risks.",
            }[name]
            lines = PRE_DETECTIVE[str(agent.relative_to(self.home))].replace(current, previous).splitlines()
            earlier[agent] = ("\n".join(
                "description: " + old_description if line.startswith("description: ") else line
                for line in lines
            ) + "\n").encode()
            agent.write_bytes(earlier[agent])

        upgraded = self.run_command("--update")
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        for agent, contents in earlier.items():
            self.assertFalse(agent.exists())
            backups = list(agent.parent.glob(agent.name + ".bak-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), contents)

    def test_update_replaces_installed_glm_53_reviewer(self):
        agent = self.home / ".config/opencode/agents/reviewer.md"
        previous = PRE_DETECTIVE[str(agent.relative_to(self.home))].encode().replace(
            b"opencode-go/glm-5.3-flash#max",
            b"opencode-go/glm-5.3#max",
        )
        agent.write_bytes(previous)

        upgraded = self.run_command("--update")
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        self.assertFalse(agent.exists())
        backups = list(agent.parent.glob(agent.name + ".bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), previous)

    def test_customized_opencode_jsonc_blocks_update_and_is_preserved_on_uninstall(self):
        config = self.home / ".config/opencode/opencode.jsonc"
        config.write_text(config.read_text() + "\n// Personal settings\n")
        before = {path: path.read_bytes() for path in self.installed_files}
        upgraded = self.run_command("--update")
        self.assertEqual(upgraded.returncode, 1)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 1)
        self.assertEqual(config.read_bytes(), before[config])
        self.assertTrue(all(not path.exists() for path in self.installed_files if path != config))

    def test_update_preserves_compatible_personal_opencode_config_exactly(self):
        config = self.home / ".config/opencode/opencode.jsonc"
        personal = json.loads(config.read_text())
        personal["mcp"] = {"personal": {"type": "local", "command": ["my-mcp"]}}
        personal["agents"]["explore"]["temperature"] = 0.2
        personal["agents"]["personal"] = {"model": "my-provider/my-model"}
        contents = (json.dumps(personal, indent=4) + "\n\n").encode()
        config.write_bytes(contents)

        for arguments in (("--update", "--dry-run"), ("--update",), ("--update",)):
            with self.subTest(arguments=arguments):
                upgraded = self.run_command(*arguments)
                self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
                self.assertEqual(config.read_bytes(), contents)
                self.assertEqual(list(config.parent.glob(config.name + ".bak-*")), [])

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 1)
        self.assertEqual(config.read_bytes(), contents)
        self.assertTrue(all(not path.exists() for path in self.installed_files if path != config))

    def test_opencode_model_conflict_blocks_update_before_any_write(self):
        config = self.home / ".config/opencode/opencode.jsonc"
        personal = json.loads(config.read_text())
        personal["agents"]["explore"]["model"] = "personal-provider/personal-model"
        personal["mcp"] = {"personal": {"type": "local", "command": ["my-mcp"]}}
        config.write_text(json.dumps(personal))
        policy = self.home / ".codex/AGENTS.md"
        policy.write_bytes(b"")
        before = {path: path.read_bytes() for path in self.installed_files}

        upgraded = self.run_command("--update")
        self.assertEqual(upgraded.returncode, 1)
        self.assertNotIn("Traceback", upgraded.stderr)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(set(self.home.rglob("*.bak-*")), set())

    def test_invalid_opencode_config_blocks_update_without_mutation(self):
        config = self.home / ".config/opencode/opencode.jsonc"
        policy = self.home / ".codex/AGENTS.md"
        policy.write_bytes(b"")
        for contents in ("{invalid json", "[]", '{"agents": []}'):
            with self.subTest(contents=contents):
                config.write_text(contents)
                before = {path: path.read_bytes() for path in self.installed_files}
                upgraded = self.run_command("--update")
                self.assertEqual(upgraded.returncode, 1)
                self.assertNotIn("Traceback", upgraded.stderr)
                self.assertEqual({path: path.read_bytes() for path in before}, before)
                self.assertEqual(set(self.home.rglob("*.bak-*")), set())

    def test_uninstall_preserves_grok_config_credentials_and_customized_agent(self):
        config = self.home / ".grok/config.toml"
        config.write_text('model = "dummy-personal-model"\n')
        credentials = self.home / ".grok/credentials.json"
        credentials.write_text('{"apiKey": "dummy-test-key"}\n')
        agent = self.home / ".grok/agents/fixer.md"
        agent.write_text("My custom Grok agent\n")
        before = {path: path.read_bytes() for path in (config, credentials, agent)}

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 1)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertIn(str(agent), removed.stdout)
        self.assertTrue(all(not path.exists() for path in self.installed_files if path != agent))

    def test_customized_agent_and_instructions_are_preserved(self):
        policy = self.home / ".config/opencode/AGENTS.md"
        policy.write_text(policy.read_text() + "\nMy additional rule\n")
        agent = self.home / ".claude/agents/fixer.md"
        agent.write_text("My custom agent\n")
        before = {path: path.read_bytes() for path in (policy, agent)}

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 1)
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertFalse((self.home / ".codex/agents/runner.toml").exists())
        self.assertIn("Preserved", removed.stdout)

    def test_symlinks_and_directories_are_preserved(self):
        target = self.home / ".claude/agents/runner.md"
        external = Path(self.directory.name) / "external.md"
        external.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(external)
        directory = self.home / ".claude/agents/inspector.md"
        directory.unlink()
        directory.mkdir()

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 1)
        self.assertTrue(target.is_symlink())
        self.assertTrue(external.is_file())
        self.assertTrue(directory.is_dir())

    def test_recorded_earlier_agent_is_removed_but_empty_personal_file_is_preserved(self):
        earlier_agent = self.home / ".claude/agents/fast.md"
        earlier_agent.write_text(
            "---\n"
            "name: fast\n"
            "description: Handles focused exploration and straightforward independent tasks.\n"
            "model: sonnet\n"
            "effort: low\n"
            "---\n\n"
            "Complete the assigned task within its stated scope.\n"
            "Return concise findings and describe any verification.\n"
        )
        empty_policy = self.home / ".codex/AGENTS.md"
        empty_policy.write_bytes(b"")

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 1)
        self.assertFalse(earlier_agent.exists())
        self.assertTrue(empty_policy.is_file())
        self.assertEqual(empty_policy.read_bytes(), b"")

    def test_update_and_uninstall_cannot_be_combined(self):
        before = {path: path.read_bytes() for path in self.installed_files}
        result = self.run_command("--update", "--uninstall")
        self.assertEqual(result.returncode, 2)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_uninstall_after_upgrade_preserves_the_upgrade_backup(self):
        policy = self.home / ".codex/AGENTS.md"
        policy.write_bytes(b"")
        upgraded = self.run_command("--update")
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        backups = list(policy.parent.glob("AGENTS.md.bak-*"))
        self.assertEqual(len(backups), 1)

        removed = self.run_command("--uninstall")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse(policy.exists())
        self.assertEqual(backups[0].read_bytes(), b"")

    def test_tool_installs_only_the_selected_files(self):
        home = self.fresh_home("only-grok")
        result = self.run_in_home(home, "--tool", "grok")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Selected: grok", result.stdout)
        self.assertEqual(
            self.installed_relative_paths(home),
            {
                ".grok/agents/runner.md",
                ".grok/agents/fixer.md",
                ".grok/agents/inspector.md",
                ".grok/agents/consultant.md",
                ".grok/rules/delegation.md",
            },
        )

    def test_tool_uninstall_leaves_the_other_tools(self):
        before = self.installed_relative_paths(self.home)
        result = self.run_command("--tool", "claude", "--uninstall")
        self.assertEqual(result.returncode, 0, result.stderr)
        removed = {
            ".claude/agents/runner.md",
            ".claude/agents/fixer.md",
            ".claude/agents/inspector.md",
            ".claude/agents/consultant.md",
            ".claude/agents/explore.md",
            ".claude/rules/delegation.md",
        }
        self.assertEqual(self.installed_relative_paths(self.home), before - removed)
        self.assertTrue((self.home / ".codex/agents/runner.toml").is_file())

    def test_tool_update_leaves_other_legacy_policies(self):
        self.install_legacy_policies()
        result = self.run_command("--tool", "codex", "--update")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.home / ".codex/AGENTS.md").read_bytes(),
            (ROOT / "codex/AGENTS.md").read_bytes(),
        )
        self.assertEqual(len(list((self.home / ".codex").glob("AGENTS.md.bak-*"))), 1)
        for target in (".claude/rules/delegation.md", ".config/opencode/AGENTS.md", ".grok/rules/delegation.md"):
            self.assertEqual((self.home / target).read_bytes(), LEGACY_POLICY)
            self.assertEqual(list((self.home / target).parent.glob(Path(target).name + ".bak-*")), [])

    def test_unselected_customization_does_not_block_another_tool(self):
        home = self.fresh_home("custom-claude")
        agent = home / ".claude/agents/fixer.md"
        agent.parent.mkdir(parents=True)
        agent.write_text("My custom agent\n")

        result = self.run_in_home(home, "--tool", "grok")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(agent.read_text(), "My custom agent\n")
        self.assertTrue((home / ".grok/agents/fixer.md").is_file())

    def test_unknown_tool_is_rejected_without_writing(self):
        home = self.fresh_home("rejected-tool")
        result = self.run_in_home(home, "--tool", "cursor")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(home.rglob("*")), [])

    def test_interactive_choice_installs_one_tool(self):
        home = self.fresh_home("interactive-grok")
        returncode, output = self.run_with_terminal_input(
            home, b"nope \x1b[A \r", wait_for="Install scope"
        )
        self.assertEqual(returncode, 0, output)
        self.assertIn("Install scope", output)
        self.assertIn("Space: toggle", output)
        self.assertIn("Selected: grok", output)
        self.assertEqual(
            self.installed_relative_paths(home),
            {
                ".grok/agents/runner.md",
                ".grok/agents/fixer.md",
                ".grok/agents/inspector.md",
                ".grok/agents/consultant.md",
                ".grok/rules/delegation.md",
            },
        )

    def test_interactive_default_installs_every_tool(self):
        home = self.fresh_home("interactive-all")
        returncode, output = self.run_with_terminal_input(home, b"5\r", wait_for="Install scope")
        self.assertEqual(returncode, 0, output)
        self.assertIn("Install scope", output)
        self.assertIn("Selected: all", output)
        self.assertGreaterEqual(output.count("●"), len(("codex", "claude", "opencode", "grok")) + 1)
        self.assertEqual(len(self.installed_relative_paths(home)), 26)

    def test_interactive_update_confirms_the_highlighted_scope(self):
        before = {path: path.read_bytes() for path in self.installed_files}
        returncode, output = self.run_with_terminal_input(
            self.home, b"\r", "--update", "--dry-run", wait_for="Update scope"
        )
        self.assertEqual(returncode, 0, output)
        self.assertIn("Update scope", output)
        self.assertIn("Selected: all", output)
        self.assertEqual({path: path.read_bytes() for path in self.installed_files}, before)

    def test_tool_flag_skips_the_prompt(self):
        home = self.fresh_home("flag-skips-prompt")
        returncode, output = self.run_with_terminal_input(home, b"\r", "--tool", "opencode")
        self.assertEqual(returncode, 0, output)
        self.assertNotIn("Install scope", output)
        self.assertIn("Selected: opencode", output)
        self.assertEqual(
            self.installed_relative_paths(home),
            {
                ".config/opencode/agents/runner.md",
                ".config/opencode/agents/fixer.md",
                ".config/opencode/agents/inspector.md",
                ".config/opencode/agents/consultant.md",
                ".config/opencode/agents/deep-inspector.md",
                ".config/opencode/opencode.jsonc",
                ".config/opencode/AGENTS.md",
            },
        )

    def test_interactive_uninstall_removes_only_the_chosen_tool(self):
        returncode, output = self.run_with_terminal_input(
            self.home, b" \x1b[B\x1b[B \r", "--uninstall", wait_for="Uninstall scope"
        )
        self.assertEqual(returncode, 0, output)
        self.assertIn("Uninstall scope", output)
        self.assertIn("Selected: claude", output)
        self.assertFalse((self.home / ".claude/agents/runner.md").exists())
        self.assertTrue((self.home / ".grok/agents/runner.md").is_file())
        self.assertTrue((self.home / ".codex/agents/runner.toml").is_file())

    def test_interactive_selects_multiple_tools(self):
        home = self.fresh_home("interactive-two")
        # Clear All, then check Codex and Grok.
        returncode, output = self.run_with_terminal_input(
            home, b" \x1b[B \x1b[B\x1b[B\x1b[B \r", wait_for="Install scope"
        )
        self.assertEqual(returncode, 0, output)
        self.assertIn("Selected: codex, grok", output)
        self.assertEqual(
            self.installed_relative_paths(home),
            {
                ".codex/agents/runner.toml",
                ".codex/agents/fixer.toml",
                ".codex/agents/inspector.toml",
                ".codex/agents/consultant.toml",
                ".codex/agents/tracker.toml",
                ".codex/agents/default.toml",
                ".codex/AGENTS.md",
                ".codex/docs/token-usage.md",
                ".grok/agents/runner.md",
                ".grok/agents/fixer.md",
                ".grok/agents/inspector.md",
                ".grok/agents/consultant.md",
                ".grok/rules/delegation.md",
            },
        )

    def test_interactive_all_checks_every_tool_again(self):
        home = self.fresh_home("interactive-recheck-all")
        # Clear All, check Codex, return to All, and check every tool.
        returncode, output = self.run_with_terminal_input(
            home, b" \x1b[B \x1b[A \r", wait_for="Install scope"
        )
        self.assertEqual(returncode, 0, output)
        self.assertIn("Selected: all", output)
        self.assertEqual(len(self.installed_relative_paths(home)), 26)

    def test_interactive_cancel_is_red_and_changes_nothing(self):
        home = self.fresh_home("interactive-cancel")
        returncode, output = self.run_with_terminal_input(home, b"\x03", wait_for="Install scope")
        self.assertEqual(returncode, 130, output)
        self.assertIn("\033[3;31mCancelled\033[0m", output)
        self.assertIn("\033[2;9mAll\033[0m", output)
        self.assertEqual(self.installed_relative_paths(home), set())

    def test_interactive_empty_selection_is_not_confirmed(self):
        home = self.fresh_home("interactive-empty")
        returncode, output = self.run_with_terminal_input(
            home, b" \r\x1b[B \r", wait_for="Install scope"
        )
        self.assertEqual(returncode, 0, output)
        self.assertIn("Select at least one tool", output)
        self.assertIn("Selected: codex", output)
        self.assertTrue((home / ".codex/agents/runner.toml").is_file())
        self.assertFalse((home / ".grok/agents/runner.md").exists())

    def test_repeated_tool_flags_install_each_named_tool(self):
        home = self.fresh_home("two-tools")
        result = self.run_in_home(home, "--tool", "grok", "--tool", "codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Selected: codex, grok", result.stdout)
        prefixes = {path.split("/", 1)[0] for path in self.installed_relative_paths(home)}
        self.assertEqual(prefixes, {".codex", ".grok"})

    def test_tool_all_cannot_be_combined_with_a_specific_tool(self):
        home = self.fresh_home("all-and-one")
        result = self.run_in_home(home, "--tool", "all", "--tool", "grok")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cannot be combined", result.stderr)
        self.assertEqual(list(home.rglob("*")), [])


if __name__ == "__main__":
    unittest.main()
