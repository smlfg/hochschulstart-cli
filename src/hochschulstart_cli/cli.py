"""Example CLI wiring together template patterns (copy into your project)."""

from __future__ import annotations

import sys
from pathlib import Path

from hochschulstart_cli import __version__
from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.config import resolve_config
from hochschulstart_cli.errors import ArgumentParser, CliError, run_main
from hochschulstart_cli.json_util import dumps
from hochschulstart_cli.state import load_state, save_state
from hochschulstart_cli.url_util import join_preserve_base_path
from hochschulstart_cli.validation import (
    parse_date,
    require_positive_int,
    require_file,
)


def _emit(data: dict, *, json_mode: bool) -> None:
    if json_mode:
        sys.stdout.write(dumps({"ok": True, **data}) + "\n")
    else:
        for k, v in data.items():
            print(f"{k}: {v}")


def build_parser(json_mode: bool) -> ArgumentParser:
    parser = ArgumentParser(prog="hochschulstart", description=__doc__)
    parser.set_json_mode(json_mode)
    global_flags = ArgumentParser(add_help=False)
    global_flags.add_argument("--json", action="store_true", help="machine-readable JSON on stdout")
    global_flags.add_argument(
        "--dry-run",
        action="store_true",
        help="do not persist state (no file writes)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", parents=[global_flags], help="print package version")

    p_cfg = sub.add_parser("config", parents=[global_flags], help="show resolved configuration")
    p_cfg.add_argument(
        "--config",
        type=Path,
        default=None,
        help="config JSON file (default: ~/.config/hochschulstart/config.json)",
    )

    p_state = sub.add_parser("state", parents=[global_flags], help="load or save JSON state file")
    p_state.add_argument("state_path", type=Path, help="state file path")
    p_state.add_argument(
        "--set",
        metavar="KEY=VALUE",
        action="append",
        default=[],
        help="set key (repeatable); merges into existing state",
    )

    p_url = sub.add_parser("url", parents=[global_flags], help="join base URL and path (prefix-safe)")
    p_url.add_argument("base_url", help="API base URL, may include a path prefix")
    p_url.add_argument("segment", help="relative path segment")

    p_validate = sub.add_parser(
        "validate",
        parents=[global_flags],
        help="run validation helpers on input",
    )
    p_validate.add_argument("--count", type=int, help="positive integer")
    p_validate.add_argument("--date", help="ISO date YYYY-MM-DD")
    p_validate.add_argument("--file", type=Path, help="must be an existing file")

    return parser


def _main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else sys.argv[1:]
    json_mode = "--json" in args_list
    parser = build_parser(json_mode)
    args = parser.parse_args(args_list)
    json_mode = args.json or json_mode
    dry_run = args.dry_run

    if args.command == "version":
        if json_mode:
            sys.stdout.write(dumps({"ok": True, "version": __version__}) + "\n")
        else:
            print(__version__)
        return ec.OK

    if args.command == "config":
        cfg = resolve_config(config_path=args.config)
        _emit(
            {
                "base_url": cfg.base_url,
                "api_token_set": bool(cfg.api_token),
                "sources": cfg.sources,
            },
            json_mode=json_mode,
        )
        return ec.OK

    if args.command == "state":
        current = load_state(args.state_path) or {}
        for item in args.set:
            if "=" not in item:
                raise CliError(f"expected KEY=VALUE, got {item!r}", code=ec.INPUT)
            key, value = item.split("=", 1)
            if not key:
                raise CliError("state key must not be empty", code=ec.INPUT)
            current[key] = value
        save_state(args.state_path, current, dry_run=dry_run)
        _emit(
            {
                "state_path": str(args.state_path),
                "dry_run": dry_run,
                "keys": sorted(current.keys()),
            },
            json_mode=json_mode,
        )
        return ec.OK

    if args.command == "url":
        joined = join_preserve_base_path(args.base_url, args.segment)
        _emit({"url": joined}, json_mode=json_mode)
        return ec.OK

    if args.command == "validate":
        out: dict = {}
        if args.count is not None:
            out["count"] = require_positive_int(args.count, name="count")
        if args.date is not None:
            out["date"] = str(parse_date(args.date))
        if args.file is not None:
            out["file"] = str(require_file(args.file))
        if not out:
            raise CliError("pass at least one of --count, --date, --file", code=ec.INPUT)
        _emit(out, json_mode=json_mode)
        return ec.OK

    raise CliError(f"unknown command: {args.command}", code=ec.INPUT)


def main() -> None:
    sys.exit(run_main(_main))


if __name__ == "__main__":
    main()
