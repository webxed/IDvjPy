"""Выбор data-каталога: --data-dir / env / portable / platform (pip-package stage 1)."""
import os
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.slow

from data_dirs import ensure_data_dir, platform_default_dir, resolve_data_dir

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_DIR = ROOT / "src" / "settings"
EXAMPLE_SETTINGS = sorted(SETTINGS_DIR.glob("*.yml"))
LLM_DIR = ROOT / "src" / "llm_providers"
EXAMPLE_LLM = sorted(LLM_DIR.glob("*.yml"))
EXPECTED_KEYS = {
    "max_lines",
    "history_lines",
    "history_keep",
    "history_completion",
    "history_forget_not_found",
    "history_queries",
    "database_tags_file",
    "backup_dir",
    "command_timeout",
    "terminal_mouse",
    "theme",
    "check_updates",
    "screensaver_idle",
    "screensaver_stars",
    "k8s_completion",
    "kctx_vars",
    "editor",
    "md_converter",
    "md_ocr",
}


@pytest.mark.parametrize("path", EXAMPLE_SETTINGS, ids=lambda p: p.name)
def test_settings_example_has_all_keys_and_defaults_to_nano(path):
    """Шаблон — источник правды: все ключи, `editor: nano`, `language: auto`."""
    text = path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    assert EXPECTED_KEYS <= set(cfg), EXPECTED_KEYS - set(cfg)
    # mcedit и прочие редакторы требуют отдельной установки — дефолт nano.
    assert cfg["editor"] == "nano"
    # Язык оставлен auto: интерфейс следует системной локали.
    assert cfg["language"] == "auto"
    # Комментарии-пояснения на месте (шаблон читают и правят руками).
    comments = [line for line in text.splitlines() if line.lstrip().startswith("#")]
    assert len(comments) >= 25


def test_settings_examples_differ_only_by_comments():
    """Языки различаются только комментариями: ключи и значения совпадают."""
    assert EXAMPLE_SETTINGS, "нет шаблонов в src/settings/*.yml"
    parsed = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in EXAMPLE_SETTINGS]
    for other in parsed[1:]:
        assert other == parsed[0]


def test_llm_providers_examples_share_structure():
    """Шаблоны провайдеров: те же провайдеры/поля, различаются языковые значения."""
    assert EXAMPLE_LLM, "нет шаблонов в src/llm_providers/*.yml"
    parsed = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in EXAMPLE_LLM]
    ref = parsed[0]
    for other in parsed[1:]:
        assert list(other["providers"]) == list(ref["providers"])
        assert other["default"] == ref["default"]
        for name, block in ref["providers"].items():
            assert set(other["providers"][name]) == set(block)


def test_llm_providers_layers_have_matching_languages():
    """Наборы языков у обоих каталогов шаблонов (и у локалей) совпадают."""
    import i18n
    from example_config import (
        available_llm_providers_languages,
        available_settings_languages,
    )

    languages = set(available_settings_languages())
    assert set(available_llm_providers_languages()) == languages
    assert languages == set(i18n.available_languages())


def test_llm_providers_defaults_are_language_specific():
    """Язык файла задаёт `answer_language`; префикс `[offline]` общий (тесты демо)."""
    expected = {"en": "English", "ru": "Russian", "zh": "Chinese"}
    for lang, name in expected.items():
        cfg = yaml.safe_load((LLM_DIR / f"{lang}.yml").read_text(encoding="utf-8"))
        assert cfg["providers"]["ds"]["answer_language"] == name
        assert cfg["providers"]["offline"]["answer"].startswith("[offline]")


def test_llm_providers_example_path_falls_back_to_en():
    from example_config import llm_providers_example_path

    zh = llm_providers_example_path("zh")
    assert zh is not None and zh.endswith("zh.yml")
    de = llm_providers_example_path("de")  # нет de → en
    assert de is not None and de.endswith("en.yml")
    assert llm_providers_example_path("")


def test_every_ui_language_has_a_settings_example():
    """У каждого языка интерфейса есть шаблон настроек (и наоборот)."""
    import i18n
    from example_config import available_settings_languages

    assert set(available_settings_languages()) == set(i18n.available_languages())


def test_settings_example_path_falls_back_to_en():
    from example_config import settings_example_path

    ru = settings_example_path("ru")
    assert ru is not None and ru.endswith("ru.yml")
    de = settings_example_path("de")  # нет de → en
    assert de is not None and de.endswith("en.yml")
    default = settings_example_path(None)
    assert default is not None and default.endswith("en.yml")
    assert settings_example_path("")


@pytest.mark.parametrize(
    ("env", "explicit", "expected"),
    [
        ({"IDVJPY_LANG": "zh"}, None, "zh"),
        ({"LC_ALL": "ru_RU.UTF-8"}, None, "ru"),
        ({"LC_MESSAGES": "zh_CN.UTF-8"}, None, "zh"),
        ({"LANG": "ru_RU.UTF-8"}, None, "ru"),
        ({"LC_ALL": "C"}, None, "en"),  # неизвестная локаль → en
        ({"LC_ALL": "ru_RU.UTF-8"}, "en", "en"),  # явный код бьёт локаль
        ({"LC_ALL": "ru_RU.UTF-8"}, "de", "en"),  # незнакомый код → en
    ],
)
def test_detect_settings_language(env, explicit, expected, monkeypatch):
    from example_config import detect_language

    for name in ("IDVJPY_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert detect_language(explicit) == expected


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


async def test_fresh_data_dir_provisioning(isolated_home, monkeypatch):
    """Новый системный data-каталог получает шаблоны settings/llm при старте."""
    from app import CommandRunner

    # Детерминированно: язык auto разрешается в en.
    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    data_dir = isolated_home / "fresh"
    app = CommandRunner(data_dir=str(data_dir))
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        settings_path = data_dir / "settings.yml"
        assert settings_path.is_file()
        text = settings_path.read_text(encoding="utf-8")
        # Скопирован именно английский шаблон (не минимальная заглушка).
        assert text == (SETTINGS_DIR / "en.yml").read_text(encoding="utf-8")
        assert "command_timeout: 10" in text
        assert "database_tags_file: mytags.db" in text
        assert "editor: nano" in text  # дефолт из шаблона (mcedit требует установки)
        llm_path = data_dir / "llm_providers.yml"
        assert llm_path.is_file()
        llm_text = llm_path.read_text(encoding="utf-8")
        assert llm_text == (LLM_DIR / "en.yml").read_text(encoding="utf-8")
        assert "providers:" in llm_text
        assert app.FILE_LLM_PROVIDERS == str(llm_path)


async def test_fresh_data_dir_provisioning_picks_language_template(
    isolated_home, monkeypatch
):
    """Язык в режиме auto определяет, какие шаблоны настроек и провайдеров скопированы."""
    from app import CommandRunner

    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    monkeypatch.setenv("LC_ALL", "ru_RU.UTF-8")
    data_dir = isolated_home / "fresh-ru"
    app = CommandRunner(data_dir=str(data_dir))
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        settings = (data_dir / "settings.yml").read_text(encoding="utf-8")
        assert settings == (SETTINGS_DIR / "ru.yml").read_text(encoding="utf-8")
        llm = (data_dir / "llm_providers.yml").read_text(encoding="utf-8")
        assert llm == (LLM_DIR / "ru.yml").read_text(encoding="utf-8")


async def test_fresh_data_dir_provisioning_respects_cli_lang(
    isolated_home, monkeypatch
):
    """Явный `--lang` бьёт системную локаль при выборе шаблона."""
    import app as app_module
    from app import CommandRunner

    monkeypatch.delenv("IDVJPY_LANG", raising=False)
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    monkeypatch.setattr(app_module, "CLI_LANGUAGE", "zh")
    data_dir = isolated_home / "fresh-zh"
    app = CommandRunner(data_dir=str(data_dir))
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        settings = (data_dir / "settings.yml").read_text(encoding="utf-8")
        assert settings == (SETTINGS_DIR / "zh.yml").read_text(encoding="utf-8")
        llm = (data_dir / "llm_providers.yml").read_text(encoding="utf-8")
        assert llm == (LLM_DIR / "zh.yml").read_text(encoding="utf-8")


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
