"""`bump_version`: синхронизация VERSION по всем файлам релиза (фича version-bump).

Логика — `src/version_bump.py` (лаунчер `bump_version.py`). Здесь проверяются
арифметика версии, обновление всех маркеров на временном репозитории и
`--check`/`--dry-run`/`--set`.
"""
from pathlib import Path

import pytest

from version_bump import (
    TARGETS,
    VersionBumpError,
    bump,
    check,
    main,
    next_minor,
    parse_version,
    read_current_version,
)

FIXTURES = {
    "src/app.py": (
        "class CommandRunner:\n"
        '    TITLE = "IDvjPy_term"\n'
        '    VERSION = "v1.10"\n\n'
        "    def run(self):\n"
        "        pass\n"
    ),
    "README.md": "# IDvjPy\n\n**IDvjPy_term** v1.10 — умный терминал.\n",
    "COMPACT_SUMMARY.md": (
        "Версия: **v1.10**.\n\n"
        "| File | Coverage |\n"
        "| `test_cmd.md` | Manual plan v1.42 (app v1.10) |\n"
        "| `src/app.py` | TUI (`CommandRunner`), v1.10 |\n\n"
        "## v1.10\n\n- старое.\n\n"
        "## v1.9\n\n- ещё старее.\n"
    ),
    "CLAUDE.md": (
        "# CLAUDE.md\n"
        "IDvjPy_term (v1.10) is a Python terminal application (TUI).\n"
        "Bump `CommandRunner.VERSION` minor on every commit (`v1.10` → `v1.11`).\n"
    ),
    "AGENTS.md": (
        "# AGENTS.md\n"
        "11. **Версия = коммит.** (`v1.10` → `v1.11`).\n"
    ),
    "test_cmd.md": (
        "# План тестирования IDvjPy_term v1.10\n\n"
        "текст\n\n"
        "**Версия документа**: v1.42  \n"
        "**Версия приложения**: v1.10\n"
    ),
    "tests/test_cmd_scenarios.py": (
        '"""Автотесты по сценариям test_cmd.md (IDvjPy_term v1.10)."""\n'
    ),
    "DEMO.md": "# Сценарий\n\nВерсия приложения: **v1.10**.\n",
}


def _make_repo(tmp_path: Path) -> Path:
    for rel, text in FIXTURES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def test_version_math():
    assert parse_version("v1.98") == (1, 98)
    assert next_minor("v1.98") == "v1.99"
    assert next_minor("v1.9") == "v1.10"
    assert next_minor("v2.0") == "v2.1"
    with pytest.raises(VersionBumpError):
        parse_version("1.98")
    with pytest.raises(VersionBumpError):
        parse_version("v1")


def test_fixture_covers_all_targets():
    assert set(TARGETS) == set(FIXTURES)


def test_bump_updates_every_marker(tmp_path):
    root = _make_repo(tmp_path)
    assert read_current_version(root) == "v1.10"
    new, changes = bump(root)
    assert new == "v1.11"
    assert set(changes) == set(TARGETS)

    assert 'VERSION = "v1.11"' in (root / "src/app.py").read_text(encoding="utf-8")
    assert "**IDvjPy_term** v1.11 —" in (root / "README.md").read_text(encoding="utf-8")

    compact = (root / "COMPACT_SUMMARY.md").read_text(encoding="utf-8")
    assert "Версия: **v1.11**." in compact
    assert "TUI (`CommandRunner`), v1.11 |" in compact
    assert "## v1.11" in compact
    assert "## v1.10" in compact  # история не переписана
    assert "Manual plan v1.43 (app v1.11)" in compact

    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert "IDvjPy_term (v1.11)" in claude
    assert "(`v1.11` → `v1.12`)" in claude

    assert "(`v1.11` → `v1.12`)" in (root / "AGENTS.md").read_text(encoding="utf-8")

    test_cmd = (root / "test_cmd.md").read_text(encoding="utf-8")
    assert "# План тестирования IDvjPy_term v1.11" in test_cmd
    assert "**Версия приложения**: v1.11" in test_cmd
    assert "**Версия документа**: v1.43" in test_cmd

    scenarios = (root / "tests/test_cmd_scenarios.py").read_text(encoding="utf-8")
    assert "(IDvjPy_term v1.11)" in scenarios

    assert "Версия приложения: **v1.11**" in (root / "DEMO.md").read_text(
        encoding="utf-8"
    )


def test_bump_result_passes_check(tmp_path):
    root = _make_repo(tmp_path)
    bump(root)
    assert check(root) == []


def test_bump_is_idempotent_for_same_version(tmp_path):
    root = _make_repo(tmp_path)
    bump(root, new_version="v1.11")
    second = bump(root, new_version="v1.11")[1]
    assert second == {}


def test_bump_set_explicit_version(tmp_path):
    root = _make_repo(tmp_path)
    new, _ = bump(root, new_version="v2.0")
    assert new == "v2.0"
    assert 'VERSION = "v2.0"' in (root / "src/app.py").read_text(encoding="utf-8")
    assert check(root) == []


def test_bump_rejects_bad_set(tmp_path):
    root = _make_repo(tmp_path)
    with pytest.raises(VersionBumpError):
        bump(root, new_version="2.0")


def test_dry_run_writes_nothing(tmp_path):
    root = _make_repo(tmp_path)
    before = (root / "src/app.py").read_text(encoding="utf-8")
    new, changes = bump(root, dry_run=True)
    assert new == "v1.11"
    assert changes
    assert (root / "src/app.py").read_text(encoding="utf-8") == before


def test_check_reports_drift(tmp_path):
    root = _make_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("v1.10", "v1.09"), encoding="utf-8"
    )
    assert any(rel == "README.md" for rel, _ in check(root))


def test_check_flags_missing_changelog_section(tmp_path):
    root = _make_repo(tmp_path)
    compact = root / "COMPACT_SUMMARY.md"
    compact.write_text(
        compact.read_text(encoding="utf-8").replace("## v1.10", "## v1.08"),
        encoding="utf-8",
    )
    assert any(rel == "COMPACT_SUMMARY.md" for rel, _ in check(root))


def test_main_check_exit_codes(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.setattr("version_bump._repo_root", lambda: root)
    assert main(["--check"]) == 0
    compact = root / "COMPACT_SUMMARY.md"
    compact.write_text(
        compact.read_text(encoding="utf-8").replace("Версия: **v1.10**", "Версия: **v1.0**"),
        encoding="utf-8",
    )
    assert main(["--check"]) == 1
    capsys.readouterr()


def test_main_bad_version_exit_code(tmp_path, monkeypatch, capsys):
    root = _make_repo(tmp_path)
    monkeypatch.setattr("version_bump._repo_root", lambda: root)
    assert main(["--set", "nope"]) == 2
    capsys.readouterr()
