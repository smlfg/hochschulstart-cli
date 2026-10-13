# QA checklist (derived CLIs)

Use this before release; items mirror recurring stresstest findings.

## Exit codes and errors

- [ ] Only documented exit codes (0, 1, 2, 3, 4, 130); argparse usage maps to **1**, not 2
- [ ] Top-level handler catches `CliError`, `KeyboardInterrupt`, `EOFError`; no traceback for expected failures
- [ ] With `--json`, exactly **one** JSON object on stdout for errors; message on stderr in human mode
- [ ] Auth failures use **2**, network **3**, parse **4**

## Input validation

- [ ] Reject negative counts where only positive values are valid
- [ ] `json.dumps(..., allow_nan=False)` (or equivalent) for all emitted/persisted JSON
- [ ] Reject JSON `null` where an object is required; parsers do not silently return `null`
- [ ] Distinguish file vs directory vs missing path with clear messages
- [ ] Validate ISO dates/datetimes; reject invalid strings

## State and side effects

- [ ] State writes are atomic (temp file + rename)
- [ ] Never overwrite state with `null` / empty object by mistake
- [ ] `--dry-run` performs **no** filesystem writes

## Configuration

- [ ] Document env var names; **env overrides** config file and keyring
- [ ] Missing credentials → exit **2**, not generic failure

## URLs

- [ ] API `base_url` path prefix preserved when joining relative paths (avoid naive `urljoin`)

## Tests

- [ ] Error-path tests (invalid flags, bad JSON, auth missing) without network
- [ ] No hard-coded `/home/...` paths; use `tmp_path` and `tests/fixtures/`
- [ ] README: every documented `your-cli ...` command has a matching subcommand in `--help`

## Documentation

- [ ] README exit-code table matches `exit_codes.py`
- [ ] README commands match implemented subcommands
- [ ] AGENTS.md points agents at patterns in this template
