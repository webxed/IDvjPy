"""Compare the local app version with GitHub main (webxed/IDvjPy)."""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Optional, Tuple

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


def parse_version_tuple(text: str) -> Optional[Tuple[int, ...]]:
    """Turn ``v1.24`` / ``1.24.0`` into a comparable tuple, or None."""
    match = RE_VERSION_TOKEN.search((text or "").strip())
    if not match:
        return None
    parts = [int(group) for group in match.groups() if group is not None]
    return tuple(parts)


def parse_version_from_source(source: str) -> Optional[str]:
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


def format_update_status(local: str, remote: str) -> Tuple[str, str]:
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
) -> str:
    """Download ``src/app.py`` from GitHub main and return its VERSION."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        source = response.read().decode("utf-8", errors="replace")
    version = parse_version_from_source(source)
    if not version:
        raise ValueError("Could not find VERSION in GitHub src/app.py")
    return version
