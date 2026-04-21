"""Shared URL/hostname validation to prevent SSRF across all route modules."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_BLOCKED_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
    "metadata.google.internal",
    "169.254.169.254",
})

_BLOCKED_SUFFIXES = (".internal", ".local", ".localhost")


def is_safe_url(url: str, *, require_https: bool = False) -> bool:
    """Return True if *url* targets a public host via http(s).

    Rejects:
      - Non-http(s) schemes (file://, ftp://, gopher://, etc.)
      - Known internal hostnames (localhost, metadata endpoints)
      - Private, loopback, link-local, and reserved IP addresses
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    allowed_schemes = ("https",) if require_https else ("http", "https")
    if parsed.scheme not in allowed_schemes:
        return False

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    if hostname in _BLOCKED_HOSTS:
        return False

    if any(hostname.endswith(suffix) for suffix in _BLOCKED_SUFFIXES):
        return False

    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False
    except ValueError:
        pass

    return True


def is_safe_domain(domain: str) -> bool:
    """Return True if *domain* is a valid public hostname (no IP literals or internal names)."""
    domain = domain.strip().lower()
    if not domain:
        return False

    if domain in _BLOCKED_HOSTS:
        return False

    if any(domain.endswith(suffix) for suffix in _BLOCKED_SUFFIXES):
        return False

    try:
        addr = ipaddress.ip_address(domain)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False
    except ValueError:
        pass

    return True
