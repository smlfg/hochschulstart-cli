"""Redaction helper must strip passwords, tokens, and e-mail addresses."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.parametrize(
    ("text", "forbidden"),
    [
        ("password=hunter2 please check", "hunter2"),
        ("passwort: geheim123", "geheim123"),
    ],
)
def test_passwords_redacted(redact_fn: Any, text: str, forbidden: str) -> None:
    out = redact_fn(text)
    assert forbidden not in out
    assert "[redacted]" in out or "[redacted-url]" in out


def test_bearer_token_redacted(redact_fn: Any) -> None:
    token = "ghp_" + "x" * 36
    out = redact_fn(f"Authorization: Bearer {token}")
    assert token not in out


def test_email_redacted(redact_fn: Any) -> None:
    out = redact_fn("contact user@example.org now")
    assert "user@example.org" not in out
