"""GitHub version check for :update."""
from update_check import (
    KIND_AHEAD,
    KIND_AVAILABLE,
    KIND_CURRENT,
    compare_versions,
    fetch_remote_version,
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
    assert "git pull" in text
    assert "webxed/IDvjPy" in text
    _, kind = format_update_status("v1.25", "v1.25")
    assert kind == KIND_CURRENT
    _, kind = format_update_status("v1.26", "v1.25")
    assert kind == KIND_AHEAD


def test_fetch_remote_version(monkeypatch):
    class _Resp:
        def read(self):
            return b'    VERSION = "v9.9"\n'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("update_check.urllib.request.urlopen", lambda *a, **k: _Resp())
    assert fetch_remote_version() == "v9.9"


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
        assert "git pull" in text
