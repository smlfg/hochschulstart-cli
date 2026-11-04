# Anforderungen: hochschulstart-cli

Stand: 2026-11-04 (Schritt R2). Grundlage sind der TOOL-BRIEF, die bestehende
README, die Live-Erkundung in `scratch/live/NOTIZEN.md` und die UX-Spec in
`docs/UX.md`. Das Tool wird nachgerüstet; vorhandene Befehle, Exit-Codes und
Tests bleiben erhalten.

## Nachfrage

- Quelle Brief/README: Das bestehende Repo `smlfg/hochschulstart-cli` deckt
  Login, Bewerbungsstatus, Ranglisten, öffentliche Fristen und Watch bereits ab.
  Der Brief verlangt ausdrücklich eine Nachrüstung, keinen Neubau.
- Belegte Lücke im eigenen Tool (README + Quellcode): `annehmen`, `absagen` und
  `rangliste --bewerbung` verlangen Bewerbungsnummern; `status` hat keinen
  Suchbegriff; JSON erscheint nur mit `--json`; Bestätigung und `[j/N]` laufen
  über stdout; ein `logout`/`whoami` fehlt.
- Nutzen: Studienbewerberinnen und -bewerber bedienen das DoSV-Portal im
  Terminal mit Studiengang oder Hochschule statt mit internen Nummern. Annahme
  und Absage bleiben verbindlich und werden nur nach ausdrücklicher Bestätigung
  gesendet.
- Datum der Prüfung: 2026-11-04. Eine neue externe Nachfrageerhebung war für
  diese Nachrüstung nicht Teil des Auftrags; die Quelle ist Brief/README.

## Ziel

`hochschulstart` soll die drei wichtigsten Aufgaben im Terminal sicher und
abtippbar erledigen:

1. Installation und Login: `pipx install …`, danach `hochschulstart login` mit
   verdeckter Passworteingabe und Session-Ablage mit Rechten 0600.
2. Bewerbungen ansehen: `hochschulstart status` zeigt Bewerbungsnummer,
   Studiengang, Hochschule und Status lesbar an; ein optionaler Suchbegriff
   filtert nach Studiengang oder Hochschule.
3. Zulassung annehmen: `hochschulstart annehmen "Musterstudiengang"` zeigt eine
   Zusammenfassung, fragt im Terminal `Annahme verbindlich? [j/N]` und sendet
   erst bei `j` alle Formularschritte bis zur verbindlichen Bestätigung.

## Muss-Anforderungen

- **M1 Positionale Suche.** `status [SUCHBEGRIFF]` filtert clientseitig,
  unabhängig von Groß-/Kleinschreibung, über Studiengang und Hochschule.
  `annehmen`/`absagen` lösen einen Studiengang oder eine Hochschule positional
  auf; eine Bewerbungsnummer bleibt als Eingabe zulässig.
- **M2 Rangliste.** `rangliste [SUCHBEGRIFF]` filtert über den zugeordneten
  Studiengang/die Hochschule; `--bewerbung` bleibt als Kompatibilitätsflag
  erhalten.
- **M3 Lesbare Ausgabe.** Im Terminal erscheinen lesbare Zeilen mit Namen,
  Hochschule und Status. `--json` oder ein nicht-interaktives stdout (Pipe,
  Agent) liefern genau ein JSON-Objekt.
- **M4 Verbindliche Aktion.** `annehmen`/`absagen` zeigen die Zusammenfassung
  und `[j/N]` auf stderr. Default ist Nein. Erst `j`/`ja` sendet alle
  Formularschritte in Reihenfolge bis zum letzten verbindlichen POST. `N`
  beendet ohne Request.
- **M5 Agentenpfad.** `--confirm`/`--yes` sind nur für nicht-interaktive
  Agenten gedacht und überspringen die Rückfrage. Ohne TTY und ohne Flag bricht
  das Tool vor jedem Request ab und nennt den nächsten Schritt.
- **M6 Login-Sicherheit.** `login` fragt Benutzername und Passwort interaktiv
  (Passwort per `getpass`), unterstützt Env/Config/keyring und speichert die
  Session im Schlüsselbund oder in einer Datei mit Rechten 0600. Passwörter und
  Cookies erscheinen nie in Ausgaben, Logs, State oder Fehlermeldungen.
- **M7 Session-Befehle.** `whoami` zeigt Benutzername und Session-Quelle ohne
  Cookie; `logout` entfernt die Session idempotent und ist ohne Session
  erfolgreich.
- **M8 Dry-Run und Watch.** `--dry-run` sendet nichts und schreibt keinen State.
  `watch` schreibt ausschließlich lokalen State.
- **M9 Fehler und Exit-Codes.** Bestehende Codes 0, 1, 2, 3, 4, 130 bleiben.
  Fehler nennen den nächsten Schritt; keine Tracebacks, auch nicht bei Strg+C
  oder EOF.
- **M10 Basis-URL testbar.** `HOCHSCHULSTART_BASE_URL` überschreibt die
  Portal-Basis, `HOCHSCHULSTART_PUBLIC_URL` die öffentliche Terminseite. Damit
  laufen Tests und Akzeptanztests gegen den Fake-Server.

## Nicht-Ziele

- Kein BundID-, 2FA- oder Captcha-Flow; solche Seiten werden erkannt und mit
  Exit 2 abgelehnt.
- Keine lokalen Hochschulfristen; `fristen` liest weiterhin nur die öffentliche
  Terminseite.
- Keine echten Schreibaktionen in Tests oder Live-Erkundungen; live nur lesende
  GET-Requests auf öffentliche Seiten.
- Keine Änderungen am UX-Gate in `tests/harness/` und keine neuen Workflows.

## Abnahmekriterien

- `docs/UX.md` bleibt gültig; `python tests/harness/ux_check.py . --spec-only`
  endet mit Exit 0.
- Für jede der drei UX-Sitzungen existiert mindestens ein Akzeptanztest in
  `tests/acceptance/` gegen `tests/harness/fake_server.py`.
- Der README-Schnellstart enthält wörtlich die `$`-Befehle der UX-Sitzungen,
  ohne Kommentarzeilen und ohne Alternativen.
- `INTERFACE.md` nennt Befehle, Flags, Ausgabeformat, Exit-Codes, Env und
  Session-Pfad.
- Die bestehenden Tests bleiben erhalten; neue Tests dürfen bis zum Bau
  (Schritt 4) rot sein.
