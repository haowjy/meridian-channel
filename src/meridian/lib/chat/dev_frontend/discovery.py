"""Discovery helpers for ``meridian chat --dev`` frontend launchers."""

from __future__ import annotations

import json
import shutil
import subprocess


def is_portless_available() -> bool:
    """Return whether the ``portless`` executable is available on ``PATH``."""

    return shutil.which("portless") is not None


def detect_tailscale_dns_name() -> str | None:
    """Return this node's Tailscale MagicDNS name, if it can be detected."""

    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        dns_name = data.get("Self", {}).get("DNSName")
        if not isinstance(dns_name, str) or not dns_name:
            return None
        return dns_name.rstrip(".")
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        return None
