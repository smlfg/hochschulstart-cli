# hochschulstart

Reference template for Python CLIs and MCP servers: patterns learned from a stresstest across six derived tools (exit codes, JSON errors, validation, config precedence, atomic state, URL joining, and network-free tests) **plus** a copyable black-box pytest suite for MCP servers.

## Install and test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
hochschulstart --help
```

With uv: `uv sync --extra dev` then `uv run --extra dev pytest`.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid input (flags, arguments, validation); argparse usage errors map here (not 2) |
| 2 | Authentication / authorization |
| 3 | Network / remote service |
| 4 | Parse error (JSON, config, state) |
| 130 | Interrupted (Ctrl-C) or EOF on interactive input |

Implementation: `hochschulstart_cli.exit_codes` and `hochschulstart_cli.errors.ArgumentParser`.

## Commands

Global flags: `--json` (single JSON object on stdout for result or error), `--dry-run` (no state writes).

- `hochschulstart version` — print package version
- `hochschulstart config` — show resolved configuration (env overrides file and keyring)
- `hochschulstart state PATH` — load/merge/save JSON state (`--set KEY=VALUE`, respects `--dry-run`)
- `hochschulstart url BASE SEGMENT` — join URL without dropping `base` path prefix
- `hochschulstart validate` — exercise validators (`--count`, `--date`, `--file`)

Examples:

```bash
hochschulstart version
hochschulstart config --json
hochschulstart url https://api.example.com/v1 users --json
hochschulstart validate --count 3 --date 2026-01-15
hochschulstart state ./tmp-state.json --set hello=world --dry-run
```

### Configuration

Precedence: environment variables, then JSON config file, then optional keyring (`pip install hochschulstart[keyring]`).

| Variable | Purpose |
|----------|---------|
| `HOCHSCHULSTART_BASE_URL` | API base URL |
| `HOCHSCHULSTART_API_TOKEN` | API token |
| `HOCHSCHULSTART_CONFIG` | Path to config JSON |

Default config path: `~/.config/hochschulstart/config.json`.

## Layout

| Module | Role |
|--------|------|
| `exit_codes.py` | Documented exit constants and argparse mapping |
| `errors.py` | `CliError`, `run_main`, JSON/human error emission |
| `validation.py` | Positive ints, dates, paths, finite numbers |
| `json_util.py` | `dumps(allow_nan=False)`, strict object parse |
| `state.py` | Atomic writes; refuse null; dry-run skips I/O |
| `url_util.py` | Prefix-preserving URL join |
| `config.py` | env > file > keyring |
| `cli.py` | Example wiring (copy patterns into your CLI) |

## Field testing (offline → online)

The playbook for testing a derived CLI like a real user would — and turning findings into issues:

- [docs/TESTING.md](docs/TESTING.md) — two rounds: offline adversarial first, then online read-only against the real site (request budget, control requests, read-only rules, issue policy).
- Report format that worked: capability table `feature | verdict | evidence`.

## Scaffold a new CLI (one per day)

```bash
python3 scripts/scaffold.py ../my-new-cli \
    --package my_new_cli --cli-name my-new-cli \
    --desc "What this CLI does"
```

Copies this reference repo, renames package / CLI name / env prefix / docs, runs `git init` plus an
initial commit, then `uv sync` and the test suite. Useful flags:

| Flag | Effect |
|------|--------|
| `--author "Name"` | Author in `pyproject.toml`/`LICENSE` |
| `--github public\|private` | `gh repo create` + first push (needs `gh` auth) |
| `--no-verify` | Skip `uv sync` and the test run |
| `--no-git` | Skip `git init` and the initial commit |

## Shared MCP test suite (`tests/shared/`)

Black-box checks against a real MCP server over **stdio**:

| Test module | What it checks |
|-------------|----------------|
| `test_stdio_mcp.py` | `initialize`, `tools/list` not empty, each tool has `description` + `inputSchema` |
| `test_error_report.py` | A configured “error” tool returns JSON with a `report` object |
| `test_redaction.py` | Your `redact()` hides passwords, bearer-style tokens, and e-mails |

Based on the stdio roundtrip and feedback tests in [ilias-mcp](https://github.com/smlfg/ilias-mcp).

### Adopt in a new CLI/MCP repo

1. Copy the directory:

   ```bash
   cp -r path/to/hochschulstart/tests/shared ./tests/shared
   ```

2. Add dev dependencies (if missing): `pytest`, `pytest-asyncio`, `mcp`.

3. Configure how pytest starts your server — **either** environment variables **or** fixtures. Without configuration the suite skips itself, so a CLI-only repo stays green.

   **Environment (good for CI):**

   ```bash
   export MCP_TEST_SERVER_COMMAND='["uv","--directory","/path/to/repo","run","your-mcp-entry"]'
   export MCP_TEST_SERVER_NAME='your-mcp'          # optional
   export MCP_TEST_ERROR_TOOL='your_login_tool'    # tool that returns ok:false + report without real credentials
   export MCP_TEST_ERROR_TOOL_ARGS='{}'
   export MCP_TEST_SERVER_ENV='{"YOUR_CONFIG_DIR":"/tmp/mcp-tests"}'  # optional JSON object
   export MCP_TEST_REDACT='your_package.feedback:redact'
   uv run pytest tests/shared
   ```

   **Fixtures (good for local dev)** — override in `tests/conftest.py`:

   ```python
   import pytest
   from pathlib import Path

   @pytest.fixture(scope="session")
   def mcp_server_command() -> list[str]:
       root = Path(__file__).resolve().parents[1]
       return ["uv", "--directory", str(root), "run", "your-mcp"]

   @pytest.fixture(scope="session")
   def mcp_server_name() -> str:
       return "your-mcp"

   @pytest.fixture(scope="session")
   def mcp_error_tool() -> str:
       return "your_login_tool"

   @pytest.fixture(scope="session")
   def redact_fn():
       from your_package.feedback import redact
       return redact
   ```

4. Run project-specific tests and the shared suite together: `uv run pytest`.

### CI suggestion

Run the shared suite in the same job as unit tests, with `MCP_TEST_*` set in the workflow `env:` block (no secrets required if the error tool only needs missing config/credentials).

## QA

See [docs/QA-CHECKLIST.md](docs/QA-CHECKLIST.md) before shipping a derived CLI.

## CI

- `.github/workflows/ci.yml` — lints nothing, but runs the full test suite (`uv run --extra dev pytest`) on Python 3.11, 3.12 and 3.13.
- `.github/workflows/pii-guard.yml` — PII guard + gitleaks.
