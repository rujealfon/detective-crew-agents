from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASE_REF = os.environ.get("RELEASE_BASE_REF", "origin/main")
TUPLE = re.compile(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)\s*,')


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=False
    )


def installed_files():
    text = (ROOT / "install-agents.py").read_text()
    block = text.split("files = [", 1)[1].split("\n    ]", 1)[0]
    return TUPLE.findall(block)


class ReleaseHashesTest(unittest.TestCase):
    def test_changed_sources_record_previous_hash(self):
        resolved = git("rev-parse", "--verify", f"{BASE_REF}^{{commit}}")
        if resolved.returncode != 0:
            message = (
                f"Cannot resolve base ref {BASE_REF!r}; fetch the base branch "
                "(for example `git fetch origin main`, or checkout with fetch-depth: 0)."
            )
            if os.environ.get("CI"):
                self.fail(message)
            self.skipTest(message)
        # Compare against the fork point, so a stale branch or a main that moved
        # during a publish run is not blamed for later releases on main.
        fork = git("merge-base", "HEAD", resolved.stdout.decode().strip())
        self.assertEqual(fork.returncode, 0, f"No merge base between HEAD and {BASE_REF}")
        base = fork.stdout.decode().strip()

        files = installed_files()
        self.assertGreaterEqual(
            len(files), 20, "install-agents.py files list could not be parsed"
        )
        previous = json.loads((ROOT / "previous-install-hashes.json").read_text())

        changed = []
        for source, target in files:
            shown = git("show", f"{base}:{source}")
            if shown.returncode != 0:
                continue  # new file, nothing was released before
            current = (ROOT / source).read_bytes()
            if shown.stdout == current:
                continue
            changed.append(source)
            digest = hashlib.sha256(shown.stdout).hexdigest()
            self.assertTrue(
                digest in previous.get(target, []),
                f"{source} changed since {BASE_REF}; add the sha256 of the released "
                f"version ({digest}) to previous-install-hashes.json under {target!r} "
                "so --update can replace it.",
            )


if __name__ == "__main__":
    unittest.main()
