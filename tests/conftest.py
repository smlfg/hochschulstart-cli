"""Repo-wide fixtures. Stay offline: no test may touch the network.

Shared MCP suite: copy ``tests/shared/`` into your repo and configure it via
``MCP_TEST_*`` env vars or fixtures — see README.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def sample_state(fixtures_dir: Path) -> Path:
    return fixtures_dir / "sample_state.json"
