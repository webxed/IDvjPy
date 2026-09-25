"""Хранилище секретов `:vault`: шифр (`src/vault.py`) и команды TUI.

Модульные тесты — про конверт (round-trip), явные ошибки и инвариант «нет
открытого текста на диске». Тесты TUI гоняют `:vault` через маскированную
модалку (`VaultSecretScreen`) и проверяют главное правило: значение записи не
появляется ни на экране, ни в истории, — наружу оно уходит только в буфер, env
и stdin.
"""
from __future__ import annotations

import json
import os
import stat

import pytest
from textual.widgets import Input

import vault
from app import CommandBlock, CommandRunner, InfoBlock
from tests.conftest import last_info, submit

PW = "vault-pass-123"


@pytest.fixture(autouse=True)
def _clean_vault_env():
    """Не оставлять переменные, отданные `:vault use`, соседним тестам."""
    yield
    for name in ("SSH_PROD", "VAULT_TOKEN", "PGPASSWORD", "MYSQL_PWD", "MY_SECRET"):
        os.environ.pop(name, None)


# --- Модуль vault.py (без TUI) --------------------------------------------


def test_round_trip_and_no_plaintext_on_disk(tmp_path):
    path = tmp_path / "v.json.enc"
    vault.write_entries(path, PW, {"SSH_PASS": {"value": "s3cret", "hint": "prod"}})
    raw = path.read_text(encoding="utf-8")
    assert "s3cret" not in raw and "SSH_PASS" not in raw
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert vault.read_entries(path, PW) == {
        "SSH_PASS": {"value": "s3cret", "hint": "prod"}
    }


def test_wrong_password_is_explicit_error(tmp_path):
    path = tmp_path / "v.json.enc"
    vault.write_entries(path, PW, {"A": {"value": "x"}})
    with pytest.raises(vault.VaultError):
        vault.read_entries(path, "not-the-password")


def test_tampered_header_fails_integrity(tmp_path):
    path = tmp_path / "v.json.enc"
    vault.write_entries(path, PW, {"A": {"value": "x"}})
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["kdf"]["salt"] = "AAAAAAAAAAAAAAAAAAAAAA=="
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(vault.VaultError):
        vault.read_entries(path, PW)


def test_missing_and_foreign_files(tmp_path):
    with pytest.raises(vault.VaultError):
        vault.read_entries(tmp_path / "nope.enc", PW)
    foreign = tmp_path / "other.json"
    foreign.write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(vault.VaultError):
        vault.read_entries(foreign, PW)


def test_newer_version_is_refused(tmp_path):
    path = tmp_path / "v.json.enc"
    vault.write_entries(path, PW, {})
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["version"] = vault.VAULT_VERSION + 5
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(vault.VaultError):
        vault.read_entries(path, PW)


def test_entry_name_and_value_rules():
    assert vault.validate_name("MY_PASS") is None
    assert vault.validate_name("_x1") is None
    assert vault.validate_name("1bad") is not None
    assert vault.validate_name("has space") is not None
    assert vault.validate_name("a" * 65) is not None
    assert vault.check_password("short") is not None
    assert vault.check_password(PW) is None
    # Длину зажимаем в разумные границы (token_urlsafe даёт больше символов, чем n).
    assert len(vault.generate_value(1)) >= 8
    assert len(vault.generate_value(9999)) <= 512
    assert len(vault.generate_value(16)) >= 16


def test_preset_env_by_program():
    assert vault.preset_env("psql -h db -U user") == "PGPASSWORD"
    assert vault.preset_env(["sshpass", "-p", "x", "ssh", "host"]) == "SSHPASS"
    assert vault.preset_env("mysql -h db") == "MYSQL_PWD"
    assert vault.preset_env("vim notes.txt") is None


def test_crypto_unavailable_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "crypto_available", lambda: False)
    path = tmp_path / "v.json.enc"
    with pytest.raises(vault.VaultError) as exc:
        vault.read_entries(path, PW)
    assert "cryptography" in str(exc.value)
    assert vault.unavailable_hint().count("pip install cryptography") == 1


# --- Команды TUI ----------------------------------------------------------


async def _answer_modal(pilot, *values: str) -> None:
    """Заполнить модалку `VaultSecretScreen` значениями (по Enter на каждое)."""
    for value in values:
        field = pilot.app.screen.query_one("#vault-input", Input)
        field.value = value
        field.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()


def _journal_text(app: CommandRunner) -> str:
    parts = [block.text_content for block in app.query(InfoBlock)]
    parts += [block.text_content for block in app.query(CommandBlock)]
    return "\n".join(parts)


async def _init_vault(pilot) -> None:
    await submit(pilot, ":vault init")
    await _answer_modal(pilot, PW, PW)


async def test_without_cryptography_reports_hint(isolated_home, monkeypatch):
    monkeypatch.setattr(vault, "crypto_available", lambda: False)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":vault")
        assert "cryptography" in last_info(app).text_content


async def test_status_init_and_unlock_cycle(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await submit(pilot, ":vault")
        assert "No vault file yet" in last_info(app).text_content

        await _init_vault(pilot)
        assert "Vault created" in last_info(app).text_content
        assert app._vault_password == PW
        assert (isolated_home / "vault.json.enc").exists()

        # Пустое хранилище подсказывает, что делать дальше.
        await submit(pilot, ":vault")
        assert "no secrets yet" in last_info(app).text_content

        # Забыли пароль — статус снова «locked», а запрос пароля открывает.
        await submit(pilot, ":vault lock")
        assert app._vault_password is None
        await submit(pilot, ":vault")
        assert "locked" in last_info(app).text_content
        await submit(pilot, ":vault unlock")
        await _answer_modal(pilot, PW)
        assert app._vault_password == PW


async def test_unlock_with_wrong_password_stays_locked(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault lock")
        await submit(pilot, ":vault unlock")
        await _answer_modal(pilot, "wrong-password-here")
        assert app._vault_password is None
        assert "Wrong password" in last_info(app).text_content


async def test_lock_then_add_asks_password_then_value(isolated_home):
    """Запертое хранилище: `add` сначала спрашивает пароль, затем значение."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault lock")
        assert app._vault_password is None
        await submit(pilot, ":vault add LATE_SEC hint here")
        await _answer_modal(pilot, PW)  # пароль
        await _answer_modal(pilot, "late-value")  # значение
        assert "Saved LATE_SEC" in last_info(app).text_content
        assert (app._vault_entries or {}).get("LATE_SEC", {}).get("value") == "late-value"


async def test_add_list_and_value_never_shown(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add SSH_PROD prod ssh")
        await _answer_modal(pilot, "s3cret-value")
        assert "Saved SSH_PROD" in last_info(app).text_content

        await submit(pilot, ":vault list")
        text = last_info(app).text_content
        assert "SSH_PROD" in text and "prod ssh" in text
        assert "s3cret-value" not in text

        # Инвариант: значения нет ни в журнале, ни в истории, ни в файле.
        assert "s3cret-value" not in _journal_text(app)
        assert "s3cret-value" not in "\n".join(app.session_history)
        assert "s3cret-value" not in (isolated_home / "vault.json.enc").read_text(
            encoding="utf-8"
        )


async def test_generated_value_is_hidden(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault gen TOKEN_LONG 40")
        assert "Generated TOKEN_LONG" in last_info(app).text_content
        stored = (app._vault_entries or {}).get("TOKEN_LONG", {}).get("value")
        assert isinstance(stored, str) and len(stored) >= 40
        assert stored not in _journal_text(app)


async def test_cp_puts_value_in_clipboard_only(isolated_home, clip_store):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add MY_SECRET")
        await _answer_modal(pilot, "clip-value")
        await submit(pilot, ":vault cp MY_SECRET")
        assert "clipboard" in last_info(app).text_content
        assert clip_store.paste() == "clip-value"
        assert app._vault_clip_pending is True
        assert "clip-value" not in _journal_text(app)

        # Чистка буфера таймером/выходом из TTY.
        app._vault_clear_clipboard()
        assert clip_store.paste() == ""
        assert app._vault_clip_pending is False


async def test_use_exports_env_and_lock_scrubs_it(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add MY_SECRET")
        await _answer_modal(pilot, "env-value")
        await submit(pilot, ":vault use MY_SECRET")
        assert os.environ.get("MY_SECRET") == "env-value"
        assert "env-value" not in _journal_text(app)
        # Значение маскируется и в чужих выводах, пока хранилище открыто.
        assert app._mask_secrets("here: env-value") == "here: ****"

        await submit(pilot, ":vault lock")
        assert "MY_SECRET" not in os.environ
        assert app._vault_env == {}


async def test_remove_entry(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add TMP_SEC")
        await _answer_modal(pilot, "value")
        await submit(pilot, ":vault rm TMP_SEC")
        assert "Removed TMP_SEC" in last_info(app).text_content
        await submit(pilot, ":vault rm TMP_SEC")
        assert "No secret named TMP_SEC" in last_info(app).text_content


async def test_exec_uses_env_not_argv(isolated_home, monkeypatch):
    app = CommandRunner()
    calls: list[tuple[str, dict[str, str] | None]] = []
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add PGPASS")
        await _answer_modal(pilot, "db-pass")
        monkeypatch.setattr(
            app,
            "run_command",
            lambda cmd, stdin_data=None, *, no_timeout=False, extra_env=None: calls.append(
                (cmd, extra_env)
            ),
        )
        await submit(pilot, ":vault exec PGPASS -- psql -h db")
    assert calls == [("psql -h db", {"PGPASSWORD": "db-pass"})]


async def test_exec_explicit_var_and_unknown_program(isolated_home, monkeypatch):
    app = CommandRunner()
    calls: list[tuple[str, dict[str, str] | None]] = []
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add MY_SECRET")
        await _answer_modal(pilot, "token-1")
        monkeypatch.setattr(
            app,
            "run_command",
            lambda cmd, stdin_data=None, *, no_timeout=False, extra_env=None: calls.append(
                (cmd, extra_env)
            ),
        )
        await submit(pilot, ":vault exec MY_SECRET=VAULT_TOKEN -- vault read secret/x")
        assert calls == [("vault read secret/x", {"VAULT_TOKEN": "token-1"})]
        # Программа без пресета и без `NAME=VAR` — явная ошибка со списком.
        await submit(pilot, ":vault exec MY_SECRET -- vim notes.txt")
        assert "no $VAR was given" in last_info(app).text_content


async def test_stdin_feeds_value(isolated_home, monkeypatch):
    app = CommandRunner()
    calls: list[tuple[str, str | None]] = []
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add MY_SECRET")
        await _answer_modal(pilot, "sudo-pass")
        monkeypatch.setattr(
            app,
            "run_command",
            lambda cmd, stdin_data=None, *, no_timeout=False, extra_env=None: calls.append(
                (cmd, stdin_data)
            ),
        )
        await submit(pilot, ":vault stdin MY_SECRET -- sudo -S true")
    assert calls == [("sudo -S true", "sudo-pass\n")]


async def test_usage_and_unknown_subcommand(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await submit(pilot, ":vault nope")
        assert "Unknown :vault subcommand" in last_info(app).text_content
        await submit(pilot, ":vault add")
        assert "Usage: :vault" in last_info(app).text_content
        await submit(pilot, ":vault add 1bad")
        assert "letters, digits" in last_info(app).text_content
