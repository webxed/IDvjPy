"""Локальная диагностика `:doctor` не зависит от настоящего PATH или сети."""
from __future__ import annotations

import pytest
from rich.text import Text

import doctor
from app import CommandRunner
from i18n import current_language, set_language, t
from tests.conftest import last_info, submit


@pytest.fixture(autouse=True)
def mocked_discovery(monkeypatch):
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _name: None)
    previous = current_language()
    set_language("en")
    yield
    set_language(previous)


def test_collect_report_marks_tools_and_context_without_revealing_proxy_value():
    paths = {"git": "/usr/bin/git", "wl-copy": "/usr/bin/wl-copy"}
    report = doctor.collect_report(
        data_dir="/tmp/idvjpy",
        settings_file="/tmp/idvjpy/settings.yml",
        database_file="/tmp/idvjpy/mytags.db",
        language="en",
        scope="only git",
        terminal_mode="tab",
        environ={"HTTPS_PROXY": "https://user:password@proxy.example"},
        checks=(doctor.ToolCheck("git", "version control"), doctor.ToolCheck("jq", "JSON")),
        which=paths.get,
    )

    text = doctor.format_report(report)
    assert "data directory: /tmp/idvjpy" in text
    assert "scope:          only git" in text
    assert "terminal mode:  tab" in text
    assert "proxy:          configured" in text
    assert "user:password" not in text
    assert "✓[/green] git" in text
    assert "○[/yellow] jq" in text
    assert "wl-copy" in text


def test_report_escapes_external_rich_markup():
    report = doctor.collect_report(
        data_dir="/tmp/[bold]oops[/bold]",
        settings_file="/tmp/[red]settings.yml",
        database_file="/tmp/db[/]",
        language="en[bold]",
        scope="[link=https://example.test]scope[/link]",
        terminal_mode="window",
        checks=(doctor.ToolCheck("[bold]git[/bold]", "doctor.purpose.git"),),
        which=lambda _name: "/usr/bin/[green]git[/green]",
    )
    rendered = doctor.format_report(report)
    assert "oops" in rendered
    assert "scope" in rendered
    assert "git" in rendered
    plain = Text.from_markup(rendered).plain
    assert "[bold]oops[/bold]" in plain
    assert "[link=https://example.test]scope[/link]" in plain
    assert "[green]git[/green]" in plain
    assert "/tmp/[red]settings.yml" in plain
    assert "/tmp/db[/]" in plain
    assert "en[bold]" in plain
    assert "[bold]git[/bold]" in plain



def test_discover_packages_uses_find_spec_and_handles_failures(monkeypatch):
    calls = []

    def fake_find_spec(name):
        calls.append(name)
        if name == "anydoc":
            return None
        return object()

    monkeypatch.setattr(doctor.importlib.util, "find_spec", fake_find_spec)
    assert doctor.discover_packages() == (
        ("cryptography", "cryptography", True),
        ("firecrawl-anydoc", "anydoc", False),
    )
    assert calls == ["cryptography", "anydoc"]

    def broken_find_spec(_name):
        raise ValueError("broken spec")

    monkeypatch.setattr(doctor.importlib.util, "find_spec", broken_find_spec)
    assert all(item[2] is None for item in doctor.discover_packages())


def test_collect_report_detects_shell_helper_and_missing_clipboard():
    report = doctor.collect_report(
        data_dir=".",
        settings_file="settings.yml",
        database_file="mytags.db",
        language="ru",
        scope="",
        terminal_mode="window",
        environ={"IDVJPY_CWD_FILE": "/tmp/idvjpy-cwd"},
        checks=(),
        which=lambda _name: None,
    )

    text = doctor.format_report(report)
    assert "shell helper:   configured" in text
    assert "no Linux backend found" in text
    assert "all tags" in text


@pytest.mark.parametrize("language", ["en", "ru", "zh"])
def test_report_locales_and_python_package_independent_of_cli(language, monkeypatch):
    set_language(language)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda _name: object())
    report = doctor.collect_report(
        data_dir=".", settings_file="settings.yml", database_file="mytags.db",
        language=language, scope="", terminal_mode="window", environ={},
        which=lambda _name: None,
    )
    text = doctor.format_report(report)
    assert "doctor." not in text
    assert t("doctor.header") in text
    assert t("doctor.purpose.git") in text
    assert t("doctor.path_missing") in text
    assert "firecrawl-anydoc (anydoc): " + t("doctor.module_found") in text
    assert t("doctor.package_note") in text


async def test_doctor_is_a_dispatched_colon_command(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":doctor")
        await pilot.pause()
        text = last_info(app).text_content
        assert "IDvjPy doctor" in text
        assert "local checks only" in text
        assert "PATH" in text
