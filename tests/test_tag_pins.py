from __future__ import annotations

from app import CommandRunner
from tag_pins import load_pins, pins_file_for, save_pins
from tests.conftest import last_info, submit


def test_pins_round_trip_deduplicate_and_are_session_specific(tmp_path):
    assert save_pins(str(tmp_path), "alpha", ["git", "linux", "git"])
    assert load_pins(str(tmp_path), "alpha") == (["git", "linux"], "")
    assert load_pins(str(tmp_path), "beta") == ([], "")
    assert pins_file_for("alpha") == "pins_alpha.json"
    assert (tmp_path / "pins_alpha.json").stat().st_mode & 0o777 == 0o600


def test_pins_bad_json_reports_error(tmp_path):
    (tmp_path / "pins_default.json").write_text("{}", encoding="utf-8")
    pins, error = load_pins(str(tmp_path), "default")
    assert pins == []
    assert "array" in error


async def test_pin_commands_and_catalog(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "#git git status")
        await submit(pilot, ":pin add git")
        assert "git" in last_info(app).text_content
        await submit(pilot, ":tags pinned")
        assert "★" in last_info(app).text_content
        await submit(pilot, ":pin rm git")
        await submit(pilot, ":tags pinned")
        assert "No matching" in last_info(app).text_content


async def test_pin_unknown_tag_is_rejected(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":pin add absent")
        assert "Unknown live tag" in last_info(app).text_content
