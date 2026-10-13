---
name: cli-betriebstest
description: Betriebstest für CLI-Repos im Orchestator-Modus — Black-Box, offline zuerst, dann online read-only gegen die echte Zielseite; ein Agent pro Repo. Use when CLI testen, Betriebstest, offline/online testen, Orchestator-Run, "auf Herz und Nieren", oder gefundene Bugs als GitHub-Issues filen.
---

# CLI-Betriebstest (Orchestator)

## Wann

Wenn ein CLI-Repo (auch ein aus diesem Template abgeleitetes) "auf Herz und Nieren" getestet werden soll: Black-Box im Betrieb, kein Code-Audit. Ausführliches Playbook: `docs/TESTING.md`.

## Grundsätze

- **Betrieb vor Code.** CLI als echter Nutzer bedienen; Code nur zur Belegsuche (Datei:Zeile) nach einem reproduzierten Befund.
- **Erst offline, dann online** — online ist der relevantere Test. Leitfrage: "Kann das CLI online echte Dinge?" → Tabelle Fähigkeit | Ja/Teilweise/Nein | Beleg.
- **Read-only**: keine Logins abschließen, keine Zugangsdaten, nichts posten/senden/kaufen. Auth-Features nur bis zur öffentlichen Grenze testen.
- **Höflich**: ≤ ~30 echte Requests, sequenziell, keine Retries; Bot-Block ist ein Befund, nicht umgehen. Kontrollgruppe: sparsam curl auf dieselbe URL.
- **2× reproduzieren**; flaky → nur Report. Sandbox: frisches HOME/XDG/CWD per mktemp -d.

## Orchestator-Run

1. Pro Repo EINEN general-Subagenten in EINER Nachricht spawnen (parallel).
2. Jeder Agent: offline-Suite + adversariales Offline-Probing → Online-Runde → Dedupe → Issues → Report.
3. Issue-Policy: `gh issue list --state all` vorab; max 5 neue Issues; Label `bug`; deutscher Body (Umgebung/Schritte/Erwartet/Tatsächlich/Beleg/Repro-Rate); bestätigte Alt-Issues per `gh issue comment` ergänzen statt Duplikat.
4. Geplante, aber fehlende Features zählen als Bug — EIN Issue pro Lücke, auch wenn die Tests nur xfail-geparkt sind.
5. Abschluss: Fähigkeits-Tabelle, Issues mit URLs, nicht testbare Bereiche, Blocker. Worktree sauber lassen, nichts fixen.

## Verweise

- `docs/TESTING.md` — Playbook im Detail.
- `docs/QA-CHECKLIST.md` — Freigabe-Checkliste für abgeleitete CLIs.
