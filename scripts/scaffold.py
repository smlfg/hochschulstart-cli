#!/usr/bin/env python3
"""Scaffold a new CLI repo from this reference template."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent

SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "dist", ".repo-work"}
SKIP_FILES = {"uv.lock", ".DS_Store"}
PACKAGE_DIR_NAME = "hochschulstart_cli"

PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
CLI_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="new repo directory (must not exist or be empty)")
    parser.add_argument("--package", required=True, help="python package name, e.g. my_cli")
    parser.add_argument("--cli-name", help="console command / distribution name (default: package with dashes)")
    parser.add_argument("--env-prefix", help="env var prefix (default: uppercase CLI name)")
    parser.add_argument("--desc", default="", help="short description for pyproject and README")
    parser.add_argument("--author", default="", help="author name for pyproject.toml")
    parser.add_argument("--github", choices=["public", "private"], help="create the GitHub repo and push")
    parser.add_argument("--no-verify", action="store_true", help="skip uv sync and the test run")
    parser.add_argument("--no-git", action="store_true", help="skip git init and the initial commit")
    return parser.parse_args()


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def is_text_file(path: Path) -> bool:
    with path.open("rb") as fh:
        return b"\0" not in fh.read(8192)


def render_text(text: str, package: str, cli_name: str, env_prefix: str) -> str:
    return (
        text.replace(PACKAGE_DIR_NAME, package)
        .replace("hochschulstart", cli_name)
        .replace("HOCHSCHULSTART", env_prefix)
    )


def patch_pyproject(text: str, args: argparse.Namespace, cli_name: str) -> str:
    desc = args.desc or f"{cli_name} CLI"
    text = re.sub(r'^description = ".*"$', f'description = "{desc}"', text, count=1, flags=re.M)
    if args.author:
        text = text.replace(
            'readme = "README.md"',
            f'readme = "README.md"\nauthors = [{{ name = "{args.author}" }}]',
            1,
        )
    return text


def scaffold_files(target: Path, args: argparse.Namespace, cli_name: str, env_prefix: str) -> None:
    for src in sorted(SOURCE.rglob("*")):
        rel = src.relative_to(SOURCE)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if src.is_dir() or src.name in SKIP_FILES:
            continue
        parts = [args.package if part == PACKAGE_DIR_NAME else part for part in rel.parts]
        dst = target.joinpath(*parts)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if is_text_file(src):
            text = render_text(src.read_text(encoding="utf-8"), args.package, cli_name, env_prefix)
            if dst.name == "pyproject.toml":
                text = patch_pyproject(text, args, cli_name)
            dst.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(src, dst)


def check_leftovers(target: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(target).parts):
            continue
        if not is_text_file(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in (PACKAGE_DIR_NAME, "hochschulstart", "HOCHSCHULSTART"):
            if token in text:
                offenders.append(f"{path.relative_to(target)}: {token}")
                break
    return offenders


def main() -> int:
    args = parse_args()
    package = args.package
    if not PACKAGE_RE.match(package):
        print(f"error: --package must match {PACKAGE_RE.pattern}", file=sys.stderr)
        return 2
    cli_name = args.cli_name or package.replace("_", "-")
    if not CLI_RE.match(cli_name):
        print(f"error: --cli-name must match {CLI_RE.pattern}", file=sys.stderr)
        return 2
    env_prefix = args.env_prefix or cli_name.replace("-", "_").upper()
    if not PREFIX_RE.match(env_prefix):
        print(f"error: --env-prefix must match {PREFIX_RE.pattern}", file=sys.stderr)
        return 2

    target: Path = args.target.resolve()
    if target.exists() and any(target.iterdir()):
        print(f"error: target {target} exists and is not empty", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)

    scaffold_files(target, args, cli_name, env_prefix)
    print(f"scaffolded {cli_name} -> {target}")

    if not args.no_git:
        run(["git", "init", "-q"], target)
        run(["git", "add", "-A"], target)
        commit = run(
            ["git", "commit", "-q", "-m", f"chore: scaffold {cli_name} from hochschulstart"],
            target,
            check=False,
        )
        if commit.returncode != 0:
            print("warning: initial commit skipped (git identity missing?)", file=sys.stderr)

    if not args.no_verify:
        if shutil.which("uv"):
            sync = run(["uv", "sync", "--extra", "dev"], target, check=False)
            if sync.returncode != 0:
                print(sync.stderr[-800:], file=sys.stderr)
                return 1
            tests = run(["uv", "run", "--extra", "dev", "pytest", "-q"], target, check=False)
            print(tests.stdout[-800:] or tests.stderr[-800:])
            if tests.returncode != 0:
                return 1
        else:
            print("warning: uv not found, skipping verification", file=sys.stderr)

    if args.github:
        gh = run(
            ["gh", "repo", "create", target.name, f"--{args.github}", "--source", ".", "--remote", "origin", "--push"],
            target,
            check=False,
        )
        if gh.returncode != 0:
            print(gh.stderr, file=sys.stderr)
            return 1
        print(gh.stdout.strip())

    leftovers = check_leftovers(target)
    if leftovers:
        print("warning: unreplaced tokens:", *leftovers[:10], sep="\n  ", file=sys.stderr)

    print(f"next: cd {target} && uv run --extra dev pytest -q")
    return 0


if __name__ == "__main__":
    sys.exit(main())
