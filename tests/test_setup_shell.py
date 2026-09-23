"""`setup.sh --shell-helper`: функция-обёртка для shell (cwd следует за приложением).

Сменить каталог родительской оболочки дочерний процесс не может, поэтому обёртка
читает `$IDVJPY_CWD_FILE` после выхода приложения и делает `cd` (как ranger/nnn).
Установка — отдельное действие `./setup.sh --shell-helper`: правит shell-rc, а не
проект, и venv не требует (проверяется ниже).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"
_BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(_BASH is None, reason="нужен bash")

# Абсолютный путь обязателен: тесты подменяют `$PATH`, и `bash` ищется до них.
BASH = _BASH or "bash"


def _run(home: Path, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """`setup.sh` с подменённым `$HOME` — чужой `.bashrc` тестов не касается."""
    env = {k: v for k, v in os.environ.items() if k not in ("IDVJPY_RC", "ZDOTDIR")}
    env.update({"HOME": str(home), "SHELL": "/bin/bash"})
    env.update(extra_env or {})
    return subprocess.run(
        [BASH, str(SETUP), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _tool_path(tmp_path: Path, *names: str) -> str:
    """PATH только из нужных утилит — `idvjpy` в нём заведомо нет."""
    bin_dir = tmp_path / "tools"
    bin_dir.mkdir()
    for name in names:
        real = shutil.which(name)
        assert real, name
        (bin_dir / name).symlink_to(real)
    return str(bin_dir)


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def _interactive(home: Path, script: str) -> str:
    """Интерактивный bash с подменённым `$HOME` — то, что реально прочитается из rc."""
    env = {k: v for k, v in os.environ.items() if k not in ("IDVJPY_RC", "ZDOTDIR")}
    env.update({"HOME": str(home), "SHELL": "/bin/bash"})
    result = subprocess.run(
        [BASH, "-ic", script], env=env, capture_output=True, text=True, timeout=60
    )
    return result.stdout + result.stderr


def test_shell_helper_writes_wrapper_block(tmp_path):
    """Блок дописывается в конец `.bashrc`; прежнее содержимое не тронуто."""
    home = _home(tmp_path)
    (home / ".bashrc").write_text("export EDITOR=vim\n", encoding="utf-8")
    res = _run(home, "--shell-helper")
    assert res.returncode == 0, res.stderr
    rc = (home / ".bashrc").read_text(encoding="utf-8")
    assert "export EDITOR=vim" in rc
    assert "idvjpy() {" in rc
    assert "IDVJPY_CWD_FILE" in rc
    # Копия прежнего файла — рядом (страховка перед правкой чужого rc).
    assert (home / ".bashrc.idvjpy.bak").read_text(encoding="utf-8") == "export EDITOR=vim\n"


def test_shell_helper_cleanup_survives_a_rm_alias(tmp_path):
    """`alias rm='rm -i'` не должен «запечься» в тело функции.

    bash раскрывает алиасы в момент чтения rc — в том числе **внутри** определений
    функций, поэтому `rm -f` в шаблоне превращался в `rm -i -f`. С `command rm`
    разбор rc алиас не подхватывает (проверяем именно результат парсинга).
    """
    home = _home(tmp_path)
    (home / ".bashrc").write_text("alias rm='rm -i'\n", encoding="utf-8")
    assert _run(home, "--shell-helper").returncode == 0
    assert "command rm -f" in (home / ".bashrc").read_text(encoding="utf-8")
    parsed = _interactive(home, "declare -f idvjpy")
    assert "command rm -f" in parsed
    assert "rm -i -f" not in parsed


def test_shell_helper_is_idempotent(tmp_path):
    """Повторный прогон обновляет свой блок, а не копит его и пустые строки."""
    home = _home(tmp_path)
    (home / ".bashrc").write_text("export EDITOR=vim\n", encoding="utf-8")
    _run(home, "--shell-helper")
    first = (home / ".bashrc").read_text(encoding="utf-8")
    _run(home, "--shell-helper")
    again = (home / ".bashrc").read_text(encoding="utf-8")
    assert again == first
    assert again.count("idvjpy() {") == 1


def test_shell_helper_uses_idvjpy_from_path(tmp_path):
    """Есть `idvjpy` в `$PATH` — обёртка зовёт его (`command` — без рекурсии)."""
    home = _home(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "idvjpy"
    fake.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    res = _run(
        home,
        "--shell-helper",
        extra_env={"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
    )
    assert res.returncode == 0, res.stderr
    assert "command idvjpy" in (home / ".bashrc").read_text(encoding="utf-8")


def test_shell_helper_falls_back_to_repo_launcher(tmp_path):
    """Пакета нет — обёртка зовёт лаунчер этого клона абсолютным путём."""
    home = _home(tmp_path)
    path = _tool_path(tmp_path, "awk", "mktemp", "cp", "mv", "cat")
    res = _run(home, "--shell-helper", extra_env={"PATH": path})
    assert res.returncode == 0, res.stderr
    rc = (home / ".bashrc").read_text(encoding="utf-8")
    assert f"python3 '{ROOT / 'app.py'}'" in rc


def test_shell_helper_respects_idvjpy_rc(tmp_path):
    """`$IDVJPY_RC` переопределяет файл; домашний rc не создаётся."""
    home = _home(tmp_path)
    custom = home / "my_rc"
    res = _run(home, "--shell-helper", extra_env={"IDVJPY_RC": str(custom)})
    assert res.returncode == 0, res.stderr
    assert "idvjpy() {" in custom.read_text(encoding="utf-8")
    assert not (home / ".bashrc").exists()


def test_shell_helper_follows_zsh(tmp_path):
    """zsh — свой rc (`.zshrc`), а не `.bashrc`."""
    home = _home(tmp_path)
    res = _run(home, "--shell-helper", extra_env={"SHELL": "/bin/zsh"})
    assert res.returncode == 0, res.stderr
    assert "idvjpy() {" in (home / ".zshrc").read_text(encoding="utf-8")


def test_shell_helper_does_not_touch_venv(tmp_path):
    """Обёртка — отдельное действие: зависимости в этом режиме не ставятся."""
    home = _home(tmp_path)
    res = _run(home, "--shell-helper")
    assert res.returncode == 0, res.stderr
    assert "Ставлю зависимости" not in res.stdout


def test_setup_help_and_unknown_flag(tmp_path):
    home = _home(tmp_path)
    ok = _run(home, "--help")
    assert ok.returncode == 0
    assert "--shell-helper" in ok.stdout
    bad = _run(home, "--nope")
    assert bad.returncode != 0
    assert "--nope" in (bad.stdout + bad.stderr)
