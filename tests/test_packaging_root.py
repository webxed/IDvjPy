"""Корневая упаковка: установка из git (`pip install .` / `uv tool install git+…`).

Проверяем, что корневой pyproject и packaging/pyproject не разъезжаются,
setup.py вкладывает src/ и отдаёт версию из CommandRunner.VERSION, а
MANIFEST.in везёт исходники в sdist.
"""
from __future__ import annotations

import ast
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


def test_package_data_covers_handbooks():
    """В wheel едут справочники: `:md` ищет их в REPO_ROOT = каталоге пакета."""
    for name in ("pyproject.toml", "packaging/pyproject.toml"):
        data = tomllib.loads((ROOT / name).read_text(encoding="utf-8"))
        patterns = data["tool"]["setuptools"]["package-data"]["idvjpy_boot"]
        assert "docs/**/*" in patterns, name
        assert "K8S_CHAINS.md" in patterns, name
    setup_py = (ROOT / "setup.py").read_text(encoding="utf-8")
    assert "EMBED_DOCS" in setup_py and "K8S_CHAINS.md" in setup_py
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include docs *.md" in manifest
    assert "include K8S_CHAINS.md" in manifest


def test_handbook_resolves_from_package_root(tmp_path, monkeypatch):
    """Раскладка установленного пакета: справочник находится рядом с src/ (+язык)."""
    import md_viewer

    package = tmp_path / "idvjpy_boot"
    (package / "docs" / "en").mkdir(parents=True)
    (package / "docs" / "en" / "SEED_TEST.md").write_text("# en", encoding="utf-8")
    (package / "docs" / "SEED_TEST.md").write_text("# base", encoding="utf-8")
    (package / "K8S_CHAINS.md").write_text("# chains", encoding="utf-8")
    monkeypatch.setattr(md_viewer, "REPO_ROOT", package)
    monkeypatch.chdir(tmp_path)

    assert md_viewer.handbook_md_path("SEED_TEST.md", lang="en") == (
        package / "docs" / "en" / "SEED_TEST.md"
    )
    # Нет каталога языка — берётся базовый справочник.
    assert md_viewer.handbook_md_path("SEED_TEST.md", lang="de") == (
        package / "docs" / "SEED_TEST.md"
    )
    # Обзор k8s лежит в корне пакета.
    assert md_viewer.handbook_md_path("K8S_CHAINS.md", lang="en") == (
        package / "K8S_CHAINS.md"
    )


def test_entry_points_do_the_same_bootstrap():
    """Установленный пакет (`idvjpy`) и `python3 app.py` делают одно и то же.

    Была расхождение: `idvjpy_boot.main()` не вызывал `apply_language(args.lang)`,
    поэтому `--lang` молча не работал у установленного пакета (а документирован
    он в README и в `:lang`).
    """
    boot = ast.parse(
        (ROOT / "packaging" / "idvjpy_boot" / "__init__.py").read_text(encoding="utf-8")
    )
    steps: set[str] = set()
    for node in ast.walk(boot):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            steps.add(node.func.attr)
    for step in (
        "parse_arguments",
        "apply_instance_name",
        "apply_language",
        "load_demo_for_cli",
        "CommandRunner",
        "run",
    ):
        assert step in steps, f"idvjpy_boot.main() не делает {step}()"

    launcher = (ROOT / "app.py").read_text(encoding="utf-8")
    for step in ("apply_instance_name", "apply_language", "load_demo_for_cli"):
        assert step in launcher, f"корневой лаунчер не делает {step}()"
