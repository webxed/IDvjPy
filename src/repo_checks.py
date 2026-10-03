"""Общие read-only проверки репозитория для быстрых локальных контуров."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TUI_CONTRACT_GROUPS: dict[str, tuple[str, ...]] = {
    "literal": (
        "tests/test_cmd_scenarios.py",
        "tests/test_tag_validation.py",
        "tests/test_tag_ref_click.py",
    ),
    "secrets": (
        "tests/test_secrets.py",
        "tests/test_vault.py",
        "tests/test_session_mailbox.py",
        "tests/test_clipboard_async.py",
    ),
    "history": (
        "tests/test_session_history.py",
        "tests/test_history_queries.py",
        "tests/test_output_history.py",
    ),
    "nonblocking": (
        "tests/test_command_stdio.py",
        "tests/test_write_journal.py",
        "tests/test_md_open.py",
        "tests/test_completion_cache.py",
        "tests/test_file_completion.py",
    ),
    "tty": (
        "tests/test_tty_signals.py",
        "tests/test_term_mode.py",
        "tests/test_stop_command.py",
    ),
    "routing": (
        "tests/test_colon_commands.py",
        "tests/test_commands.py",
        "tests/test_safe_mode.py",
        "tests/test_safe_mode_ui.py",
    ),
    "input-mouse": (
        "tests/test_paste_right_click.py",
        "tests/test_mouse_selection.py",
        "tests/test_completion.py",
        "tests/test_tag_ref_click.py",
    ),
}

APP_CONTRACT_TESTS = tuple(
    dict.fromkeys(test for tests in TUI_CONTRACT_GROUPS.values() for test in tests)
)


def unique(items: list[str] | tuple[str, ...]) -> list[str]:
    """Убрать повторы, сохранив детерминированный исходный порядок."""
    return list(dict.fromkeys(items))


def untracked_paths_from_porcelain(output: str) -> list[str]:
    """Извлечь неотслеживаемые пути из `git status --porcelain=v1 -z`."""
    return [entry[3:] for entry in output.split("\0") if entry.startswith("?? ")]


def git_changed_files(*, base: str | None = None, staged: bool = False) -> list[str]:
    """Изменённые и неотслеживаемые файлы Git без изменения index/worktree."""
    if staged:
        args = ["git", "diff", "--cached", "--name-only"]
    elif base:
        args = ["git", "diff", "--name-only", f"{base}...HEAD"]
    else:
        args = ["git", "diff", "--name-only", "HEAD"]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode:
        raise RuntimeError(status.stderr.strip() or "git status failed")
    return unique([
        *[line for line in result.stdout.splitlines() if line],
        *untracked_paths_from_porcelain(status.stdout),
    ])


def protected_data_paths(paths: list[str] | tuple[str, ...]) -> list[str]:
    """Пути пользовательских данных, которые не должны входить в commit."""
    bad: list[str] = []
    for raw in paths:
        path = raw.replace("\\", "/")
        if path.startswith("./"):
            path = path[2:]
        name = Path(path).name
        protected = (
            path == "settings.yml"
            or path.startswith(".codegraph/")
            or path.startswith("backups/")
            or name.endswith(".db")
            or name.startswith("history") and name.endswith(".txt")
            or name.startswith("secrets_") and ".json" in name
            or name.startswith("inbox_") and name.endswith(".jsonl")
            or name.startswith("session_") and name.endswith(".pid")
            or name in {"demo_cmd.txt", "test_ses.txt", "playbook.yml"}
            or name.startswith(".bashrc_term")
            and name not in {".bashrc_term.example"}
        )
        if protected:
            bad.append(raw)
    return bad


def focused_tests_for_path(path: str) -> list[str]:
    """Минимальный набор pytest-файлов для одной известной поверхности."""
    path = path.replace("\\", "/")
    selected: list[str] = []
    if path.startswith("tests/test_") and path.endswith(".py"):
        selected.append(path)
    if path == "src/app.py":
        selected.extend(APP_CONTRACT_TESTS)
    if path.startswith(("src/locales/", "src/i18n.py", "src/help_texts.py", "src/colon_commands.py")):
        selected.extend(("tests/test_i18n.py", "tests/test_help_topics.py", "tests/test_colon_commands.py"))
    if path.startswith(("src/seed_", "src/seed_text/")):
        selected.extend(("tests/test_seed_catalog.py", "tests/test_seed_i18n.py"))
    if path.startswith(("src/demo.py", "src/demos/")):
        selected.extend(("tests/test_demo.py", "tests/test_demo_i18n.py"))
    if path in {"src/db_transfer.py", "src/database_v2.py", "src/backup_db.py", "backup_db.py"}:
        selected.extend(("tests/test_db_transfer.py", "tests/test_backup_cli.py", "tests/test_backup_management.py"))
    if path in {"src/version_bump.py", "bump_version.py"}:
        selected.extend(("tests/test_version_bump.py", "tests/test_release_meta.py"))
    if path == ".github/workflows/tests.yml":
        selected.append("tests/test_ci_shards.py")
    if path.startswith("packaging/") or path in {"setup.py", "pyproject.toml", "MANIFEST.in"}:
        selected.append("tests/test_packaging_root.py")
    if path.startswith("docker/"):
        selected.append("tests/test_docker_stand.py")
    if path == "src/system_complete.py":
        selected.append("tests/test_system_command_completion.py")
    if path.startswith("src/") and path.endswith(".py") and path != "src/app.py":
        conventional = f"tests/test_{Path(path).stem}.py"
        if (ROOT / conventional).is_file():
            selected.append(conventional)
    return [test for test in unique(selected) if (ROOT / test).is_file()]


def focused_tests_for_paths(paths: list[str] | tuple[str, ...]) -> list[str]:
    """Минимальный набор pytest-файлов для известных изменённых поверхностей."""
    return unique([test for path in paths for test in focused_tests_for_path(path)])


def markdown_links(text: str) -> list[str]:
    """Простые Markdown-ссылки вне внешних URL; достаточно для docs guard."""
    import re

    return re.findall(r"(?<!!)\[[^]]*\]\(([^)]+)\)", text)


def local_link_error(markdown: Path, target: str) -> str | None:
    """Ошибка относительной Markdown-ссылки или None для корректной/внешней."""
    target = target.split("#", 1)[0].strip()
    if not target or "://" in target or target.startswith(("mailto:", "#")):
        return None
    destination = (markdown.parent / target).resolve()
    try:
        destination.relative_to(ROOT.resolve())
    except ValueError:
        return "link leaves repository"
    return None if destination.exists() else "target does not exist"
