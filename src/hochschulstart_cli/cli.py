"""hochschulstart.de (DoSV): Bewerbungsportal-CLI.

Kommandos: login, status, rangliste, fristen, watch, annehmen, absagen.
Sicherheitsregel: annehmen/absagen senden nur mit ``--confirm``; ohne beendet
die CLI **vor jedem Request** mit Exit 1. Ohne Session: Exit 2. ``--dry-run``
zeigt den geplanten Request, sendet ihn aber nicht.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from hochschulstart_cli import __version__
from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.config import (
    ResolvedConfig,
    config_dir,
    require_credentials,
    resolve_config,
)
from hochschulstart_cli.errors import ArgumentParser, CliError, run_main
from hochschulstart_cli.http_client import PortalClient
from hochschulstart_cli.json_util import dumps
from hochschulstart_cli.parsing import (
    extract_form,
    login_error_hint,
    parse_applications,
    parse_ranglisten,
    parse_termine,
    unsupported_auth_method,
)
from hochschulstart_cli.session import load_session, save_session
from hochschulstart_cli.state import load_state, save_state
from hochschulstart_cli.validation import require_positive_int

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


def _reject_unsupported_auth(html: str) -> None:
    method = unsupported_auth_method(html)
    if method:
        raise CliError(
            f"nicht unterstütztes Auth-Verfahren erkannt ({method})",
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
    missing = []
    if not username:
        missing.append("--username oder HOCHSCHULSTART_USERNAME")
    if not password:
        missing.append("--password-file oder HOCHSCHULSTART_PASSWORD")
    if missing:
        raise CliError("Zugangsdaten fehlen: " + ", ".join(missing), code=ec.AUTH)

    client = _client(cfg, require_session=False)
    page = client.get(LOGIN_PAGE)
    _check(page, context="Login-Seite")
    _reject_unsupported_auth(page.text)
    try:
        form = extract_form(page.text, action_contains="login")
    except CliError:
        form = {"action": LOGIN_FALLBACK_ACTION, "method": "post", "inputs": {}}
    action = form.get("action") or LOGIN_FALLBACK_ACTION
    fields = _login_form_fields(form, username, password)
    resp = client.post_form(action, fields)
    if resp.status in (401, 403) or not client.session_cookie:
        _reject_unsupported_auth(resp.text)
        hint = login_error_hint(resp.text) or login_error_hint(page.text)
        detail = f" ({hint})" if hint else " (Hinweis: Konto muss aktiviert sein)"
        raise CliError(f"Login fehlgeschlagen: Zugangsdaten prüfen{detail}", code=ec.AUTH)
    _check(resp, context="Login")
    saved = save_session(client.session_cookie, dry_run=args.dry_run)
    _emit(
        {
            "login": "ok",
            "username": username,
            "session_saved": saved,
            "dry_run": args.dry_run,
        },
        json_mode=json_mode,
    )
    return ec.OK


def cmd_status(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    client = _client(cfg)
    resp = client.get(APPLICATIONS_PATH)
    _check(resp, context="Bewerbungsübersicht")
    applications = parse_applications(resp.text)
    if args.status:
        wanted = args.status.lower()
        applications = [a for a in applications if wanted in (a.get("status") or "").lower()]
    _emit({"count": len(applications), "applications": applications}, json_mode=json_mode)
    return ec.OK


def cmd_rangliste(args, json_mode: bool) -> int:
    cfg = resolve_config(config_path=args.config)
    client = _client(cfg)
    resp = client.get(RANGLISTEN_PATH)
    _check(resp, context="Ranglisten")
    entries = parse_ranglisten(resp.text)
    if args.bewerbung:
        entries = [e for e in entries if args.bewerbung in (e.get("bewerbung") or "")]
        if not entries:
            raise CliError(f"keine Ranglisten-Einträge für Bewerbung {args.bewerbung!r}", code=ec.INPUT)
    _emit({"count": len(entries), "ranglisten": entries}, json_mode=json_mode)
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


def _decide(action: str, args, json_mode: bool) -> int:
    if not args.confirm:
        raise CliError(
            f"{action} sendet nichts ohne --confirm: '{action} {args.bewerbung_id} --confirm' verwenden",
            code=ec.INPUT,
        )
    cfg = resolve_config(config_path=args.config)
    client = _client(cfg)
    html, status = _detail(client, args.bewerbung_id)
    if status and any(t in status.lower() for t in TERMINAL_STATUS):
        raise CliError(f"Bewerbung {args.bewerbung_id} ist bereits '{status}' — keine Aktion nötig", code=ec.INPUT)
    if action == "annehmen" and status and not any(k in status.lower() for k in ("angebot", "zulassung")):
        raise CliError(
            f"Bewerbung {args.bewerbung_id} hat kein Zulassungsangebot (Status: {status}) — annehmen nicht möglich",
            code=ec.INPUT,
        )
    try:
        form = extract_form(html, action_contains=action)
    except CliError:
        form = {"action": f"{APPLICATIONS_PATH}/{args.bewerbung_id}/{action}", "method": "post", "inputs": {}}
    target = form.get("action") or f"{APPLICATIONS_PATH}/{args.bewerbung_id}/{action}"
    fields = {k: v for k, v in (form.get("hidden") or {}).items()}
    if args.dry_run:
        _emit(
            {
                "action": action,
                "application_id": args.bewerbung_id,
                "dry_run": True,
                "sent": False,
                "request": {"method": "POST", "url": target, "form_fields": sorted(fields)},
            },
            json_mode=json_mode,
        )
        return ec.OK
    resp = client.post_form(target, fields)
    _check(resp, context=f"{action} {args.bewerbung_id}")
    low = resp.text.lower()
    if any(marker in low for marker in ("fehlgeschlagen", "nicht möglich", "ungültig")):
        raise CliError(f"{action} {args.bewerbung_id} wurde von der Plattform abgelehnt", code=ec.INPUT)
    _emit(
        {
            "action": action,
            "application_id": args.bewerbung_id,
            "sent": True,
            "result": "ok",
        },
        json_mode=json_mode,
    )
    return ec.OK


def cmd_annehmen(args, json_mode: bool) -> int:
    return _decide("annehmen", args, json_mode)


def cmd_absagen(args, json_mode: bool) -> int:
    return _decide("absagen", args, json_mode)


def build_parser(json_mode: bool) -> ArgumentParser:
    parser = ArgumentParser(prog="hochschulstart", description=__doc__)
    parser.set_json_mode(json_mode)
    global_flags = ArgumentParser(add_help=False)
    global_flags.add_argument("--json", action="store_true", help="genau ein JSON-Objekt auf stdout")
    global_flags.add_argument("--dry-run", action="store_true", help="nichts senden/schreiben (nur zeigen)")

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("version", parents=[global_flags], help="Paketversion ausgeben")
    p.set_defaults(func=cmd_version)

    p = sub.add_parser("config", parents=[global_flags], help="aufgelöste Konfiguration zeigen")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei (Default: ~/.config/hochschulstart/config.json)")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("login", parents=[global_flags], help="Session im DoSV-Portal aufbauen")
    p.add_argument("--username", help="Benutzername (sonst Env/Config/keyring)")
    p.add_argument("--password-file", type=Path, help="Datei mit dem Passwort (statt Env/Config/keyring)")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("status", parents=[global_flags], help="Bewerbungen inkl. Status auflisten")
    p.add_argument("--status", help="nur Bewerbungen mit diesem Status-Teilstring")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("rangliste", parents=[global_flags], help="eigene Ranglisten-Positionen zeigen")
    p.add_argument("--bewerbung", help="auf eine Bewerbungsnummer filtern")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_rangliste)

    p = sub.add_parser("fristen", parents=[global_flags], help="öffentliche Termine & Fristen zeigen")
    p.add_argument("--url", help="Quell-URL der Terminübersicht")
    p.add_argument("--limit", type=int, help="maximale Anzahl Einträge")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_fristen)

    p = sub.add_parser("watch", parents=[global_flags], help="Statusänderungen lokal beobachten")
    p.add_argument("--state", type=Path, default=None, help="Watch-State-Datei (Default: Config-Verzeichnis/watch.json)")
    p.add_argument("--config", type=Path, default=None, help="Config-Datei")
    p.set_defaults(func=cmd_watch)

    for action, helptext in (("annehmen", "Zulassungsangebot annehmen (nur mit --confirm)"),
                             ("absagen", "Bewerbung absagen/zurückziehen (nur mit --confirm)")):
        p = sub.add_parser(action, parents=[global_flags], help=helptext)
        p.add_argument("bewerbung_id", help="Bewerbungsnummer")
        p.add_argument("--confirm", action="store_true", help="Aktion wirklich senden (Pflicht)")
        p.add_argument("--config", type=Path, default=None, help="Config-Datei")
        p.set_defaults(func=cmd_annehmen if action == "annehmen" else cmd_absagen)

    return parser


def _main(argv: list[str] | None = None) -> int:
    args_list = argv if argv is not None else __import__("sys").argv[1:]
    json_mode = "--json" in args_list
    parser = build_parser(json_mode)
    args = parser.parse_args(args_list)
    json_mode = args.json or json_mode
    return args.func(args, json_mode)


def main() -> None:
    import sys

    sys.exit(run_main(_main))


if __name__ == "__main__":
    main()
