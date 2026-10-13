# Agent notes (hochschulstart)

This repo is a **pattern library**, not a production product. When building or reviewing a derived CLI:

1. **Exit codes** — Import `hochschulstart_cli.exit_codes`; use `errors.ArgumentParser` and `errors.run_main` so argparse usage exits with **1** and Ctrl-C/EOF exit **130**.
2. **Errors** — Raise `CliError(message, code=...)`; never print tracebacks for expected failures. With `--json`, emit one object: `{"ok": false, "error": {"code": N, "message": "..."}}`.
3. **Validation** — Use `validation.py` helpers; call `json_util.dumps` / `reject_nan_in_json_tree` before persisting.
4. **State** — Use `state.save_state(..., dry_run=)`; never write `null`.
5. **Config** — `config.resolve_config()`; env wins over file and keyring.
6. **URLs** — `url_util.join_preserve_base_path`, not raw `urljoin` on prefixed bases.
7. **Tests** — Copy patterns from `tests/test_cli_errors.py` and `tests/test_readme_commands.py`; stay offline; fixtures under `tests/fixtures/`.
8. **Docs** — Keep README commands in sync with `--help`; run `docs/QA-CHECKLIST.md` mentally before marking work done.
9. **Field test** — Test the CLI in operation, not the code: run `docs/TESTING.md` (offline adversarial first, then online read-only) and file findings with `.github/ISSUE_TEMPLATE/bug.md`. A ready-made opencode skill lives in `.opencode/skills/cli-betriebstest/`.

Do **not** add secrets or invented personal data. Keep `ci.yml` and `pii-guard.yml`; add further workflows only when requested.

Install for local work: `pip install -e ".[dev]"` then `pytest`.
