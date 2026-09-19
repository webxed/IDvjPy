"""Справка TUI (`:?`, `:? <тема>`, `:i`).

Тексты — в ``src/locales/help/<lang>/<имя>.txt`` (``en`` — источник правды,
``ru`` — перевод; каталоги и выбор языка — ``src/i18n.py``). Здесь только точки
доступа, чтобы ``app.py`` не знал про файлы. Маркер ``VER`` в ``main`` подменяется
версией приложения при показе.

Темы (`:? llm`, `:? tags`, …) — реестр ниже: у каждой темы есть **каноническое**
имя (оно попадает в оглавление справки и в подсказки) и алиасы, включая русские
слова. Неизвестная тема — явная ошибка у вызывающего, а не молчаливый откат.
"""
from __future__ import annotations

from i18n import text

# Имена текстов справки (файлы `locales/help/<lang>/<имя>.txt`).
HELP_TEXTS = (
    "main",
    "runbook",
    "calc",
    "ingress",
    "llm",
    "tags",
    "vars",
    "md",
    "kctx",
    "send",
    "session",
)

# Темы `:? <тема>` в порядке оглавления: каноническое имя → имя текста.
HELP_TOPICS: tuple[tuple[str, str], ...] = (
    ("calc", "calc"),
    ("run", "runbook"),
    ("i", "ingress"),
    ("md", "md"),
    ("llm", "llm"),
    ("tags", "tags"),
    ("vars", "vars"),
    ("kctx", "kctx"),
    ("send", "send"),
    ("session", "session"),
)

# Алиасы тем (лишние имена и русские слова). Ключ — то, что набрал человек,
# значение — текст из `HELP_TOPICS`; сами канонические имена тоже работают.
_HELP_TOPIC_ALIASES: dict[str, str] = {
    "calculator": "calc",
    "калькулятор": "calc",
    "runbook": "runbook",
    "playbook": "runbook",
    "цепочки": "runbook",
    "ingress": "ingress",
    "k8s": "ingress",
    "markdown": "md",
    "rg": "md",
    "ai": "llm",
    "провайдеры": "llm",
    "tag": "tags",
    "query": "tags",
    "теги": "tags",
    "var": "vars",
    "secrets": "vars",
    "secret": "vars",
    "переменные": "vars",
    "кластеры": "kctx",
    "mailbox": "send",
    "ящик": "send",
    "sessions": "session",
    "new": "session",
    "сессии": "session",
}


def help_topic_names() -> tuple[str, ...]:
    """Канонические имена тем (`:? calc`, `:? llm`, …) — для оглавления и подсказок."""
    return tuple(name for name, _ in HELP_TOPICS)


def help_topic(name: str) -> str | None:
    """Текст темы по имени или алиасу; ``None`` — такой темы нет.

    Пустой файл темы считается отсутствующей темой: молча показывать пустой
    блок хуже явной ошибки.
    """
    key = (name or "").strip().lower()
    text_name = dict(HELP_TOPICS).get(key) or _HELP_TOPIC_ALIASES.get(key)
    if text_name is None:
        return None
    body = text(text_name)
    return body or None


def main_help() -> str:
    """Полная справка по `:`-командам и префиксам (`:?`)."""
    return text("main")


def ingress_help() -> str:
    """Справка `:i` (Kubernetes Ingress Analyzer)."""
    return text("ingress")
