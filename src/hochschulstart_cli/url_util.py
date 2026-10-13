"""URL joining that keeps a configured API path prefix on ``base_url``."""

from __future__ import annotations


def join_preserve_base_path(base_url: str, *parts: str) -> str:
    """
    Join ``parts`` onto ``base_url`` without dropping non-root path segments.

    ``urllib.parse.urljoin("https://api.example.com/v1/", "users")``
    yields ``https://api.example.com/users`` (prefix lost). This helper
    preserves ``/v1`` when appending relative paths.
    """
    base = base_url.rstrip("/")
    suffix = "/".join(p.strip("/") for p in parts if p)
    if not suffix:
        return base
    return f"{base}/{suffix}"
