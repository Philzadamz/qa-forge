"""SSRF guard for server-side fetches of user-supplied URLs (PRD §12 "SSRF allowlist").

Rejects any URL whose host resolves to a loopback, private, link-local (incl. cloud metadata
169.254.169.254), reserved, multicast, or unspecified address. Redirects are not followed by
callers, so a public host can't bounce the fetch into the internal network. A DNS-rebinding
race between this check and the actual connect remains possible; docs/decisions/009 records
that trade-off.
"""

import ipaddress
import socket
from collections.abc import Iterable
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


_BLOCKED_NETWORK_FLAGS = (
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_reserved",
    "is_multicast",
    "is_unspecified",
)


def assert_public_http_url(url: str, *, allowed_hosts: Iterable[str] = ()) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("URL must use http or https")
    if not parsed.hostname:
        raise UnsafeUrlError("URL has no host")
    if parsed.hostname.lower() in {h.lower() for h in allowed_hosts}:
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Could not resolve host {parsed.hostname!r}") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if any(getattr(address, flag) for flag in _BLOCKED_NETWORK_FLAGS):
            raise UnsafeUrlError(f"Host {parsed.hostname!r} resolves to a non-public address")
