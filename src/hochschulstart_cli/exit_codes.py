"""Central exit-code matrix for CLIs built from this template.

Document these in README and map argparse's default ``2`` to :data:`INPUT`.
"""

from __future__ import annotations

OK = 0
"""Success."""

INPUT = 1
"""Invalid user input (flags, arguments, validation)."""

AUTH = 2
"""Authentication / authorization failure."""

NETWORK = 3
"""Network or remote service failure."""

PARSE = 4
"""Response or file could not be parsed (JSON, config, state)."""

ABORT = 130
"""Interrupted by user (Ctrl-C) or EOF on interactive prompt."""

# argparse uses 2 for usage errors; never expose that to callers.
_ARGPARSE_USAGE = 2


def map_argparse_exit(code: int) -> int:
    """Map :mod:`argparse` exit codes to the documented matrix."""
    if code == _ARGPARSE_USAGE:
        return INPUT
    return code


def is_documented(code: int) -> bool:
    return code in (OK, INPUT, AUTH, NETWORK, PARSE, ABORT)
