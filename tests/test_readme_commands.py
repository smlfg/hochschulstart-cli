"""Every documented shell command must appear in ``--help`` (subcommand names)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

COMMAND_RE = re.compile(r"`(hochschulstart(?:\s+[\w-]+)*)`")


def test_readme_commands_in_help():
    text = README.read_text(encoding="utf-8")
    commands = COMMAND_RE.findall(text)
    assert commands, "README must document at least one `hochschulstart ...` command"

    proc = subprocess.run(
        [sys.executable, "-m", "hochschulstart_cli", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    help_text = proc.stdout
    assert proc.returncode == 0

    for cmd in commands:
        parts = cmd.split()
        assert parts[0] == "hochschulstart"
        if len(parts) == 1:
            continue
        sub = parts[1]
        assert sub in help_text, f"README documents `{cmd}` but --help lacks subcommand {sub}"
