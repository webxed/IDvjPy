"""Выбор data-каталога: --data-dir / env / portable / platform (pip-package stage 1)."""
import os
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.slow

from data_dirs import ensure_data_dir, platform_default_dir, resolve_data_dir

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_SETTINGS = ROOT / "src" / "settings.example.yml"


def test_settings_example_has_all_keys_and_defaults_to_nano():
    """Шаблон — источник правды: все ключи и комментарии, редактор по умолчанию nano."""
    text = EXAMPLE_SETTINGS.read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    expected = {
        "max_lines",
        "history_lines",
        "history_keep",
        "database_tags_file",
        "backup_dir",
        "command_timeout",
        "terminal_mouse",
        "theme",
        "check_updates",
        "screensaver_idle",
        "screensaver_stars",
        "k8s_completion",
        "editor",
    }
    assert expected <= set(cfg), expected - set(cfg)
    # mcedit и прочие редакторы требуют отдельной установки — дефолт nano.
    assert cfg["editor"] == "nano"
    # Комментарии-пояснения на месте (шаблон читают и правят руками).
    comments = [line for line in text.splitlines() if line.lstrip().startswith("#")]
    assert len(comments) >= 25


def test_root_settings_yml_is_gitignored():
    """Личный /settings.yml не должен попасть в репозиторий."""
    patterns = [
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    ]
    assert "/settings.yml" in patterns
    # `:playbook` — локальный сценарий демо, тоже вне git.
    assert "playbook.yml" in patterns
    # Файлы, которые специально лежат в репозитории, не прячем широкими шаблонами.
    assert "!/requirements.txt" in patterns
    assert "!/requirements-dev.txt" in patterns
    assert "!/test_cmd.md" in patterns


def test_explicit_arg_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("IDVJPY_DATA_DIR", str(tmp_path / "envdir"))
    target = tmp_path / "explicit"
    target.mkdir()
    assert resolve_data_dir(str(target)) == str(target)
    # Абсолютный путь с ~ раскрывается.
    assert os.path.isabs(resolve_data_dir(str(target)))


def test_env_used_when_no_explicit(tmp_path, monkeypatch):
    monkeypatch.delenv("IDVJPY_DATA_DIR", raising=False)
    target = tmp_path / "envdir"
    target.mkdir()
    monkeypatch.setenv("IDVJPY_DATA_DIR", str(target))
    monkeypatch.chdir(tmp_path)  # settings.yml нет → не portable
    assert resolve_data_dir() == str(target)


def test_portable_cwd_when_settings_present(tmp_path, monkeypatch):
    monkeypatch.delenv("IDVJPY_DATA_DIR", raising=False)
    (tmp_path / "settings.yml").write_text("command_timeout: 5\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert resolve_data_dir() == str(tmp_path)


def test_platform_default_linux_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("IDVJPY_DATA_DIR", raising=False)
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.chdir(tmp_path)  # без settings.yml
    assert resolve_data_dir() == str(xdg / "idvjpy")


def test_platform_default_macos(tmp_path, monkeypatch):
    monkeypatch.delenv("IDVJPY_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.chdir(tmp_path)
    path = platform_default_dir()
    assert path.endswith(os.path.join("Library", "Application Support", "IDvjPy"))
    assert os.path.isabs(path)


def test_ensure_creates_directory(tmp_path):
    target = tmp_path / "nested" / "dir"
    assert ensure_data_dir(str(target)) == str(target)
    assert target.is_dir()


async def test_fresh_data_dir_provisioning(isolated_home):
    """Новый системный data-каталог получает шаблоны settings/llm при старте."""
    from app import CommandRunner

    data_dir = isolated_home / "fresh"
    app = CommandRunner(data_dir=str(data_dir))
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        settings_path = data_dir / "settings.yml"
        assert settings_path.is_file()
        text = settings_path.read_text(encoding="utf-8")
        assert "command_timeout: 10" in text
        assert "database_tags_file: mytags.db" in text
        assert "editor: nano" in text  # дефолт из шаблона (mcedit требует установки)
        llm_path = data_dir / "llm_providers.yml"
        assert llm_path.is_file()
        assert "providers:" in llm_path.read_text(encoding="utf-8")
        assert app.FILE_LLM_PROVIDERS == str(llm_path)


async def test_app_uses_data_dir_for_files(isolated_home):
    from app import CommandRunner
    from tests.conftest import submit, wait_command_done

    data_dir = isolated_home / "appdata"
    app = CommandRunner(data_dir=str(data_dir))
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, "echo hello-data")
        await wait_command_done(app, timeout=8.0)
        assert app._data_dir == str(data_dir)
        assert app.FILE_HISTORY.startswith(str(data_dir) + os.sep)
        assert app.db_file.startswith(str(data_dir) + os.sep)
        assert (data_dir / "history_default.txt").is_file()
        assert "hello-data" in (data_dir / "history_default.txt").read_text(encoding="utf-8")
