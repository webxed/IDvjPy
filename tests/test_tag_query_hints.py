"""Подсказки при наборе `?`: список тегов, фильтр по буквам и клик по строке.

Клик по пункту — «спросить библиотеку одним движением»: `?tag` вставляется
в строку и сразу выполняется (пункт помечен `run`). Клавиатура остаётся
отдельным путём: Tab/Enter вставляют `?tag` без запуска, как у `:`-команд.
"""
from __future__ import annotations

from app import CommandRunner, InfoBlock
from tests.conftest import completion_click_spans, input_widget, submit


async def _type(app: CommandRunner, pilot, value: str):
    """Набрать значение в поле ввода (без посимвольной печати)."""
    inp = input_widget(app)
    inp.value = value
    inp.cursor_position = len(value)
    await pilot.pause()
    await pilot.pause()
    return inp


async def _seed(pilot) -> None:
    """Библиотека с двумя тегами и комментарием у `vault`."""
    await submit(pilot, "#vault vault write auth/approle/login role_id=$ROLE_ID")
    await submit(pilot, "#vault vault read secret/data/app")
    await submit(pilot, "#kube kubectl get pods -n $NS")
    await submit(pilot, "#vault=HashiCorp Vault")


async def test_tag_query_lists_tags_with_hints(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _seed(pilot)
        await _type(app, pilot, "?")
        clist = app._completion_list
        assert clist.is_visible()
        assert "?vault" in clist.all_candidates
        assert "?kube" in clist.all_candidates
        # Подсказка рядом с именем: число команд и комментарий тега.
        vault = next(d for d in clist.all_displays if d.startswith("?vault"))
        assert "(2)" in vault
        assert "HashiCorp Vault" in vault


async def test_tag_query_prefix_filters_and_sorts(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _seed(pilot)
        await _type(app, pilot, "?va")
        clist = app._completion_list
        assert clist.is_visible()
        assert clist.all_candidates == ["?vault"]


async def test_tag_query_does_not_hijack_double_question(isolated_home):
    """`??` — «все команды», его список тегов не перебивает."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _seed(pilot)
        await _type(app, pilot, "??")
        clist = app._completion_list
        assert "?vault" not in clist.all_candidates


async def test_tag_query_space_closes_hints(isolated_home):
    """`?vault ` — запрос набран, подсказки не мешают."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _seed(pilot)
        await _type(app, pilot, "?vault ")
        assert not app._completion_list.is_visible()


async def test_tag_query_tab_inserts_without_running(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _seed(pilot)
        inp = await _type(app, pilot, "?va")
        await pilot.press("tab")
        await pilot.pause()
        assert inp.value == "?vault"
        assert not app.query("CommandBlock")  # ничего не запускалось


async def test_tag_query_click_line_runs_query(isolated_home):
    """Клик по строке списка: `?vault` во ввод и сразу выполнение."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _seed(pilot)
        await _type(app, pilot, "?va")
        clist = app._completion_list
        assert clist.all_candidates == ["?vault"]

        action = await _click_first_row(app, pilot, clist)
        assert action == "app.pick_completion(0)"
        assert input_widget(app).value == ""  # строка ушла на выполнение
        # Запрос выполнился: в журнале команды тега vault.
        texts = "\n".join(block.text_content for block in app.query(InfoBlock))
        assert "vault write auth/approle/login" in texts
        assert not app.query("CommandBlock")  # сам запрос — не shell-команда


async def test_completion_click_without_run_only_inserts(isolated_home):
    """Пункты без `run` (пути): клик только вставляет — как Tab."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        (isolated_home / "alpha.txt").write_text("x\n", encoding="utf-8")
        await _type(app, pilot, "ls ./alp")
        clist = app._completion_list
        assert clist.is_visible()

        assert await _click_first_row(app, pilot, clist)
        assert "./alpha.txt" in input_widget(app).value
        assert not app.query("CommandBlock")  # не выполнено


async def _click_first_row(app, pilot, clist) -> str:
    """Найти клетку со `@click` в списке и кликнуть по ней — как мышью.

    Возвращает действие, которое несла строка (проверка, что кликается
    именно пункт списка, а не что-нибудь ещё).
    """
    target = None
    for y in range(clist.region.y, clist.region.bottom):
        for x in range(clist.region.x, clist.region.right):
            style = app.screen.get_style_at(x, y)
            meta = getattr(style, "meta", None) if style is not None else None
            if meta and "@click" in meta:
                target = (x, y, meta["@click"])
                break
        if target:
            break
    assert target is not None, "в списке нет кликабельной строки"
    x, y, action = target
    assert await pilot.click(clist, offset=(x - clist.region.x, y - clist.region.y))
    await pilot.pause()
    await pilot.pause()
    return action


async def test_tag_query_link_covers_only_the_command(isolated_home):
    """Ссылка — только на команде: счётчик и комментарий остаются текстом.

    Регрессия: `[@click=…]` оборачивал всю строку, и кликабельным (а значит
    и подсвеченным) выглядело всё — `?vault  (2)  HashiCorp Vault` целиком.
    """
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await _seed(pilot)
        await _type(app, pilot, "?va")
        clist = app._completion_list
        spans = completion_click_spans(clist)
        assert list(spans.values()) == ["?vault"]

        row = next(iter(spans))
        line = clist.render_line(row).text
        assert "(2)" in line  # счётчик виден
        assert "HashiCorp" in line  # комментарий виден
        assert "(" not in spans[row]  # но они не ссылка
        assert "HashiCorp" not in spans[row]
