"""Contract-Tests: Happy Paths, JSON-Envelope, Session, Watch-State, --dry-run."""

from __future__ import annotations

import json

from conftest import json_out
from fake_portal import SYNTH_SESSION
from hochschulstart_cli import exit_codes as ec


def _login(cli_runner):
    proc = cli_runner("login", "--json")
    assert proc.returncode == ec.OK, proc.stderr
    return json_out(proc)


def test_login_post_includes_csrf_hidden_field(cli_runner, portal):
    assert cli_runner("login", "--json").returncode == ec.OK
    posts = [r for r in portal.requests if r["method"] == "POST" and r["path"] == "/bewerber/login"]
    assert len(posts) == 1
    assert "tx_login_token=SYNTH-FORM-TOKEN" in posts[0]["body"]


def test_login_dry_run_sends_no_requests(cli_runner, portal):
    proc = cli_runner("login", "--dry-run", "--json")
    assert proc.returncode == ec.OK
    payload = json_out(proc)
    assert payload["dry_run"] is True
    assert payload["session_saved"] == "dry-run"
    assert payload.get("sent") is False
    assert "benutzername" in payload["request"]["form_fields"]
    assert not portal.requests, "login --dry-run darf keine HTTP-Requests senden"


def test_login_saves_session_without_leaking_secrets(cli_runner, portal):
    payload = _login(cli_runner)
    assert payload["login"] == "ok"
    assert payload["session_saved"] in ("file", "keyring")
    session_file = cli_runner.config_dir / "session.json"
    assert session_file.exists()
    combined = cli_runner("config", "--json").stdout
    assert SYNTH_SESSION not in combined
    assert "testpass" not in combined
    assert "testuser" not in combined  # config zeigt nur *_set, keine Werte


def test_status_happy_path(cli_runner, portal):
    _login(cli_runner)
    proc = cli_runner("status", "--json")
    assert proc.returncode == ec.OK
    payload = json_out(proc)
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert payload["applications"][0]["id"] == "B-1001"
    assert payload["applications"][0]["status"] == "Zulassungsangebot"


def test_status_filter(cli_runner, portal):
    _login(cli_runner)
    payload = json_out(cli_runner("status", "--status", "eingegangen", "--json"))
    assert payload["count"] == 1
    assert payload["applications"][0]["id"] == "B-1002"


def test_rangliste_happy_and_filter(cli_runner, portal):
    _login(cli_runner)
    payload = json_out(cli_runner("rangliste", "--json"))
    assert payload["count"] == 2
    assert payload["ranglisten"][0]["rang"] == "42"
    filtered = json_out(cli_runner("rangliste", "--bewerbung", "B-1002", "--json"))
    assert filtered["count"] == 1
    assert filtered["ranglisten"][0]["quote"] == "Abiturbestenquote"


def test_rangliste_unknown_filter_exit_1(cli_runner, portal):
    _login(cli_runner)
    proc = cli_runner("rangliste", "--bewerbung", "B-9999", "--json")
    assert proc.returncode == ec.INPUT


def test_fristen_public_without_session(cli_runner, portal):
    proc = cli_runner("fristen", "--json")
    assert proc.returncode == ec.OK
    payload = json_out(proc)
    assert payload["count"] == 5
    assert payload["termine"][0]["date"] == "26.10.2026"
    assert any(r["path"] == "/terminuebersicht" for r in portal.requests)


def test_fristen_limit_and_invalid_limit(cli_runner, portal):
    payload = json_out(cli_runner("fristen", "--limit", "2", "--json"))
    assert payload["count"] == 2
    proc = cli_runner("fristen", "--limit", "0", "--json")
    assert proc.returncode == ec.INPUT


def test_watch_initial_then_unchanged(cli_runner, portal):
    _login(cli_runner)
    first = json_out(cli_runner("watch", "--json"))
    assert first["watched"] == 2
    assert {c["change"] for c in first["changes"]} == {"neu"}
    state_file = cli_runner.config_dir / "watch.json"
    assert state_file.exists()
    assert SYNTH_SESSION not in state_file.read_text(encoding="utf-8")

    second = json_out(cli_runner("watch", "--json"))
    assert second["changes"] == []


def test_watch_detects_status_change(cli_runner, portal):
    _login(cli_runner)
    cli_runner("watch", "--json")
    portal.applications[0]["status"] = "Angenommen"
    payload = json_out(cli_runner("watch", "--json"))
    assert payload["changes"] == [
        {"application": "B-1001", "change": "status", "from": "Zulassungsangebot", "to": "Angenommen"}
    ]


def test_watch_dry_run_writes_nothing(cli_runner, portal):
    _login(cli_runner)
    proc = cli_runner("watch", "--dry-run", "--json")
    assert proc.returncode == ec.OK
    payload = json_out(proc)
    assert payload["dry_run"] is True
    assert not (cli_runner.config_dir / "watch.json").exists()


def test_annehmen_confirm_sends_post_and_updates_status(cli_runner, portal):
    _login(cli_runner)
    proc = cli_runner("annehmen", "B-1001", "--confirm", "--json")
    assert proc.returncode == ec.OK
    payload = json_out(proc)
    assert payload["sent"] is True and payload["action"] == "annehmen"
    assert portal.applications[0]["status"] == "Angenommen"
    gets = [r for r in portal.requests if r["method"] == "GET" and r["path"].endswith("/annehmen")]
    posts = [r for r in portal.requests if r["method"] == "POST" and r["path"].endswith("/annehmen")]
    assert len(gets) == 1, "Portal zeigt erst einen Bestätigungsdialog (GET)"
    assert len(posts) == 1
    assert "tx_bewerbung_token=SYNTH-DECISION-TOKEN" in posts[0]["body"]
    assert "confirmed=" in posts[0]["body"]


def test_absagen_confirm_sends_post(cli_runner, portal):
    _login(cli_runner)
    proc = cli_runner("absagen", "B-1002", "--confirm", "--json")
    assert proc.returncode == ec.OK
    assert portal.applications[1]["status"] == "Abgesagt"


def test_annehmen_dry_run_sends_no_post(cli_runner, portal):
    _login(cli_runner)
    proc = cli_runner("annehmen", "B-1001", "--confirm", "--dry-run", "--json")
    assert proc.returncode == ec.OK
    payload = json_out(proc)
    assert payload["sent"] is False
    assert "tx_bewerbung_token" in payload["request"]["form_fields"]
    assert portal.applications[0]["status"] == "Zulassungsangebot", "dry-run darf nichts senden"
    assert not [r for r in portal.requests if r["method"] == "POST" and r["path"].endswith("/annehmen")]


def test_annehmen_empty_id_no_http(cli_runner, portal):
    _login(cli_runner)
    portal.requests.clear()
    proc = cli_runner("annehmen", "", "--confirm", "--json")
    assert proc.returncode == ec.INPUT
    assert "leer" in json_out(proc)["error"]["message"].lower()
    assert portal.requests == []


def test_annehmen_path_traversal_id_no_http(cli_runner, portal):
    _login(cli_runner)
    portal.requests.clear()
    proc = cli_runner("annehmen", "../B-1002", "--confirm", "--json")
    assert proc.returncode == ec.INPUT
    assert portal.requests == []


def test_annehmen_without_offer_exit_1(cli_runner, portal):
    _login(cli_runner)
    proc = cli_runner("annehmen", "B-1002", "--confirm", "--json")
    assert proc.returncode == ec.INPUT
    payload = json_out(proc)
    assert "kein Zulassungsangebot" in payload["error"]["message"]
    assert not [r for r in portal.requests if r["method"] == "POST" and r["path"].endswith("/annehmen")]
    assert portal.applications[1]["status"] == "Bewerbung eingegangen"


def test_annehmen_invalid_token_exit_1(cli_runner, portal, monkeypatch):
    from fake_portal import SYNTH_DECISION_TOKEN, _decision_confirm_html

    _login(cli_runner)

    def bad_confirm(app_id: str, action: str) -> str:
        return _decision_confirm_html(app_id, action).replace(SYNTH_DECISION_TOKEN, "BAD-TOKEN")

    monkeypatch.setattr("fake_portal._decision_confirm_html", bad_confirm)
    proc = cli_runner("annehmen", "B-1001", "--confirm", "--json")
    assert proc.returncode == ec.INPUT
    assert "Formular-Token" in json_out(proc)["error"]["message"]


def test_annehmen_already_accepted_exit_1(cli_runner, portal):
    _login(cli_runner)
    cli_runner("annehmen", "B-1001", "--confirm", "--json")
    proc = cli_runner("annehmen", "B-1001", "--confirm", "--json")
    assert proc.returncode == ec.INPUT
    assert "bereits" in json_out(proc)["error"]["message"]


def test_config_shows_sources_not_secrets(cli_runner, portal):
    _login(cli_runner)
    payload = json_out(cli_runner("config", "--json"))
    assert payload["username_set"] is True
    assert payload["password_set"] is True
    assert payload["session_present"] is True
    assert payload["session_source"] == "file"
    assert payload["sources"]["username"] == "env"
    dumped = json.dumps(payload)
    assert "testpass" not in dumped
    assert SYNTH_SESSION not in dumped
