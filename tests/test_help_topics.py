"""Темы справки `:? <тема>`: реестр, разбор ввода, подсказки и оглавление.

Тексты тем — `src/locales/help/<lang>/<имя>.txt`, реестр — `src/help_texts.py`.
Проверяем то, что легко сломать при правках: алиасы ведут к тем же текстам,
неизвестная тема — явная ошибка (а не молчаливый показ общей справки), склеенный
`:?calc` подсказывает пробел, в `main` каждой локали перечислены все темы, а
подсказки после `:? ` предлагают имена тем.
"""
from __future__ import annotations

import i18n
from app import CommandRunner
from help_texts import HELP_TOPICS, help_topic, help_topic_names, main_help
from tests.conftest import input_widget, last_info, submit


def test_topic_names_are_unique_and_have_text():
    """Реестр без дублей и без пустых текстов (пустой файл темы = её нет)."""
    names = help_topic_names()
    assert len(names) == len(set(names))
    assert set(names) == {name for name, _ in HELP_TOPICS}
    for name in names:
        assert help_topic(name), f"нет текста темы: {name}"


def test_topic_texts_exist_in_every_language():
    """Тема должна читаться на любом языке (иначе откат на `en` — молча)."""
    for lang in i18n.available_languages():
        i18n.set_language(lang)
        try:
            for name in help_topic_names():
                body = help_topic(name)
                assert body and body.strip(), f"нет справки {name} в {lang}"
        finally:
            i18n.set_language(i18n.DEFAULT_LANG)


def test_aliases_resolve_to_canonical_text():
    aliases = {
        "calculator": "calc",
        "калькулятор": "calc",
        "runbook": "run",
        "playbook": "run",
        "ingress": "i",
        "k8s": "i",
        "markdown": "md",
        "rg": "md",
        "ai": "llm",
        "tag": "tags",
        "теги": "tags",
        "secrets": "vars",
        "mailbox": "send",
        "sessions": "session",
        "new": "session",
    }
    for alias, canonical in aliases.items():
        assert help_topic(alias) == help_topic(canonical), alias


def test_unknown_topic_has_no_text():
    assert help_topic("nope") is None
    assert help_topic("") is None


def test_main_help_lists_every_topic_in_every_language():
    """Оглавление `:?` не должно расходиться с реестром тем."""
    for lang in i18n.available_languages():
        i18n.set_language(lang)
        try:
            body = main_help().lower()
            missing = [n for n in help_topic_names() if f":? {n}" not in body]
            assert not missing, f"нет темы в оглавлении {lang}: {missing}"
        finally:
            i18n.set_language(i18n.DEFAULT_LANG)


async def test_topic_shows_its_own_text(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await submit(pilot, ":? llm")
        text = last_info(app).text_content
        assert "max_attachment_bytes" in text
        # Разметка заголовка остаётся разметкой, а литеральные скобки — экранированы.
        assert "[bold]" in text and "\\[bold]" not in text
        assert "\\[tid]" in text, "литеральные скобки должны быть экранированы"
        # Общая справка не подмешивается.
        assert "Help topics" not in text


async def test_unknown_topic_reports_error(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await submit(pilot, ":? nope")
        text = last_info(app).text_content
        assert "nope" in text
        assert ":? calc" in text, "ошибка должна перечислять темы"
        assert "Help topics" not in text, "молчаливый откат на общую справку"


async def test_glued_topic_hints_space(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await submit(pilot, ":?calc")
        text = last_info(app).text_content
        assert ":? calc" in text and ":?calc" in text


async def test_plain_help_still_shows_main(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await submit(pilot, ":?")
        assert "Help topics" in last_info(app).text_content


async def test_completion_offers_topics(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        inp = input_widget(app)
        inp.value = ":? "
        inp.cursor_position = 3
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        assert clist.total_candidates == len(help_topic_names())
        assert ":? llm" in clist.all_displays
        # Буква фильтрует темы, а не весь список `:`-команд.
        inp.value = ":? t"
        inp.cursor_position = 4
        await pilot.pause()
        assert clist.all_candidates == ["tags"]
        # Тема набрана — список гаснет, дальше Enter выполняет `:? tags`.
        inp.value = ":? tags "
        inp.cursor_position = 8
        await pilot.pause()
        assert not clist.is_visible()
