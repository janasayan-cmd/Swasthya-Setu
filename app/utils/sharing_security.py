"""Security and Destination Validation Utilities for Clinical Data Sharing (Phase 44).

Protects against:
- SSRF (Server-Side Request Forgery)
- Untrusted destination URLs
- Internal network enumeration
- Scheme tampering (HTTP vs HTTPS)
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import SharingDestinationInvalidException


BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",  # AWS/GCP/Azure link-local metadata
    "instance-data",
}


def is_ip_address(host: str) -> bool:
    """Check if the given host string is an IP address."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def is_private_or_restricted_ip(ip_str: str) -> bool:
    """Check if IP address falls in private, loopback, link-local, or reserved ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


def get_allowed_destinations() -> List[str]:
    """Retrieve configured destination allowlist from settings."""
    raw = getattr(settings, "SHARING_ALLOWED_DESTINATIONS", "")
    if not raw:
        return []
    return [dest.strip().rstrip("/").lower() for dest in raw.split(",") if dest.strip()]


def validate_destination_url(
    url: Optional[str],
    allowed_list: Optional[List[str]] = None,
    allow_empty: bool = True,
) -> bool:
    """Validate external destination URL for SSRF vulnerabilities and allowlist compliance.

    Raises:
        SharingDestinationInvalidException: If URL is invalid, targets internal IP, or not in allowlist.
    """
    if not url:
        if allow_empty:
            return True
        raise SharingDestinationInvalidException("Destination URL is required for external sharing.")

    try:
        parsed = urlparse(url.strip())
    except Exception as exc:
        raise SharingDestinationInvalidException(f"Malformed destination URL: {exc}")

    # Enforce safe scheme
    if parsed.scheme.lower() not in ("http", "https"):
        raise SharingDestinationInvalidException(
            f"Unsupported URL scheme '{parsed.scheme}'. Only HTTPS or HTTP are permitted."
        )

    # In production, require HTTPS
    if getattr(settings, "is_production", False) and parsed.scheme.lower() != "https":
        raise SharingDestinationInvalidException("External destinations must use HTTPS in production.")

    host = (parsed.hostname or "").lower()
    if not host:
        raise SharingDestinationInvalidException("Destination URL must specify a valid hostname.")

    # Check blocked hostnames
    if host in BLOCKED_HOSTNAMES:
        raise SharingDestinationInvalidException(
            f"Destination host '{host}' is strictly prohibited (loopback or cloud metadata)."
        )

    # Check for direct IP submission
    if is_ip_address(host):
        if is_private_or_restricted_ip(host):
            raise SharingDestinationInvalidException(
                f"Destination IP '{host}' belongs to a private or restricted network range."
            )

    # Validate against configured allowlist if configured
    configured_allowlist = allowed_list if allowed_list is not None else get_allowed_destinations()
    if configured_allowlist:
        clean_url = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}".rstrip("/")
        matched = any(clean_url.startswith(allowed_dest) for allowed_dest in configured_allowlist)
        if not matched:
            raise SharingDestinationInvalidException(
                f"Destination '{clean_url}' is not in the approved external destinations allowlist."
            )

    return True
