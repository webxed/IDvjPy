"""`:scope` — область видимости тегов у сессии (TUI-часть).

Модуль (`src/tag_scope.py`) проверяется в `tests/test_tag_scope.py`; здесь —
интеграция: фильтр списков и подсказок, явные адреса вопреки фильтру, маркер в
заголовке, файл сессии, независимость сессий и явная ошибка на битом файле.
"""
from __future__ import annotations

import json

import database_v2 as database
from app import CommandRunner
from screensaver import load_library_reminders
from tag_scope import MODE_HIDE, MODE_ONLY, load_scope, scope_file_for
from tests.conftest import info_texts, input_widget, last_info, submit

GIT_TAGS = ("git", "gstat")
K8S_TAGS = ("kvars", "kpod")


def _seed(db: str) -> None:
    """Две группы тегов: git (канонический набор) и k8s."""
    database.init_db(db)
    database.add_command(db, "git status", "git")
    database.add_command(db, "git status -sb", "gstat")
    database.add_command(db, "kubectl get pods -n $NS", "kpod")
    database.add_command(db, "kubectl get nodes", "kvars")


def _tags_of(db: str, tags: tuple[str, ...]) -> None:
    """Засеять только перечисленные теги (для изоляции проверок)."""
    database.init_db(db)
    for tag in tags:
        database.add_command(db, f"{tag} --help", tag)


async def test_scope_add_keeps_only_the_named_group(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")

        text = last_info(app).text_content
        assert "only git" in text
        assert app._visible_tag_names() == set(GIT_TAGS)

        # Файл сессии: `only`, только группа.
        with open(scope_file_for(app.instance_name), encoding="utf-8") as handle:
            payload = json.load(handle)
        assert payload == {"mode": MODE_ONLY, "groups": ["git"], "tags": []}


async def test_scope_hides_tags_in_listings_and_completions(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")

        # `?` — список тегов: k8s не показывается.
        await submit(pilot, "?")
        listing = last_info(app).text_content
        assert "gstat" in listing
        assert "kpod" not in listing

        # Подсказки `!tag`: только видимые.
        items, _ = app.get_bang_completions("!", 1)
        assert {item.insert for item in items} == {"!git", "!gstat"}


async def test_hidden_tag_still_addressable_and_counted(isolated_home):
    """Инвариант: scope фильтрует списки, а не команды и учёт запусков."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")

        # Явный адрес `?tag` работает и для скрытого тега.
        await submit(pilot, "?kpod")
        assert "kubectl get pods" in last_info(app).text_content

        # `!tag[tid]` подставляет команду во ввод.
        await submit(pilot, "!kpod[1]")
        assert "kubectl get pods" in input_widget(app).value

        # Учёт запусков и кэш библиотеки видят всё (иначе `:stats` «плавал» бы).
        assert "kpod" in {entry["tag"] for entry in app._library()}
        assert "kpod" not in app._visible_tag_names()

        # `:stats` — про всю библиотеку, но окно об этом предупреждает.
        await submit(pilot, ":stats")
        stats = last_info(app).text_content
        assert "kpod" in stats
        assert "Scope" in stats


async def test_double_question_filters_and_explains_scope(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")
        await submit(pilot, "??")

        listing = last_info(app).text_content
        assert "git status" in listing
        assert "kubectl get pods" not in listing
        assert "Scope: only git" in listing
        assert ":scope clear" in listing


async def test_scope_rm_switches_to_hide_mode(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope rm kpod")

        assert app._tag_scope.mode == MODE_HIDE
        visible = app._visible_tag_names()
        assert "kpod" not in visible
        assert {"git", "gstat", "kvars"} <= visible
        assert "hide kpod" in last_info(app).text_content


async def test_scope_clear_and_all_restore_everything(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")
        await submit(pilot, ":scope clear")
        assert app._tag_scope.is_empty
        assert app._visible_tag_names() == set(GIT_TAGS + K8S_TAGS)

        await submit(pilot, ":scope rm git")
        await submit(pilot, ":scope all")
        assert app._tag_scope.is_empty
        assert app._visible_tag_names() == set(GIT_TAGS + K8S_TAGS)


async def test_scope_status_without_arguments(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope")
        assert "no filter" in last_info(app).text_content

        await submit(pilot, ":scope add git")
        await submit(pilot, ":scope")
        assert "only git" in last_info(app).text_content


async def test_unknown_name_is_an_explicit_error(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add nope")

        text = last_info(app).text_content
        assert "Unknown group or tag: nope" in text
        assert "git" in text  # список групп подсказан
        assert app._tag_scope.is_empty
        assert not (isolated_home / scope_file_for(app.instance_name)).exists()


async def test_mixing_add_and_rm_is_reported(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope rm kpod")
        await submit(pilot, ":scope add git")

        assert "clear" in last_info(app).text_content
        assert app._tag_scope.mode == MODE_HIDE  # прежний scope не тронут


async def test_scope_marker_in_the_window_title(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        base = app.title
        assert "only" not in base
        await submit(pilot, ":scope add git")
        assert app.title.startswith(base)
        assert app.title.endswith("· only git")


async def test_scope_survives_restart(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")

    app2 = CommandRunner()
    async with app2.run_test(size=(100, 40)) as pilot2:
        await pilot2.pause()
        assert app2._tag_scope.label == "only git"


async def test_sessions_have_independent_scopes(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")

        await submit(pilot, ":session other")
        assert app._tag_scope.is_empty  # у новой сессии свой файл
        await submit(pilot, ":scope rm kpod")
        assert app._tag_scope.mode == MODE_HIDE

        await submit(pilot, ":session default")
        assert app._tag_scope.label == "only git"  # вернулись к своему


async def test_broken_scope_file_is_reported_not_guessed(isolated_home):
    (isolated_home / scope_file_for("default")).write_text("{not json", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await pilot.pause()

        assert app._tag_scope.is_empty  # фильтр выключен, а не «угадан»
        assert app._visible_tag_names() == set(GIT_TAGS + K8S_TAGS)
        assert any("scope_default.json" in text for text in info_texts(app))


async def test_scope_file_is_removed_when_cleared(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        _seed(app.db_file)
        app._invalidate_library()
        await submit(pilot, ":scope add git")
        path = isolated_home / scope_file_for(app.instance_name)
        assert path.exists()
        await submit(pilot, ":scope clear")
        assert not path.exists()
        scope, error = load_scope(str(isolated_home), app.instance_name)
        assert scope.is_empty and not error


def test_screensaver_ticker_respects_scope(tmp_path):
    """Заставка — тоже список: лента уважает scope сессии."""
    db = str(tmp_path / "ticks.db")
    _tags_of(db, GIT_TAGS + K8S_TAGS)
    everything = load_library_reminders(db)
    only_git = load_library_reminders(db, set(GIT_TAGS))
    assert any("git" in item for item in only_git)
    assert not any("kpod" in item or "kvars" in item for item in only_git)
    assert len(only_git) < len(everything)
