"""Install or uninstall personal Codex, Claude Code, OpenCode, and Grok Build agent setup files."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import termios
import tty

TOOLS = ("codex", "claude", "opencode", "grok")


def opencode_agents_match(installed, desired):
    """Accept configured agent fields while preserving unrelated personal settings."""
    try:
        config = json.loads(installed)
        required = json.loads(desired)["agents"]
    except (ValueError, UnicodeDecodeError):
        return False
    if not isinstance(config, dict) or not isinstance(config.get("agents"), dict):
        return False
    agents = config["agents"]
    return all(
        isinstance(agents.get(name), dict)
        and all(agents[name].get(key) == value for key, value in settings.items())
        for name, settings in required.items()
    )


def read_menu_key(fd):
    """Read one menu key. Arrows move, Space toggles, and Enter confirms."""
    char = os.read(fd, 1)
    if not char:
        return "eof"
    if char in (b"\r", b"\n"):
        return "enter"
    if char == b" ":
        return "space"
    if char == b"\x03":
        return "interrupt"
    if char != b"\x1b":
        return "other"
    sequence = b""
    while len(sequence) < 2:
        piece = os.read(fd, 2 - len(sequence))
        if not piece:
            return "eof"
        sequence += piece
    if sequence in (b"[A", b"OA"):
        return "up"
    if sequence in (b"[B", b"OB"):
        return "down"
    return "other"


def replace_menu(lines, previous_lines):
    """Draw lines over the previous menu and clear any leftover rows."""
    parts = [f"\033[{previous_lines}A"] if previous_lines else []
    parts.extend(f"\r\033[2K{line}\n" for line in lines)
    leftover = max(0, previous_lines - len(lines))
    parts.extend("\r\033[2K\n" for _ in range(leftover))
    if leftover:
        parts.append(f"\033[{leftover}A")
    sys.stdout.write("".join(parts))
    sys.stdout.flush()
    return len(lines)


def render_scope_menu(title, labels, checked_rows, cursor, previous_lines, hint):
    """Draw a checkbox menu, replacing the previous draw in place."""
    lines = [f"\033[36m◆\033[0m {title}"]
    for index, (name, detail) in enumerate(labels):
        pointer = "❯" if index == cursor else " "
        if index in checked_rows:
            suffix = f" \033[2m{detail}\033[0m" if detail else ""
            lines.append(f"{pointer} \033[92m●\033[0m {name}{suffix}")
        else:
            text = f"{name} {detail}".strip()
            lines.append(f"\033[2m{pointer} ○ {text}\033[0m")
    lines.append(f"\033[2m{hint}\033[0m")
    return replace_menu(lines, previous_lines)


def render_cancelled(title, summary, previous_lines):
    """Replace the open menu with the struck-through choice and a red cancel line."""
    lines = [
        f"\033[36m◆\033[0m {title}",
        f"  \033[2;9m{summary}\033[0m",
        "  \033[3;31mCancelled\033[0m",
    ]
    replace_menu(lines, previous_lines)


def selection_summary(checked):
    if checked == set(TOOLS):
        return "All"
    labels = {"codex": "Codex", "claude": "Claude", "opencode": "OpenCode", "grok": "Grok"}
    names = [labels[name] for name in TOOLS if name in checked]
    return ", ".join(names) if names else "None"


def prompt_for_tools(parser, operation):
    """Ask for any combination of tools. All checks or clears every tool."""
    title = f"{operation.capitalize()} scope"
    labels = (
        ("All", "(Codex, Claude, OpenCode, and Grok)"),
        ("Codex", ""),
        ("Claude", ""),
        ("OpenCode", ""),
        ("Grok", ""),
    )
    checked = set(TOOLS)
    cursor = 0
    default_hint = "↑/↓ to navigate • Space: toggle • Enter: confirm"
    hint = default_hint
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    drawn = 0
    try:
        # Keep keystrokes already typed. The default setraw flushes unread input.
        tty.setraw(fd, termios.TCSANOW)
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        while True:
            rows = {index + 1 for index, name in enumerate(TOOLS) if name in checked}
            if len(rows) == len(TOOLS):
                rows.add(0)
            drawn = render_scope_menu(title, labels, rows, cursor, drawn, hint)
            key = read_menu_key(fd)
            hint = default_hint
            if key == "up":
                cursor = (cursor - 1) % len(labels)
            elif key == "down":
                cursor = (cursor + 1) % len(labels)
            elif key == "space":
                if cursor == 0:
                    checked = set() if checked == set(TOOLS) else set(TOOLS)
                else:
                    name = TOOLS[cursor - 1]
                    if name in checked:
                        checked.remove(name)
                    else:
                        checked.add(name)
            elif key == "enter":
                if not checked:
                    hint = "Select at least one tool • Space: toggle • Enter: confirm"
                    continue
                return tuple(name for name in TOOLS if name in checked)
            elif key == "interrupt":
                render_cancelled(title, selection_summary(checked), drawn)
                parser.exit(130)
            elif key == "eof":
                parser.exit(1, "No selection received.\n")
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def resolve_tools(parser, args):
    """Use --tool when given. Otherwise prompt on a terminal, or select every tool."""
    if args.tool:
        if "all" in args.tool and set(args.tool) != {"all"}:
            parser.error("--tool all cannot be combined with a specific tool")
        if "all" in args.tool:
            return TOOLS
        return tuple(name for name in TOOLS if name in args.tool)
    # Pipes and tests keep the previous behavior of operating on every tool.
    if sys.stdin.isatty() and sys.stdout.isatty():
        operation = "uninstall" if args.uninstall else "update" if args.update else "install"
        return prompt_for_tools(parser, operation)
    return TOOLS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-home", type=Path, default=Path.home())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--tool",
        action="append",
        choices=("all", *TOOLS),
        help="Operate on these tools. Repeat to select more than one. Prompts on a terminal when omitted.",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--update", action="store_true", help="Back up and replace recognized earlier setup files")
    action.add_argument("--uninstall", action="store_true", help="Remove recognized setup files and preserve customized files")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    home = args.target_home.expanduser().resolve()
    previous = json.loads((source / "previous-install-hashes.json").read_text())
    files = [
        ("codex/runner.toml", ".codex/agents/runner.toml"),
        ("codex/fixer.toml", ".codex/agents/fixer.toml"),
        ("codex/inspector.toml", ".codex/agents/inspector.toml"),
        ("codex/consultant.toml", ".codex/agents/consultant.toml"),
        ("codex/tracker.toml", ".codex/agents/tracker.toml"),
        ("codex/default.toml", ".codex/agents/default.toml"),
        ("codex/AGENTS.md", ".codex/AGENTS.md"),
        ("codex/docs/token-usage.md", ".codex/docs/token-usage.md"),
        ("claude/runner.md", ".claude/agents/runner.md"),
        ("claude/fixer.md", ".claude/agents/fixer.md"),
        ("claude/inspector.md", ".claude/agents/inspector.md"),
        ("claude/consultant.md", ".claude/agents/consultant.md"),
        ("claude/explore.md", ".claude/agents/explore.md"),
        ("claude/rules/delegation.md", ".claude/rules/delegation.md"),
        ("opencode/runner.md", ".config/opencode/agents/runner.md"),
        ("opencode/fixer.md", ".config/opencode/agents/fixer.md"),
        ("opencode/inspector.md", ".config/opencode/agents/inspector.md"),
        ("opencode/consultant.md", ".config/opencode/agents/consultant.md"),
        ("opencode/opencode.jsonc", ".config/opencode/opencode.jsonc"),
        ("opencode/AGENTS.md", ".config/opencode/AGENTS.md"),
        ("grok/runner.md", ".grok/agents/runner.md"),
        ("grok/fixer.md", ".grok/agents/fixer.md"),
        ("grok/inspector.md", ".grok/agents/inspector.md"),
        ("grok/consultant.md", ".grok/agents/consultant.md"),
        ("grok/rules/delegation.md", ".grok/rules/delegation.md"),
    ]
    legacy_files = [
        ("codex", ".codex/agents/fast.toml"),
        ("codex", ".codex/agents/worker.toml"),
        ("codex", ".codex/agents/reviewer.toml"),
        ("codex", ".codex/agents/explorer.toml"),
        ("claude", ".claude/agents/fast.md"),
        ("claude", ".claude/agents/worker.md"),
        ("claude", ".claude/agents/reviewer.md"),
        ("claude", ".claude/agents/oracle.md"),
        ("opencode", ".config/opencode/agents/fast.md"),
        ("opencode", ".config/opencode/agents/worker.md"),
        ("opencode", ".config/opencode/agents/reviewer.md"),
        ("grok", ".grok/agents/fast.md"),
        ("grok", ".grok/agents/worker.md"),
        ("grok", ".grok/agents/reviewer.md"),
        ("codex", ".codex/agents/chief-inspector.toml"),
        ("claude", ".claude/agents/chief-inspector.md"),
        ("opencode", ".config/opencode/agents/chief-inspector.md"),
        ("grok", ".grok/agents/chief-inspector.md"),
        ("claude", ".claude/docs/opus-review.md"),
        ("opencode", ".config/opencode/docs/deep-review.md"),
        ("opencode", ".config/opencode/agents/deep-inspector.md"),
    ]
    prompted = not args.tool and sys.stdin.isatty() and sys.stdout.isatty()
    selected = resolve_tools(parser, args)
    selected_names = set(selected)
    files = [item for item in files if item[0].split("/", 1)[0] in selected_names]
    if prompted or args.tool:
        label = "all" if selected_names == set(TOOLS) else ", ".join(selected)
        print(f"Selected: {label}")

    legacy_files = [target for tool, target in legacy_files if tool in selected_names]

    if args.uninstall:
        files += [(None, target) for target in legacy_files]
        preserved = False
        for relative_source, relative_target in files:
            target = home / relative_target
            if target.is_symlink() or (target.exists() and not target.is_file()):
                print(f"Preserved non-regular file: {target}")
                preserved = True
                continue
            if not target.exists():
                print(f"Not installed: {target}")
                continue
            installed = target.read_bytes()
            current = (source / relative_source).read_bytes() if relative_source else None
            digest = hashlib.sha256(installed).hexdigest()
            # Empty personal files can predate this setup; leave them in place.
            recognized = installed and (installed == current or digest in previous.get(relative_target, []))
            if not recognized:
                print(f"Preserved customized or unrecognized file: {target}")
                preserved = True
                continue
            if args.dry_run:
                print(f"Would remove: {target}")
            else:
                target.unlink()
                print(f"Removed: {target}")
        if preserved:
            parser.exit(1, "Some files were preserved. Review the reported paths to finish removal manually.\n")
        return

    # Preflight every file so a conflict preserves the entire installed setup.
    changes = []
    for relative_source, relative_target in files:
        contents = (source / relative_source).read_bytes()
        target = home / relative_target
        if target.is_symlink() or (target.exists() and not target.is_file()):
            parser.exit(1, f"Refusing to replace non-regular file: {target}\n")
        old = target.read_bytes() if target.exists() else None
        if old is not None and old != contents:
            if relative_source == "opencode/opencode.jsonc" and opencode_agents_match(old, contents):
                # Preserve the complete personal config, including its formatting.
                changes.append((target, old, old))
                continue
            digest = hashlib.sha256(old).hexdigest()
            if digest not in previous.get(relative_target, []):
                parser.exit(1, f"Unrecognized existing instructions or agent; preserved unchanged: {target}\n")
            if not args.update:
                parser.exit(1, f"Recognized earlier setup at {target}. Rerun with --update to back up and replace it.\n")
        changes.append((target, contents, old))

    # Retired names are checked before any writes, just like their replacements.
    retired = []
    for relative_target in legacy_files:
        target = home / relative_target
        if target.is_symlink() or (target.exists() and not target.is_file()):
            parser.exit(1, f"Refusing to replace non-regular file: {target}\n")
        if not target.exists():
            continue
        old = target.read_bytes()
        if hashlib.sha256(old).hexdigest() not in previous.get(relative_target, []):
            parser.exit(1, f"Unrecognized existing instructions or agent; preserved unchanged: {target}\n")
        if not args.update:
            parser.exit(1, f"Recognized earlier setup at {target}. Rerun with --update to back up and replace it.\n")
        retired.append((target, old))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for target, contents, old in changes:
        action = "Already installed" if old == contents else "Update" if old is not None else "Install"
        if args.dry_run or old == contents:
            print(f"{action}: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if old is not None:
            backup = target.with_name(target.name + ".bak-" + stamp)
            with backup.open("xb") as output:
                output.write(old)
            print(f"Backup: {backup}")
        if old is None:
            with target.open("xb") as output:
                output.write(contents)
        else:
            # Replace a complete file, so an interrupted write cannot truncate it.
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                    temporary_path = Path(output.name)
                    output.write(contents)
                shutil.copymode(target, temporary_path)
                temporary_path.replace(target)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()
        print(f"{action}: {target}")

    for target, old in retired:
        if args.dry_run:
            print(f"Would retire: {target}")
            continue
        backup = target.with_name(target.name + ".bak-" + stamp)
        with backup.open("xb") as output:
            output.write(old)
        target.unlink()
        print(f"Backup: {backup}")
        print(f"Retired: {target}")


if __name__ == "__main__":
    main()
