"""Справка TUI (`:?`, `:? run`, `:? calc`, `:i`).

Тексты — в ``src/locales/help/<lang>/<name>.txt`` (``en`` — источник правды,
``ru`` — перевод; каталоги и выбор языка — ``src/i18n.py``). Здесь только точки
доступа, чтобы ``app.py`` не знал про файлы. Маркер ``VER`` в ``main`` подменяется
версией приложения при показе.
"""
from __future__ import annotations

from i18n import text

# Имена текстов справки (файлы `locales/help/<lang>/<имя>.txt`).
HELP_TEXTS = ("main", "runbook", "calc", "ingress")


def main_help() -> str:
    """Полная справка по `:`-командам и префиксам (`:?`)."""
    return text("main")


def runbook_help() -> str:
    """Справка по прогону цепочки (`:? run`)."""
    return text("runbook")


def calc_help() -> str:
    """Справочник калькулятора и ipcalc (`:? calc`)."""
    return text("calc")


def ingress_help() -> str:
    """Справка `:i` (Kubernetes Ingress Analyzer)."""
    return text("ingress")
