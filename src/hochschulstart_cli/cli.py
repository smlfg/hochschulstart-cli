"""hochschulstart.de (DoSV): Bewerbungsportal-CLI.

Kommandos: login, status, rangliste, fristen, watch, annehmen, absagen.
Sicherheitsregel: annehmen/absagen senden nur mit ``--confirm`` — im Terminal
fragt die CLI zusätzlich verbindlich nach; ohne beendet die CLI **vor jedem
Request** mit Exit 1. Ohne Session: Exit 2. ``--dry-run`` zeigt den geplanten
Request, sendet ihn aber nicht. Ohne ``--json``: lesbare Textausgabe für
Menschen; Prompts nur im echten Terminal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from hochschulstart_cli import __version__
from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.config import (
    KEYRING_SERVICE,
    ResolvedConfig,
    config_dir,
    require_credentials,
    resolve_config,
)
from hochschulstart_cli.errors import ArgumentParser, CliError, run_main
from hochschulstart_cli.http_client import PortalClient
from hochschulstart_cli.json_util import dumps
from hochschulstart_cli.parsing import (
    decision_accepted,
    decision_error_hint,
    extract_form,
    login_error_hint,
    parse_applications,
    parse_ranglisten,
    parse_termine,
    unsupported_auth_method,
)
from hochschulstart_cli.session import (
    clear_session,
    load_session,
    save_login_marker,
    save_session,
    session_path,
)
from hochschulstart_cli.state import load_state, save_state
from hochschulstart_cli.url_util import join_preserve_base_path
from hochschulstart_cli.validation import require_application_id, require_positive_int

LOGIN_PAGE = "/bewerber"
APPLICATIONS_PATH = "/bewerber/bewerbungen"
RANGLISTEN_PATH = "/bewerber/ranglisten"
LOGIN_FALLBACK_ACTION = "/bewerber/login"

TERMINAL_STATUS = ("angenommen", "abgesagt", "abgelehnt", "zurückgezogen", "zurueckgezogen")


def _emit(data: dict, *, json_mode: bool) -> None:
    if json_mode:
        print(dumps({"ok": True, **data}))
        return
    for key, value in data.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    print("  - " + "; ".join(f"{k}={v}" for k, v in item.items()))
                else:
                    print(f"  - {item}")
        elif value is None or value == "":
            continue
        else:
            print(f"{key}: {value}")


def _client(cfg: ResolvedConfig, *, require_session: bool = True) -> PortalClient:
    cookie: str | None = None
    if require_session:
        cookie, _ = load_session()
        if not cookie:
            raise CliError(
                "keine aktive Session: zuerst 'hochschulstart login' ausführen",
                code=ec.AUTH,
            )
    return PortalClient(cfg.base_url, session_cookie=cookie)


def _login_page_confirmed(html: str) -> bool:
    if _has_password_form(html):
        return False
    text = html.lower()
    return any(
        marker in text
        for marker in ("angemeldet", "bewerbungsportal", "mein konto", "willkommen")
    )


def _has_password_form(html: str) -> bool:
    try:
        form = extract_form(html)
    except CliError:
        return False
    return any("pass" in name.lower() for name in (form.get("inputs") or {}))


def _reject_unsupported_auth(html: str) -> None:
    # Ein normales Login-Formular mit Passwortfeld ist keine Auth-Wand; der
    # Hinweis-Link auf die BundID steht auch auf der funktionierenden Login-Seite.
    if _has_password_form(html):
        return
    method = unsupported_auth_method(html)
    if method:
        raise CliError(
            f"nicht unterstütztes Auth-Verfahren erkannt ({method}) — "
            "Anmeldung im Browser auf hochschulstart.de durchführen",
            code=ec.AUTH,
        )


def _check(resp, *, context: str) -> None:
    if resp.status in (401, 403):
        raise CliError(f"{context}: Anmeldung erforderlich oder abgelehnt (HTTP {resp.status})", code=ec.AUTH)
    if resp.status == 404:
        raise CliError(f"{context}: nicht gefunden (HTTP 404)", code=ec.INPUT)
    if resp.status >= 400:
        raise CliError(f"{context}: HTTP {resp.status}", code=ec.NETWORK)
    title_low = resp.text[:2000].lower()
    if "wartung" in title_low and "<title>wartung" in title_low:
        raise CliError("Das DoSV-Bewerbungsportal ist derzeit nicht erreichbar (Wartung).", code=ec.NETWORK)


def _form_post_fields(form: dict) -> dict[str, str]:
    fields: dict[str, str] = dict(form.get("hidden") or {})
    for name, value in (form.get("inputs") or {}).items():
        if name in fields:
            continue
        if value:
            fields[name] = value
    return fields


def _resolve_decision_post(
    client: PortalClient,
    html: str,
    action: str,
    bewerbung_id: str,
) -> tuple[str, dict[str, str]]:
    fallback = f"{APPLICATIONS_PATH}/{bewerbung_id}/{action}"
    try:
        form = extract_form(html, action_contains=action)
    except CliError:
        form = {"action": fallback, "method": "post", "inputs": {}, "hidden": {}}
    target = form.get("action") or fallback
    method = (form.get("method") or "post").lower()
    if method == "get":
        resp = client.get(target)
        _check(resp, context=f"{action} {bewerbung_id} (Bestätigung)")
        try:
            form = extract_form(resp.text, action_contains=action)
        except CliError:
            form = extract_form(resp.text)
        target = form.get("action") or target
        method = (form.get("method") or "post").lower()
    if method != "post":
        raise CliError(
            f"{action} {bewerbung_id}: Bestätigungsformular erwartet POST, bekam {method!r}",
            code=ec.PARSE,
        )
    return target, _form_post_fields(form)


def _login_form_fields(form: dict, username: str, password: str) -> dict[str, str]:
    fields: dict[str, str] = dict(form.get("hidden") or {})
    used_user = used_pass = False
    for name, value in (form.get("inputs") or {}).items():
        if name in fields:
            continue
        low = name.lower()
        if not used_user and any(k in low for k in ("benutzer", "username", "user")):
            fields[name] = username
            used_user = True
        elif not used_pass and any(k in low for k in ("passwort", "password", "pass")):
            fields[name] = password
            used_pass = True
        elif value:
            fields[name] = value
    if not used_user:
        fields["benutzername"] = username
    if not used_pass:
        fields["passwort"] = password
    return fields


def _read_password_file(path: Path) -> str:
    if not path.is_file():
        raise CliError(f"Passwortdatei nicht gefunden: {path}", code=ec.INPUT)
    return path.read_text(encoding="utf-8").strip("\r\n")


def _interactive(json_mode: bool) -> bool:
    """Interaktive Prompts nur im echten Terminal; JSON/Pipes bleiben maschinenlesbar."""
    import sys

    return not json_mode and sys.stdin.isatty()


def _prompt_credentials() -> tuple[str, str] | None:
    """Benutzername/Passwort im Terminal fragen; None ohne TTY (kein Prompt)."""
    import getpass
    import sys

    if not sys.stdin.isatty():
        return None
    if sys.stdout.isatty():
        print("Zugangsdaten für hochschulstart.de (das Passwort wird nicht angezeigt):")
    username = input("Benutzername: ").strip()
    password = getpass.getpass("Passwort: ")
    return username, password


def _keyring_import():
    try:
        import keyring
    except ImportError:
        return None
    return keyring


def _offer_keyring_store(username: str | None, password: str) -> None:
    """Passwort optional im Schlüsselbund ablegen (nur interaktiv, nur wenn nutzbar)."""
    keyring = _keyring_import()
    if keyring is None:
        return
    answer = input("Passwort im Schlüsselbund speichern? [J/n] ").strip().lower()
    if answer not in ("", "j", "ja"):
        return
    try:
        if username is not None:
            keyring.set_password(KEYRING_SERVICE, "username", username)
        keyring.set_password(KEYRING_SERVICE, "password", password)
    except Exception as exc:
        print(
            f"Hinweis: Speichern im Schlüsselbund fehlgeschlagen ({type(exc).__name__}) — "
            "Passwort wurde nicht gespeichert.",
            file=_stderr(),
        )
        return
    print("Passwort im Schlüsselbund gespeichert.", file=_stderr())


def _stderr():
    import sys

    return sys.stderr


def cmd_version(_args, json_mode: bool) -> int:
    if json_mode:
        print(dumps({"ok": True, "version": __version__}))
    else:
        print(__version__)
    return ec.OK


def cmd_config(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    cookie, session_source = load_session()
    _emit(
        {
            "base_url": cfg.base_url,
            "public_url": cfg.public_url,
            "username_set": bool(cfg.username),
            "password_set": bool(cfg.password),
            "session_present": bool(cookie),
            "session_source": session_source,
            "sources": cfg.sources,
        },
        json_mode=json_mode,
    )
    return ec.OK


def cmd_login(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    username = args.username or cfg.username
    password = _read_password_file(args.password_file) if args.password_file else cfg.password
    prompted_username = prompted_password = False
    if (not username or not password) and _interactive(json_mode):
        creds = _prompt_credentials()
        if creds is not None:
            if not username and creds[0]:
                username = creds[0]
                prompted_username = True
            if not password and creds[1]:
                password = creds[1]
                prompted_password = True
    missing = []
    if not username:
        missing.append("--username oder HOCHSCHULSTART_USERNAME")
    if not password:
        missing.append("--password-file oder HOCHSCHULSTART_PASSWORD")
    if missing:
        raise CliError(
            "Zugangsdaten fehlen: "
            + ", ".join(missing)
            + " oder `hochschulstart login` im Terminal ausführen",
            code=ec.AUTH,
        )

    if args.dry_run:
        fields = _login_form_fields(
            {"action": LOGIN_FALLBACK_ACTION, "method": "post", "inputs": {}, "hidden": {}},
            username,
            password,
        )
        target = join_preserve_base_path(cfg.base_url, LOGIN_FALLBACK_ACTION)
        _emit(
            {
                "login": "ok",
                "username": username,
                "session_saved": "dry-run",
                "dry_run": True,
                "sent": False,
                "request": {"method": "POST", "url": target, "form_fields": sorted(fields)},
            },
            json_mode=json_mode,
        )
        return ec.OK

    client = _client(cfg, require_session=False)
    page = client.get(LOGIN_PAGE)
    _check(page, context="Login-Seite")
    _reject_unsupported_auth(page.text)
    try:
        # Live enthält die action eine session-spezifische numerische ID
        # (z. B. /bewerber/2376), nicht das Wort "login".
        form = extract_form(page.text)
    except CliError:
        form = {"action": LOGIN_FALLBACK_ACTION, "method": "post", "inputs": {}}
    action = form.get("action") or LOGIN_FALLBACK_ACTION
    fields = _login_form_fields(form, username, password)
    resp = client.post_form(action, fields)
    if resp.status in (401, 403):
        _reject_unsupported_auth(resp.text)
        hint = login_error_hint(resp.text) or login_error_hint(page.text)
        detail = f" ({hint})" if hint else " (Hinweis: Konto muss aktiviert sein)"
        raise CliError(f"Login fehlgeschlagen: Zugangsdaten prüfen{detail}", code=ec.AUTH)
    _check(resp, context="Login")
    hint = login_error_hint(resp.text)
    if hint:
        raise CliError(f"Login fehlgeschlagen: {hint}", code=ec.AUTH)
    _reject_unsupported_auth(resp.text)
    if not _login_page_confirmed(resp.text):
        raise CliError(
            "Login nicht bestätigt: das Portal zeigt keine angemeldete Seite. "
            "Zugangsdaten prüfen und `hochschulstart login` erneut ausführen",
            code=ec.AUTH,
        )
    if client.session_cookie:
        saved = save_session(client.session_cookie, dry_run=args.dry_run)
    else:
        saved = save_login_marker(dry_run=args.dry_run)
    if prompted_password and _interactive(json_mode):
        _offer_keyring_store(username if prompted_username else None, password)
    if json_mode:
        _emit(
            {
                "login": "ok",
                "username": username,
                "session_saved": saved,
                "dry_run": args.dry_run,
            },
            json_mode=True,
        )
    else:
        print("Login erfolgreich.")
        if saved == "keyring":
            print("Session im Schlüsselbund gespeichert.")
        elif saved == "file":
            print(f"Session gespeichert (Datei mit Rechten 0600): {session_path()}")
        else:
            print(f"Session gespeichert ({saved}).")
    return ec.OK


def cmd_whoami(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    cookie, source = load_session()
    if not cookie:
        raise CliError(
            "keine aktive Session: zuerst 'hochschulstart login' ausführen",
            code=ec.AUTH,
        )
    username = cfg.username or "(unbekannt)"
    if json_mode:
        _emit(
            {
                "username": username,
                "session_source": source,
            },
            json_mode=True,
        )
    else:
        print(f"Benutzer: {username}")
        print(f"Session: {source}")
    return ec.OK


def cmd_logout(args, json_mode: bool) -> int:
    resolve_config(config_path=args.config)
    cookie, _source = load_session()
    clear_session()
    if json_mode:
        _emit({"logged_out": True, "session_present": False}, json_mode=True)
    elif cookie:
        print("Session entfernt.")
    else:
        print("Keine Session vorhanden.")
    return ec.OK


def _matches(application: dict[str, str], query: str) -> bool:
    needle = query.casefold()
    return any(
        needle in (application.get(field) or "").casefold()
        for field in ("program", "university", "id")
    )


def _application_line(index: int, application: dict[str, str]) -> str:
    program = application.get("program") or "?"
    university = application.get("university") or "?"
    status = application.get("status") or "?"
    app_id = application.get("id") or "?"
    return f"{index}) {program} – {university} – {status} ({app_id})"


def _emit_applications(applications: list[dict[str, str]]) -> None:
    print(f"Bewerbungen ({len(applications)}):")
    for index, application in enumerate(applications, start=1):
        print(_application_line(index, application))


def cmd_status(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    client = _client(cfg)
    resp = client.get(APPLICATIONS_PATH)
    _check(resp, context="Bewerbungsübersicht")
    applications = parse_applications(resp.text)
    if args.search:
        applications = [a for a in applications if _matches(a, args.search)]
    if args.status:
        wanted = args.status.lower()
        applications = [a for a in applications if wanted in (a.get("status") or "").lower()]
    if json_mode:
        _emit({"count": len(applications), "applications": applications}, json_mode=True)
    else:
        _emit_applications(applications)
    return ec.OK


def _load_applications(client: PortalClient) -> list[dict[str, str]]:
    resp = client.get(APPLICATIONS_PATH)
    _check(resp, context="Bewerbungsübersicht")
    return parse_applications(resp.text)


def cmd_rangliste(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    client = _client(cfg)
    matched_ids: set[str] | None = None
    if args.search:
        applications = [a for a in _load_applications(client) if _matches(a, args.search)]
        if not applications:
            raise CliError(
                f"keine Bewerbung zu {args.search!r} gefunden — "
                f"'hochschulstart status {args.search}' zeigt die Treffer",
                code=ec.INPUT,
            )
        matched_ids = {a.get("id") or "" for a in applications}
    resp = client.get(RANGLISTEN_PATH)
    _check(resp, context="Ranglisten")
    entries = parse_ranglisten(resp.text)
    if matched_ids is not None:
        entries = [e for e in entries if (e.get("bewerbung") or "") in matched_ids]
    if args.bewerbung:
        entries = [e for e in entries if args.bewerbung in (e.get("bewerbung") or "")]
        if not entries:
            raise CliError(
                f"keine Ranglisten-Einträge für Bewerbung {args.bewerbung!r} — "
                "'hochschulstart rangliste' zeigt alle Einträge",
                code=ec.INPUT,
            )
    if json_mode:
        _emit({"count": len(entries), "ranglisten": entries}, json_mode=True)
    else:
        print(f"Ranglisten ({len(entries)}):")
        for index, entry in enumerate(entries, start=1):
            print(
                f"{index}) {entry.get('bewerbung', '?')} – "
                f"{entry.get('quote', '?')} – Rang {entry.get('rang', '?')} "
                f"(Grenzrang {entry.get('grenzrang', '?')})"
            )
    return ec.OK


def cmd_fristen(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    client = PortalClient(cfg.base_url)
    url = args.url or cfg.public_url
    resp = client.get(url)
    _check(resp, context="Terminübersicht")
    termine = parse_termine(resp.text)
    if args.limit is not None:
        limite = require_positive_int(args.limit, name="--limit")
        termine = termine[:limite]
    _emit({"source": url, "count": len(termine), "termine": termine}, json_mode=json_mode)
    return ec.OK


def _snapshot(client: PortalClient) -> dict:
    apps_resp = client.get(APPLICATIONS_PATH)
    _check(apps_resp, context="Bewerbungsübersicht")
    applications = parse_applications(apps_resp.text)
    status_map: dict[str, dict[str, str]] = {}
    for app in applications:
        key = app.get("id") or app.get("program") or "?"
        status_map[key] = {
            "status": app.get("status", ""),
            "rang": app.get("rang", ""),
            "program": app.get("program", ""),
            "university": app.get("university", ""),
        }
    rang_map: dict[str, str] = {}
    rang_resp = client.get(RANGLISTEN_PATH)
    if rang_resp.status < 400:
        try:
            for entry in parse_ranglisten(rang_resp.text):
                key = "|".join([entry.get("bewerbung", "?"), entry.get("quote", "?")])
                rang_map[key] = entry.get("rang", "")
        except CliError:
            rang_map = {}
    return {"applications": status_map, "ranglisten": rang_map}


def _diff(previous: dict | None, current: dict) -> list[dict]:
    changes: list[dict] = []
    prev_apps = (previous or {}).get("applications") or {}
    for key, now in current["applications"].items():
        before = prev_apps.get(key)
        if before is None:
            changes.append({"application": key, "change": "neu", "to": now.get("status", "")})
            continue
        if before.get("status") != now.get("status"):
            changes.append(
                {
                    "application": key,
                    "change": "status",
                    "from": before.get("status", ""),
                    "to": now.get("status", ""),
                }
            )
        if before.get("rang") != now.get("rang"):
            changes.append(
                {
                    "application": key,
                    "change": "rang",
                    "from": before.get("rang", ""),
                    "to": now.get("rang", ""),
                }
            )
    for key, before in prev_apps.items():
        if key not in current["applications"]:
            changes.append({"application": key, "change": "entfernt", "from": before.get("status", "")})
    return changes


def cmd_watch(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    client = _client(cfg)
    state_path: Path = args.state or (config_dir() / "watch.json")
    previous = load_state(state_path)
    current = _snapshot(client)
    current["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    changes = _diff(previous, current)
    save_state(state_path, current, dry_run=args.dry_run)
    _emit(
        {
            "state_path": str(state_path),
            "dry_run": args.dry_run,
            "changes": changes,
            "watched": len(current["applications"]),
        },
        json_mode=json_mode,
    )
    return ec.OK


def _detail(client: PortalClient, bewerbung_id: str) -> tuple[dict, str | None]:
    resp = client.get(f"{APPLICATIONS_PATH}/{bewerbung_id}")
    _check(resp, context=f"Bewerbung {bewerbung_id}")
    status: str | None = None
    try:
        apps = parse_applications(resp.text)
        if apps:
            status = apps[0].get("status") or None
    except CliError:
        status = None
    return resp.text, status


def _stderr_write(text: str) -> None:
    import sys

    sys.stderr.write(text)
    sys.stderr.flush()


def _stdout_write(text: str) -> None:
    import sys

    sys.stdout.write(text)


def _choose_application(
    action: str,
    matches: list[dict[str, str]],
    *,
    interactive: bool,
) -> dict[str, str]:
    if len(matches) == 1:
        return matches[0]
    listing = "\n".join(
        _application_line(index, application)
        for index, application in enumerate(matches, start=1)
    )
    if not interactive:
        raise CliError(
            f"mehrere Bewerbungen passen zur Auswahl — bitte den Suchbegriff genauer "
            f"angeben, z. B. die Bewerbungsnummer:\n{listing}",
            code=ec.INPUT,
        )
    _stderr_write("Mehrere Bewerbungen passen zu deiner Suche:\n" + listing + "\n")
    _stderr_write("Auswahl (Nummer): ")
    answer = input().strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(matches):
        raise CliError(
            "ungültige Auswahl — Nummer aus der Liste eingeben oder den Suchbegriff "
            "genauer fassen",
            code=ec.INPUT,
        )
    return matches[int(answer) - 1]


def _interactive_decision(
    action: str,
    application: dict[str, str],
    *,
    interactive: bool,
) -> bool:
    """Zusammenfassung + verbindliche Rückfrage auf stderr; True nur bei j/ja."""
    if not interactive:
        return False
    app_id = application.get("id") or "?"
    _stderr_write(
        f"Bewerbung: {app_id}\n"
        f"Studiengang: {application.get('program') or '?'}\n"
        f"Hochschule: {application.get('university') or '?'}\n"
        f"Status: {application.get('status') or '?'}\n"
    )
    question = "Annahme verbindlich? [j/N] " if action == "annehmen" else "Absage verbindlich? [j/N] "
    _stderr_write(question)
    answer = input().strip().lower()
    if answer in ("j", "ja"):
        return True
    _stderr_write("Abgebrochen — nichts gesendet.\n")
    return False


def _decide(action: str, args, json_mode: bool) -> int:
    query = args.suchbegriff
    require_application_id(query, name="Suchbegriff")
    confirm = bool(args.confirm)
    interactive = _interactive(json_mode)
    if not confirm and not interactive and not args.dry_run:
        raise CliError(
            f"{action} sendet nichts ohne Bestätigung: im Terminal ausführen und "
            f"mit j bestätigen, oder für Agenten '{action} {query} --confirm' verwenden",
            code=ec.INPUT,
        )

    cfg = resolve_config(config_path=args.config)
    client = _client(cfg)
    matches = [a for a in _load_applications(client) if _matches(a, query)]
    if not matches:
        raise CliError(
            f"keine Bewerbung zu {query!r} gefunden — 'hochschulstart status {query}' "
            "zeigt die vorhandenen Bewerbungen",
            code=ec.INPUT,
        )
    application = _choose_application(action, matches, interactive=interactive)
    bewerbung_id = application.get("id") or ""
    require_application_id(bewerbung_id, name="Bewerbungsnummer")
    status = application.get("status") or ""
    if status and any(t in status.lower() for t in TERMINAL_STATUS):
        raise CliError(
            f"Bewerbung {bewerbung_id} ist bereits '{status}' — keine Aktion nötig",
            code=ec.INPUT,
        )
    if action == "annehmen" and status and not any(
        k in status.lower() for k in ("angebot", "zulassung")
    ):
        raise CliError(
            f"Bewerbung {bewerbung_id} hat kein Zulassungsangebot (Status: {status}) — "
            "annehmen nicht möglich",
            code=ec.INPUT,
        )

    html, _status = _detail(client, bewerbung_id)
    target, fields = _resolve_decision_post(client, html, action, bewerbung_id)
    if args.dry_run:
        _emit(
            {
                "action": action,
                "application_id": bewerbung_id,
                "dry_run": True,
                "sent": False,
                "request": {"method": "POST", "url": target, "form_fields": sorted(fields)},
            },
            json_mode=json_mode,
        )
        return ec.OK

    if not confirm and not _interactive_decision(
        action, application, interactive=interactive
    ):
        return ec.OK

    resp = client.post_form(target, fields)
    if resp.status >= 400:
        hint = decision_error_hint(resp.text) or f"HTTP {resp.status}"
        code = ec.INPUT if resp.status < 500 else ec.NETWORK
        raise CliError(f"{action} {bewerbung_id}: {hint}", code=code)
    _check(resp, context=f"{action} {bewerbung_id}")
    hint = decision_error_hint(resp.text)
    if hint:
        raise CliError(f"{action} {bewerbung_id}: {hint}", code=ec.INPUT)
    if not decision_accepted(resp.text, action):
        raise CliError(f"{action} {bewerbung_id} wurde von der Plattform abgelehnt", code=ec.INPUT)

    verb = "Angenommen" if action == "annehmen" else "Abgesagt"
    program = application.get("program") or "?"
    if json_mode:
        _emit(
            {
                "action": action,
                "application_id": bewerbung_id,
                "program": program,
                "university": application.get("university") or "",
                "sent": True,
                "result": "ok",
            },
            json_mode=True,
        )
    else:
        print(f"{verb}: {bewerbung_id} ({program})")
    return ec.OK


def cmd_annehmen(args, json_mode: bool) -> int:
    return _decide("annehmen", args, json_mode)


def cmd_absagen(args, json_mode: bool) -> int:
    return _decide("absagen", args, json_mode)


def build_parser(json_mode: bool) -> ArgumentParser:
    parser = ArgumentParser(prog="hochschulstart", description=__doc__)
    parser.set_json_mode(json_mode)
    parser.add_argument("--version", action="version", version=__version__)
    global_flags = ArgumentParser(add_help=False)
    global_flags.add_argument("--json", action="store_true", help="genau ein JSON-Objekt auf stdout")
    global_flags.add_argument("--dry-run", action="store_true", help="nichts senden/schreiben (nur zeigen)")

    sub = parser.add_subparsers(dest="command", required=True)

    def command_parser(name: str, **kwargs):
        p = sub.add_parser(name, parents=[global_flags], **kwargs)
        p.set_json_mode(json_mode)
        return p

    p = command_parser("version", help="Paketversion ausgeben")
    p.set_defaults(func=cmd_version)

    p = command_parser("config", help="aufgelöste Konfiguration zeigen")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei (Default: ~/.config/hochschulstart/config.json)")
    p.set_defaults(func=cmd_config)

    p = command_parser("login", help="Session im DoSV-Portal aufbauen (fehlende Zugangsdaten fragt die CLI im Terminal ab)")
    p.add_argument("--username", help="Benutzername (sonst Env/Config/keyring/Terminal-Prompt)")
    p.add_argument("--password-file", type=Path, help="Datei mit dem Passwort (statt Env/Config/keyring/Terminal-Prompt)")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_login)

    p = command_parser("whoami", help="angemeldeten Benutzer und Session-Quelle zeigen")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_whoami)

    p = command_parser("logout", help="Session entfernen (idempotent)")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_logout)

    p = command_parser("status", help="Bewerbungen inkl. Status auflisten")
    p.add_argument("search", nargs="?", help="Suchbegriff in Studiengang/Hochschule/Bewerbungsnummer")
    p.add_argument("--status", help="nur Bewerbungen mit diesem Status-Teilstring")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_status)

    p = command_parser("rangliste", help="eigene Ranglisten-Positionen zeigen")
    p.add_argument("search", nargs="?", help="Suchbegriff in Studiengang/Hochschule/Bewerbungsnummer")
    p.add_argument("--bewerbung", help="auf eine Bewerbungsnummer filtern")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_rangliste)

    p = command_parser("fristen", help="öffentliche Termine & Fristen zeigen")
    p.add_argument("--url", help="Quell-URL der Terminübersicht")
    p.add_argument("--limit", type=int, help="maximale Anzahl Einträge")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_fristen)

    p = command_parser("watch", help="Statusänderungen lokal beobachten")
    p.add_argument("--state", type=Path, default=None, help="Watch-State-Datei (Default: Config-Verzeichnis/watch.json)")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_watch)

    for action, helptext in (("annehmen", "Zulassungsangebot annehmen (Terminal: Rückfrage [j/N])"),
                             ("absagen", "Bewerbung absagen/zurückziehen (Terminal: Rückfrage [j/N])")):
        p = command_parser(action, help=helptext)
        p.add_argument("suchbegriff", help="Studiengang, Hochschule oder Bewerbungsnummer")
        p.add_argument(
            "--confirm",
            "--yes",
            dest="confirm",
            action="store_true",
            help="ohne Rückfrage senden (nur für Agenten; ohne TTY Pflicht)",
        )
        p.add_argument("--config", type=Path, default=None, help="Config-Datei")
        p.set_defaults(func=cmd_annehmen if action == "annehmen" else cmd_absagen)

    return parser


def _main(argv: list[str] | None = None) -> int:
    import sys

    args_list = argv if argv is not None else sys.argv[1:]
    explicit_json = "--json" in args_list
    parser = build_parser(explicit_json)
    args = parser.parse_args(args_list)
    explicit_json = explicit_json or bool(getattr(args, "json", False))
    auto_json = not sys.stdout.isatty()
    json_mode = explicit_json or auto_json
    return args.func(args, json_mode)


def main() -> None:
    import sys

    sys.exit(run_main(_main))


if __name__ == "__main__":
    main()
