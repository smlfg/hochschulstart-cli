# UX-Spec: hochschulstart-cli

`hochschulstart` ist die Kommandozeile für das DoSV-Bewerbungsportal von
hochschulstart.de. Sie baut eine Session auf, zeigt Bewerbungen und Ranglisten,
liest öffentliche Fristen und beobachtet Statusänderungen lokal. Annahme und
Absage sind verbindlich und werden erst nach einer ausdrücklichen Bestätigung
gesendet.

Die Live-Erkundung vom 2026-11-04 ist in `scratch/live/NOTIZEN.md` festgehalten.
Öffentliche Seiten wurden lesend per GET geprüft; Login- und Kontoseiten sind
synthetisch, weil kein Testkonto verwendet wurde. Schreibende Schritte hinter
der Login-Schranke sind deshalb als `synthetisch` markiert.

## Meta

Das Meta-Objekt benennt den Befehlsnamen im PATH, den Installationsbefehl und die
Umgebungsvariablen. `HOCHSCHULSTART_BASE_URL` überschreibt die Portal-Basis,
`HOCHSCHULSTART_PUBLIC_URL` die öffentliche Terminseite. Für den Fake-Server im
Gate zeigt `HOCHSCHULSTART_PUBLIC_URL` auf den relativen Pfad `/termine`; im
echten Betrieb bleibt der Default die öffentliche Terminseite.

```ux-meta
{"tool": "hochschulstart",
 "install": "pipx install git+https://github.com/smlfg/hochschulstart-cli",
 "base_url_env": "HOCHSCHULSTART_BASE_URL",
 "env": {"HOCHSCHULSTART_PUBLIC_URL": "/termine",
         "HOCHSCHULSTART_SESSION": "SYNTH-SESSION-0001"},
 "credential_env": ["HOCHSCHULSTART_USERNAME", "HOCHSCHULSTART_PASSWORD", "HOCHSCHULSTART_SESSION"]}
```

## Sitzungen

### Installation und Login

Der Login fragt im Terminal nach DoSV-Benutzername und Passwort. Das Passwort
wird nicht angezeigt und nicht in argv oder Logs geschrieben. Die Session landet
im Schlüsselbund oder in einer Datei mit Rechten 0600. Ist kein Schlüsselbund
verfügbar, nennt die CLI den Dateipfad; die Zugangsdaten selbst werden nicht
ausgegeben.

```ux-session
$ pipx install git+https://github.com/smlfg/hochschulstart-cli
$ hochschulstart login
< Benutzername:
> testuser
< Passwort:
> geheim
< Login erfolgreich.
< Session gespeichert (Datei mit Rechten 0600).
! exit 0
```

### Bewerbungen ansehen

`status` zeigt alle Bewerbungen mit Bewerbungsnummer, Studiengang, Hochschule und
Status. Ein optionaler positionaler Suchbegriff filtert clientseitig nach
Studiengang oder Hochschule. Die Ausgabe ist für Menschen lesbar; `--json` oder
ein nicht-interaktives stdout liefern genau ein JSON-Objekt.

```ux-session
$ hochschulstart status
< Bewerbungen (2):
< 1) Musterstudiengang – Musteruniversität – Zulassungsangebot (B-1001)
< 2) Synthetisches Fach – Beispielhochschule – Bewerbung eingegangen (B-1002)
! exit 0
```

### Zulassungsangebot verbindlich annehmen

`annehmen` nimmt einen Studiengang oder eine Hochschule als positionalen
Suchbegriff. Die CLI löst den Treffer auf, zeigt Bewerbung, Studiengang,
Hochschule und Status und fragt danach mit Default Nein. Erst nach `j` wird
genau der eine verbindliche Request gesendet. Bei `N` endet der Befehl ohne
schreibenden Request. Ohne TTY und ohne `--confirm`/`--yes` bricht die CLI vor
jedem Request ab; `--confirm` ist nur für Agenten gedacht.

```ux-session
$ hochschulstart annehmen "Musterstudiengang"
< Bewerbung: B-1001
< Studiengang: Musterstudiengang
< Hochschule: Musteruniversität
< Status: Zulassungsangebot
< Annahme verbindlich? [j/N]
> j
< Angenommen: B-1001 (Musterstudiengang)
! exit 0
```

## Lesende Routen

Die Leserouten decken Login, Bewerbungsübersicht, Ranglisten und die öffentliche
Terminseite ab. Der Login ist ein POST, löst aber keine Bewerbungsaktion aus und
zählt deshalb zu den lesenden Routen. Die Login-Seite ist synthetisch; die
action `/bewerber/2376` entspricht dem live beobachteten Muster einer
session-spezifischen numerischen Formular-action. Die öffentliche Terminseite
wurde live gelesen und gekürzt übernommen.

```ux-routes
[{"method":"GET","path":"/bewerber","response":"tests/fixtures/ux/login_synthetisch.html","status":200,"content_type":"text/html; charset=utf-8"},
 {"method":"POST","path":"/bewerber/2376","response":"tests/fixtures/ux/login_erfolg.html","status":200,"content_type":"text/html; charset=utf-8"},
 {"method":"GET","path":"/bewerber/bewerbungen","response":"tests/fixtures/ux/bewerbungen.html","status":200,"content_type":"text/html; charset=utf-8"},
 {"method":"GET","path":"/bewerber/ranglisten","response":"tests/fixtures/ux/ranglisten.html","status":200,"content_type":"text/html; charset=utf-8"},
 {"method":"GET","path":"/termine","response":"tests/fixtures/ux/termine.html","status":200,"content_type":"text/html; charset=utf-8"}]
```

## Formularschritte der schreibenden Aktion

Die Liste enthält alle Requests der Aktion `annehmen` in Reihenfolge. Detailseite
und Bestätigungsformular werden vor der `[j/N]`-Frage geladen, damit die
Zusammenfassung vollständig ist; sie lösen nichts Verbindliches aus und tragen
deshalb `before_confirm: true`. Der letzte Schritt ist der eine verbindliche
POST und trägt `final: true`. Alle Schritte sind synthetisch, weil die
Bestätigungsseite live nur hinter der Login-Schranke erreichbar ist.

`absagen` verwendet denselben Ablauf mit `/absagen` statt `/annehmen`; die
UX-Sitzung zeigt exemplarisch `annehmen`.

```ux-formsteps
[{"id":"bewerbung_detail","method":"GET","path":"/bewerber/bewerbungen/B-1001","sends":[],"response":"tests/fixtures/ux/bewerbung_detail.html","before_confirm":true,"live":"synthetisch"},
 {"id":"annahme_bestaetigung","method":"GET","path":"/bewerber/bewerbungen/B-1001/annehmen","sends":[],"response":"tests/fixtures/ux/annehmen_bestaetigung.html","before_confirm":true,"live":"synthetisch"},
 {"id":"annahme_verbindlich","method":"POST","path":"/bewerber/bewerbungen/B-1001/annehmen","sends":["tx_bewerbung_token","__referrer","confirmed"],"response":"tests/fixtures/ux/annahme_erfolg.html","final":true,"live":"synthetisch"}]
```

Der verbindliche Schritt sendet das Formular-Token und die Bestätigungsfelder
der vorherigen Seite. Fehlt ein Schritt oder endet die Aktion nach dem ersten
Request, meldet `ux_check.py` UX08 und `ux_session.py` bricht den Lauf ab.
