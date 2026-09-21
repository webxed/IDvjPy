"""Файловые подсказки: режимы `file_completion` = auto | paths | off.

`auto` (по умолчанию) не листит cwd для подкомандных CLI (`kubectl get po`,
`docker co`, `git ch`), но оставляет файлы у `cat`/`vim`/`grep`/… и для явных
путей (`./`, `/`, `~/`). `paths` — только явные пути и cd/pushd. `off` — выкл.
"""
from __future__ import annotations

from app import CommandRunner
from tests.conftest import input_widget, type_keys, wait_command_done


async def test_auto_skips_cwd_files_for_subcommand_clis(isolated_home):
    (isolated_home / "podfile.txt").write_text("x", encoding="utf-8")
    (isolated_home / "project.log").write_text("x", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.file_completion == "auto"
        # Подкомандные CLI — без мусора из cwd.
        assert app.get_completion_candidates("kubectl get po") == []
        assert app.get_completion_candidates("docker co") == []
        assert app.get_completion_candidates("git ch") == []
        # Команды, работающие с файлами, — файлы видны.
        assert "podfile.txt" in app.get_completion_candidates("cat po")
        assert "project.log" in app.get_completion_candidates("grep -n x pro")


async def test_auto_explicit_paths_always_work(isolated_home):
    (isolated_home / "podfile.txt").write_text("x", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Явный путь — файлы даже у подкомандного CLI.
        assert "./podfile.txt" in app.get_completion_candidates("kubectl get ./po")
        assert "./podfile.txt" in app.get_completion_candidates("cat ./po")


async def test_paths_mode_only_explicit_paths(isolated_home):
    (isolated_home / "podfile.txt").write_text("x", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.file_completion = "paths"
        assert app.get_completion_candidates("cat po") == []
        assert "./podfile.txt" in app.get_completion_candidates("cat ./po")
        # cd/pushd — путь в обоих режимах.
        assert "podfile.txt" in app.get_completion_candidates("cd po")


async def test_off_disables_file_completion(isolated_home):
    (isolated_home / "podfile.txt").write_text("x", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.file_completion = "off"
        assert app.get_completion_candidates("cat ./po") == []
        assert app.get_completion_candidates("cd po") == []
        assert app.get_completion_candidates("cat po") == []


def _cwd_files(isolated_home) -> None:
    (isolated_home / "tfile.txt").write_text("x", encoding="utf-8")
    (isolated_home / "other.txt").write_text("x", encoding="utf-8")
    (isolated_home / "subdir").mkdir()


async def test_auto_uses_the_current_command_segment(isolated_home):
    """Контекст считается по текущему сегменту: после `|`/`&&`/`;` — своя команда.

    Симптом: `cat f | grep ot` давало подсказки из cwd по `cat` — чужой токен
    оставлял висящий список, а Enter затирал набранное подсказкой.
    """
    _cwd_files(isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Чужая команда: у `grep` первый аргумент — шаблон (см. ниже), файлов нет.
        assert "other.txt" not in app.get_completion_candidates("cat tfile.txt | grep ot")
        assert "other.txt" not in app.get_completion_candidates("ls ot && echo ec")
        assert "other.txt" not in app.get_completion_candidates("cat ot; vim ec")
        # А внутри своего сегмента подсказки остаются.
        assert "other.txt" in app.get_completion_candidates("cd subdir && ls ot")
        assert "other.txt" in app.get_completion_candidates("echo x; cat ot")


async def test_pattern_commands_hint_only_after_their_pattern(isolated_home):
    """У `grep`/`sed`/`jq`/`awk` первый аргумент — шаблон, а не файл."""
    _cwd_files(isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Первый аргумент — шаблон: файловые подсказки тут только мешали бы.
        assert app.get_completion_candidates("grep ot") == []
        assert app.get_completion_candidates("rg ot") == []
        # Со второго аргумента путь идёт — подсказки нужны.
        assert "other.txt" in app.get_completion_candidates("grep -n x ot")
        assert "other.txt" in app.get_completion_candidates("sed 's/a/b/' ot")
        assert "other.txt" in app.get_completion_candidates("jq .f ot")
        assert "other.txt" in app.get_completion_candidates("awk '{print $1}' ot")
        # У файл-первых команд — как раньше, на любом аргументе.
        assert "other.txt" in app.get_completion_candidates("cat ot")
        assert "other.txt" in app.get_completion_candidates("ls -la ot")


async def test_no_stale_hints_while_typing_another_command(isolated_home):
    """Покадрово: набрал чужую команду — список подсказок закрылся, Enter запускает."""
    _cwd_files(isolated_home)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Подсказки для аргумента `cat` — законные (на них и наткнулся пользователь).
        await type_keys(pilot, "cat tfile.txt")
        await pilot.pause()
        assert app._completion_list.is_visible()
        # А дальше в строке чужая команда: список не должен висеть ни на одном символе.
        for char in " | grep ot":
            await type_keys(pilot, char)
            await pilot.pause()
            assert not app._completion_list.is_visible(), (
                f"подсказки висят на {input_widget(app).value!r}"
            )
        await pilot.press("enter")
        await pilot.pause()
        # Enter выполнил строку, а не подставил подсказку (ввод очищен).
        assert input_widget(app).value == ""


async def test_path_with_a_space_replaces_only_the_token(isolated_home):
    """Путь с пробелом — один токен: Enter не теряет префикс команды.

    Баг: кандидат с пробелом подставлялся **вместо всей строки** — `:md ./my`
    превращалось в `./my report.md`; следующий Enter выполнил бы путь как
    команду, а `:md` пропадал (заметно на документах «Еженедельный отчёт.md»).
    """
    (isolated_home / "my report.md").write_text("# hi\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_keys(pilot, ":md ./my")
        await pilot.pause()
        assert app._completion_list.is_visible()
        await pilot.press("enter")
        await pilot.pause()
        assert input_widget(app).value == ":md ./my report.md"
        # `:`-команде путь отдаётся без кавычек: она склеивает аргументы сама
        # (`handle_colon_command` → `split()`, `:md` → `" ".join(args)`).
        assert "./my report.md" in app.get_completion_candidates(":md ./my")
        # Строка не выполнена — второй Enter уже открывает markdown.
        await pilot.press("enter")
        await pilot.pause()
        assert input_widget(app).value == ""


async def test_shell_command_gets_the_path_quoted_and_runs(isolated_home):
    """Путь с пробелом у shell-команды едет в кавычках — и команда работает.

    Раньше вставлялось `cat ./my report.md`, shell делил это на два аргумента,
    и файл «не находился». У `:`-команд путь остаётся как есть — см. тест выше.
    """
    (isolated_home / "my report.md").write_text("hi\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await type_keys(pilot, "cat ./my")
        await pilot.pause()
        assert app._completion_list.is_visible()
        await pilot.press("enter")
        await pilot.pause()
        assert input_widget(app).value == "cat './my report.md'"
        await pilot.press("enter")
        block = await wait_command_done(app)
        assert block.raw_stdout.strip() == "hi"


async def test_settings_file_completion_mode(isolated_home):
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "file_completion: paths\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.file_completion == "paths"


async def test_invalid_file_completion_falls_back_to_auto(isolated_home):
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + "file_completion: nonsense\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.file_completion == "auto"
