"""Fehlerpfad-Vertrag der Domänen-Kommandos (offline, Fake-Portal).

Ohne Session -> 2, Netz down -> 3, kaputtes HTML -> 4, fehlende Args -> 1,
--confirm-Gating -> ohne confirm kein einziger Request.
"""

from __future__ import annotations

import os
import stat

import pytest

from conftest import json_out
from hochschulstart_cli import exit_codes as ec


def test_status_without_session_exit_2_no_request(cli_runner, portal):
    proc = cli_runner("status", "--json")
    assert proc.returncode == ec.AUTH
    payload = json_out(proc)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.AUTH
    assert portal.requests == [], "ohne Session darf kein Request rausgehen"


def test_annehmen_without_confirm_aborts_before_request(cli_runner, portal):
    proc = cli_runner("annehmen", "B-1001", "--json")
    assert proc.returncode == ec.INPUT
    payload = json_out(proc)
    assert payload["error"]["code"] == ec.INPUT
    assert "--confirm" in payload["error"]["message"]
    assert portal.requests == [], "ohne --confirm darf kein Request rausgehen"


def test_absagen_without_confirm_aborts_before_request(cli_runner, portal):
    proc = cli_runner("absagen", "B-1001", "--json")
    assert proc.returncode == ec.INPUT
    assert portal.requests == []


def test_annehmen_confirm_without_session_exit_2(cli_runner, portal):
    proc = cli_runner("annehmen", "B-1001", "--confirm", "--json")
    assert proc.returncode == ec.AUTH
    assert portal.requests == []


def test_login_missing_credentials_exit_2(cli_runner, portal):
    proc = cli_runner(
        "login",
        "--json",
        env_extra={"HOCHSCHULSTART_USERNAME": None, "HOCHSCHULSTART_PASSWORD": None},
    )
    assert proc.returncode == ec.AUTH
    payload = json_out(proc)
    assert payload["error"]["code"] == ec.AUTH
    assert portal.requests == []


def test_login_wrong_password_exit_2(cli_runner, portal):
    proc = cli_runner("login", "--json", env_extra={"HOCHSCHULSTART_PASSWORD": "falsch"})
    assert proc.returncode == ec.AUTH
    payload = json_out(proc)
    assert payload["error"]["code"] == ec.AUTH
    assert "Benutzername oder Passwort ist falsch" in payload["error"]["message"]
    assert "testpass" not in proc.stdout + proc.stderr
    assert "testuser" not in proc.stdout + proc.stderr


def test_login_wrong_password_http_200_exit_2(cli_runner, portal):
    portal.login_fail_status = 200
    proc = cli_runner("login", "--json", env_extra={"HOCHSCHULSTART_PASSWORD": "falsch"})
    assert proc.returncode == ec.AUTH
    payload = json_out(proc)
    assert "Benutzername oder Passwort ist falsch" in payload["error"]["message"]


@pytest.mark.parametrize("wall", ["captcha", "2fa", "bundid"])
def test_login_unsupported_auth_wall_exit_2(cli_runner, portal, wall):
    portal.auth_wall = wall
    proc = cli_runner("login", "--json")
    assert proc.returncode == ec.AUTH
    payload = json_out(proc)
    assert payload["error"]["code"] == ec.AUTH
    assert "nicht unterstütztes Auth-Verfahren erkannt" in payload["error"]["message"]
    assert "Zugangsdaten prüfen" not in payload["error"]["message"]
    posts = [r for r in portal.requests if r["method"] == "POST"]
    assert posts == [], "bei Auth-Wand darf kein Login-POST erfolgen"


def test_login_post_returns_2fa_wall_exit_2(cli_runner, portal):
    portal.login_response_wall = "2fa"
    proc = cli_runner("login", "--json")
    assert proc.returncode == ec.AUTH
    payload = json_out(proc)
    assert "nicht unterstütztes Auth-Verfahren erkannt" in payload["error"]["message"]
    assert "2FA" in payload["error"]["message"]


def test_network_down_exit_3(cli_runner, portal):
    proc = cli_runner(
        "fristen",
        "--json",
        env_extra={"HOCHSCHULSTART_PUBLIC_URL": "http://127.0.0.1:9/terminuebersicht"},
    )
    assert proc.returncode == ec.NETWORK
    payload = json_out(proc)
    assert payload["error"]["code"] == ec.NETWORK


def test_watch_unwritable_state_exit_4_no_traceback(cli_runner, portal, tmp_path):
    assert cli_runner("login", "--json").returncode == ec.OK
    ro = tmp_path / "ro"
    ro.mkdir()
    os.chmod(
        ro,
        stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
    )
    proc = cli_runner("watch", "--json", "--state", str(ro / "watch.json"))
    assert proc.returncode == ec.PARSE
    assert "Traceback" not in proc.stderr
    payload = json_out(proc)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.PARSE
    assert "cannot write state" in payload["error"]["message"]


def test_login_unwritable_session_dir_exit_4_no_traceback(cli_runner, portal, tmp_path):
    ro = tmp_path / "xdg"
    ro.mkdir()
    os.chmod(
        ro,
        stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
    )
    proc = cli_runner(
        "login",
        "--json",
        env_extra={"HOCHSCHULSTART_CONFIG_DIR": str(ro / "hochschulstart")},
    )
    assert proc.returncode == ec.PARSE
    assert "Traceback" not in proc.stderr
    payload = json_out(proc)
    assert payload["ok"] is False
    assert payload["error"]["code"] == ec.PARSE
    assert "Session" in payload["error"]["message"]


def test_broken_html_exit_4(cli_runner, portal):
    assert cli_runner("login", "--json").returncode == ec.OK
    portal.mode = "bad_html"
    proc = cli_runner("status", "--json")
    assert proc.returncode == ec.PARSE
    payload = json_out(proc)
    assert payload["error"]["code"] == ec.PARSE


def test_maintenance_page_exit_3(cli_runner, portal):
    portal.mode = "maintenance"
    proc = cli_runner("login", "--json")
    assert proc.returncode == ec.NETWORK


def test_missing_argument_exit_1(cli_runner, portal):
    proc = cli_runner("annehmen", "--json")
    assert proc.returncode == ec.INPUT
    assert portal.requests == []


def test_unknown_flag_exit_1(cli_runner, portal):
    proc = cli_runner("--nope")
    assert proc.returncode == ec.INPUT


@pytest.mark.parametrize("command", ["version"])
def test_version_human(cli_runner, portal, command):
    proc = cli_runner(command)
    assert proc.returncode == ec.OK
    assert proc.stdout.strip()
