"""Локальная диагностика окружения для ``:doctor``.

Только поиск утилит в PATH и спецификаций Python-модулей: без запуска
программ, импорта проверяемых модулей и сетевых запросов.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rich.markup import escape

from i18n import t


@dataclass(frozen=True)
class ToolCheck:
    """Одна строка проверки утилиты из PATH; purpose — ключ локали."""

    name: str
    purpose: str
    required: bool = False


@dataclass(frozen=True)
class DoctorReport:
    """Снимок локального состояния, который форматирует TUI."""

    data_dir: str
    settings_file: str
    database_file: str
    language: str
    scope: str
    terminal_mode: str
    clipboard_backends: tuple[str, ...]
    proxy_configured: bool
    shell_helper_configured: bool
    tools: tuple[tuple[ToolCheck, str | None], ...]
    packages: tuple[tuple[str, str, bool | None], ...] = ()


CORE_TOOLS: tuple[ToolCheck, ...] = (
    ToolCheck("git", "doctor.purpose.git"),
    ToolCheck("sqlite3", "doctor.purpose.sqlite3"),
)
OPTIONAL_TOOLS: tuple[ToolCheck, ...] = (
    ToolCheck("kubectl", "doctor.purpose.kubectl"),
    ToolCheck("helm", "doctor.purpose.helm"),
    ToolCheck("jq", "doctor.purpose.jq"),
    ToolCheck("ocrmypdf", "doctor.purpose.ocrmypdf"),
    ToolCheck("tesseract", "doctor.purpose.tesseract"),
    ToolCheck("anydoc", "doctor.purpose.anydoc_cli"),
    ToolCheck("markitdown", "doctor.purpose.markitdown"),
)
CLIPBOARD_TOOLS: tuple[str, ...] = ("wl-copy", "wl-paste", "xclip", "xsel")
# Только имена верхнего уровня: find_spec для точечного имени может импортировать родителя.
OPTIONAL_PACKAGES: tuple[tuple[str, str], ...] = (
    ("cryptography", "cryptography"),
    ("firecrawl-anydoc", "anydoc"),
)


def find_clipboard_backends(
    which: Callable[[str], str | None] = shutil.which,
) -> tuple[str, ...]:
    """Названия доступных Linux clipboard-backend'ов без их запуска."""
    return tuple(name for name in CLIPBOARD_TOOLS if which(name))


def has_proxy(environ: Mapping[str, str]) -> bool:
    """Есть ли настроенный HTTP(S) proxy; значения не печатаются."""
    names = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")
    return any(bool(environ.get(name, "").strip()) for name in names)


def shell_helper_configured(environ: Mapping[str, str]) -> bool:
    """Shell helper настроен, когда родитель передал файл возврата cwd."""
    return bool(environ.get("IDVJPY_CWD_FILE", "").strip())


def discover_packages() -> tuple[tuple[str, str, bool | None], ...]:
    """Найти спецификации без импорта; сбой поиска не означает отсутствие."""
    results = []
    for package, module in OPTIONAL_PACKAGES:
        try:
            found = importlib.util.find_spec(module) is not None
        except Exception:
            # Битый __spec__ или import hooks не должны ломать весь отчёт.
            found = None
        results.append((package, module, found))
    return tuple(results)


def collect_report(
    *,
    data_dir: str,
    settings_file: str,
    database_file: str,
    language: str,
    scope: str,
    terminal_mode: str,
    environ: Mapping[str, str] | None = None,
    checks: Sequence[ToolCheck] = CORE_TOOLS + OPTIONAL_TOOLS,
    which: Callable[[str], str | None] = shutil.which,
) -> DoctorReport:
    """Собрать отчёт через PATH и find_spec, не проверяя работоспособность."""
    env = os.environ if environ is None else environ
    resolved = tuple((check, which(check.name)) for check in checks)
    return DoctorReport(
        data_dir=str(Path(data_dir)),
        settings_file=str(Path(settings_file)),
        database_file=str(Path(database_file)),
        language=(language or "en").strip() or "en",
        scope=(scope or "").strip(),
        terminal_mode=(terminal_mode or "window").strip() or "window",
        clipboard_backends=find_clipboard_backends(which),
        proxy_configured=has_proxy(env),
        shell_helper_configured=shell_helper_configured(env),
        tools=resolved,
        packages=discover_packages(),
    )


def format_report(report: DoctorReport) -> str:
    """Локализованный Rich-отчёт: внешние значения только как литералы."""

    lines = [t("doctor.header"), "", t("doctor.context")]
    for key, value in (
        ("data_dir", report.data_dir),
        ("settings", report.settings_file),
        ("database", report.database_file),
        ("language", report.language),
        ("scope", report.scope or t("doctor.all_tags")),
        ("terminal", report.terminal_mode),
    ):
        lines.append("  " + t(f"doctor.{key}", value=escape(value)))
    for key, value in (
        ("shell_helper", t("doctor.configured" if report.shell_helper_configured else "doctor.not_detected")),
        ("proxy", t("doctor.configured" if report.proxy_configured else "doctor.not_configured")),
        ("clipboard", ", ".join(escape(name) for name in report.clipboard_backends) or t("doctor.no_clipboard")),
    ):
        lines.append("  " + t(f"doctor.{key}", value=value))
    lines.extend(("", t("doctor.tools")))
    for check, path in report.tools:
        status = "[green]✓[/green]" if path else "[yellow]○[/yellow]"
        suffix = escape(path) if path else t("doctor.path_missing")
        lines.append("  " + t(
            "doctor.tool_row", status=status, name=escape(check.name),
            purpose=escape(t(check.purpose)), result=suffix,
        ))
    lines.extend(("", t("doctor.packages")))
    for package, module, found in report.packages:
        key = "module_unknown" if found is None else "module_found" if found else "module_missing"
        lines.append("  " + t(
            "doctor.package_row", name=escape(package), module=escape(module),
            result=t(f"doctor.{key}"),
        ))
    lines.extend(("", t("doctor.package_note"), "", t("doctor.footer")))
    return "\n".join(lines)
