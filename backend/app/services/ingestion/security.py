"""Guards against SSRF and other abuse of the "give me a URL and I'll clone
it" ingestion entry point.

A repository ingestion endpoint that accepts an arbitrary URL is a classic
server-side request forgery vector: without validation, a caller could ask
the server to "clone" `https://169.254.169.254/...` (cloud metadata service)
or an internal-only host and exfiltrate the response via clone failure
timing/errors. This module is the single choke point all ingestion paths
must go through before any network call is made.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.exceptions import UnprocessableIngestionError

_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable -- fail closed
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_source_url(source_url: str, *, allow_private_hosts: bool = False) -> str:
    """Validates a repository source URL. Returns the normalized URL or raises
    `UnprocessableIngestionError` with a caller-facing reason.

    `allow_private_hosts` exists only for local development/test fixtures
    (e.g. cloning a `file://` fixture repo in CI) and must never be reachable
    from a production request path.
    """
    settings = get_settings()
    parsed = urlparse(source_url)

    if parsed.scheme not in settings.ingestion_allowed_schemes:
        allowed = ", ".join(settings.ingestion_allowed_schemes)
        raise UnprocessableIngestionError(f"Unsupported URL scheme '{parsed.scheme}'. Allowed: {allowed}.")

    if not parsed.hostname:
        raise UnprocessableIngestionError("Source URL is missing a hostname.")

    if allow_private_hosts:
        return source_url

    hostname = parsed.hostname.lower()
    if hostname in _BLOCKED_HOSTNAMES:
        raise UnprocessableIngestionError(f"Host '{hostname}' is not allowed.")

    try:
        resolved_ips = {str(info[4][0]) for info in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as exc:
        raise UnprocessableIngestionError(f"Could not resolve host '{hostname}'.") from exc

    if any(_is_blocked_ip(ip) for ip in resolved_ips):
        raise UnprocessableIngestionError(
            f"Host '{hostname}' resolves to a private/internal address and is not allowed."
        )

    return source_url
