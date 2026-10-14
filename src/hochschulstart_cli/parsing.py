"""HTML-Parsing der öffentlichen/portal-eigenen Seiten (stdlib ``html.parser``).

Alle Parser sind bewusst tolerant gegenüber Layout-Details, aber streng
gegenüber fehlenden Kernstrukturen: ist die erwartete Tabelle/Formular nicht
erkennbar, gibt es einen Parse-Fehler (Exit 4) statt stiller Leerlisten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError

_DATE_RE = re.compile(r"^(\d{2}\.\d{2}\.\d{4}|tba\.?\d{0,4})$", re.IGNORECASE)
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS.sub(" ", unescape(text)).strip()


def _parse_error(message: str) -> CliError:
    return CliError(message, code=ec.PARSE)


@dataclass
class Table:
    rows: list[list[str]] = field(default_factory=list)
    has_header_row: bool = False


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.tables: list[Table] = []
        self.forms: list[dict] = []
        self._table: Table | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._form: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "table":
            self._table = Table()
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            if tag == "th":
                self._table.has_header_row = True
        elif tag in ("p", "br", "div", "li") and self._cell is not None:
            self._cell.append(" ")
        elif tag == "form":
            self._form = {
                "action": a.get("action", ""),
                "method": (a.get("method") or "get").lower(),
                "inputs": {},
                "hidden": {},
            }
        elif tag == "input" and self._form is not None:
            name = a.get("name")
            if name:
                self._form["inputs"][name] = a.get("value", "")
                if a.get("type", "").lower() == "hidden":
                    self._form["hidden"][name] = a.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_clean("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag == "form" and self._form is not None:
            self.forms.append(self._form)
            self._form = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _parse(html: str) -> _TableParser:
    parser = _TableParser()
    parser.feed(html)
    parser.close()
    return parser


def parse_tables(html: str) -> list[Table]:
    return _parse(html).tables


def _find_table(tables: list[Table], header_words: tuple[str, ...], *, min_cols: int = 2) -> Table | None:
    for table in tables:
        for row in table.rows[:2]:
            labels = " ".join(row).lower()
            if all(w in labels for w in header_words) and len(row) >= min_cols:
                return table
    return None


def _header_index(header: list[str], *names: str) -> int | None:
    for i, cell in enumerate(header):
        low = cell.lower()
        if any(n in low for n in names):
            return i
    return None


def parse_applications(html: str) -> list[dict[str, str]]:
    """Bewerbungsübersicht (Studiengang/Hochschule/Status) aus Tabellen lesen."""
    tables = parse_tables(html)
    table = _find_table(tables, ("studiengang", "status"), min_cols=1) or _find_table(
        tables, ("bewerbung", "status"), min_cols=1
    )
    if table is None:
        raise _parse_error("Bewerbungsübersicht nicht erkennbar (keine Tabelle mit Studiengang/Status)")
    header = table.rows[0]
    idx = {
        "id": _header_index(header, "bewerbungsnummer", "bewerbung", "id"),
        "program": _header_index(header, "studiengang", "studienangebot"),
        "university": _header_index(header, "hochschule"),
        "status": _header_index(header, "status"),
        "rang": _header_index(header, "rang"),
        "frist": _header_index(header, "frist"),
    }
    if idx["program"] is None or idx["status"] is None:
        raise _parse_error("Bewerbungsübersicht: Spalten Studiengang/Status fehlen")
    out: list[dict[str, str]] = []
    for row in table.rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        app: dict[str, str] = {}
        for key, i in idx.items():
            if i is not None and i < len(row) and row[i]:
                app[key] = row[i]
        if app.get("program") or app.get("id"):
            out.append(app)
    if not out:
        raise _parse_error("Bewerbungsübersicht: keine Bewerbungszeilen gefunden")
    return out


def parse_ranglisten(html: str) -> list[dict[str, str]]:
    """Ranglisten-Einträge (eigener Rang, Grenzrang, Quote) aus Tabellen lesen."""
    tables = parse_tables(html)
    table = _find_table(tables, ("rang",), min_cols=2) or _find_table(tables, ("grenzrang",), min_cols=2)
    if table is None:
        raise _parse_error("Rangliste nicht erkennbar (keine Tabelle mit Rang/Grenzrang)")
    header = table.rows[0]
    idx = {
        "bewerbung": _header_index(header, "bewerbung"),
        "quote": _header_index(header, "quote", "auswahl"),
        "rang": _header_index(header, "ihr rang", "eigener rang", "rang"),
        "grenzrang": _header_index(header, "grenzrang"),
        "wert": _header_index(header, "wert", "punkt"),
        "los": _header_index(header, "los"),
    }
    if idx["rang"] is None:
        raise _parse_error("Rangliste: Spalte 'Ihr Rang' fehlt")
    out: list[dict[str, str]] = []
    for row in table.rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        entry: dict[str, str] = {}
        for key, i in idx.items():
            if i is not None and i < len(row) and row[i]:
                entry[key] = row[i]
        if entry.get("rang") or entry.get("bewerbung"):
            out.append(entry)
    if not out:
        raise _parse_error("Rangliste: keine Einträge gefunden")
    return out


def parse_termine(html: str) -> list[dict[str, str]]:
    """Termin-/Fristentabelle(n): Datum (dd.mm.yyyy oder tba) + Beschreibung."""
    rows: list[list[str]] = []
    for table in parse_tables(html):
        rows.extend(table.rows)
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if len(row) < 2:
            continue
        date = row[0].strip()
        if not _DATE_RE.match(date):
            continue
        detail = row[1].strip()
        if not detail:
            continue
        title = detail.split(". ")[0] if ". " in detail[:160] else detail
        key = (date, detail)
        if key in seen:
            continue
        seen.add(key)
        out.append({"date": date, "title": title, "detail": detail})
    if not out:
        raise _parse_error("Terminübersicht nicht erkennbar (keine Datumszeilen gefunden)")
    return out


def unsupported_auth_method(html: str) -> str | None:
    """Captcha, 2FA oder BundID — nicht per Benutzername/Passwort automatisierbar."""
    text = _clean(re.sub(r"<[^>]+>", " ", html)).lower()
    blob = f"{text} {html.lower()}"
    if re.search(r"bund[\s-]?id", blob) or "bundesident" in blob:
        return "BundID"
    if any(
        token in blob
        for token in ("captcha", "recaptcha", "hcaptcha", "turnstile", "g-recaptcha", "h-captcha")
    ):
        return "Captcha"
    if (
        re.search(r"\b2fa\b", blob)
        or "zwei-faktor" in blob
        or "zweifaktor" in blob
        or "two-factor" in blob
        or "einmalpasswort" in blob
        or ("authenticator" in blob and "code" in blob)
    ):
        return "2FA"
    return None


def login_error_hint(html: str) -> str | None:
    """Bekannte Login-Fehlertexte aus der Portal-Antwort (ohne Credentials)."""
    text = _clean(re.sub(r"<[^>]+>", " ", html))
    low = text.lower()
    if "benutzername oder passwort" in low and "falsch" in low:
        return "Benutzername oder Passwort ist falsch"
    if "ungültig" in low and "passwort" in low:
        return "Zugangsdaten ungültig"
    if "konto" in low and "aktivier" in low:
        return "Konto ist noch nicht aktiviert"
    if "csrf" in low or "formular-token" in low or ("sicherheits" in low and "token" in low):
        return "Sitzung abgelaufen oder ungültiges Formular-Token — Login-Seite erneut laden"
    return None


def extract_form(html: str, *, action_contains: str | None = None) -> dict:
    """Formular (action, method, inputs) finden; optional per action-Teilstring."""
    forms = _parse(html).forms
    if not forms:
        raise _parse_error("kein Formular auf der Seite gefunden")
    if action_contains:
        for form in forms:
            if action_contains in form["action"]:
                return form
        raise _parse_error(f"Formular mit action~{action_contains!r} nicht gefunden")
    return forms[0]
