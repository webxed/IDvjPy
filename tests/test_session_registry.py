"""Реестр активных сессий: `session_<имя>.pid` (см. `src/session_registry.py`).

`:new` без имени (кнопка «New session» / ``Ctrl+N``) берёт наименьшее свободное
`sN` **среди работающих** сессий. Раньше имя считалось по файлам
`history_*.txt` / `.bashrc_term_*`: они остаются от закрытых сессий, и нумерация
уползала вверх (s2, s3, s4…) на каждое нажатие, хотя работала по-прежнему одна
сессия. Здесь — юнит-уровень, без TUI.
"""
import os
import stat
import subprocess
import sys

import pytest

from session_registry import (
    active_sessions,
    free_session_name,
    pid_alive,
    read_pid,
    register,
    registry_file_for,
    registry_path,
    unregister,
)

# --- Имена и пути ----------------------------------------------------------


def test_registry_file_naming():
    assert registry_file_for("s2") == "session_s2.pid"
    assert registry_path("/data", "s3") == os.path.join("/data", "session_s3.pid")


# --- pid-файл --------------------------------------------------------------


def _dead_pid() -> int:
    """pid процесса, который уже завершился (гарантированно мёртвый)."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_pid_alive_self_dead_and_junk():
    assert pid_alive(os.getpid()) is True
    assert pid_alive(_dead_pid()) is False
    assert pid_alive(0) is False
    assert pid_alive(-1) is False


def test_read_pid_missing_junk_and_zero(tmp_path):
    assert read_pid(str(tmp_path / "nope.pid")) is None
    for name, text in (("garbage.pid", "abc\n"), ("zero.pid", "0\n"), ("empty.pid", "")):
        (tmp_path / name).write_text(text, encoding="utf-8")
        assert read_pid(str(tmp_path / name)) is None
    (tmp_path / "ok.pid").write_text(" 42 \n", encoding="utf-8")
    assert read_pid(str(tmp_path / "ok.pid")) == 42


# --- register / active_sessions -------------------------------------------


def test_register_creates_private_file_with_own_pid(tmp_path):
    assert register(str(tmp_path), "s2") is True
    path = registry_path(str(tmp_path), "s2")
    assert read_pid(path) == os.getpid()
    # Реестр не должен быть читаем другими пользователями машины.
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert active_sessions(str(tmp_path)) == ["s2"]


def test_register_creates_missing_directory(tmp_path):
    target = tmp_path / "data" / "nested"
    assert register(str(target), "s2") is True
    assert read_pid(registry_path(str(target), "s2")) == os.getpid()


def test_register_with_explicit_pid(tmp_path):
    """При `:new` резервируем pid поднятого терминала: окно перезапишет своим."""
    assert register(str(tmp_path), "s2", pid=12345) is True
    assert read_pid(registry_path(str(tmp_path), "s2")) == 12345


@pytest.mark.parametrize("bad_pid", [None, 0, -1])
def test_register_junk_pid_falls_back_to_own(tmp_path, bad_pid):
    assert register(str(tmp_path), "s2", pid=bad_pid) is True
    assert read_pid(registry_path(str(tmp_path), "s2")) == os.getpid()


def test_active_sessions_sorted(tmp_path):
    register(str(tmp_path), "s10")
    register(str(tmp_path), "s2")
    register(str(tmp_path), "alpha")
    assert active_sessions(str(tmp_path)) == ["alpha", "s10", "s2"]


def test_active_sessions_drops_stale_pid_file(tmp_path):
    """Сессия закрылась жёстко — pid мёртв, файл подчищается."""
    register(str(tmp_path), "s2", pid=_dead_pid())
    assert active_sessions(str(tmp_path)) == []
    assert not os.path.exists(registry_path(str(tmp_path), "s2"))


def test_active_sessions_ignores_broken_and_empty_names(tmp_path):
    (tmp_path / "session_s2.pid").write_text("not-a-pid\n", encoding="utf-8")
    (tmp_path / "session_s3.pid").write_text("", encoding="utf-8")
    (tmp_path / "session_.pid").write_text(str(os.getpid()), encoding="utf-8")
    assert active_sessions(str(tmp_path)) == []


def test_active_sessions_ignores_unrelated_files(tmp_path):
    (tmp_path / "history_s2.txt").write_text("seq 1\n", encoding="utf-8")
    (tmp_path / "settings.yml").write_text("", encoding="utf-8")
    assert active_sessions(str(tmp_path)) == []


def test_active_sessions_missing_dir(tmp_path):
    assert active_sessions(str(tmp_path / "nope")) == []


# --- unregister ------------------------------------------------------------


def test_unregister_removes_own_file(tmp_path):
    register(str(tmp_path), "s2")
    assert unregister(str(tmp_path), "s2") is True
    assert not os.path.exists(registry_path(str(tmp_path), "s2"))
    assert active_sessions(str(tmp_path)) == []


def test_unregister_keeps_foreign_record(tmp_path):
    """Имя успели переиспользовать — чужую запись не трогаем."""
    foreign = os.getpid() + 1
    register(str(tmp_path), "s2", pid=foreign)
    assert unregister(str(tmp_path), "s2", pid=os.getpid()) is False
    assert read_pid(registry_path(str(tmp_path), "s2")) == foreign


def test_unregister_without_pid_removes_any_record(tmp_path):
    register(str(tmp_path), "s2", pid=os.getpid() + 1)
    assert unregister(str(tmp_path), "s2") is True


def test_unregister_missing_file_is_false(tmp_path):
    assert unregister(str(tmp_path), "s2") is False


# --- free_session_name -----------------------------------------------------


def test_free_session_name_starts_at_s2(tmp_path):
    """`s1` не занимаем: им был бы «default»."""
    assert free_session_name(str(tmp_path)) == "s2"


def test_free_session_name_skips_live_sessions(tmp_path):
    register(str(tmp_path), "s2")
    assert free_session_name(str(tmp_path)) == "s3"
    register(str(tmp_path), "s3")
    assert free_session_name(str(tmp_path)) == "s4"


def test_free_session_name_reuses_closed_session(tmp_path):
    register(str(tmp_path), "s2", pid=_dead_pid())
    assert free_session_name(str(tmp_path)) == "s2"


def test_free_session_name_picks_lowest_number(tmp_path):
    """Свободное место ищем по возрастанию номера, а не по алфавиту."""
    register(str(tmp_path), "s2")
    register(str(tmp_path), "s10")
    assert free_session_name(str(tmp_path)) == "s3"


def test_free_session_name_honours_taken(tmp_path):
    assert free_session_name(str(tmp_path), taken=("s2",)) == "s3"
    assert free_session_name(str(tmp_path), taken=("s2", "s3")) == "s4"


def test_free_session_name_ignores_files_of_closed_sessions(tmp_path):
    """Суть правки: файлы закрытых сессий имя не занимают.

    `history_*.txt` / `.bashrc_term_*` остаются после выхода, поэтому имя,
    посчитанное по ним, уползало вверх на каждое нажатие «New session».
    """
    for name in ("history_s2.txt", "history_s3.txt", ".bashrc_term_s2", ".bashrc_term_s3"):
        (tmp_path / name).write_text("seq 1\n", encoding="utf-8")
    assert free_session_name(str(tmp_path)) == "s2"
