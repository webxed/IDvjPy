"""Офлайн-объяснения статичны: не выполняют ввод и не возвращают его аргументы."""
from __future__ import annotations

import pytest

import explain
from app import CommandBlock, CommandRunner
from i18n import current_language, set_language, t
from tests.conftest import last_info, submit


@pytest.fixture(autouse=True)
def _english_catalogue():
    previous = current_language()
    set_language("en")
    yield
    set_language(previous)


@pytest.mark.parametrize(
    ("command", "program", "effect", "flags"),
    [
        ("git status --short --branch", "git", "reads_state", (("--short", "short"), ("--branch", "branch"))),
        ("kubectl get pods -A", "kubectl", "reads_state", (("-A", "all_namespaces"),)),
        ("terraform apply", "terraform", "may_change", ()),
        ("sqlite3 library.db 'DELETE FROM commands'", "sqlite3", "changes_data", ()),
        ("env -u TOKEN git status", "git", "reads_state", ()),
    ],
)
def test_analyse_known_commands_and_effects(command, program, effect, flags):
    result = explain.analyse(command)
    assert result.program == program
    assert result.effect == effect
    assert result.flags == flags


def test_unknown_command_does_not_claim_purpose_or_effect():
    result = explain.analyse("custom-tool --dangerous")
    assert result.purpose is None
    assert result.effect == "unknown_effect"


@pytest.mark.parametrize("command", ["git status | grep main", "git status && rm -rf /tmp/x"])
def test_compound_commands_are_not_misrepresented_as_single_command(command):
    result = explain.analyse(command)
    assert result.program is None
    assert result.effect == "unknown_effect"


def test_malformed_command_is_reported_without_echoing_input():
    rendered = explain.format_explanation("git 'secret")
    assert t("explain.parse_error") in rendered
    assert "secret" not in rendered


def test_arguments_and_live_secret_are_not_rendered():
    rendered = explain.format_explanation("curl -H 'Authorization: Bearer very-secret-token' https://private.example")
    assert "very-secret-token" not in rendered
    assert "private.example" not in rendered


async def test_explain_dispatched_without_running_command(isolated_home, monkeypatch):
    app = CommandRunner()
    def fail_if_run(*_args, **_kwargs):
        raise AssertionError(":explain must not launch commands")
    monkeypatch.setattr(app, "run_command", fail_if_run)

    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":explain kubectl get pods -A")
        await pilot.pause()
        text = last_info(app).text_content
        assert "Kubernetes command-line client" in text
        assert "reads state or output" in text
        assert "include all Kubernetes namespaces" in text
        assert not app.query(CommandBlock)


async def test_explain_usage_and_localization(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":explain")
        assert "Usage: :explain" in last_info(app).text_content

        set_language("ru")
        await submit(pilot, ":explain git status")
        assert "Разбор команды" in last_info(app).text_content
