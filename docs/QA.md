# Pflicht-QA (Schritt 6)

Datum: 2026-11-05
Version: 0.1.0
Commit: `5116b40` (QA-Baseline; Nachprüfung bis `f6e5796`, Arbeitsbaum sauber)
Prüfer: unabhängige QA-Iteration (find -> file, keine Code-Fixes)

## Umgebung

- Frische Installation durch den Orchestrator:
  `pipx install git+https://github.com/smlfg/hochschulstart-cli@master`
  in `./scratch/pipx` (Protokoll: `scratch/qa/pipx-install.log`).
- Alle Aufrufe über `PATH=$PWD/scratch/pipx/bin:$PATH`, nie aus `scratch/venv`.
- Pseudo-Terminal: `script -q -e -c "<befehl>" <log>`; interaktive
  Login-Prompts zusätzlich mit dem PTY-Harness (`tests/harness/ux_session.py`).
  Die `script`-Läufe wurden mit verzögerten Eingaben gefahren, damit `getpass`
  die Passworteingabe sicher erhält.
- Offline-Portale: `tests/harness/fake_server.py` mit `ux-routes` aus
  `docs/UX.md`; für den vollständigen Login->Status->Aktion-Lauf zusätzlich
  `tests/fake_portal.py` (setzt wie das echte Portal ein Session-Cookie).
- Live: ausschließlich lesende GET-Requests auf öffentliche Seiten bzw. auf
  `dosv.hochschulstart.de/...` mit synthetischer Session. Kein echtes Konto,
  kein echter Login-POST, keine verbindliche Aktion.
- Isolation: frisches `HOME`/`XDG_CONFIG_HOME`/`HOCHSCHULSTART_CONFIG_DIR` je
  Lauf unter `scratch/tmp`, `TMPDIR` unter `scratch/tmp`.

## Ergebnis

**64 von 64 Prüfungen OK (nach Nachprüfung S6; zuvor 59/64, 5 FAIL).**

| Prüfung | Befehl | Erwartet | Ergebnis | Beleg (gekürzt) |
|---|---|---|---|---|
| Frische pipx-Installation | `pipx install git+…@master` | Paket + App im PATH | OK | `installed package hochschulstart 0.1.0`, `These apps are now available: hochschulstart` |
| Version über PATH | `hochschulstart --version` | `0.1.0`, Exit 0 | OK | `0.1.0`, Exit 0 |
| Top-Level-Hilfe | `hochschulstart --help` | Exit 0, verständlich | OK | Usage + alle 11 Unterkommandos, Exit 0 |
| Hilfe je Unterkommando | `hochschulstart <cmd> --help` | Exit 0 | OK | 11/11 Unterkommandos Exit 0 |
| App-Auflösung | `which hochschulstart` | Pfad unter `scratch/pipx/bin` | OK | `scratch/pipx/bin/hochschulstart` |
| Login-Prompts | `hochschulstart login` (PTY) | `Benutzername:`/`Passwort:` | OK | beide Prompts, danach `Login erfolgreich.` |
| Passwort nicht sichtbar | Login mit `testpass` (PTY) | kein Passwort-Echo/Leak | OK | Passwortzeile leer, `testpass` in keiner Ausgabe |
| Session-Rechte | Login (PTY) | Datei 0600 oder Keyring | OK | `session.json`, Modus `0o600`, Cookie nur intern |
| Login Strg+D | `login`, dann `^D` | Exit 130, kein Traceback | OK | `interrupted`, Exit 130 |
| Login falsche Daten | `login` mit `testuser`/`wrongpass` (PTY) | Exit 2, nächster Schritt | OK | `Login fehlgeschlagen: Zugangsdaten prüfen (Benutzername oder Passwort ist falsch)` |
| Login ohne TTY | `login` ohne Creds/Flag | Exit 2, nächster Schritt | OK | `Zugangsdaten fehlen … 'hochschulstart login' im Terminal ausführen` |
| Login `--dry-run` | `login --dry-run` | kein Request | OK | `sent: false`, nur POST-Plan |
| Captcha/2FA/BundID | `login` mit Auth-Wand | Exit 2, kein POST | OK | 3/3 `nicht unterstütztes Auth-Verfahren erkannt (…), posts=0` |
| Keyring-Rückfrage | `login` mit keyring-Extra | `[J/n]` auf stderr | OK | `Passwort im Schlüsselbund speichern? [J/n]` im stderr-Log |
| Keyring-Hinweis | `login` aus frischer pipx-Installation | Hinweis auf optionalen Keyring | OK (nach Fix 408bb55) | `Hinweis: Optionaler Schlüsselbund per 'pipx inject hochschulstart keyring' …` |
| Kompletter Quickstart | Login -> `status` -> `annehmen` (fake_portal, PTY) | Session, lesbarer Status, Aktion | OK | Login 0600, 2 Bewerbungen, Annahme mit `j` |
| Status lesbar | `status` (TTY) | Text, Namen statt IDs | OK | `Bewerbungen (2):`, Studiengang/Hochschule/Status/Nummer |
| Status Suchbegriff | `status Musterstudiengang` | genau 1 Treffer | OK | `Bewerbungen (1): … B-1001` |
| Status Hochschule/Umlaut | `status Musteruniversität` | Treffer | OK | `Bewerbungen (1): … B-1001` |
| Status Umlaut-Umschrift | `status Musteruniversitaet`/`Koeln`/`oekologie` | Treffer wie mit Umlaut | OK (nach Fix 869e7bc) | jeweils 1 Treffer (B-1001 bzw. B-1003) |
| `--status`-Filter | `status --status zulassung` (6 Testzeilen) | jeder Treffer passt | OK | 2/2 Treffer mit Status `Zulassungsangebot`, keine Fremdtreffer |
| Leeres Suchergebnis | `status Nichtsda` | Exit 0, `0` Treffer | OK | `Bewerbungen (0):` |
| Status `--json` | `status --json` | genau ein valides Objekt | OK | `{"ok": true, "count": 2, …}` |
| JSON bei stdout-Pipe | `script -c "hochschulstart status"` mit stdout in einer Pipe | JSON, weil stdout kein TTY | OK (nach Fix b52ad79) | genau ein JSON-Objekt (`ok=true`, `count=6`) |
| Status ohne Session | `status` ohne Session | Exit 2, `login` nennen | OK | `keine aktive Session: zuerst 'hochschulstart login' ausführen` |
| Kaputte Session-Datei | `status` mit `{not json` | Exit 4, kein Traceback | OK | `ungültige Session-Datei …`, Exit 4 |
| Rangliste | `rangliste` | lesbare Einträge | OK | `Ranglisten (2):`, Rang/Grenzrang |
| Rangliste Suche | `rangliste Musterstudiengang` | genau 1 Treffer | OK | `Ranglisten (1): … B-1001` |
| Rangliste `--bewerbung` | `rangliste --bewerbung B-1001` | genau 1 Treffer | OK | `Ranglisten (1): … B-1001` |
| Rangliste ohne Treffer | `rangliste Nichtsda` | Exit 1, nächster Schritt | OK | `keine Bewerbung zu 'Nichtsda' … 'hochschulstart status Nichtsda' zeigt die Treffer` |
| Watch schreibt State | `watch --state scratch/qa/watch-state.json` | State mit Status/Rang | OK | 2 Bewerbungen, keine Secrets |
| Watch zweiter Lauf | derselbe Befehl | keine Änderungen | OK | `changes:` leer |
| Watch `--dry-run` | `watch --dry-run` | kein State | OK | Datei nicht angelegt |
| Watch-State-Inhalt | State-Datei prüfen | nur Nummern/Status/Rang | OK | keine Cookies/Passwörter |
| Fristen offline | `fristen`, `fristen --limit 2` | Text + Limit | OK | `count: 5` bzw. `count: 2` |
| Fristen live | `fristen --json` | plausible öffentliche Termine | OK | 77 Einträge, Quelle `…/termine`, alle Datumsstrings im HTML |
| Fristen Limit live | `fristen --limit 5`/`--limit 10` | genau N Einträge | OK | `count: 5`/`count: 10` |
| Fristen `--json` | `fristen --json` | valides Objekt | OK | `ok=true`, `count=77` |
| Falsche Quell-URL | `HOCHSCHULSTART_PUBLIC_URL=http://127.0.0.1:1/termine fristen` | Exit 3, nächster Schritt | OK | `Netzwerkfehler … Verbindung prüfen und den Befehl erneut ausführen` |
| Ungültiges Limit | `fristen --limit 0` | Exit 1, Ablehnung | OK (nach Fix f6e5796) | `--limit muss positiv sein (erhielt 0) — 'hochschulstart --help' zeigt die gültigen Werte` |
| Live angemeldete Leser | `status`, `rangliste`, `watch --dry-run`, `annehmen/absagen --dry-run` mit synthetischer Session | Exit 2 mit Login-Hinweis statt Parse-Fehler | OK (nach Fix 680f67f) | 5/5 Exit 2, `Session ungültig/abgelaufen — 'hochschulstart login' ausführen` |
| Live-Login-Grenze | `login`, dann `^D` | Prompt, Exit 130 | OK | Prompt erscheint, `interrupted`, Exit 130 |
| Live-Login-Dry-Run | `login --dry-run` mit Dummy-Creds | kein Request | OK | `sent: false`, POST-Plan auf `/bewerber/login` |
| Annehmen-Zusammenfassung | `annehmen "Musterstudiengang"` (PTY, `N`) | Zusammenfassung + `[j/N]` auf stderr | OK | Bewerbung/Studiengang/Hochschule/Status + `Annahme verbindlich? [j/N]` im stderr-Log |
| Annehmen `N` | Antwort `N` | Exit 0, kein POST | OK | `Abgebrochen — nichts gesendet.`, Request-Log: nur GETs |
| Annehmen `j` | Antwort `j` | genau ein verbindlicher POST | OK | 1 POST mit `tx_bewerbung_token`, `__referrer`, `confirmed` |
| Annehmen `--confirm` | ohne TTY, `--confirm` | sendet direkt | OK | `{"ok": true, "sent": true, "result": "ok"}` + 1 POST |
| Annehmen `--yes` | ohne TTY, `--yes` | Alias sendet direkt | OK | gleiches Ergebnis wie `--confirm`, 1 POST |
| Annehmen ohne TTY/Flag | ohne TTY, ohne `--confirm` | Exit 1, kein Request | OK | `annehmen sendet nichts ohne Bestätigung … --confirm`, Request-Log leer |
| Annehmen `--dry-run` | gültiges Angebot | kein POST, Felder zeigen | OK | `sent: False`, `form_fields: [...confirmed, tx_bewerbung_token...]`, nur GETs |
| Annehmen ohne Angebot | `annehmen B-1002 --confirm` | Exit 1, kein POST | OK | `hat kein Zulassungsangebot (Status: Bewerbung eingegangen) — annehmen nicht möglich` |
| Annehmen mehrdeutig | `annehmen e` (PTY), Auswahl `1`, dann `N` | nummerierte Auswahl, kein POST | OK | Liste auf stderr, danach Zusammenfassung + `[j/N]`, kein POST |
| Absagen | `absagen B-1002` (PTY, `N`/`j`) | `[j/N]`, `N` ohne POST, `j` mit 1 POST | OK | `Absage verbindlich? [j/N]`, danach `Abgesagt: B-1002 …` |
| Strg+C am Prompt | `annehmen` (PTY), dann `^C` | Exit 130, kein Traceback | OK | `interrupted`, Exit 130 |
| Aktion ohne Session | `annehmen … --confirm` ohne Session | Exit 2, kein Request | OK | `keine aktive Session …`, Request-Log leer |
| Fehler nennen Schritt | Netz/Login/keine Session/kein Treffer | nächster Schritt genannt | OK | z. B. `Verbindung prüfen …`, `'hochschulstart login' ausführen` |
| Parse-/HTTP-Fehler | kaputtes HTML, HTTP 500 | nächster Schritt genannt | OK (nach Fix f6e5796) | `… Seite erneut laden; bleibt der Fehler, das Portal im Browser prüfen` bzw. `HTTP 500 — Befehl erneut ausführen …` |
| argparse-Usage | fehlende/ungültige Argumente | Exit 1, kein Traceback | OK | `annehmen`, `bogus`, `--limit abc` jeweils Exit 1 |
| JSON-Fehlervertrag | `--json` mit Fehler | genau ein Objekt | OK | 19/19 gesammelte JSON-Ausgaben valide, je ein Objekt |
| Keine Tracebacks | alle QA-Läufe | keine Tracebacks | OK | `grep -rl Traceback scratch/qa/*` leer |
| Keine Secrets | Logs/State/JSON | keine Passwörter/Cookies | OK | synthetische Creds nicht in Ausgaben; State ohne Cookie |
| Testsuite | `scratch/venv/bin/pytest -q` | grün | OK (nach Fix f6e5796) | `135 passed, 6 skipped` |
| README-Kommandos | README gegen `--help` | alle vorhanden | OK | 16 Befehlszeilen, keine fehlenden Unterkommandos |
| Exit-Codes | gesammelte Läufe | 0/1/2/3/4/130 wie dokumentiert | OK | Erfolg 0, Usage 1, Auth 2, Netz 3, Parse 4, Abbruch 130 |

## Nachprüfung S6 (2026-11-05)

Alle fünf FAILs sind im Code behoben und live erneut geprüft; es bleiben keine
offenen FAILs. Belege liegen unter `scratch/qa/s6-*.out`, `scratch/qa/s6-live-*`
und `scratch/qa/s6-recheck.out`.

1. **Session ungültig/abgelaufen -> Exit 2.** Der HTTP-Client erkennt eine
   vorhandene Session, die auf die Anmeldeseite umgeleitet wird oder in einer
   Redirect-Schleife endet, und meldet
   `Session ungültig/abgelaufen — 'hochschulstart login' ausführen`. Live mit
   synthetischer Session: `status`, `rangliste`, `watch --dry-run`,
   `annehmen --dry-run`, `absagen --dry-run` jeweils Exit 2 (`680f67f`).
2. **JSON bei stdout ohne TTY.** `auto_json` hängt nur noch an stdout; stdin darf
   ein TTY sein. `script -c "hochschulstart status | cat"` liefert ein
   JSON-Objekt (`b52ad79`).
3. **Umlaut-Umschrift.** Die Suche faltet Groß-/Kleinschreibung und
   `ä/ö/ü/ß` zu `ae/oe/ue/ss`; `Musteruniversitaet`, `Koeln` und `oekologie`
   liefern dieselben Treffer wie die Umlautform (`869e7bc`).
4. **Keyring-Hinweis.** Nach einem Login, der als Datei 0600 gespeichert wird und
   ohne installierten Keyring läuft, nennt die CLI
   `pipx inject hochschulstart keyring` (`408bb55`).
5. **Nächster Schritt bei Fehlern.** Parse-, HTTP- und Limit-Fehler nennen
   erneut versuchen, Portal im Browser prüfen bzw. `--help`; die Limit-Meldung
   ist deutsch (`f6e5796`).

## Nicht testbar / Grenzen

- Echter Login, echte Bewerbungsdaten und verbindliche Annahme/Absage sind ohne
  Testkonto nicht prüfbar. Live wurden nur öffentliche GETs und authentifizierte
  GETs mit synthetischer Session ausgeführt; Letztere enden erwartungsgemäß an
  der Login-Schranke (inzwischen Exit 2, siehe Nachprüfung S6). Kein POST an das echte Portal.
- Der UX-Fake (`tests/harness/fake_server.py`) setzt bei der Login-Route kein
  `Set-Cookie`; deshalb ist der vollständige Ablauf Login -> Status dort nur mit
  `HOCHSCHULSTART_SESSION` aus `ux-meta.env` möglich. Der vollständige
  Quickstart inklusive Session-Persistenz wurde gegen `tests/fake_portal.py`
  geprüft (dort setzt der Login ein Cookie).
- `fristen` liest nur die öffentliche Terminseite; lokale Hochschulfristen sind
  nicht Gegenstand dieses Tests.

## Beobachtungen ohne FAIL

- `fristen` wiederholt in `title` den Fließtext aus `detail` (teils lang); die
  Ausgabe ist dadurch weniger übersichtlich, aber inhaltlich korrekt.
- Im Nicht-TTY-Abbruch von `annehmen` lautet der Hinweis `'annehmen … --confirm'`
  ohne vorangestelltes `hochschulstart`; verständlich, aber inkonsistent zu
  anderen Fehlermeldungen.
