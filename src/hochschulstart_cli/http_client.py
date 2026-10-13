"""HTTP-Client für das DoSV-Bewerbungsportal (stdlib, keine Runtime-Dependencies).

Sicherheit: Cookie-/Passwortwerte erscheinen nie in Fehlermeldungen.
Höflich: eigener User-Agent, kleiner Mindestabstand zwischen Requests.
"""

from __future__ import annotations

import http.cookies
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from hochschulstart_cli import exit_codes as ec
from hochschulstart_cli.errors import CliError

UA = "hochschulstart-cli/0.1.0 (+https://github.com/smlfg; kontakt: lokal, read-only Nutzung)"

_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    "Cache-Control": "no-cache",
}

SESSION_COOKIE_NAME = "JSESSIONID"


@dataclass
class HttpResponse:
    status: int
    url: str
    text: str
    headers: dict[str, str] = field(default_factory=dict)


class PortalClient:
    """Dünner HTTP-Client; hält optional eine Session-Cookie im Speicher."""

    def __init__(
        self,
        base_url: str,
        *,
        session_cookie: str | None = None,
        timeout: float = 20.0,
        polite_delay: float = 0.3,
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise CliError(f"base_url must be http(s): {base_url!r}", code=ec.INPUT)
        self.base_url = base_url.rstrip("/")
        self.session_cookie = session_cookie
        self.timeout = timeout
        self.polite_delay = polite_delay
        self._last_request = 0.0

    def _tick(self) -> None:
        if self.polite_delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.polite_delay:
            time.sleep(self.polite_delay - elapsed)

    def _request(self, method: str, path: str, *, data: bytes | None = None) -> HttpResponse:
        from hochschulstart_cli.url_util import join_preserve_base_path

        url = path if path.startswith(("http://", "https://")) else join_preserve_base_path(self.base_url, path)
        headers = dict(_HEADERS)
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if self.session_cookie:
            headers["Cookie"] = f"{SESSION_COOKIE_NAME}={self.session_cookie}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        self._tick()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                status = resp.status
                final_url = resp.geturl()
                resp_headers = {k: v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as e:  # 4xx/5xx: Antwort trotzdem auswerten
            body = e.read() if e.fp else b""
            status = e.code
            final_url = e.geturl() if hasattr(e, "geturl") else url
            resp_headers = {k: v for k, v in (e.headers or {}).items()}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise CliError(f"Netzwerkfehler für {url}: {reason}", code=ec.NETWORK) from None
        self._last_request = time.monotonic()

        self._capture_cookie(resp_headers.get("Set-Cookie", ""))

        text = body.decode("utf-8", errors="replace")
        if final_url != url and "wartung" in urllib.parse.urlsplit(final_url).netloc.lower():
            raise CliError(
                "Das DoSV-Bewerbungsportal ist derzeit nicht erreichbar (Wartung).",
                code=ec.NETWORK,
                details={"final_url": final_url},
            )
        return HttpResponse(status=status, url=final_url, text=text, headers=resp_headers)

    def _capture_cookie(self, set_cookie: str) -> None:
        if not set_cookie:
            return
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(set_cookie)
        except http.cookies.CookieError:
            return
        morsel = jar.get(SESSION_COOKIE_NAME)
        if morsel and morsel.value:
            self.session_cookie = morsel.value

    def get(self, path: str) -> HttpResponse:
        return self._request("GET", path)

    def post_form(self, path: str, fields: dict[str, str]) -> HttpResponse:
        body = urllib.parse.urlencode(fields).encode("utf-8")
        return self._request("POST", path, data=body)

    def stop(self) -> None:
        """Hook für Tests; urllib hält keine Verbindungen offen."""
