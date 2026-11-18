"""Проверка версии на GitHub для :update."""
import urllib.request

import update_check
from net import PROXY_AUTH_HINT
from update_check import (
    KIND_AHEAD,
    KIND_AVAILABLE,
    KIND_CURRENT,
    compare_versions,
    fetch_remote_version,
    format_update_fetch_error,
    format_update_status,
    parse_version_from_source,
    parse_version_tuple,
)


def test_parse_version_tuple():
    assert parse_version_tuple("v1.24") == (1, 24)
    assert parse_version_tuple("1.25") == (1, 25)
    assert parse_version_tuple("v1.2.3") == (1, 2, 3)
    assert parse_version_tuple("nope") is None


def test_parse_version_from_source():
    source = 'class CommandRunner(App):\n    VERSION = "v1.25"\n'
    assert parse_version_from_source(source) == "v1.25"
    assert parse_version_from_source("VERSION = 'nope'") is None


def test_compare_versions():
    assert compare_versions("v1.24", "v1.25") == -1
    assert compare_versions("v1.25", "v1.25") == 0
    assert compare_versions("v1.26", "v1.25") == 1
    assert compare_versions("v1.25", "1.25.0") == 0


def test_format_update_status_kinds():
    text, kind = format_update_status("v1.24", "v1.25")
    assert kind == KIND_AVAILABLE
    assert "v1.25" in text
    assert "pull" in text
    _, kind = format_update_status("v1.25", "v1.25")
    assert kind == KIND_CURRENT
    _, kind = format_update_status("v1.26", "v1.25")
    assert kind == KIND_AHEAD


def test_update_hint_points_at_the_running_copy():
    """В подсказке — готовая команда с каталогом: не надо искать, где копия."""
    text, kind = format_update_status(
        "v1.218", "v1.223", repo_dir="/home/exed/WibeCoding/Idivjopy"
    )
    assert kind == KIND_AVAILABLE
    assert 'git -C /home/exed/WibeCoding/Idivjopy pull' in text


def test_update_hint_quotes_paths_with_spaces():
    text, _ = format_update_status("v1.218", "v1.223", repo_dir="/mnt/c/My Code/IDvjPy")
    assert 'git -C "/mnt/c/My Code/IDvjPy" pull' in text


def test_update_hint_falls_back_to_url_outside_git(monkeypatch, tmp_path):
    """Без `.git` рядом (архив, пакет) `git pull` не сработает — остаётся ссылка."""
    module = tmp_path / "src" / "update_check.py"
    module.parent.mkdir()
    module.write_text("", encoding="utf-8")
    (tmp_path / "src" / "app.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(update_check, "__file__", str(module))
    assert update_check.repo_root() is None
    text, _ = format_update_status("v1.218", "v1.223")
    assert "webxed/IDvjPy" in text


def test_repo_root_is_detected_from_module_path(monkeypatch, tmp_path):
    module = tmp_path / "src" / "update_check.py"
    module.parent.mkdir()
    module.write_text("", encoding="utf-8")
    (tmp_path / "src" / "app.py").write_text("", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(update_check, "__file__", str(module))
    assert update_check.repo_root() == tmp_path


def test_fetch_remote_version(monkeypatch):
    class _Resp:
        def read(self):
            return b'    VERSION = "v9.9"\n'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    # Подменяем seam модуля: транспорт — `net.open_url` (он ставит redirect-guard), а
    # не `urllib.request.urlopen`, который при запросе уже не вызывается.
    monkeypatch.setattr(update_check, "_open_url", lambda *a, **k: _Resp())
    assert fetch_remote_version() == "v9.9"


def test_format_update_fetch_error_hints_when_407_without_user():
    err = OSError("Tunnel connection failed: 407 Proxy Authentication Required")
    text = format_update_fetch_error(err, {"HTTPS_PROXY": "http://proxy:8080"})
    assert "Could not check updates" in text
    assert "407" in text
    assert "$PROXY_USER" in text
    assert "$PROXY_PASS" in text
    assert PROXY_AUTH_HINT in text
    with_user = format_update_fetch_error(err, {"PROXY_USER": "alice"})
    assert PROXY_AUTH_HINT not in with_user
    timeout = format_update_fetch_error(TimeoutError("timed out"), {})
    assert PROXY_AUTH_HINT not in timeout
    assert "Could not check updates" in timeout


def test_fetch_remote_version_uses_proxy_auth(monkeypatch):
    seen = {}

    class _Resp:
        def read(self):
            return b'    VERSION = "v9.9"\n'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class _Opener:
        def open(self, *a, **k):
            return _Resp()

    def fake_build_opener(*handlers):
        for handler in handlers:
            if isinstance(handler, urllib.request.ProxyHandler):
                # .proxies нет в typeshed для ProxyHandler (есть в рантайме)
                seen["proxies"] = dict(getattr(handler, "proxies", {}))
        return _Opener()

    monkeypatch.setattr("update_check.urllib.request.build_opener", fake_build_opener)
    env = {
        "HTTPS_PROXY": "http://proxy.example:3128",
        "PROXY_USER": "alice",
        "PROXY_PASS": "s3cret",
    }
    assert fetch_remote_version(environ=env) == "v9.9"
    assert seen["proxies"]["https"] == "http://alice:s3cret@proxy.example:3128"


async def test_colon_update_reports_newer_remote(isolated_home, monkeypatch):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    monkeypatch.setattr("app.fetch_remote_version", lambda **k: "v9.9")
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":update")
        text = ""
        for _ in range(30):
            await pilot.pause()
            text = last_info(app).text_content
            if "v9.9" in text:
                break
        assert "v9.9" in text
        assert "Update available" in text
        # Команда целиком: каталог запущенной копии, а не голый `git pull`.
        assert "git -C " in text and " pull" in text
        assert str(update_check.repo_root()) in text


async def test_colon_update_hints_proxy_login(isolated_home, monkeypatch):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    monkeypatch.delenv("PROXY_USER", raising=False)
    monkeypatch.delenv("PROXY_PASS", raising=False)

    def boom(**_k):
        raise OSError("Tunnel connection failed: 407 Proxy Authentication Required")

    monkeypatch.setattr("app.fetch_remote_version", boom)
    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, ":update")
        text = ""
        for _ in range(30):
            await pilot.pause()
            text = last_info(app).text_content
            if "$PROXY_USER" in text:
                break
        assert "Could not check updates" in text
        assert "407" in text
        assert "$PROXY_USER" in text
        assert "$PROXY_PASS" in text
