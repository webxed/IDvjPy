"""Compare the local app version with GitHub main (webxed/IDvjPy)."""
from __future__ import annotations

import os
import re
import urllib.request
from collections.abc import Mapping
from urllib.parse import quote, urlsplit, urlunsplit

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

_PROXY_USER_KEYS = ("PROXY_USER",)
_PROXY_PASS_KEYS = ("PROXY_PASS",)
_HTTP_PROXY_KEYS = ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")
_HTTPS_PROXY_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
)


def _env_first(environ: Mapping[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = (environ.get(name) or "").strip()
        if value:
            return value
    return ""


def inject_proxy_userinfo(proxy_url: str, user: str, password: str = "") -> str:
    """Put user[:password] into a proxy URL that has no userinfo yet."""
    raw = (proxy_url or "").strip()
    if not raw or not (user or "").strip():
        return raw
    if "://" not in raw:
        raw = "http://" + raw
    parts = urlsplit(raw)
    if parts.username:
        return raw
    host = parts.hostname or ""
    if not host:
        return raw
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    auth = quote(user.strip(), safe="")
    if password:
        auth = f"{auth}:{quote(password, safe='')}"
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{auth}@{host}{port}"
    return urlunsplit((parts.scheme or "http", netloc, parts.path, parts.query, parts.fragment))


def proxy_handler_map(environ: Mapping[str, str]) -> dict[str, str] | None:
    """Proxy URLs with ``PROXY_USER`` / ``PROXY_PASS`` filled in, or None."""
    user = _env_first(environ, _PROXY_USER_KEYS)
    if not user:
        return None
    password = _env_first(environ, _PROXY_PASS_KEYS)
    http = _env_first(environ, _HTTP_PROXY_KEYS)
    https = _env_first(environ, _HTTPS_PROXY_KEYS)
    mapping: dict[str, str] = {}
    if http:
        mapping["http"] = inject_proxy_userinfo(http, user, password)
    if https:
        mapping["https"] = inject_proxy_userinfo(https, user, password)
    return mapping or None


def redact_proxy_secrets(text: str, environ: Mapping[str, str]) -> str:
    """Strip proxy password (and encoded form) from an error string."""
    out = text or ""
    password = _env_first(environ, _PROXY_PASS_KEYS)
    if password:
        out = out.replace(password, "***")
        encoded = quote(password, safe="")
        if encoded != password:
            out = out.replace(encoded, "***")
    return out


PROXY_AUTH_HINT = (
    "Proxy requires login. Set $PROXY_USER and $PROXY_PASS "
    "in .bashrc_term (or type $PROXY_USER=… here), then :update."
)


def looks_like_proxy_auth_error(text: str) -> bool:
    raw = text or ""
    low = raw.lower()
    return "407" in raw or "proxy authentication required" in low


def format_update_fetch_error(exc: BaseException, environ: Mapping[str, str]) -> str:
    """Journal text for a failed GitHub fetch; hint if the proxy wants a login."""
    detail = redact_proxy_secrets(str(exc), environ)
    text = f"Could not check updates: {detail}"
    if looks_like_proxy_auth_error(detail) and not _env_first(environ, _PROXY_USER_KEYS):
        text = f"{text}\n{PROXY_AUTH_HINT}"
    return text


def _open_url(request: urllib.request.Request, timeout: float, environ: Mapping[str, str]):
    proxies = proxy_handler_map(environ)
    if proxies:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


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
