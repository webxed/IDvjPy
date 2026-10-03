"""Синхронизация личных YAML с шаблоном (`src/settings_sync.py`).

Модуль чистый (без Textual), поэтому проверяем разбор, план и запись напрямую.
Главное свойство: свежая копия шаблона уже синхронна, а в старый личный файл
доливаются только недостающие блоки — значения и комментарии не трогаются.
"""
from __future__ import annotations

import yaml

import settings_sync
from example_config import llm_providers_example_path, settings_example_path


def _template(name: str) -> str:
    path = settings_example_path("en") if name == "settings" else llm_providers_example_path("en")
    assert path
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# --- Свежая копия шаблона уже синхронна ------------------------------------


def test_fresh_settings_template_has_nothing_to_sync():
    plan = settings_sync.plan_sync(_template("settings"), _template("settings"))
    assert plan.is_empty
    assert not plan.obsolete


def test_fresh_llm_template_has_nothing_to_sync():
    plan = settings_sync.plan_sync(_template("llm"), _template("llm"))
    assert plan.is_empty
    assert not plan.obsolete


# --- Недостающие ключи верхнего уровня --------------------------------------


def test_missing_top_level_key_is_appended():
    template = "max_lines: 1\n\nhistory_lines: 2\n"
    user = "max_lines: 99\n"
    plan, lines = settings_sync.render_sync(user, template, "v9.9")
    assert [b.key for b in plan.missing_top] == ["history_lines"]
    text = "\n".join(lines)
    assert "max_lines: 99" in text  # чужое значение не тронуто
    assert "history_lines: 2" in text
    assert "settings sync" in text
    assert yaml.safe_load(text) == {"max_lines": 99, "history_lines": 2}


def test_existing_value_different_from_template_is_kept():
    template = "editor: nano\n"
    user = "editor: vim\n"
    plan, lines = settings_sync.render_sync(user, template, "v9.9")
    assert plan.is_empty
    assert lines == ["editor: vim", ""]


def test_obsolete_key_reported_but_not_deleted():
    template = "max_lines: 1\n"
    user = "max_lines: 1\nlegacy_key: true\n"
    plan, lines = settings_sync.render_sync(user, template, "v9.9")
    assert plan.obsolete == ["legacy_key"]
    assert plan.is_empty
    assert "legacy_key: true" in "\n".join(lines)


# --- Вложенные ключи (llm_providers.yml) ------------------------------------


def test_missing_provider_is_inserted_inside_providers():
    template = (
        "default: ds\n\nproviders:\n"
        "  ds:\n    model: m\n    timeout: 1\n"
        "  grok:\n    model: g\n    timeout: 2\n"
    )
    user = "default: ds\n\nproviders:\n  ds:\n    model: mine\n    timeout: 5\n"
    plan, lines = settings_sync.render_sync(user, template, "v9.9")
    assert plan.missing_nested and plan.missing_nested[0][0] == ("providers",)
    text = "\n".join(lines)
    data = yaml.safe_load(text)
    assert data["providers"]["ds"]["model"] == "mine"  # пользовательское значение
    assert data["providers"]["ds"]["timeout"] == 5
    assert data["providers"]["grok"] == {"model": "g", "timeout": 2}
    # Новый провайдер вставлен с тем же отступом, что и существующий.
    assert "\n  grok:\n" in text


def test_missing_field_added_to_existing_provider():
    template = (
        "providers:\n"
        "  ds:\n    url: u\n    model: m\n    timeout: 7\n"
    )
    user = "providers:\n  ds:\n    url: mine\n    model: m\n"
    plan, lines = settings_sync.render_sync(user, template, "v9.9")
    assert [(p, b.key) for p, b in plan.missing_nested] == [(("providers", "ds"), "timeout")]
    text = "\n".join(lines)
    data = yaml.safe_load(text)
    assert data["providers"]["ds"] == {"url": "mine", "model": "m", "timeout": 7}


def test_obsolete_provider_reported_once():
    template = "providers:\n  ds:\n    model: m\n"
    user = "providers:\n  ds:\n    model: m\n  old:\n    model: x\n"
    plan = settings_sync.plan_sync(user, template)
    assert plan.obsolete == ["providers.old"]


# --- Запись на диск: бэкап, атомарность, идемпотентность --------------------


def test_apply_sync_creates_backup_and_is_idempotent(tmp_path):
    template = "max_lines: 1\n\nhistory_lines: 2\n"
    target = tmp_path / "settings.yml"
    target.write_text("max_lines: 99\n", encoding="utf-8")

    result = settings_sync.apply_sync(str(target), template, "v9.9", backup_dir=str(tmp_path / "backups"))
    assert result.applied and result.added == 1
    assert result.backup and (tmp_path / "backups").is_dir()
    assert yaml.safe_load(target.read_text(encoding="utf-8"))["history_lines"] == 2

    again = settings_sync.apply_sync(str(target), template, "v9.9", backup_dir=str(tmp_path / "backups"))
    assert not again.applied and again.plan.is_empty


def test_apply_sync_skips_when_nothing_missing(tmp_path):
    template = "max_lines: 1\n"
    target = tmp_path / "settings.yml"
    target.write_text("max_lines: 1\n", encoding="utf-8")
    result = settings_sync.apply_sync(str(target), template, "v9.9")
    assert not result.applied and not result.error


def test_apply_sync_on_missing_file_reports_error(tmp_path):
    result = settings_sync.apply_sync(str(tmp_path / "nope.yml"), "a: 1\n", "v9.9")
    assert not result.applied and result.error


# --- Команда `:settings` через TUI ------------------------------------------


async def test_settings_command_status_and_sync(isolated_home):
    from app import CommandRunner
    from tests.conftest import input_widget, last_info, submit

    data_dir = isolated_home / "appdata"
    app = CommandRunner(data_dir=str(data_dir))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        # Свежий каталог получает полный шаблон — синхронизировать нечего.
        await submit(pilot, ":settings")
        status = last_info(app).text_content
        assert "settings.yml" in status and "llm_providers.yml" in status
        assert "0" in status

        # Убираем ключ из личного файла — sync должен вернуть его обратно.
        settings_path = data_dir / "settings.yml"
        original = settings_path.read_text(encoding="utf-8")
        trimmed = "".join(
            line for line in original.splitlines(keepends=True)
            if not line.startswith("git_prompt:")
        )
        settings_path.write_text(trimmed, encoding="utf-8")

        await submit(pilot, ":settings sync")
        assert "git_prompt" in last_info(app).text_content
        assert input_widget(app).value == ":settings sync --yes"
        # Первый Enter только показал план — файл ещё не тронут.
        assert "git_prompt:" not in settings_path.read_text(encoding="utf-8")

        await submit(pilot, ":settings sync --yes")
        assert "git_prompt:" in settings_path.read_text(encoding="utf-8")
        assert (data_dir / "backups").is_dir()
