"""Сборка idvjpy-term из репозитория: `pip install .` / `uv tool install git+…`.

Установка из git/каталога не может опираться на готовые
``packaging/idvjpy_boot/src`` и ``packaging/idvjpy_boot/docs`` (их там нет —
это генерируемые ресурсы). Кастомный ``build_py`` перед обычной сборкой копирует
актуальные ``src/``, ``docs/`` и ``K8S_CHAINS.md`` во вложенные ресурсы пакета
(как ``packaging/build_wheel.sh``), после — убирает копии. Версия берётся из
``CommandRunner.VERSION`` (``v1.60`` → ``1.60.0``), поэтому не дублируется в коде.

Вложенные ``docs/`` нужны, потому что ``:md`` ищет справочники в ``REPO_ROOT`` —
у установленного пакета это каталог ``idvjpy_boot/`` (``src/md_viewer.py``).
"""
from __future__ import annotations

import pathlib
import re
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = pathlib.Path(__file__).resolve().parent
PACKAGE = ROOT / "packaging" / "idvjpy_boot"
EMBED = PACKAGE / "src"
EMBED_DOCS = PACKAGE / "docs"
EMBED_OVERVIEW = PACKAGE / "K8S_CHAINS.md"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def read_version() -> str:
    """Версия wheel из VERSION в src/app.py (`vMAJOR.MINOR` → `MAJOR.MINOR.0`)."""
    text = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    match = re.search(r'VERSION = "v(\d+)\.(\d+)"', text)
    return f"{match.group(1)}.{match.group(2)}.0" if match else "0.0.0"


def _embed_resources() -> None:
    """Скопировать src/, docs/ и K8S_CHAINS.md в пакет (перед сборкой)."""
    if EMBED.exists():
        shutil.rmtree(EMBED)
    shutil.copytree(ROOT / "src", EMBED, ignore=IGNORE)
    if EMBED_DOCS.exists():
        shutil.rmtree(EMBED_DOCS)
    shutil.copytree(ROOT / "docs", EMBED_DOCS, ignore=IGNORE)
    shutil.copy2(ROOT / "K8S_CHAINS.md", EMBED_OVERVIEW)


def _clean_resources() -> None:
    """Убрать вложенные ресурсы: они генерируются на каждой сборке."""
    shutil.rmtree(EMBED, ignore_errors=True)
    shutil.rmtree(EMBED_DOCS, ignore_errors=True)
    EMBED_OVERVIEW.unlink(missing_ok=True)


class build_py(_build_py):
    """Вкладывает ресурсы в пакет на время сборки и убирает копии после."""

    def run(self) -> None:
        _embed_resources()
        try:
            super().run()
        finally:
            _clean_resources()


setup(version=read_version(), cmdclass={"build_py": build_py})
