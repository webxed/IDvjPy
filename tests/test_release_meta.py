"""Метаданные release: документация и тесты должны называть текущую CommandRunner.VERSION.

Держит ручное правило «версия = коммит» честным: версия приложения живёт в
src/app.py, а README / CLAUDE / AGENTS / COMPACT_SUMMARY / test_cmd.md должны
следовать за ней в одном коммите. ``:update`` сравнивает ту же строку VERSION
с main на GitHub, поэтому расхождение документа и приложения вводило бы в
заблуждение проверку обновлений.
"""
import re
from pathlib import Path

from app import CommandRunner

ROOT = Path(__file__).resolve().parents[1]

_MATCH = re.fullmatch(r"v(\d+)\.(\d+)", CommandRunner.VERSION)
assert _MATCH, f"CommandRunner.VERSION has an unexpected shape: {CommandRunner.VERSION!r}"
CURRENT = CommandRunner.VERSION
NEXT = f"v{_MATCH.group(1)}.{int(_MATCH.group(2)) + 1}"


def test_app_source_names_version():
    text = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    assert f'VERSION = "{CURRENT}"' in text


def test_readme_names_version():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"**IDvjPy_term** {CURRENT} —" in text


def test_localized_readmes_name_version():
    """Локализованные README (docs/<lang>/) носят тот же маркер версии."""
    for rel in ("docs/en/README.md", "docs/zh/README.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert f"**IDvjPy_term** {CURRENT} —" in text, rel


def test_compact_summary_names_version():
    text = (ROOT / "COMPACT_SUMMARY.md").read_text(encoding="utf-8")
    assert f"Версия: **{CURRENT}**." in text
    assert f"| `src/app.py` | TUI (`CommandRunner`), {CURRENT} |" in text
    assert f"## {CURRENT}" in text  # раздел changelog для этого релиза


def test_claude_names_version_and_next_bump():
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert f"IDvjPy_term ({CURRENT})" in text
    assert f"(`{CURRENT}` → `{NEXT}`)" in text


def test_agents_names_next_bump():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert f"(`{CURRENT}` → `{NEXT}`)" in text


def test_manual_test_plan_names_version():
    text = (ROOT / "test_cmd.md").read_text(encoding="utf-8")
    assert f"# План тестирования IDvjPy_term {CURRENT}" in text
    assert f"**Версия приложения**: {CURRENT}" in text


def test_cmd_scenarios_docstring_names_version():
    text = (ROOT / "tests" / "test_cmd_scenarios.py").read_text(encoding="utf-8")
    assert f"(IDvjPy_term {CURRENT})" in text
