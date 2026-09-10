"""Сборка idvjpy-term из репозитория: `pip install .` / `uv tool install git+…`.

Установка из git/каталога не может опираться на готовый
``packaging/idvjpy_boot/src`` (его там нет — это генерируемый ресурс).
Кастомный ``build_py`` перед обычной сборкой копирует актуальный ``src/``
во вложенный ресурс пакета (как ``packaging/build_wheel.sh``), после —
убирает копию. Версия берётся из ``CommandRunner.VERSION`` (``v1.60`` →
``1.60.0``), поэтому не дублируется в коде.
"""
from __future__ import annotations

import pathlib
import re
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = pathlib.Path(__file__).resolve().parent
EMBED = ROOT / "packaging" / "idvjpy_boot" / "src"


def read_version() -> str:
    """Версия wheel из VERSION в src/app.py (`vMAJOR.MINOR` → `MAJOR.MINOR.0`)."""
    text = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    match = re.search(r'VERSION = "v(\d+)\.(\d+)"', text)
    return f"{match.group(1)}.{match.group(2)}.0" if match else "0.0.0"


class build_py(_build_py):
    """Вкладывает src/ в пакет на время сборки и убирает копию после."""

    def run(self) -> None:
        if EMBED.exists():
            shutil.rmtree(EMBED)
        shutil.copytree(
            ROOT / "src",
            EMBED,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        try:
            super().run()
        finally:
            shutil.rmtree(EMBED, ignore_errors=True)


setup(version=read_version(), cmdclass={"build_py": build_py})
