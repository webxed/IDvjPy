"""Внешний источник библиотеки тегов для `:import <url>` (HTTP/HTTPS).

Приложение только **запрашивает** — портов не слушает и серверов не поднимает.
Прокси с логином — общий слой `src/net.py`: те же `$PROXY_USER` / `$PROXY_PASS`
и та же подсказка при «407», что у `:update` и `:llm`.

По умолчанию разрешён только `https://`: содержимое едет прямо в библиотеку
тегов, и подменять его по пути не должен никто. `http://` — только с явным
флагом (`--insecure`), и этот выбор виден в сообщении. Размер ограничен
(``DEFAULT_MAX_BYTES``): это текстовая библиотека, а не файловый хостинг.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import net

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_BYTES = 2 * 1024 * 1024
SECURE_SCHEMES = ("https",)
INSECURE_SCHEMES = ("http",)
SUPPORTED_SCHEMES = SECURE_SCHEMES + INSECURE_SCHEMES
USER_AGENT = "IDvjPy-term"


@dataclass(frozen=True)
class FetchResult:
    """Загруженный файл переноса: текст и откуда он (для отчёта в журнале)."""

    url: str
    text: str
    size: int


class RemoteError(Exception):
    """Ошибка загрузки с готовым текстом для журнала (без пароля прокси)."""


def looks_remote(source: str) -> bool:
    """Похоже ли имя на URL (иначе это путь к локальному файлу)."""
    return urlsplit((source or "").strip()).scheme.lower() in SUPPORTED_SCHEMES


def safe_url(url: str) -> str:
    """URL без userinfo — логин/пароль из адреса не должны попасть в журнал."""
    parts = urlsplit(url)
    if not parts.username:
        return url
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port else ""
    return urlunsplit((parts.scheme, f"{host}{port}", parts.path, parts.query, parts.fragment))


def fetch_text(
    url: str,
    *,
    environ: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    allow_insecure: bool = False,
) -> FetchResult:
    """Скачать файл переноса по HTTP(S).

    Возвращает :class:`FetchResult` или бросает :class:`RemoteError` с готовым
    текстом (включая подсказку про прокси-логин при 407).
    """
    raw = (url or "").strip()
    scheme = urlsplit(raw).scheme.lower()
    if scheme not in SUPPORTED_SCHEMES:
        raise RemoteError(
            f"Unsupported URL scheme: {scheme or '(none)'} — expected https://"
        )
    if scheme in INSECURE_SCHEMES and not allow_insecure:
        raise RemoteError(
            f"Refusing {safe_url(raw)}: http:// is not encrypted. "
            "Use https:// or pass --insecure if you trust the source."
        )
    env = dict(environ or {})
    request = urllib.request.Request(raw, headers={"User-Agent": USER_AGENT})
    try:
        with net.open_url(request, timeout, env) as response:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise RemoteError(
                        f"File is too large: more than {max_bytes} bytes "
                        f"({safe_url(raw)})"
                    )
                chunks.append(chunk)
    except RemoteError:
        raise
    except Exception as exc:  # noqa: BLE001 — любой сбой сети → текст для журнала
        raise RemoteError(
            net.format_fetch_error(exc, env, subject=f"Could not fetch {safe_url(raw)}")
        ) from None
    text = b"".join(chunks).decode("utf-8-sig", errors="replace")
    return FetchResult(url=safe_url(raw), text=text, size=total)
