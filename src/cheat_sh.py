"""Запросы к cheat.sh (cht.sh) — команда `:cht <запрос>`.

cheat.sh — сервис шпаргалок: `https://cht.sh/<запрос>` возвращает текст
(команды UNIX, вопросы по языкам, поиск). Здесь только HTTP через stdlib
(`urllib`), как в `:llm` и `:update`; прокси с логином ($PROXY_USER/$PROXY_PASS)
поддерживается через общие хелперы `update_check`.

Правила запроса (см. https://github.com/chubin/cheat.sh):
  - `tar`                 — шпаргалка по команде;
  - `python read file`    — вопрос по языку: пробелы становятся `+`;
  - `~snapshot`           — поиск по шпаргалкам (`~keyword`, опц. `/r`, `/bi`);
  - `go/:learn`, `:list`  — спецстраницы;
  - `/1`, `/2` в конце    — другой вариант ответа;
  - опции через `?`: `Q` — без комментариев, `T` — без цветов (`?QT`).

По умолчанию подставляется `T` (без ANSI), а на всякий случай ANSI-последова-
тельности вырезаются из ответа и после запроса — в журнал не должен попасть
мусор из escape-кодов.
"""
from __future__ import annotations

import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

from update_check import (
    looks_like_proxy_auth_error,
    proxy_handler_map,
    redact_proxy_secrets,
)

DEFAULT_BASE_URL = "https://cht.sh"
DEFAULT_OPTIONS = "T"
DEFAULT_TIMEOUT = 15.0
# cheat.sh отдаёт text/plain только «curl»-подобному клиенту (клиент cht.sh
# шлёт `-A curl`); для остальных UA это HTML-страница просмотрщика.
USER_AGENT = "curl"
MAX_ERROR_BODY = 300

# ANSI CSI / OSC / одиночные escape-последовательности.
RE_ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-Z\\-_])"
)

CHEAT_SH_PROXY_HINT = (
    "Proxy requires login: set $PROXY_USER and $PROXY_PASS "
    "(in .bashrc_term or type $PROXY_USER=… here), then retry :cht."
)


class CheatShError(Exception):
    """Ошибка запроса к cheat.sh (сеть, HTTP, пустой ответ)."""


def strip_ansi(text: str) -> str:
    """Убрать ANSI-последовательности: в журнал идёт чистый текст."""
    return RE_ANSI.sub("", text or "")


def _merge_options(*chunks: str) -> str:
    """Собрать опции вида `QT`, сохранив порядок и убрав дубликаты."""
    ordered: list[str] = []
    for chunk in chunks:
        for char in chunk or "":
            if char.isalnum() and char not in ordered:
                ordered.append(char)
    return "".join(ordered)


def build_url(
    query: str,
    base_url: str = DEFAULT_BASE_URL,
    options: str = DEFAULT_OPTIONS,
) -> str:
    """Собрать URL запроса cheat.sh.

    Пробелы в запросе → `+` (как делает клиент cht.sh), ведущий `/` отбрасывается.
    Свои опции в запросе (`lua/table+keys?Q`) объединяются с опциями по умолчанию.
    """
    raw = (query or "").strip().lstrip("/")
    path, _, user_options = raw.partition("?")
    path = "+".join(path.split())
    path = urllib.parse.quote(path, safe="/+~-_.:,()@%")
    merged = _merge_options(user_options, options)
    url = base_url.rstrip("/") + "/" + path
    if merged:
        url += "?" + merged
    return url


def _open(request: urllib.request.Request, timeout: float, env: Mapping[str, str]):
    """urlopen с учётом прокси, требующего логин (как в :llm / :update)."""
    proxies = proxy_handler_map(env)
    if proxies:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


def _error_text(detail: str, env: Mapping[str, str]) -> str:
    clean = redact_proxy_secrets(detail, env)
    if looks_like_proxy_auth_error(clean):
        clean += "\n" + CHEAT_SH_PROXY_HINT
    return clean


def fetch_cheat_sheet(
    query: str,
    base_url: str = DEFAULT_BASE_URL,
    options: str = DEFAULT_OPTIONS,
    env: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Запросить cheat.sh и вернуть текст шпаргалки (без ANSI).

    Бросает CheatShError с понятным сообщением при сетевых/HTTP-ошибках и
    пустом ответе (неизвестный запрос).
    """
    env = os.environ if env is None else env
    url = build_url(query, base_url, options)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
    )
    try:
        with _open(request, timeout, env) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = strip_ansi(exc.read().decode("utf-8", errors="replace")).strip()
        except Exception:
            pass
        detail = body[:MAX_ERROR_BODY] if body else str(exc.reason)
        raise CheatShError(
            _error_text(f"HTTP {exc.code} from {url}: {detail}", env)
        ) from exc
    except urllib.error.URLError as exc:
        raise CheatShError(
            _error_text(f"Network error for {url}: {exc.reason}", env)
        ) from exc
    except TimeoutError as exc:
        raise CheatShError(f"Timeout after {timeout:g}s for {url}.") from exc

    text = strip_ansi(raw).replace("\r\n", "\n").rstrip("\n")
    if not text.strip():
        raise CheatShError(f"Nothing found for '{query}' ({url}).")
    if text.lstrip()[:6].lower().startswith("<html"):
        raise CheatShError(
            f"cheat.sh returned HTML for '{query}' ({url}); "
            "check cheat_sh_url / User-Agent."
        )
    return text + "\n"
