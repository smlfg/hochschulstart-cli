# Interface: hochschulstart-cli

Stand: 2026-11-04 (Schritt R2). Dieser Vertrag beschreibt den Zielzustand nach
der Nachrüstung. Vorhandene Befehle, Flags und Exit-Codes bleiben gültig; neue
positionale Suchbegriffe und die stderr-Prompts kommen hinzu.

## Aufruf

```
hochschulstart <kommando> [argumente] [optionen]
```

`--help` und `--version` enden mit Exit 0. Unterkommandos sind:

`login`, `whoami`, `logout`, `status`, `rangliste`, `fristen`, `watch`,
`annehmen`, `absagen`, `config`, `version`.

## Ausgabe

- Standardausgabe (stdout): Daten und Ergebnis. Im Terminal lesbar, mit Namen
  statt nur IDs.
- Fehlerausgabe (stderr): Zusammenfassungen vor einer verbindlichen Aktion,
  Rückfragen wie `[j/N]`, Fehlermeldungen und Hinweise auf den nächsten Schritt.
- `--json`: genau ein JSON-Objekt auf stdout, auch im Fehlerfall
  (`{"ok": false, "error": {"code": N, "message": "..."}}`).
- Ohne `--json`, aber mit nicht-interaktivem stdout (Pipe/Agent), gibt das Tool
  ebenfalls genau ein JSON-Objekt aus. Ein echtes Terminal erhält lesbaren Text.
- Secrets (Passwort, Session-Cookie) erscheinen nie in stdout, stderr, JSON,
  State oder Fehlermeldungen.

## Befehle und Argumente

### `login`

```
hochschulstart login [--username NAME] [--password-file PFAD]
                     [--config PFAD] [--dry-run] [--json]
```

Baut die DoSV-Session auf. Fehlen Benutzername oder Passwort und ist stdin ein
Terminal, fragt die CLI `Benutzername:` und `Passwort:` (verdeckt per
`getpass`). Ohne TTY und ohne Zugangsdaten: Exit 2 mit Hinweis auf
`hochschulstart login` im Terminal. `--password-file` liest das Passwort aus
einer Datei; ein Passwort als argv-Flag gibt es nicht. Nach Erfolg:
`Login erfolgreich.` und `Session gespeichert …`. `--dry-run` zeigt nur den
geplanten Login-POST und sendet nichts.

### `whoami`

```
hochschulstart whoami [--json]
```

Zeigt den Benutzernamen und die Session-Quelle (`env`, `keyring`, `file`), nie
den Cookie. Ohne Session: Exit 2 mit Hinweis auf `hochschulstart login`.

### `logout`

```
hochschulstart logout [--json]
```

Entfernt Session aus keyring und Session-Datei. Idempotent: ohne vorhandene
Session ebenfalls Exit 0. Gibt keine Secrets aus.

### `status [SUCHBEGRIFF]`

```
hochschulstart status [SUCHBEGRIFF] [--status TEXT]
                      [--config PFAD] [--json]
```

Liest die Bewerbungsübersicht. Der optionale positionale Suchbegriff filtert
clientseitig, unabhängig von Groß-/Kleinschreibung, über Studiengang,
Hochschule und Bewerbungsnummer. `--status` filtert zusätzlich nach
Status-Teilstring. Terminalausgabe:

```
Bewerbungen (2):
1) Musterstudiengang – Musteruniversität – Zulassungsangebot (B-1001)
2) Synthetisches Fach – Beispielhochschule – Bewerbung eingegangen (B-1002)
```

JSON: `{"ok": true, "count": N, "applications": [...]}`.

### `rangliste [SUCHBEGRIFF]`

```
hochschulstart rangliste [SUCHBEGRIFF] [--bewerbung ID]
                         [--config PFAD] [--json]
```

Zeigt eigene Ranglisten-Positionen. Ohne Suchbegriff alle Einträge. Ein
positionaler Begriff wird wie bei `status` gegen die Bewerbungen aufgelöst und
filtert die Ranglisten-Einträge. `--bewerbung` bleibt als Filter nach
Bewerbungsnummer erhalten. JSON: `{"ok": true, "count": N, "ranglisten": [...]}`.

### `fristen`

```
hochschulstart fristen [--url URL] [--limit N] [--config PFAD] [--json]
```

Liest ausschließlich die öffentliche Terminseite (Default:
`HOCHSCHULSTART_PUBLIC_URL`). `--limit` begrenzt die Anzahl. Keine lokalen
Hochschulfristen.

### `watch`

```
hochschulstart watch [--state PFAD] [--config PFAD] [--dry-run] [--json]
```

Vergleicht Bewerbungsstatus und Ranglisten mit dem lokalen State. Schreibt nur
lokalen State; `--dry-run` schreibt nichts. Sendet keine Portal-Schreibaktion.

### `annehmen SUCHBEGRIFF`

```
hochschulstart annehmen SUCHBEGRIFF [--confirm | --yes]
                          [--config PFAD] [--dry-run] [--json]
```

`SUCHBEGRIFF` ist ein Studiengang, eine Hochschule oder eine Bewerbungsnummer.
Die CLI löst den Treffer gegen die Bewerbungsübersicht auf:

- kein Treffer: Exit 1 mit Liste der nächsten Schritte,
- mehrere Treffer im Terminal: nummerierte Auswahl,
- mehrere Treffer ohne TTY: Liste und Exit 1 (Usage).

Danach lädt sie Detail- und Bestätigungsseite (nichts Verbindliches), zeigt auf
**stderr**:

```
Bewerbung: B-1001
Studiengang: Musterstudiengang
Hochschule: Musteruniversität
Status: Zulassungsangebot
Annahme verbindlich? [j/N]
```

Default ist Nein. Erst `j`/`ja` sendet **alle** Formularschritte in Reihenfolge
bis zum letzten verbindlichen POST. Danach auf stdout:
`Angenommen: B-1001 (Musterstudiengang)`. `N` beendet ohne Request mit Exit 0
(bewusste Ablehnung). Ist der Status bereits terminal (angenommen, abgesagt,
abgelehnt, zurückgezogen) oder fehlt ein Zulassungsangebot, endet der Befehl
vor jedem Request mit Exit 1.

`--confirm`/`--yes` sind nur für Agenten: Sie überspringen die Rückfrage und
senden direkt. Ohne TTY und ohne `--confirm`/`--yes` bricht die CLI **vor jedem
Request** ab und nennt `--confirm` als nächsten Schritt. `--dry-run` zeigt den
geplanten Request samt Formularfeld-Namen, sendet nichts und schreibt keinen
State.

### `absagen SUCHBEGRIFF`

Wie `annehmen`, mit `/absagen` statt `/annehmen`, Rückfrage
`Absage verbindlich? [j/N]` und Erfolgszeile `Abgesagt: B-1002 (…)`.

### `config`, `version`

```
hochschulstart config [--config PFAD] [--json]
hochschulstart version [--json]
```

`config` zeigt die aufgelöste Konfiguration ohne Secrets (nur `*_set` und
Quellen). `version` zeigt die Paketversion.

## Flags

| Flag | Gültig bei | Bedeutung |
|------|------------|-----------|
| `--json` | allen Unterkommandos | genau ein JSON-Objekt auf stdout |
| `--dry-run` | `login`, `annehmen`, `absagen`, `watch` | nichts senden/schreiben, nur zeigen |
| `--confirm`, `--yes` | `annehmen`, `absagen` | ohne Rückfrage senden; nur für Agenten |
| `--username NAME` | `login` | Benutzername (sonst Env/Config/keyring/Terminal) |
| `--password-file PFAD` | `login` | Passwort aus Datei; kein Passwort in argv |
| `--status TEXT` | `status` | Filter nach Status-Teilstring |
| `--bewerbung ID` | `rangliste` | Kompatibilitätsfilter nach Bewerbungsnummer |
| `--url URL` | `fristen` | andere öffentliche Terminquelle |
| `--limit N` | `fristen` | maximale Anzahl Einträge |
| `--state PFAD` | `watch` | Pfad der Watch-State-Datei |
| `--config PFAD` | fast allen | Config-Datei statt Default |

Es gibt keine Pflicht-Option statt eines positionalen Namens.

## Exit-Codes

| Code | Bedeutung |
|------|-----------|
| 0 | Erfolg, auch bewusstes `N` bei der Rückfrage und idempotentes `logout` |
| 1 | Ungültige Eingabe, kein/mehrdeutiger Treffer, kein Zulassungsangebot, Abbruch ohne TTY und ohne `--confirm`, argparse-Usage |
| 2 | Authentifizierung: keine Session, falsche/fehlende Zugangsdaten, BundID/2FA/Captcha |
| 3 | Netzwerk oder Portal nicht erreichbar (auch Wartung) |
| 4 | Parse-Fehler (HTML, JSON, Config, State) |
| 130 | Abbruch durch Nutzer (Strg+C) oder EOF an einem Prompt |

## Umgebungsvariablen

| Variable | Zweck |
|----------|-------|
| `HOCHSCHULSTART_BASE_URL` | Portal-Basis (Default `https://dosv.hochschulstart.de`) |
| `HOCHSCHULSTART_PUBLIC_URL` | öffentliche Terminseite |
| `HOCHSCHULSTART_USERNAME` | DoSV-Benutzername |
| `HOCHSCHULSTART_PASSWORD` | DoSV-Passwort |
| `HOCHSCHULSTART_SESSION` | Session-Cookie direkt (CI/Tests) |
| `HOCHSCHULSTART_CONFIG` | Pfad zur Config-JSON |
| `HOCHSCHULSTART_CONFIG_DIR` | Verzeichnis für Config, Session und Watch-State |

Präzedenz für Zugangsdaten: env > Config-Datei > keyring. Die Session-Cookie
liegt getrennt: env > keyring > Datei.

## Pfade

| Inhalt | Default |
|--------|---------|
| Config | `$XDG_CONFIG_HOME/hochschulstart/config.json`, sonst `~/.config/hochschulstart/config.json` |
| Session | `<Config-Verzeichnis>/session.json` mit Rechten `0600` (oder keyring) |
| Watch-State | `<Config-Verzeichnis>/watch.json` |

`HOCHSCHULSTART_CONFIG_DIR` überschreibt das Config-Verzeichnis. Sessions und
Watch-State liegen nie im Repo oder im Arbeitsverzeichnis. Der Watch-State
enthält nur Bewerbungsnummern, Status und Rang, keine Credentials.

## Sicherheit und Grenzen

- `annehmen`/`absagen` senden nur nach `j` im TTY oder mit
  `--confirm`/`--yes`. Ohne TTY und ohne Flag: kein Request.
- `--dry-run` sendet nie, auch keine Zugangsdaten.
- Live werden ausschließlich lesende GET-Requests auf öffentliche Seiten
  geprüft; Tests laufen offline gegen das synthetische Fake-Portal.
- BundID, 2FA und Captcha werden erkannt und mit Exit 2 abgelehnt.
