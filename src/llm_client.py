"""Запросы к LLM по конфигу из YAML (команда `:llm <провайдер> <сообщение>`).

Конфиг — `llm_providers.yml` в каталоге запуска (пример: src/llm_providers.example.yml).
Каждый провайдер описывает URL, заголовки и тело запроса шаблоном с
плейсхолдерами. Ключи API — не в конфиге: значения вида `$VAR` подставляются
из окружения (os.environ + local_env приложения).

Плейсхолдеры тела:
  %MODEL%    — значение provider.model    (JSON-escaped)
  %SYSTEM%   — provider.system (если задан; JSON-escaped, в кавычках)
  %MSG%      — текст пользователя          (JSON-escaped)
  %MSG_RAW%  — текст пользователя          (как есть, без кавычек/escape)
Если `body` не задан, строится стандартное OpenAI-совместимое тело
`chat/completions` (model/messages/system/stream:false).

Извлечение ответа: `response_path` точками (`choices.0.message.content`); без
него — эвристика по списку известных полей. Сеть только через urllib (stdlib).

Контекст приложения (`:llm ask <задача>` или ключ `app_context` провайдера)
собирает `llm_context.py` и дописывается в system-сообщение (до правила языка).
"""
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from update_check import (
    looks_like_proxy_auth_error,
    proxy_handler_map,
    redact_proxy_secrets,
)

DEFAULT_TIMEOUT = 60.0
# Многоходовость: сколько последних пар (user+assistant) держать в контексте.
DEFAULT_HISTORY_TURNS = 0
MAX_HISTORY_TURNS = 50
# Лимит на вложенный файл (`@путь`): больше — явная ошибка, не молчаливая обрезка.
DEFAULT_MAX_ATTACHMENT_BYTES = 200_000
# `@путь` в сообщении: не трогает email (`user@host`) и `@@literal`.
RE_FILE_REF = re.compile(r"(?<![\w@$])@([^\s@]+)")
LLM_PROXY_HINT = (
    "Proxy requires login: set $PROXY_USER and $PROXY_PASS "
    "(in .bashrc_term or type $PROXY_USER=… here), then retry :llm."
)

_LANG_RULE = (
    "Always answer in {lang}. Do not switch to another language "
    "(in particular, do not reply in Chinese or English) unless the user "
    "explicitly asks for that language."
)
MISSING_BODY_FALLBACKS = (
    "choices.0.message.content",
    "choices.0.text",
    "message.content",
    "output.choices.0.message.content",
    "response",
    "content",
    "output_text",
    "result",
)


class LlmError(Exception):
    """Ошибка конфигурации, запроса или ответа LLM."""


def example_config_path() -> str:
    """Путь к эталонному llm_providers.example.yml (рядом с этим модулем)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_providers.example.yml")


def load_providers(path: str) -> dict[str, Any]:
    """Читает llm_providers.yml; возвращает словарь конфигурации."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise LlmError(f"Config not found: {path} ({e})") from e
    try:
        import yaml

        cfg = yaml.safe_load(raw)
    except Exception as e:
        raise LlmError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(cfg, dict) or not isinstance(cfg.get("providers"), dict):
        raise LlmError(
            f"{path} must be a mapping with a `providers:` section "
            "(see {example_config_path()})."
        )
    return cfg


def provider_names(cfg: dict[str, Any]) -> list[str]:
    return sorted(cfg["providers"])


def default_provider(cfg: dict[str, Any]) -> str | None:
    name = str(cfg.get("default") or "").strip()
    return name if name in cfg["providers"] else None


def describe(cfg: dict[str, Any]) -> str:
    """Человекочитаемый список провайдеров (для :llm без аргументов)."""
    lines = ["[bold]LLM providers:[/bold]"]
    default = default_provider(cfg)
    for name in provider_names(cfg):
        prov = cfg["providers"][name]
        model = prov.get("model") or ""
        mark = "  (default)" if name == default else ""
        lines.append(f"  [cyan]{name}[/cyan]{mark}  {model}")
    lines.append("  [dim]Usage: :llm <message> · :llm <provider> <message> [@file …][/dim]")
    lines.append("  [dim]       :llm ask <task> — default provider + saved tags → !tag[tid] refs[/dim]")
    return "\n".join(lines) + "\n"


def _code_fence(content: str) -> str:
    """Безопасное ```-ограждение: длиннее любой серии бэктиков в файле."""
    longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def history_turns_for(provider: dict[str, Any]) -> int:
    """Сколько пар (user+assistant) держать в контексте у провайдера.

    Ключ `history_turns` в llm_providers.yml; нечисловое/отрицательное → 0
    (без контекста), больше `MAX_HISTORY_TURNS` — обрезается.
    """
    try:
        value = int(provider.get("history_turns") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(value, MAX_HISTORY_TURNS))


def trim_history(messages: list[dict[str, str]], turns: int) -> list[dict[str, str]]:
    """Оставляет последние `turns` пар, не начиная с «висячего» assistant."""
    if turns <= 0:
        return []
    kept = list(messages[-turns * 2 :])
    while kept and kept[0].get("role") != "user":
        kept.pop(0)
    return kept


def append_exchange(
    messages: list[dict[str, str]],
    user_text: str,
    assistant_text: str,
    turns: int,
) -> list[dict[str, str]]:
    """Добавляет пару user/assistant и обрезает контекст до `turns` пар."""
    if turns <= 0:
        return []
    updated = [
        *messages,
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text},
    ]
    return trim_history(updated, turns)


def expand_file_refs(
    text: str,
    base_dir: str,
    *,
    max_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
) -> tuple[str, list[tuple[str, int]]]:
    """Раскрывает `@путь` в тексте в содержимое файла (блок в ```).

    Возвращает ``(новый_текст, [(путь, число_символов), …])``.
    Ошибки — `LlmError` с понятным текстом: нет файла, каталог, бинарный/
    не-UTF-8, больше `max_bytes`. Относительные пути — от `base_dir` (cwd),
    `~` раскрывается. Чтобы передать литеральный `@`, удвойте его: `@@`.
    """
    attachments: list[tuple[str, int]] = []

    def repl(match: re.Match) -> str:
        raw = match.group(1)
        path = os.path.expanduser(raw)
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)
        path = os.path.normpath(path)
        if os.path.isdir(path):
            raise LlmError(f"Attachment {raw} is a directory, not a file.")
        try:
            with open(path, "rb") as f:
                data = f.read(max_bytes + 1)
        except OSError as e:
            raise LlmError(f"Cannot read attachment {raw}: {e}") from e
        if len(data) > max_bytes:
            raise LlmError(
                f"Attachment {raw} is too large: > {max_bytes} bytes "
                "(limit DEFAULT_MAX_ATTACHMENT_BYTES; split the file or paste a fragment)."
            )
        if b"\x00" in data:
            raise LlmError(f"Attachment {raw} looks binary (NUL byte); only text files are supported.")
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise LlmError(f"Attachment {raw} is not UTF-8 text: {e}") from e
        attachments.append((path, len(content)))
        fence = _code_fence(content)
        body = content if content.endswith("\n") else content + "\n"
        return f"{fence}{raw}\n{body}{fence}"

    return RE_FILE_REF.sub(repl, text), attachments


def _require_env(template: str, env: dict[str, str], where: str) -> str:
    """Заменяет `$VAR` в строке; неизвестная переменная — явная ошибка."""
    missing: list[str] = []

    def repl(match: re.Match) -> str:
        name = match.group(1) or ""
        if name in env:
            return env[name]
        missing.append(name)
        return match.group(0)

    out = re.sub(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?", repl, template)
    if missing:
        raise LlmError(
            f"Missing env variable(s) for {where}: {', '.join(sorted(set(missing)))}. "
            "Set them via `$VAR=val` or export before starting the app."
        )
    return out


def _json_literal(value: str) -> str:
    """JSON-строка-литерал с кавычками (безопасно вставлять в JSON-шаблон)."""
    return json.dumps(value, ensure_ascii=False)


def _dig(data: Any, path: str | None) -> Any:
    if path is None or not path.strip():
        return None
    node: Any = data
    for part in path.strip().split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def _extract_text(payload: Any, response_path: str | None) -> str:
    if isinstance(payload, str):
        return payload
    if response_path:
        found = _dig(payload, response_path)
        if found is None:
            raise LlmError(f"response_path '{response_path}' not found in the response.")
        return str(found)
    for candidate in MISSING_BODY_FALLBACKS:
        found = _dig(payload, candidate)
        if found is not None:
            return str(found)
    # Последний шанс — читаемый дамп (диагностика от провайдера).
    raise LlmError(
        "No known answer field in the response. Set `response_path` "
        f"in llm_providers.yml. Got: {json.dumps(payload, ensure_ascii=False)[:200]}"
    )


def _effective_system(
    provider: dict[str, Any], app_context: str | None = None
) -> str:
    """Системный промпт: base + контекст приложения + правило языка.

    `app_context` — «шпаргалка» приложения и выжимка библиотеки тегов
    (`llm_context.build_app_context`); идёт до правила языка, чтобы оно
    оставалось последней и самой сильной инструкцией. Без answer_language
    и контекста возвращает provider.system как есть.
    """
    parts: list[str] = []
    base = str(provider.get("system") or "").strip()
    if base:
        parts.append(base)
    if app_context and str(app_context).strip():
        parts.append(str(app_context).strip())
    lang = str(provider.get("answer_language") or "").strip()
    if lang:
        parts.append(_LANG_RULE.format(lang=lang))
    return "\n\n".join(parts)


def _default_body(
    model: str,
    system: str | None,
    message: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.extend(history or [])
    messages.append({"role": "user", "content": message})
    body: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
    return body


def build_body(
    provider: dict[str, Any],
    message: str,
    env: dict[str, str],
    history: list[dict[str, str]] | None = None,
    app_context: str | None = None,
) -> str:
    """Тело запроса: пользовательский шаблон с плейсхолдерами или OpenAI-форма.

    `history` — предыдущие пары `{role, content}` (`:llm` многоходовость).
    Шаблон получает их как `%HISTORY%` (JSON-массив, без кавычек); в авто-теле
    они встают между system и текущим user-сообщением.
    `app_context` — контекст приложения (`:llm ask` / ключ app_context);
    дописывается в system-сообщение (оно же уходит в `%SYSTEM%`).
    """
    model = str(provider.get("model") or "")
    system = _effective_system(provider, app_context)
    template = provider.get("body")
    if template is None:
        return json.dumps(
            _default_body(model, system, message, history), ensure_ascii=False
        )
    text = str(template)
    text = text.replace("%MSG_RAW%", message)
    text = text.replace("%MSG%", _json_literal(message))
    text = text.replace("%SYSTEM%", _json_literal(system))
    text = text.replace("%MODEL%", _json_literal(model))
    text = text.replace("%HISTORY%", json.dumps(history or [], ensure_ascii=False))
    return _require_env(text, env, "body")


def build_headers(provider: dict[str, Any], env: dict[str, str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in (provider.get("headers") or {}).items():
        headers[str(key)] = _require_env(str(value), env, f"header '{key}'")
    return headers


def _open_request(
    request: urllib.request.Request, timeout: float, env: dict[str, str]
):
    """urlopen с учётом аутентифицирующего прокси (как в :update).

    Если заданы $PROXY_USER/$PROXY_PASS и прокси в окружении — креды
    вставляются в прокси-URL, иначе — стандартный opener (env-прокси как есть).
    """
    proxies = proxy_handler_map(env)
    if proxies:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


def _proxy_aware_error(prefix: str, text: str, env: dict[str, str]) -> str:
    """Чистит секреты и добавляет подсказку про прокси при 407."""
    clean = redact_proxy_secrets(text, env)
    message = f"{prefix}{clean}"
    if looks_like_proxy_auth_error(clean):
        message += "\n" + LLM_PROXY_HINT
    return message


def perform_request(
    provider: dict[str, Any],
    message: str,
    env: dict[str, str],
    timeout: float = DEFAULT_TIMEOUT,
    history: list[dict[str, str]] | None = None,
    app_context: str | None = None,
) -> str:
    """Выполняет запрос и возвращает текстовый ответ модели.

    `history` — предыдущие пары сообщений (многоходовость `:llm`).
    `app_context` — контекст приложения (шпаргалка + библиотека тегов).
    Бросает LlmError с понятным сообщением при сетевых/HTTP/разборных ошибках.
    """
    url = str(provider.get("url") or "").strip()
    if not url:
        raise LlmError("Provider has no `url`.")
    headers = build_headers(provider, env)
    body = build_body(provider, message, env, history, app_context).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with _open_request(request, timeout, env) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        message = _proxy_aware_error(f"HTTP {e.code} from {url}: ", detail or str(e.reason), env)
        raise LlmError(message) from e
    except urllib.error.URLError as e:
        message = _proxy_aware_error(f"Network error for {url}: ", str(e.reason), env)
        raise LlmError(message) from e
    except TimeoutError as e:
        raise LlmError(f"Timeout after {timeout:g}s for {url}.") from e
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = raw
    return _extract_text(payload, provider.get("response_path"))
