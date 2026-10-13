# Field testing a derived CLI (offline → online)

Unit tests prove the code; field tests prove the tool works against the real site — and that is where the bugs that matter live (stale markup, ignored parameters, broken detail pages). This playbook distills a stresstest across six derived CLIs. Test the CLI **in operation, not the code**.

## Round 1 — offline, adversarial (fast, deterministic)

- Run the suite, then poke the binary as a black box: `--help` for every command, wrong/missing args, unknown IDs, config edges (env > file > keyring, broken files), state edges (dry-run writes nothing, corrupt state), and the JSON contract (`--json` emits exactly one valid JSON object; exit codes per README table).
- Isolation: fresh `HOME`, `XDG_*` and CWD via `mktemp -d` for every probe. No real sessions or configs of the owner.
- Secrets never appear in stdout/stderr/tracebacks/state files.
- Parked features count as bugs: if the repo ships specs/tests for an unimplemented command (xfail parks), report it once (one issue per gap). Help texts and error hints must never reference commands that do not exist.

## Round 2 — online, read-only (the round that matters)

The question per capability: **can the CLI do real things online?** Answer with a table `feature | yes/partly/no | evidence`.

Rules:

- **Read-only**: no logins completed, never enter credentials, no posts/messages/purchases. Authenticated features: test only up to the public boundary (login page reached? captcha?) and mark them "not testable without credentials".
- **Budget**: ≤ ~30 real requests, strictly sequential, no retry loops, respect the CLI's own rate defaults. A bot block (403/429/challenge) is a finding — log it, do not bypass it, do not keep hammering.
- **Control group**: a sparse `curl -sI` / `curl -s` against the same URL separates CLI bugs from site behavior. Watch for HEAD/GET asymmetries (some WAFs answer HEAD differently, e.g. 303 vs 200).
- Reproduce each candidate **2×**; flaky observations go into the report, not the issue tracker.
- Typical classes seen live: list works but detail breaks; filter/pagination parameters silently ignored; rent fields swapped (cold vs warm); description `null`; stale CSS selectors; URL slug dropped; timezone shift; dead official links; state files overwritten.

## Filing issues

- Dedupe first, **including closed issues**: `gh issue list --state all`, plus `gh search issues`.
- Max ~5 new issues per repo — quality over quantity.
- Label `bug`; body per `.github/ISSUE_TEMPLATE/bug.md` (environment, steps, expected, actual with exact output and exit code, evidence, repro rate).
- Confirmed old issues: add an evidence comment (`gh issue comment`) instead of opening a duplicate.
- Network failures of your own environment are not bugs.

## Report

One markdown report per repo: capability table, commands run, issues filed (URLs), rejected candidates, and untestable areas. Leave the repo worktree clean — never fix while testing.

## Orchestrator mode ("one agent per repo")

- Spawn one general agent per repo, all in parallel; give each the rules above, a request budget and the dedupe/issue policy.
- Agents test the CLI in operation, not the codebase.
- A ready-made skill for opencode lives in `.opencode/skills/cli-betriebstest/`.
