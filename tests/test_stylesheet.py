"""Стили TUI: Textual CSS лежит в `src/app.tcss` (а не в `app.css`).

Расширение `.tcss` — не украшение: содержимое понимает только Textual
(`$surface`, `dock`, `layout`, `text-style`), а редакторы видят в `.css`
браузерный CSS и сыплют ложными «property value expected» / «Unknown property»
на каждой `$переменной`. Тест сторожит путь в `CommandRunner.CSS_PATH`, то что
ресурс реально существует, и что он не «переехал» обратно в `.css` в коде и
упаковке (файл читают из wheel — там он через glob `src/**/*`).
"""
from __future__ import annotations

from pathlib import Path

from app import CommandRunner

ROOT = Path(__file__).resolve().parents[1]

STYLESHEET = "app.tcss"


def test_css_path_points_to_tcss():
    css_path = CommandRunner.CSS_PATH
    # Textual разрешает список путей; здесь ожидаем один файл.
    assert isinstance(css_path, str), f"CSS_PATH is not a single file: {css_path!r}"
    assert css_path.endswith(STYLESHEET), css_path
    assert Path(css_path).is_file()
    assert (ROOT / "src" / STYLESHEET).is_file()


def test_stylesheet_uses_textual_only_syntax():
    """Проверка причины расширения: файл — Textual CSS, не браузерный."""
    text = (ROOT / "src" / STYLESHEET).read_text(encoding="utf-8")
    assert "$surface" in text  # Textual-переменная темы
    assert "dock:" in text  # свойство Textual, в CSS его нет


def test_no_browser_css_left_in_code_and_packaging():
    sources = [
        *(ROOT / "src").glob("*.py"),
        *(ROOT / "tests").glob("*.py"),
        *(ROOT / "packaging").rglob("*.py"),
        *(ROOT / "packaging").rglob("*.sh"),
        ROOT / "pyproject.toml",
        ROOT / "MANIFEST.in",
        ROOT / "setup.py",
    ]
    offenders = [
        path.relative_to(ROOT)
        for path in sources
        # Сам этот файл называет старое имя в объяснении — его не считаем.
        if path.is_file()
        and path.resolve() != Path(__file__).resolve()
        and "app.css" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"стили снова упоминаются как app.css: {offenders}"


def test_stylesheet_is_packaged():
    """Файл должен попадать в wheel: упаковка копирует src/ целиком."""
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include src *" in manifest
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"src/**/*"' in pyproject
