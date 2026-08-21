"""Базовые сценарии: ввод, выполнение, история, переменные, выход."""
from app import CommandBlock, CommandRunner, InfoBlock

from tests.conftest import input_widget, last_info, submit, type_keys, wait_command_done


async def test_app_starts_with_input_focused(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert input_widget(app).has_focus
        welcome = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "IDvjPy_term" in welcome
        assert "v1.24" in welcome
        assert ":?" in welcome
        assert "#tag cmd" in welcome
        assert "Define your variables" in welcome
        assert r"\]" not in welcome


async def test_starts_without_existing_database(isolated_home):
    db = isolated_home / "test_history.db"
    assert not db.exists()
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert db.is_file()
        texts = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "Empty command database" in texts
        assert "seed_linux_commands.py --seed" in texts
        assert "seed_k8s_chains.py --seed" in texts
        assert "seed_git.py --seed" in texts
        assert "seed_ops.py --seed" in texts
        assert "seed_docker.py --seed" in texts
        assert "seed_ansible.py --seed" in texts
        assert "seed_systemd.py --seed" in texts
        assert "seed_sysinfo.py --seed" in texts
        assert "seed_pipe.py --seed" in texts
        assert "seed_ip.py --seed" in texts
        assert "seed_sysstat.py --seed" in texts
        assert "seed_netdbg.py --seed" in texts
        assert "seed_pkg.py --seed" in texts
        assert "seed_user.py --seed" in texts
        assert "seed_ssh.py --seed" in texts
        assert "Ops по отдельности" in texts


async def test_seed_hint_skipped_when_database_has_commands(isolated_home):
    import database_v2 as database

    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    database.add_command(str(db), "echo hi", "demo")
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        texts = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "IDvjPy_term" in texts
        assert "Empty command database" not in texts
        assert "seed_linux_commands.py --seed" not in texts


async def test_echo_command_creates_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo ok-from-test")
        block = await wait_command_done(app)
        assert "ok-from-test" in block.raw_stdout
        assert block.return_code == 0
        assert input_widget(app).value == ""


async def test_failed_command_shows_stderr(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "ls /this-path-does-not-exist-idivjopy")
        block = await wait_command_done(app)
        assert block.return_code != 0
        assert block.raw_stderr.strip() != ""


async def test_empty_enter_does_not_create_command_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "")
        assert list(app.query(CommandBlock)) == []


async def test_session_history_up_down(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo first")
        await wait_command_done(app)
        await submit(pilot, "echo second")
        await wait_command_done(app)

        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "echo second"
        # После подстановки истории может открыться completion — Up уйдёт в список.
        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "echo first"
        await pilot.press("escape")
        await pilot.press("down")
        assert input_widget(app).value == "echo second"


async def test_history_up_filters_by_typed_text(isolated_home):
    (isolated_home / CommandRunner.FILE_HISTORY).write_text(
        "echo unrelated-aaaa\n"
        "kubectl get pods unique-hist-xyz\n"
        "ls /tmp\n"
        "kubectl describe pod unique-hist-xyz\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await type_keys(pilot, "unique-hist-xyz")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "kubectl describe pod unique-hist-xyz"
        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "kubectl get pods unique-hist-xyz"
        await pilot.press("escape")
        await pilot.press("down")
        assert input_widget(app).value == "kubectl describe pod unique-hist-xyz"
        await pilot.press("escape")
        await pilot.press("down")
        assert input_widget(app).value == "unique-hist-xyz"


async def test_colon_h_search_newest_first(isolated_home):
    (isolated_home / CommandRunner.FILE_HISTORY).write_text(
        "echo skip-me\n"
        "curl http://old-hist-grep\n"
        "curl http://old-hist-grep\n"
        "ls /tmp\n"
        "curl http://new-hist-grep\n"
        "curl http://new-hist-grep\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":h /hist-grep")
        text = last_info(app).text_content
        assert "echo skip-me" not in text
        assert "ls /tmp" not in text
        assert f"{CommandRunner.FILE_HISTORY} /hist-grep  2/2" in text
        assert text.count("old-hist-grep") == 1
        assert text.count("new-hist-grep") == 1
        assert text.index("new-hist-grep") < text.index("old-hist-grep")


async def test_colon_h_empty_slash_falls_back_to_tail(isolated_home):
    (isolated_home / CommandRunner.FILE_HISTORY).write_text("one\ntwo\nthree\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":h /")
        text = last_info(app).text_content
        assert "Usage: :h /text" not in text
        assert "one" in text
        assert "two" in text
        assert "three" in text


async def test_colon_h_slash_completes_unique_history(isolated_home):
    """`:h /` — подсказки из history.txt, без каталогов и без повторов."""
    (isolated_home / CommandRunner.FILE_HISTORY).write_text(
        "echo skip-me\n"
        "kubectl get pods\n"
        "kubectl get pods\n"
        "kubectl describe pod\n"
        "kubectl get pods\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await type_keys(pilot, ":h /kubectl")
        await pilot.pause()
        assert app._completion_list.is_visible()
        cands = app._completion_list.all_candidates
        assert cands == ["kubectl get pods", "kubectl describe pod"]
        assert cands.count("kubectl get pods") == 1
        assert "echo skip-me" not in cands
        await pilot.press("tab")
        await pilot.pause()
        assert input_widget(app).value == "kubectl get pods"


async def test_history_cache_reloads_when_file_changes(isolated_home):
    """Кэш history.txt сбрасывается, если файл дописал другой процесс."""
    path = isolated_home / CommandRunner.FILE_HISTORY
    path.write_text("echo one\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app._read_file_history() == ["echo one"]
        cached = app._history_file_stat
        assert cached is not None
        assert app._read_file_history() == ["echo one"]
        assert app._history_file_stat == cached
        path.write_text("echo one\necho two\n", encoding="utf-8")
        assert app._read_file_history() == ["echo one", "echo two"]


async def test_default_instance_writes_history_default(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo hist-default-file")
        await wait_command_done(app)
        text = (isolated_home / "history_default.txt").read_text(encoding="utf-8")
        assert "echo hist-default-file" in text
        assert not (isolated_home / "history.txt").exists()


async def test_migrates_legacy_history_txt(isolated_home):
    (isolated_home / "history.txt").write_text("echo legacy-hist\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        dest = isolated_home / CommandRunner.FILE_HISTORY
        assert dest.read_text(encoding="utf-8") == "echo legacy-hist\n"
        await type_keys(pilot, ":h /legacy-hist")
        await pilot.pause()
        assert app._completion_list.is_visible()
        assert "echo legacy-hist" in app._completion_list.all_candidates


async def test_instance_name_uses_separate_history_file(isolated_home, monkeypatch):
    monkeypatch.setattr("app.INSTANCE_NAME", "user1")
    monkeypatch.setattr(CommandRunner, "FILE_BASHRC", ".bashrc_term_user1")
    monkeypatch.setattr(CommandRunner, "FILE_HISTORY", "history_user1.txt")
    (isolated_home / "history.txt").write_text("echo from-legacy\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo inst-only")
        await wait_command_done(app)
        inst = (isolated_home / "history_user1.txt").read_text(encoding="utf-8")
        assert "echo from-legacy" in inst
        assert "echo inst-only" in inst
        shared = (isolated_home / "history.txt").read_text(encoding="utf-8")
        assert "echo inst-only" not in shared


async def test_hash_space_parks_in_history_without_running(isolated_home):
    """`# command` — в journal и history_*, без запуска и без тега."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "# curl https://parked.example/later")
        assert list(app.query(CommandBlock)) == []
        assert "# curl https://parked.example/later" in last_info(app).text_content
        hist = (isolated_home / CommandRunner.FILE_HISTORY).read_text(encoding="utf-8")
        assert "# curl https://parked.example/later" in hist

        await submit(pilot, "#logs echo still-a-tag")
        assert "Saved:" in last_info(app).text_content
        assert "logs[1]" in last_info(app).text_content
        hist = (isolated_home / CommandRunner.FILE_HISTORY).read_text(encoding="utf-8")
        assert "#logs echo still-a-tag" not in hist


def test_history_append_skips_consecutive_duplicate(isolated_home):
    from app import append_history_file_line, read_history_file_lines

    path = str(isolated_home / "history.txt")
    assert append_history_file_line(path, "echo same")
    assert not append_history_file_line(path, "echo same")
    assert append_history_file_line(path, "echo other")
    assert append_history_file_line(path, "echo same")
    lines, _ = read_history_file_lines(path)
    assert lines == ["echo same", "echo other", "echo same"]


def _mp_append_history(path: str, prefix: str, count: int) -> None:
    import sys
    from pathlib import Path

    src = str(Path(__file__).resolve().parents[1] / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from app import append_history_file_line

    for i in range(count):
        append_history_file_line(path, f"{prefix}-{i}")


def test_history_concurrent_appends(isolated_home):
    """Несколько процессов дописывают history.txt без потери строк."""
    from multiprocessing import Process

    from app import read_history_file_lines

    path = str(isolated_home / "history.txt")
    workers = 4
    each = 40
    procs = [
        Process(target=_mp_append_history, args=(path, f"w{w}", each))
        for w in range(workers)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=30)
        assert proc.exitcode == 0, proc.exitcode
    lines, _ = read_history_file_lines(path)
    expected = {f"w{w}-{i}" for w in range(workers) for i in range(each)}
    assert set(lines) == expected
    assert len(lines) == workers * each


async def test_variable_assignment_and_substitution(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$FOO=bar-test")
        assert "Variable $FOO set to 'bar-test'" in last_info(app).text_content
        assert app.local_env["FOO"] == "bar-test"

        await submit(pilot, "echo $FOO")
        block = await wait_command_done(app)
        assert "bar-test" in block.raw_stdout


async def test_out_placeholder_is_lazy_last_line(isolated_home):
    """$OUT читает последнюю строку блока только в момент команды, не пишется в env."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "printf 'aaa\\nbbb\\n'")
        await wait_command_done(app)
        assert "OUT" not in app.local_env

        await submit(pilot, "echo Hello, $OUT")
        block = await wait_command_done(app)
        assert "Hello, bbb" in block.raw_stdout
        assert "OUT" not in app.local_env

        await submit(pilot, "$OUT=nope")
        assert "not stored" in last_info(app).text_content
        assert "OUT" not in app.local_env

        await submit(pilot, "$OUT")
        assert "bbb" in last_info(app).text_content


async def test_echo_myvar_from_legacy_bashrc_term(isolated_home):
    """`.bashrc_term` с MYVAR не должен теряться из‑за `.bashrc_term_default` с NS."""
    (isolated_home / ".bashrc_term").write_text(
        '# Terminal-specific bashrc file\nexport MYVAR="1"\n',
        encoding="utf-8",
    )
    (isolated_home / ".bashrc_term_default").write_text(
        '# Terminal-specific environment variables\nexport NS="markovskiy"\n',
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.local_env.get("MYVAR") == "1"
        assert app.local_env.get("NS") == "markovskiy"
        await submit(pilot, "echo $MYVAR")
        block = await wait_command_done(app)
        assert "1" in block.raw_stdout


async def test_colon_clear_and_quit(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo keep-me")
        await wait_command_done(app)
        await submit(pilot, ":c")
        texts = [block.text_content for block in app.query(InfoBlock)]
        assert any("All blocks cleared" in text for text in texts)
        assert list(app.query(CommandBlock)) == []

        await submit(pilot, ":q")
    # Context manager exits cleanly after :q.


async def test_shift_insert_pastes_into_input(isolated_home, monkeypatch):
    monkeypatch.setattr("pyperclip.paste", lambda: "pasted-value")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "echo ")
        await pilot.press("shift+insert")
        await pilot.pause()
        assert "pasted-value" in input_widget(app).value


async def test_ctrl_d_clears_input_line(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "echo keep-this")
        await pilot.pause()
        inp = input_widget(app)
        assert inp.value == "echo keep-this"
        await pilot.press("ctrl+d")
        await pilot.pause()
        assert inp.value == ""
        assert inp.has_focus


async def test_ctrl_c_copies_whole_input_line(isolated_home):
    import pyperclip

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "echo copy-all-input")
        await pilot.pause()
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert pyperclip.paste() == "echo copy-all-input"
        assert input_widget(app).value == "echo copy-all-input"
        assert input_widget(app).has_focus


async def test_ctrl_c_on_block_copies_stdout(isolated_home):
    import pyperclip
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo copied-from-block")
        await wait_command_done(app)
        await pilot.press("tab")
        await pilot.pause()
        assert isinstance(app.focused, CommandBlock)
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert "copied-from-block" in pyperclip.paste()


async def test_tty_prefix_empty_shows_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ">")
        assert "Usage:" in last_info(app).text_content
        await submit(pilot, ">   ")
        assert "Usage:" in last_info(app).text_content


async def test_tty_prefix_runs_substituted_command(isolated_home, monkeypatch):
    ran = []

    def fake_tty(self, command):
        ran.append(command)
        return 0

    monkeypatch.setattr(CommandRunner, "_run_in_tty", fake_tty)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$HOST=example.com")
        await submit(pilot, "> ssh $HOST")
        assert ran == ["ssh example.com"]
        text = last_info(app).text_content
        assert "TTY:" in text
        assert "ssh example.com" in text
        assert "Exit code: 0" in text
        assert "> ssh $HOST" in app.session_history


async def test_tty_prefix_no_space(isolated_home, monkeypatch):
    ran = []
    monkeypatch.setattr(CommandRunner, "_run_in_tty", lambda self, command: ran.append(command) or 3)
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ">true")
        assert ran == ["true"]
        assert "Exit code: 3" in last_info(app).text_content


async def test_cd_changes_app_cwd(isolated_home):
    import os
    from pathlib import Path

    sub = isolated_home / "inner"
    sub.mkdir()
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        start = os.getcwd()
        await submit(pilot, "cd inner")
        assert os.getcwd() == str(sub.resolve())
        assert f"cwd: {sub.resolve()}" in last_info(app).text_content
        await submit(pilot, "cd -")
        assert os.getcwd() == start


async def test_colon_cd_and_missing_dir(isolated_home):
    import os

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        here = os.getcwd()
        await submit(pilot, ":cd")
        assert here in last_info(app).text_content
        await submit(pilot, ":cd no-such-idivjopy-dir")
        assert "not a directory" in last_info(app).text_content
        assert os.getcwd() == here


async def test_replay_puts_command_in_input(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo replay-me-please")
        await wait_command_done(app)
        await submit(pilot, ":r")
        assert "echo replay-me-please" in input_widget(app).value


async def test_journal_search_focuses_matching_block(isolated_home):
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo search-alpha-unique")
        await wait_command_done(app)
        await submit(pilot, "echo search-omega-unique")
        await wait_command_done(app)
        await submit(pilot, ":/search-alpha-unique")
        assert isinstance(app.focused, CommandBlock)
        assert "search-alpha-unique" in (app.focused.source_command or app.focused.header)
        assert app.focused.line_nav_active
        assert "search-alpha-unique" in app.focused._current_plain_line()


async def test_journal_search_jumps_to_matching_line(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "seq 1 40")
        await wait_command_done(app)
        await submit(pilot, ":/27")
        assert isinstance(app.focused, CommandBlock)
        assert app.focused.line_nav_active
        assert app.focused._current_plain_line().strip() == "27"


async def test_journal_search_next_and_prev_line(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "python3 -c 'print(\"aaa-hit\"); print(\"bbb\"); print(\"aaa-hit\")'")
        await wait_command_done(app)
        await submit(pilot, ":/aaa-hit")
        assert isinstance(app.focused, CommandBlock)
        first = app.focused.line_index
        assert "aaa-hit" in app.focused._current_plain_line()
        await pilot.press("escape")
        await submit(pilot, ":n")
        second = app.focused.line_index
        assert second > first
        assert "aaa-hit" in app.focused._current_plain_line()
        await pilot.press("escape")
        await submit(pilot, ":N")
        assert app.focused.line_index == first


async def test_theme_loaded_from_settings(isolated_home):
    settings = isolated_home / "settings.yml"
    settings.write_text(settings.read_text(encoding="utf-8") + "theme: textual-light\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.theme == "textual-light"


async def test_toggle_dark_saves_theme(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        before = app.theme
        app.action_toggle_dark()
        await pilot.pause()
        assert app.theme != before
        saved = (isolated_home / "settings.yml").read_text(encoding="utf-8")
        assert f"theme: {app.theme}" in saved


async def test_colon_theme_sets_and_lists(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":theme nord")
        assert app.theme == "nord"
        assert "theme: nord" in (isolated_home / "settings.yml").read_text(encoding="utf-8")
        await submit(pilot, ":theme")
        listed = last_info(app).text_content
        assert "nord" in listed
        assert "Available:" in listed
        await submit(pilot, ":theme not-a-theme")
        assert "Unknown theme" in last_info(app).text_content
        assert app.theme == "nord"
