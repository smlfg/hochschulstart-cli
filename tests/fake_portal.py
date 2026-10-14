"""Offline-Fake des DoSV-Portals (stdlib http.server, ThreadingHTTPServer).

Bildet Login-Formular, Bewerbungsübersicht, Ranglisten, Termine sowie den
Annehmen-/Absagen-Flow mit synthetischen Daten nach. Jeder Request wird
aufgezeichnet (Request-Recorder), damit Tests beweisen können, dass z. B.
ohne ``--confirm`` **kein** Request rausgeht.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SYNTH_USERNAME = "testuser"
SYNTH_PASSWORD = "testpass"
SYNTH_SESSION = "SYNTH-SESSION-0001"
SYNTH_CSRF = "SYNTH-CSRF-0001"

AUTH_CAPTCHA_HTML = """<!DOCTYPE html><html lang="de"><head><title>Sicherheitsabfrage</title></head>
<body><h1>Sicherheitsabfrage</h1><p>Bitte bestätigen Sie das Captcha.</p><div class="g-recaptcha"></div></body></html>"""

AUTH_2FA_HTML = """<!DOCTYPE html><html lang="de"><head><title>2FA</title></head>
<body><h1>Zwei-Faktor-Authentifizierung</h1><p>Authenticator-Code eingeben.</p></body></html>"""

AUTH_BUNDID_HTML = """<!DOCTYPE html><html lang="de"><head><title>BundID</title></head>
<body><h1>Anmeldung mit BundID</h1><p>Weiter mit Ihrer BundID.</p></body></html>"""

_AUTH_WALL_HTML = {
    "captcha": AUTH_CAPTCHA_HTML,
    "2fa": AUTH_2FA_HTML,
    "bundid": AUTH_BUNDID_HTML,
}

LOGIN_HTML = """<!DOCTYPE html><html lang="de"><head><title>Bewerbungsportal Anmeldung</title></head>
<body>
<h1>Bewerbungsportal für das Dialogorientierte Serviceverfahren (DoSV)</h1>
<form action="/bewerber/login" method="post" id="loginform">
  <input type="hidden" name="tx_login_token" value="SYNTH-FORM-TOKEN">
  <label>Benutzername <input type="text" name="benutzername" id="benutzername"></label>
  <label>Passwort <input type="password" name="passwort" id="passwort"></label>
  <button type="submit">Anmelden</button>
</form>
</body></html>"""

MAINTENANCE_HTML = """<!DOCTYPE html><html lang="de"><head><title>Wartung</title></head>
<body><h1>Das Bewerbungsportal ist wegen Wartung vorübergehend nicht erreichbar.</h1></body></html>"""

BAD_HTML = "<html><body><p>unerwartete Struktur ohne Tabellen</p></body></html>"

TERMINE_ROWS = [
    ("26.10.2026", "Start der Bewerbungsphase (09:00 Uhr)", "Start für die bundesweit zulassungsbeschränkten Studiengänge."),
    ("15.01.2027", "Ende der Bewerbungsphase (Ausschlussfrist)", ""),
    ("16.01.2027", "Start der Koordinierungsphase", "Zulassungsangebote sind ab Beginn möglich."),
    ("22.01.2027", "Stichtag, bevor die Koordinierungsregeln greifen", "Priorisierung bis zum Stichtag vornehmen."),
    ("31.03.2027", "Ende des Verfahrens", ""),
]


def _applications_table(rows: list[dict]) -> str:
    head = (
        "<tr><th>Bewerbungsnummer</th><th>Studiengang</th><th>Hochschule</th>"
        "<th>Status</th><th>Rang</th><th>Frist</th></tr>"
    )
    body = "".join(
        f"<tr><td>{r['id']}</td><td>{r['program']}</td><td>{r['university']}</td>"
        f"<td>{r['status']}</td><td>{r['rang']}</td><td>{r['frist']}</td></tr>"
        for r in rows
    )
    return f"<table class='table'><tbody>{head}{body}</tbody></table>"


def _ranglisten_table(rows: list[dict]) -> str:
    head = (
        "<tr><th>Bewerbung</th><th>Quote</th><th>Ihr Rang</th><th>Grenzrang</th>"
        "<th>Ihr Wert</th><th>Losnummer</th></tr>"
    )
    body = "".join(
        f"<tr><td>{r['bewerbung']}</td><td>{r['quote']}</td><td>{r['rang']}</td>"
        f"<td>{r['grenzrang']}</td><td>{r['wert']}</td><td>{r['los']}</td></tr>"
        for r in rows
    )
    return f"<table class='table'><tbody>{head}{body}</tbody></table>"


def _termine_table(rows: list[tuple[str, str, str]]) -> str:
    body = "".join(f"<tr><td>{d}</td><td><p><strong>{t}</strong></p><p>{x}</p></td><td>&nbsp;</td></tr>" for d, t, x in rows)
    return f"<table class='table'><tbody>{body}</tbody></table>"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # Tests sollen still sein
        pass

    @property
    def portal(self) -> FakePortal:
        return self.server.portal  # type: ignore[attr-defined]

    def _send(self, status: int, body: str, *, cookie: str | None = None) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", f"JSESSIONID={cookie}; Path=/")
        self.end_headers()
        self.wfile.write(data)

    def _session_ok(self) -> bool:
        cookie = self.headers.get("Cookie", "")
        return f"JSESSIONID={self.portal.session}" in cookie

    def _record(self, body: bytes = b"") -> None:
        self.portal.requests.append(
            {
                "method": self.command,
                "path": urlparse(self.path).path,
                "query": urlparse(self.path).query,
                "body": body.decode("utf-8", errors="replace"),
                "cookies": self.headers.get("Cookie", ""),
            }
        )

    def do_GET(self) -> None:
        self._record()
        path = urlparse(self.path).path
        portal = self.portal
        if portal.mode == "maintenance":
            return self._send(200, MAINTENANCE_HTML)
        if portal.mode == "http_500":
            return self._send(500, "<html><body>Serverfehler</body></html>")

        if path in ("/bewerber", "/bewerber/"):
            if portal.auth_wall in _AUTH_WALL_HTML:
                return self._send(200, _AUTH_WALL_HTML[portal.auth_wall])
            return self._send(200, LOGIN_HTML)
        if path == "/terminuebersicht":
            return self._send(200, f"<html><body>{_termine_table(TERMINE_ROWS)}</body></html>")
        if path in ("/bewerber/bewerbungen", "/bewerber/bewerbungen/"):
            if not self._session_ok():
                return self._send(401, LOGIN_HTML)
            if portal.mode == "bad_html":
                return self._send(200, BAD_HTML)
            return self._send(200, f"<html><body><h1>Bewerbungsübersicht</h1>{_applications_table(portal.applications)}</body></html>")
        if path.startswith("/bewerber/bewerbungen/"):
            if not self._session_ok():
                return self._send(401, LOGIN_HTML)
            if portal.mode == "bad_html":
                return self._send(200, BAD_HTML)
            app_id = path.split("/")[3]
            row = next((r for r in portal.applications if r["id"] == app_id), None)
            if row is None:
                return self._send(404, "<html><body>nicht gefunden</body></html>")
            forms = (
                f"<form action='/bewerber/bewerbungen/{app_id}/annehmen' method='post'>"
                f"<input type='hidden' name='csrf_token' value='{SYNTH_CSRF}'></form>"
                f"<form action='/bewerber/bewerbungen/{app_id}/absagen' method='post'>"
                f"<input type='hidden' name='csrf_token' value='{SYNTH_CSRF}'></form>"
            )
            return self._send(
                200,
                f"<html><body><h1>Bewerbung {app_id}</h1>{_applications_table([row])}{forms}</body></html>",
            )
        if path == "/bewerber/ranglisten":
            if not self._session_ok():
                return self._send(401, LOGIN_HTML)
            if portal.mode == "bad_html":
                return self._send(200, BAD_HTML)
            return self._send(200, f"<html><body>{_ranglisten_table(portal.ranglisten)}</body></html>")
        return self._send(404, "<html><body>nicht gefunden</body></html>")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        self._record(raw)
        path = urlparse(self.path).path
        portal = self.portal
        fields = {k: v[0] for k, v in parse_qs(raw.decode("utf-8", errors="replace")).items()}
        if portal.mode == "maintenance":
            return self._send(200, MAINTENANCE_HTML)
        if path == "/bewerber/login":
            if fields.get("benutzername") == portal.username and fields.get("passwort") == portal.password:
                if portal.login_response_wall in _AUTH_WALL_HTML:
                    return self._send(200, _AUTH_WALL_HTML[portal.login_response_wall])
                return self._send(200, "<html><body>Angemeldet</body></html>", cookie=portal.session)
            fail_body = (
                LOGIN_HTML.replace(
                    "</form>",
                    "<p>Benutzername oder Passwort ist falsch.</p></form>",
                )
            )
            if portal.login_fail_status == 200:
                return self._send(200, fail_body)
            return self._send(403, "<html><body>Benutzername oder Passwort ist falsch</body></html>")
        if path.startswith("/bewerber/bewerbungen/") and path.endswith(("/annehmen", "/absagen")):
            action = path.rsplit("/", 1)[1]
            app_id = path.split("/")[3]
            if not self._session_ok():
                return self._send(401, LOGIN_HTML)
            if fields.get("csrf_token") != SYNTH_CSRF:
                return self._send(400, "<html><body>Ungültiges Formular-Token</body></html>")
            row = next((r for r in portal.applications if r["id"] == app_id), None)
            if row is None:
                return self._send(404, "<html><body>nicht gefunden</body></html>")
            row["status"] = "Angenommen" if action == "annehmen" else "Abgesagt"
            return self._send(200, f"<html><body>{action} erfolgreich für {app_id}</body></html>")
        if path == "/bewerber/annehmen-abort":
            return self._send(200, LOGIN_HTML)
        return self._send(404, "<html><body>nicht gefunden</body></html>")


class FakePortal:
    def __init__(self) -> None:
        self.username = SYNTH_USERNAME
        self.password = SYNTH_PASSWORD
        self.session = SYNTH_SESSION
        self.mode = "ok"  # ok | bad_html | http_500 | maintenance
        self.auth_wall: str | None = None  # captcha | 2fa | bundid — Login-Seite ohne Passwort-Formular
        self.login_response_wall: str | None = None  # nach POST: weiterer Auth-Schritt ohne Session
        self.login_fail_status = 403  # 403 | 200 — Portal-Fehlermeldung im Body
        self.requests: list[dict] = []
        self.applications = [
            {
                "id": "B-1001",
                "program": "Musterstudiengang",
                "university": "Musteruniversität",
                "status": "Zulassungsangebot",
                "rang": "42",
                "frist": "15.01.2027",
            },
            {
                "id": "B-1002",
                "program": "Synthetisches Fach",
                "university": "Beispielhochschule",
                "status": "Bewerbung eingegangen",
                "rang": "–",
                "frist": "15.01.2027",
            },
        ]
        self.ranglisten = [
            {"bewerbung": "B-1001", "quote": "AdH", "rang": "42", "grenzrang": "120", "wert": "3,5", "los": "7"},
            {
                "bewerbung": "B-1002",
                "quote": "Abiturbestenquote",
                "rang": "310",
                "grenzrang": "250",
                "wert": "1,7",
                "los": "11",
            },
        ]
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.portal = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def requests_for(self, path: str) -> list[dict]:
        return [r for r in self.requests if r["path"] == path]
