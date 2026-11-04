# hochschulstart

CLI für das DoSV-Bewerbungsportal von hochschulstart.de: Login, Bewerbungsstatus,
Ranglisten, öffentliche Fristen und ein lokaler Watch auf Statusänderungen.
**Annahme/Absage werden nur mit `--confirm` gesendet** — ohne `--confirm` beendet
sich die CLI vor jedem Request mit Exit 1.

> Kein Ersatz für das Portal: rechtsverbindliche Erklärungen (Annehmen/Absagen)
> bleiben deine eigene Entscheidung. Die CLI fasst nur zusammen und sendet exakt
> den einen Request, den du mit `--confirm` freigibst.

## Schnellstart

`pipx` installiert den Befehl direkt in den PATH. Danach anmelden, Bewerbungen
ansehen und eine Zulassung mit Suchbegriff annehmen:

```bash
pipx install git+https://github.com/smlfg/hochschulstart-cli
hochschulstart login
hochschulstart status
hochschulstart annehmen "Musterstudiengang"
```

`login` fragt im Terminal nach Benutzername und Passwort. `status` zeigt
Studiengang, Hochschule und Status; `annehmen` fragt vor der verbindlichen
Aktion mit `[j/N]` nach. Im Terminal gibt die CLI lesbaren Text aus; für
Skripte/Agenten gibt es `--json`. Interaktiv gefragt wird nur, wenn eine echte
Tastatur (TTY) davor hängt.

## Installation

```bash
git clone <repo-url> && cd hochschulstart-cli
uv sync --extra dev
uv run hochschulstart --help
```

Alternativ: `pip install -e ".[dev]"`. Optionale keyring-Ablage:
`pip install -e ".[keyring]"`.

## Kommandos

Global (jeweils direkt **nach** dem Unterkommando, z. B. `status --json`):
`--json` (genau **ein** JSON-Objekt auf stdout, auch im Fehlerfall),
`--dry-run` (nichts senden/schreiben, nur zeigen).

| Kommando | Zweck |
|----------|-------|
| `hochschulstart login` | Session im DoSV-Portal aufbauen (creds: Flags/env/config/keyring; sonst interaktiv im Terminal) |
| `hochschulstart status` | Bewerbungen inkl. Status (`--status` filtert) |
| `hochschulstart rangliste` | eigene Ranglisten-Positionen (`--bewerbung` filtert) |
| `hochschulstart fristen` | öffentliche Terminübersicht (`--url`, `--limit`) |
| `hochschulstart watch` | Statusänderungen lokal beobachten (`--state PATH`) |
| `hochschulstart annehmen ID` | Zulassungsangebot annehmen — **nur mit `--confirm`** oder Terminal-Bestätigung |
| `hochschulstart absagen ID` | Bewerbung absagen/zurückziehen — **nur mit `--confirm`** oder Terminal-Bestätigung |
| `hochschulstart config` | aufgelöste Konfiguration (ohne Secrets) |
| `hochschulstart version` | Paketversion |

Beispiele:

```bash
hochschulstart login                                       # oder interaktiv: ohne Flags im Terminal
hochschulstart status                                      # Menschen: Namen statt IDs
hochschulstart status --status "Zulassungsangebot"
hochschulstart fristen --limit 10
hochschulstart login --dry-run                             # zeigt nur den Login-POST, sendet nichts
hochschulstart status --json                               # für Skripte/Agenten
hochschulstart rangliste --bewerbung B-1001
hochschulstart watch --state ~/.local/state/hochschulstart/watch.json
hochschulstart annehmen B-1001 --confirm --dry-run         # zeigt nur den Request
hochschulstart annehmen B-1001                             # Terminal: Bestätigungsfrage [j/N]
hochschulstart annehmen B-1001 --confirm                   # sendet wirklich (nicht interaktiv)
```

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Erfolg |
| 1 | Ungültige Eingabe (Flags, Argumente, Validierung); auch Abbruch ohne `--confirm` bzw. abgelehnte Terminal-Bestätigung; argparse-Usage |
| 2 | Authentifizierung (keine Session, fehlende/falsche Zugangsdaten) |
| 3 | Netzwerk / Portal nicht erreichbar (z. B. Wartung) |
| 4 | Parse-Fehler (HTML/JSON/Config/State unerwartet) |
| 130 | Abbruch durch Nutzer (Ctrl-C) oder EOF |

Implementierung: `hochschulstart_cli.exit_codes` und `hochschulstart_cli.errors`.

## Konfiguration

Präzedenz pro Feld: **env > Config-Datei > keyring**. Die Session-Cookie liegt
separat (env > keyring > Datei mit `0600`) und wird nie ausgegeben.

| Variable | Zweck |
|----------|-------|
| `HOCHSCHULSTART_BASE_URL` | Portal-Basis (Default: `https://dosv.hochschulstart.de`) |
| `HOCHSCHULSTART_PUBLIC_URL` | öffentliche Terminseite (Default: `https://www.hochschulstart.de/bewerben-beobachten/termine`) |
| `HOCHSCHULSTART_USERNAME` | DoSV-Benutzername |
| `HOCHSCHULSTART_PASSWORD` | DoSV-Passwort |
| `HOCHSCHULSTART_SESSION` | Session-Cookie direkt (CI/Tests) |
| `HOCHSCHULSTART_CONFIG` | Pfad zur Config-JSON |
| `HOCHSCHULSTART_CONFIG_DIR` | Verzeichnis für Config/Session/Watch-Defaults |

Default-Config: `~/.config/hochschulstart/config.json` (JSON-Objekt mit
`base_url`, `public_url`, `username`, `password`). Passwörter gehören nicht in
argv-Argumente; `login` akzeptiert deshalb `--password-file`.

## Tests

Komplett offline: `tests/fake_portal.py` ist ein stdlib-`ThreadingHTTPServer`,
der Login-Formular, Bewerbungsübersicht, Ranglisten, Termine und den
Annehmen-/Absagen-Flow mit synthetischen Daten nachbildet — inklusive
Request-Recorder, der beweist, dass z. B. ohne `--confirm` kein Request rausgeht.

```bash
uv run --extra dev pytest -q
```

Abgedeckt: jedes Kommando happy path + Fehlerpfade (ohne Session → 2, Netz down
→ 3, kaputtes HTML/JSON → 4, fehlende Args → 1), `--confirm`-Gating,
JSON-Envelope (genau ein Objekt), Watch-State/dry-run, Secret-Leaks.

## Live-Check (öffentlich, read-only)

Durchgeführt am 14.10.2026 (Nachzug zu Issue #1), ausschließlich öffentliche
Seiten, kein Login, keine Formulare, ~8 Requests:

| Prüfung | Ergebnis |
|---------|----------|
| `https://www.hochschulstart.de/` | erreichbar (HTTP 200, TYPO3) |
| `https://www.hochschulstart.de/bewerben-beobachten/termine` | erreichbar; 6 HTML-Tabellen, **77** Terminzeilen — `fristen`/`parse_termine` passt (Snapshot: `tests/fixtures/termine_live_2026-10-14.html`) |
| `https://www.hochschulstart.de/bewerben-beobachten/bewerbungsstatus` | erreichbar (Infoseite) |
| `https://dosv.hochschulstart.de/bewerber` | **noch Wartung**: HTTP 302 → `https://wartung-bw.hochschulstart.de/`; `hochschulstart login` endet mit Exit **3** |
| Login-Flow (CSRF-Token, Fehlermeldungen) | offline gegen Fake-Portal verifiziert (`tx_login_token` im POST, Portal-Fehlertext bei HTTP 403/200); **live mit Konto** nach Ende der Wartung noch offen |
| `status` / `rangliste` mit echten Bewerbungsdaten | **noch nicht live testbar** (DoSV-Portal in Wartung); offline Happy-Path in `tests/test_contract_commands.py` |

Die CLI erkennt Wartungs-Redirects (`wartung` im Ziel-Host) und Wartungs-HTML
und beendet mit Exit 3 statt Unsinn zu parsen.

## Sicherheit

- `annehmen`/`absagen` senden **nur** mit `--confirm`; ohne beendet die CLI
  **vor jedem Request**   mit Exit 1. Im echten Terminal fragt die CLI außerdem
  nach („Wirklich annehmen/absagen? Das ist verbindlich. [j/N]“) — nur `j`/`ja`
  setzt die Aktion fort, alles andere bricht ohne Request ab. Mit `--confirm`
  aber ohne Session: Exit 2.
- `--dry-run` zeigt Methode, Ziel-URL und Formularfeld-Namen, sendet aber nichts
  und schreibt keinen State.
- Passwörter und Session-Cookies erscheinen nie in stdout/stderr, JSON, State
  oder Fehlermeldungen; `config --json` meldet nur `*_set`/Quellen.
- Vor der Annahme prüft die CLI den Status: kein Zulassungsangebot oder bereits
  angenommen/abgesagt → Exit 1, kein Request.
- Watch-State enthält nur Bewerbungsnummern/Status/Rang, keine Credentials.

## Grenzen

- Portal-Pfade (`/bewerber`, `/bewerber/bewerbungen`, `/bewerber/ranglisten`)
  sind aus der öffentlichen Struktur abgeleitet; der echte DoSV-Login braucht
  ein registriertes, aktiviertes Konto und ist nicht offline testbar. Bei
  Portalumbau ggf. Pfade in `cli.py` anpassen.
- Kein Captcha-/2FA-/Bund-ID-Flow; `login` unterstützt nur den klassischen
  DoSV-Benutzername/Passwort-Login. Wenn das Portal stattdessen Captcha, 2FA
  oder BundID verlangt, bricht `login` mit Exit **2** und der Meldung
  „nicht unterstütztes Auth-Verfahren erkannt“ ab (nicht „Zugangsdaten prüfen“).
- `fristen` liest die öffentliche Terminseite; örtliche Fristen einzelner
  Hochschulen stehen dort nicht.

## Layout

| Modul | Rolle |
|-------|-------|
| `cli.py` | Kommandos und Wiring |
| `http_client.py` | stdlib-HTTP-Client (Cookie, Wartungserkennung, höflich) |
| `parsing.py` | HTML-Parser (Bewerbungen, Ranglisten, Termine, Formulare) |
| `config.py` | env > Datei > keyring |
| `session.py` | Session-Cookie: env > keyring > Datei (0600) |
| `state.py` | atomare Writes; `--dry-run` schreibt nichts |
| `errors.py`, `exit_codes.py`, `json_util.py`, `validation.py`, `url_util.py` | Template-Muster |

## QA

Siehe [docs/QA-CHECKLIST.md](docs/QA-CHECKLIST.md) und [docs/TESTING.md](docs/TESTING.md).
