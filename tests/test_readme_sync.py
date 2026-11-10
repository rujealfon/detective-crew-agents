import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ("runner", "fixer", "inspector", "consultant", "explore")


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def parse_frontmatter(text, name):
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", f"{name}: missing opening ---"
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    assert end is not None, f"{name}: missing closing ---"
    fields = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def agent_settings():
    settings = {}
    for agent in AGENTS:
        name = f"claude/{agent}.md"
        fields = parse_frontmatter(read(name), name)
        for key in ("model", "effort"):
            assert fields.get(key), f"{name}: frontmatter has no {key}"
        settings[agent] = (fields["model"], fields["effort"])
    return settings


def split_row(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def display_name(model):
    match = re.fullmatch(r"claude-([a-z]+)-(\d+(?:-\d+)*)", model)
    assert match, f"unrecognized Claude model id: {model!r}"
    return f"{match.group(1).capitalize()} {match.group(2).replace('-', '.')}"


def model_table_settings(readme):
    """Return {agent: (model, effort)} from the Claude Code row of the model table."""
    lines = readme.splitlines()
    header_idx = [
        i for i, line in enumerate(lines)
        if line.startswith("|") and all(f"`{a}`" in line for a in AGENTS)
    ]
    assert len(header_idx) == 1, (
        f"README.md: expected exactly one model table header with {AGENTS}, found {len(header_idx)}"
    )
    header = split_row(lines[header_idx[0]])
    rows = []
    for line in lines[header_idx[0] + 1:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    claude_rows = [r for r in rows if r.startswith("| Claude Code |")]
    assert len(claude_rows) == 1, "README.md: expected exactly one '| Claude Code |' model row"
    cells = split_row(claude_rows[0])
    assert len(cells) == len(header), "README.md: Claude Code row column count differs from header"
    result = {}
    for agent in AGENTS:
        assert f"`{agent}`" in header, f"README.md: model table lacks column `{agent}`"
        cell = cells[header.index(f"`{agent}`")]
        match = re.fullmatch(r"`([^`]+)`,\s*(\w+)", cell)
        assert match, f"README.md: model table cell for {agent} not like '`model`, effort': {cell!r}"
        result[agent] = (match.group(1), match.group(2))
    return result


def role_table_configs(readme):
    """Return {agent: configuration cell} from the table under the Claude orchestration heading."""
    lines = readme.splitlines()
    heading = [i for i, line in enumerate(lines) if line.strip() == "### Claude orchestration"]
    assert len(heading) == 1, "README.md: expected exactly one '### Claude orchestration' heading"
    header = None
    for i in range(heading[0] + 1, len(lines)):
        if lines[i].startswith("#"):
            break
        if lines[i].startswith("| Agent |"):
            header = i
            break
    assert header is not None, "README.md: no role table under '### Claude orchestration'"
    assert split_row(lines[header]) == ["Agent", "Assignment", "Configuration"], (
        f"README.md: Claude role table header changed: {lines[header]!r}"
    )
    configs = {}
    for line in lines[header + 2:]:
        if not line.startswith("|"):
            break
        cells = split_row(line)
        assert len(cells) == 3, f"README.md: malformed Claude role row: {line!r}"
        match = re.fullmatch(r"`(\w+)`", cells[0])
        if match and match.group(1).lower() in AGENTS:
            agent = match.group(1).lower()
            assert agent not in configs, f"README.md: duplicate Claude role row {cells[0]}"
            configs[agent] = cells[2]
    assert sorted(configs) == sorted(AGENTS), (
        f"README.md: Claude role table has agents {sorted(configs)}, expected {sorted(AGENTS)}"
    )
    return configs


class ReadmeSyncTests(unittest.TestCase):
    def test_model_table_matches_agent_files(self):
        table = model_table_settings(read("README.md"))
        self.assertEqual(sorted(table), sorted(AGENTS))
        for agent, expected in agent_settings().items():
            self.assertEqual(
                table[agent], expected,
                f"README.md model table for {agent} is {table[agent]}, claude/{agent}.md says {expected}",
            )

    def test_role_table_matches_agent_files(self):
        configs = role_table_configs(read("README.md"))
        for agent, (model, effort) in agent_settings().items():
            prefix = f"{display_name(model)}, {effort}"
            self.assertTrue(
                configs[agent].startswith(prefix),
                f"README.md Claude role table for {agent} is {configs[agent]!r}, "
                f"claude/{agent}.md expects it to start with {prefix!r}",
            )

    def test_opus_review_is_inlined_in_delegation_policy(self):
        policy = read("claude/rules/delegation.md")
        self.assertIn('`model: "opus"`', policy)
        self.assertRegex(policy, r"override at high\s+effort")
        self.assertNotIn("opus-review.md", policy)
        self.assertFalse((ROOT / "claude/docs/opus-review.md").exists())

    def test_policies_stay_project_agnostic(self):
        forbidden = re.compile(
            r"\b(pnpm|yarn|npm (run|test)|test:guards)\b|root `test/`", re.IGNORECASE
        )
        for name in (
            "claude/rules/delegation.md",
            "opencode/AGENTS.md",
            "codex/AGENTS.md",
            "grok/rules/delegation.md",
        ):
            match = forbidden.search(read(name))
            found = match.group(0) if match else None
            self.assertIsNone(match, f"{name} mentions repo-specific {found!r}")


if __name__ == "__main__":
    unittest.main()
