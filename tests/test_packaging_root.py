"""Корневая упаковка: установка из git (`pip install .` / `uv tool install git+…`).

Проверяем, что корневой pyproject и packaging/pyproject не разъезжаются,
setup.py вкладывает src/ и отдаёт версию из CommandRunner.VERSION, а
MANIFEST.in везёт исходники в sdist.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

from app import CommandRunner

ROOT = Path(__file__).resolve().parents[1]


def _expected_version() -> str:
    match = re.fullmatch(r"v(\d+)\.(\d+)", CommandRunner.VERSION)
    assert match, CommandRunner.VERSION
    return f"{match.group(1)}.{match.group(2)}.0"


def test_root_pyproject_and_packaging_agree():
    root = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pkg = tomllib.loads((ROOT / "packaging" / "pyproject.toml").read_text(encoding="utf-8"))
    assert root["project"]["name"] == pkg["project"]["name"] == "idvjpy-term"
    script = {"idvjpy": "idvjpy_boot:main"}
    assert root["project"]["scripts"] == pkg["project"]["scripts"] == script
    assert root["project"]["dependencies"] == pkg["project"]["dependencies"]
    assert root["project"]["requires-python"] == pkg["project"]["requires-python"] == ">=3.12"
    assert root["project"]["dynamic"] == ["version"]
    # Корневой pyproject везёт пакет из packaging/idvjpy_boot.
    assert root["tool"]["setuptools"]["package-dir"]["idvjpy_boot"] == "packaging/idvjpy_boot"


def test_setup_py_embeds_src_and_reports_version():
    text = (ROOT / "setup.py").read_text(encoding="utf-8")
    assert "shutil.copytree" in text
    assert "packaging" in text and "idvjpy_boot" in text
    proc = subprocess.run(
        [sys.executable, "setup.py", "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == _expected_version()


def test_manifest_includes_src_tree():
    text = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include src *" in text
    assert ".bashrc_term.example" in text
