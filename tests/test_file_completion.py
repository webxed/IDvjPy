"""Файловые подсказки: режимы `file_completion` = auto | paths | off.

`auto` (по умолчанию) не листит cwd для подкомандных CLI (`kubectl get po`,
`docker co`, `git ch`), но оставляет файлы у `cat`/`vim`/`grep`/… и для явных
путей (`./`, `/`, `~/`). `paths` — только явные пути и cd/pushd. `off` — выкл.
"""
from __future__ import annotations

from app import CommandRunner


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
