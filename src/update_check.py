"""Compare the local app version with GitHub main (webxed/IDvjPy).

HTTP и прокси-логин живут в общем сетевом слое `src/net.py` (там же их берёт
`:import <url>`); здесь — только логика сравнения версий и разбор `src/app.py`.
"""
from __future__ import annotations

import os
import re
import urllib.request
from collections.abc import Mapping

from net import format_fetch_error
from net import open_url as _open_url

GITHUB_REPO = "https://github.com/webxed/IDvjPy"
GITHUB_MAIN_APP_PY = (
    "https://raw.githubusercontent.com/webxed/IDvjPy/main/src/app.py"
)
RE_VERSION_ASSIGN = re.compile(
    r'^    VERSION = ["\'](v?\d+\.\d+(?:\.\d+)?)["\']',
    re.MULTILINE,
)
RE_VERSION_TOKEN = re.compile(r"v?(\d+)\.(\d+)(?:\.(\d+))?")

KIND_AVAILABLE = "available"
KIND_CURRENT = "current"
KIND_AHEAD = "ahead"











def format_update_fetch_error(exc: BaseException, environ: Mapping[str, str]) -> str:
    """Journal text for a failed GitHub fetch; hint if the proxy wants a login."""
    return format_fetch_error(exc, environ, subject="Could not check updates")




def parse_version_tuple(text: str) -> tuple[int, ...] | None:
    """Turn ``v1.24`` / ``1.24.0`` into a comparable tuple, or None."""
    match = RE_VERSION_TOKEN.search((text or "").strip())
    if not match:
        return None
    parts = [int(group) for group in match.groups() if group is not None]
    return tuple(parts)


def parse_version_from_source(source: str) -> str | None:
    """Read ``CommandRunner.VERSION`` from ``src/app.py`` text."""
    match = RE_VERSION_ASSIGN.search(source or "")
    if not match:
        return None
    return match.group(1)


def compare_versions(local: str, remote: str) -> int:
    """-1 if local < remote, 0 if equal, 1 if local > remote.

    Raises ValueError if either side is not a version.
    """
    left = parse_version_tuple(local)
    right = parse_version_tuple(remote)
    if left is None or right is None:
        raise ValueError(f"Cannot compare versions: {local!r} vs {remote!r}")
    if len(left) < len(right):
        left = left + (0,) * (len(right) - len(left))
    elif len(right) < len(left):
        right = right + (0,) * (len(left) - len(right))
    if left < right:
        return -1
    if left > right:
        return 1
    return 0


def format_update_status(local: str, remote: str) -> tuple[str, str]:
    """Human status and kind: available / current / ahead."""
    cmp = compare_versions(local, remote)
    if cmp < 0:
        return (
            f"Update available: {remote} (this is {local}). "
            f"git pull  {GITHUB_REPO}",
            KIND_AVAILABLE,
        )
    if cmp > 0:
        return (
            f"This is {local}; GitHub main is {remote} (local is ahead).",
            KIND_AHEAD,
        )
    return (f"Up to date ({local}).", KIND_CURRENT)


def fetch_remote_version(
    url: str = GITHUB_MAIN_APP_PY,
    timeout: float = 5.0,
    user_agent: str = "IDvjPy-term",
    environ: Mapping[str, str] | None = None,
) -> str:
    """Download ``src/app.py`` from GitHub main and return its VERSION.

    If ``PROXY_USER`` (and optional ``PROXY_PASS``) are set and a proxy URL is
    present (``HTTPS_PROXY`` / ``HTTP_PROXY``), credentials are inserted so a
    407 authenticating proxy can complete the HTTPS CONNECT.
    """
    env = os.environ if environ is None else environ
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent},
    )
    with _open_url(request, timeout, env) as response:
        source = response.read().decode("utf-8", errors="replace")
    version = parse_version_from_source(source)
    if not version:
        raise ValueError("Could not find VERSION in GitHub src/app.py")
    return version
