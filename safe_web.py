"""Validation and bounded redirects for user-supplied website scans.

DNS preflight is defense in depth, not DNS pinning; public deployments
should also restrict outbound network access to public addresses.
"""
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlsplit

import requests

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_REDIRECTS = {301, 302, 303, 307, 308}


def normalize_domain(value):
    """Accept a public-style DNS hostname or HTTP(S) website URL."""
    raw = str(value).strip()
    if not raw or any(c.isspace() or ord(c) < 32 for c in raw) or "\\" in raw:
        raise ValueError("Enter a valid public website domain.")
    parsed = urlsplit(raw if "://" in raw else "https://" + raw)
    if parsed.scheme not in ("http", "https") or parsed.username is not None or parsed.password is not None:
        raise ValueError("Only HTTP(S) websites without credentials are supported.")
    if parsed.port is not None and parsed.port != (443 if parsed.scheme == "https" else 80):
        raise ValueError("Only standard web ports are supported.")
    host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
    labels = host.split(".")
    if (len(host) > 253 or len(labels) < 2 or not all(_LABEL.fullmatch(label) for label in labels)
            or not any(c.isalpha() for c in labels[-1])
            or labels[-1] in {"local", "localhost", "internal", "invalid", "test", "onion", "lan", "home", "arpa"}):
        raise ValueError("Enter a public DNS hostname, not a local address or IP.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise ValueError("IP addresses are not supported.")


def validate_public_url(url):
    host = normalize_domain(url)
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Unsupported redirect scheme.")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                       type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("Website DNS lookup failed.") from exc
    if not addresses:
        raise ValueError("Website DNS lookup returned no addresses.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise ValueError("Website resolves to a non-public address.")
    return host


def safe_request(url, *, headers, timeout, use_head=False, max_redirects=4):
    """Check each redirect before issuing the next request."""
    with requests.Session() as session:
        session.trust_env = False
        for _ in range(max_redirects + 1):
            validate_public_url(url)
            response = session.request("HEAD" if use_head else "GET", url,
                                       headers=headers, timeout=timeout, allow_redirects=False)
            if response.status_code not in _REDIRECTS or not response.headers.get("Location"):
                return response
            url = urljoin(response.url, response.headers["Location"])
            response.close()
    raise ValueError("Website exceeded the redirect limit.")
