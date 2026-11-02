"""Общий сетевой слой: HTTP(S) через stdlib + прокси с логином.

Здесь живёт всё, что нужно исходящим запросам приложения: `:update` (версия на
GitHub), `:llm` (провайдеры), `:import <url>` (библиотека тегов). Прокси-логин
задаётся переменными `PROXY_USER` / `PROXY_PASS` (их читают все три пути), а
«407» превращается в подсказку, а не в сырой traceback. Приложение само портов
не слушает и никаких серверов не поднимает.

Модуль не зависит от Textual.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Collection, Mapping
from urllib.parse import quote, urlsplit, urlunsplit

PROXY_USER_KEYS = ("PROXY_USER",)
PROXY_PASS_KEYS = ("PROXY_PASS",)
HTTP_PROXY_KEYS = ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")
HTTPS_PROXY_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
)

PROXY_AUTH_HINT = (
    "Proxy requires login. Set $PROXY_USER and $PROXY_PASS "
    "in .bashrc_term (or type $PROXY_USER=… here), then retry."
)


def env_first(environ: Mapping[str, str], names: tuple[str, ...]) -> str:
    """Первое непустое значение из списка имён переменных окружения."""
    for name in names:
        value = (environ.get(name) or "").strip()
        if value:
            return value
    return ""


def inject_proxy_userinfo(proxy_url: str, user: str, password: str = "") -> str:
    """Вставить user[:password] в URL прокси, если их там ещё нет."""
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
    """URL прокси с подставленными ``PROXY_USER`` / ``PROXY_PASS`` (или None)."""
    user = env_first(environ, PROXY_USER_KEYS)
    if not user:
        return None
    password = env_first(environ, PROXY_PASS_KEYS)
    http = env_first(environ, HTTP_PROXY_KEYS)
    https = env_first(environ, HTTPS_PROXY_KEYS)
    mapping: dict[str, str] = {}
    if http:
        mapping["http"] = inject_proxy_userinfo(http, user, password)
    if https:
        mapping["https"] = inject_proxy_userinfo(https, user, password)
    return mapping or None


def redact_proxy_secrets(text: str, environ: Mapping[str, str]) -> str:
    """Убрать пароль прокси (и его URL-кодированную форму) из сообщения об ошибке."""
    out = text or ""
    password = env_first(environ, PROXY_PASS_KEYS)
    if password:
        out = out.replace(password, "***")
        encoded = quote(password, safe="")
        if encoded != password:
            out = out.replace(encoded, "***")
    return out


def looks_like_proxy_auth_error(text: str) -> bool:
    """Похоже на отказ прокси требующего логин (407)."""
    raw = text or ""
    return "407" in raw or "proxy authentication required" in raw.lower()


def allowed_redirect_schemes(
    initial_scheme: str, extra: Collection[str] | None = None
) -> frozenset[str]:
    """Схемы, разрешённые для redirect: своя схема запроса плюс https.

    Понижение `https → http` запрещено: urllib иначе сам проходит такой переход
    и содержимое (`:import`, `:update`) едет открытым текстом, хотя адрес был
    https. Повышение `http → https` разрешено. `extra` — явный выбор вызывающего
    (`:import --insecure`).
    """
    schemes = {"https"}
    if initial_scheme:
        schemes.add(initial_scheme.lower())
    if extra:
        schemes.update(str(scheme).lower() for scheme in extra if scheme)
    return frozenset(schemes)


class SchemeCheckingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect-обработчик, проверяющий схему **до** запроса на новый адрес."""

    def __init__(self, allowed: Collection[str]) -> None:
        super().__init__()
        self.allowed = frozenset(allowed)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        scheme = urlsplit(newurl or "").scheme.lower()
        if scheme not in self.allowed:
            raise urllib.error.HTTPError(
                newurl,
                code,
                f"refusing redirect to {scheme or '(none)'} scheme",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(
    request: urllib.request.Request,
    timeout: float,
    environ: Mapping[str, str],
    *,
    extra_schemes: Collection[str] | None = None,
):
    """Открыть запрос: прокси с логином и проверка схемы на каждом redirect."""
    initial = urlsplit(request.full_url).scheme.lower()
    handlers: list[urllib.request.BaseHandler] = [
        SchemeCheckingRedirectHandler(allowed_redirect_schemes(initial, extra_schemes))
    ]
    proxies = proxy_handler_map(environ)
    if proxies:
        handlers.append(urllib.request.ProxyHandler(proxies))
    opener = urllib.request.build_opener(*handlers)
    return opener.open(request, timeout=timeout)


def format_fetch_error(
    exc: BaseException, environ: Mapping[str, str], *, subject: str
) -> str:
    """Текст ошибки запроса: без пароля прокси + подсказка при 407."""
    detail = redact_proxy_secrets(str(exc), environ)
    text = f"{subject}: {detail}"
    if looks_like_proxy_auth_error(detail) and not env_first(environ, PROXY_USER_KEYS):
        text = f"{text}\n{PROXY_AUTH_HINT}"
    return text
