"""Parser-Tests gegen statische HTML-Fixtures (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError
from hochschulstart_cli.parsing import (
    extract_form,
    login_error_hint,
    parse_applications,
    parse_ranglisten,
    parse_termine,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_applications_fields():
    apps = parse_applications(_read("applications.html"))
    assert [a["id"] for a in apps] == ["B-2001", "B-2002"]
    assert apps[0]["program"] == "Musterstudiengang"
    assert apps[0]["status"] == "Zulassungsangebot"
    assert apps[0]["rang"] == "42"
    assert apps[1]["status"] == "Bewerbung eingegangen"


def test_parse_ranglisten_fields():
    entries = parse_ranglisten(_read("ranglisten.html"))
    assert len(entries) == 1
    assert entries[0]["bewerbung"] == "B-2001"
    assert entries[0]["quote"] == "AdH"
    assert entries[0]["rang"] == "42"
    assert entries[0]["grenzrang"] == "120"


def test_parse_termine_fields():
    termine = parse_termine(_read("termine.html"))
    assert [t["date"] for t in termine] == ["26.10.2026", "15.01.2027", "tba.2027"]
    assert "Bewerbungsphase" in termine[0]["title"]


def test_parse_termine_live_snapshot_2026_10_14():
    """Tabellenstruktur von www.hochschulstart.de (14.10.2026, read-only curl)."""
    termine = parse_termine(_read("termine_live_2026-10-14.html"))
    assert len(termine) >= 70
    assert termine[0]["date"] == "26.10.2026"
    assert "Bewerbungsphase" in termine[0]["title"]


def test_parse_unexpected_html_is_parse_error():
    with pytest.raises(CliError) as e:
        parse_applications(_read("unexpected.html"))
    assert e.value.code == ec.PARSE
    with pytest.raises(CliError):
        parse_ranglisten(_read("unexpected.html"))
    with pytest.raises(CliError):
        parse_termine(_read("unexpected.html"))


def test_login_error_hint_from_portal_html():
    html = "<html><body><p>Benutzername oder Passwort ist falsch.</p></body></html>"
    assert login_error_hint(html) == "Benutzername oder Passwort ist falsch"


def test_extract_form_login_fields():
    form = extract_form(_read("login.html"), action_contains="login")
    assert form["action"] == "/bewerber/login"
    assert form["method"].lower() == "post"
    assert form["inputs"]["tx_login_token"] == "SYNTH-FORM-TOKEN"
    assert "benutzername" in form["inputs"]
    assert "passwort" in form["inputs"]


def test_extract_form_missing_action_is_parse_error():
    with pytest.raises(CliError) as e:
        extract_form(_read("login.html"), action_contains="annehmen")
    assert e.value.code == ec.PARSE
