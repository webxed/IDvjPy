"""Хранилище секретов `:vault`: шифр (`src/vault.py`) и команды TUI.

Модульные тесты — про конверт (round-trip), явные ошибки и инвариант «нет
открытого текста на диске». Тесты TUI гоняют `:vault` через маскированную
модалку (`VaultSecretScreen`) и проверяют главное правило: значение записи не
появляется ни на экране, ни в истории, — наружу оно уходит только в буфер, env
и stdin.
"""
from __future__ import annotations

import asyncio
import json
import os
import stat
import time

import pytest
from textual.widgets import Input, Static

import totp
import vault
from app import CommandBlock, CommandRunner, InfoBlock
from tests.conftest import last_info, submit, wait_clipboard

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
    assert vault.preset_env(["sshpass", "-e", "ssh", "host"]) == "SSHPASS"
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


async def _answer_value_modal(pilot, value: str, comment: str | None = None) -> None:
    """Окно значения (`:vault add`): значение и (опционально) поле комментария."""
    field = pilot.app.screen.query_one("#vault-input", Input)
    field.value = value
    field.focus()
    if comment is not None:
        pilot.app.screen.query_one("#vault-comment", Input).value = comment
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
        await wait_clipboard(app)
        assert clip_store.paste() == ""
        assert app._vault_clip_pending is False


async def test_use_exports_env_and_lock_keeps_it(isolated_home):
    """`lock` забывает пароль, но переменные `use` остаются в окружении (и маскируются)."""
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
        assert app._vault_password is None, "пароль забыт"
        assert os.environ.get("MY_SECRET") == "env-value", "переменная осталась"
        assert app._vault_env == {"MY_SECRET": "env-value"}
        # И после замка значение всё ещё не показывается: переменная-то жива.
        assert app._mask_secrets("here: env-value") == "here: ****"
        assert "Kept 1 exported" in last_info(app).text_content


async def test_unuse_clears_exported_vars(isolated_home):
    """Ручная очистка переменных: `:vault unuse NAME` и `:vault unuse *`."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add MY_SECRET")
        await _answer_modal(pilot, "v1")
        await submit(pilot, ":vault add SSH_PROD")
        await _answer_modal(pilot, "v2")
        await submit(pilot, ":vault use MY_SECRET")
        await submit(pilot, ":vault use SSH_PROD")
        assert os.environ.get("MY_SECRET") == "v1"
        assert os.environ.get("SSH_PROD") == "v2"

        await submit(pilot, ":vault unuse MY_SECRET")
        assert "MY_SECRET" not in os.environ
        assert os.environ.get("SSH_PROD") == "v2", "чужая переменная не тронута"
        assert "Removed 1" in last_info(app).text_content

        # Хранилище при этом не заперто — пароль не спрашивают.
        assert app._vault_password == PW
        await submit(pilot, ":vault unuse nope")
        assert "No exported variable named nope" in last_info(app).text_content

        await submit(pilot, ":vault unuse *")
        assert "SSH_PROD" not in os.environ
        assert app._vault_env == {}
        await submit(pilot, ":vault unuse *")
        assert "No exported variables to remove" in last_info(app).text_content


async def test_autolock_locks_after_idle_and_asks_password_again(isolated_home, clip_store):
    """Тишина дольше `vault_idle_lock` запирает хранилище (пароль забыт), но переменные
    `use` остаются в окружении; следующее чтение секрета снова требует пароль."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add MY_SECRET")
        await _answer_modal(pilot, "idle-value")
        await submit(pilot, ":vault use MY_SECRET")
        assert os.environ.get("MY_SECRET") == "idle-value"

        # Прошло больше срока без обращений — таймер срабатывает.
        app._vault_last_use = time.monotonic() - (app.vault_idle_lock * 60 + 5)
        app._vault_auto_lock()

        assert app._vault_password is None, "хранилище заперто по простою"
        assert app._vault_entries is None
        assert os.environ.get("MY_SECRET") == "idle-value", "переменная осталась"
        assert app._mask_secrets("x idle-value") == "x ****", "и всё ещё маскируется"
        assert "auto-locked" in last_info(app).text_content
        assert app._vault_timer is None

        # Чтение секрета снова требует пароль (а не отдаёт значение молча).
        await submit(pilot, ":vault cp MY_SECRET")
        assert type(pilot.app.screen).__name__ == "VaultSecretScreen"
        await _answer_modal(pilot, PW)
        await wait_clipboard(app)
        assert clip_store.paste() == "idle-value"


async def test_autolock_not_early_then_fires(isolated_home):
    """Сразу после обращения не запирает (перевзводит таймер)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        app._vault_last_use = time.monotonic()
        app._vault_auto_lock()
        assert app._vault_password == PW, "рано запирать нельзя"
        assert app._vault_timer is not None, "таймер перевзведён"


async def test_autolock_setting_and_session_override(isolated_home):
    """`:vault autolock N` меняет срок на сессию; 0 — выключает; статус это видит."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        assert app._vault_timer is not None, "после разблокировки таймер взведён"
        assert app.vault_idle_lock == 15  # из settings.yml по умолчанию

        await submit(pilot, ":vault autolock 0")
        assert app.vault_idle_lock == 0
        assert app._vault_timer is None
        assert "auto-lock off" in last_info(app).text_content
        await submit(pilot, ":vault")
        assert "auto-lock: off" in last_info(app).text_content

        await submit(pilot, ":vault autolock 5")
        assert app.vault_idle_lock == 5
        assert app._vault_timer is not None
        assert "5 min" in last_info(app).text_content
        await submit(pilot, ":vault autolock")
        assert "5 min" in last_info(app).text_content  # без аргумента — показать
        await submit(pilot, ":vault")
        assert "auto-lock: 5 min" in last_info(app).text_content


async def test_autolock_timer_fires_by_itself(isolated_home):
    """Настоящий таймер Textual: по тишине хранилище запирается без ручного вызова."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault autolock 0.003")  # ≈ 0.18 с
        assert app.vault_idle_lock > 0
        for _ in range(60):
            if app._vault_password is None:
                break
            await asyncio.sleep(0.05)
        assert app._vault_password is None, "таймер автоблокировки не сработал"
        assert "auto-locked" in last_info(app).text_content


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


async def test_add_modal_has_comment_field_prefilled(isolated_home):
    """В окне значения есть поле комментария; из `add NAME …` оно предзаполнено."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add API_KEY прод api")
        comment_field = pilot.app.screen.query_one("#vault-comment", Input)
        assert comment_field.value == "прод api"
        await _answer_value_modal(pilot, "k-123", "прод api;https://api.example/key")
        entry = (app._vault_entries or {})["API_KEY"]
        assert entry["value"] == "k-123"
        assert entry["hint"] == "прод api;https://api.example/key"
        # Значение — по-прежнему только в маске, в журнал не попадает.
        assert "k-123" not in _journal_text(app)
        await submit(pilot, ":vault list")
        text = last_info(app).text_content
        assert "API_KEY" in text
        assert "      прод api" in text and "      https://api.example/key" in text


async def test_add_modal_blocks_empty_value(isolated_home):
    """Enter с пустым значением окно не закрывает (иначе теряется комментарий)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add NO_VALUE")
        await _answer_value_modal(pilot, "")
        assert type(pilot.app.screen).__name__ == "VaultSecretScreen"


async def test_add_modal_value_and_comment_fields_do_not_overlap(isolated_home):
    """Поля значения и комментария видны и не накладываются друг на друга.

    Глобальный стиль приложения докит `Input` к верху контейнера; в окне `add`
    поля должно быть два и они идут в потоке — иначе комментарий закрывает
    значение (регрессия из-за `Input { dock: top }`).
    """
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add API_KEY")
        value_field = pilot.app.screen.query_one("#vault-input", Input)
        comment_field = pilot.app.screen.query_one("#vault-comment", Input)
        assert value_field.region.height > 0 and comment_field.region.height > 0
        assert value_field.region.y < comment_field.region.y
        assert value_field.region != comment_field.region
        assert pilot.app.screen.focused is value_field


async def test_comment_command_edits_without_value(isolated_home):
    """`:vault comment` — правит/показывает/снимает комментарий, значения не трогает."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add SSH_PROD")
        await _answer_value_modal(pilot, "s3cret")

        await submit(pilot, ":vault comment SSH_PROD прод ssh;ssh://deploy@host")
        entry = (app._vault_entries or {})["SSH_PROD"]
        assert entry["value"] == "s3cret", "значение не тронуто"
        assert entry["hint"] == "прод ssh;ssh://deploy@host"
        assert "s3cret" not in _journal_text(app)

        await submit(pilot, ":vault comment SSH_PROD")
        assert "прод ssh;ssh://deploy@host" in last_info(app).text_content

        # В списке несколько ссылок — каждая с новой строки.
        await submit(pilot, ":vault list")
        text = last_info(app).text_content
        assert "      прод ssh" in text and "      ssh://deploy@host" in text

        await submit(pilot, ":vault comment SSH_PROD -")
        assert "hint" not in (app._vault_entries or {})["SSH_PROD"]
        await submit(pilot, ":vault comment SSH_PROD")
        assert "(none)" in last_info(app).text_content

        await submit(pilot, ":vault comment NOPE x")
        assert "No secret named NOPE" in last_info(app).text_content


async def test_comment_shown_in_cp_and_use_not_in_status(isolated_home, clip_store):
    """Комментарий виден в `cp`/`use` (чтобы не копировать наугад), но не в `:vault`."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add SSH_PROD")
        await _answer_value_modal(pilot, "s3cret", "прод ssh")

        await submit(pilot, ":vault cp SSH_PROD")
        assert clip_store.paste() == "s3cret"
        assert "прод ssh" in last_info(app).text_content

        await submit(pilot, ":vault use SSH_PROD")
        assert "прод ssh" in last_info(app).text_content

        await submit(pilot, ":vault")
        assert "прод ssh" not in last_info(app).text_content, "статус короткий"


async def test_remove_warns_about_exported_var(isolated_home):
    """Удаление записи не трогает переменные `use`, но говорит, что значение осталось."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add MY_SECRET")
        await _answer_modal(pilot, "keep-value")
        await submit(pilot, ":vault use MY_SECRET")
        await submit(pilot, ":vault rm MY_SECRET")
        text = last_info(app).text_content
        assert "Removed MY_SECRET" in text
        assert "unuse" in text and "MY_SECRET" in text
        assert os.environ.get("MY_SECRET") == "keep-value", "переменная не снята"


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


# --- TOTP-записи (`:vault add NAME --totp`, `:vault totp NAME`) ------------

SECRET = "JBSWY3DPEHPK3PXP"
OPAUTH = (
    "otpauth://totp/ACME%20Co:john@example.com"
    "?secret=JBSWY3DPEHPK3PXP&issuer=ACME&algorithm=SHA256&digits=7&period=45"
)


def _stored_code(entry: dict) -> str:
    """Код, который обязан положить в буфер `:vault totp` (для сверки)."""
    spec = totp.spec_from_entry(entry)
    assert spec is not None
    return totp.code_at(
        spec.secret, digits=spec.digits, period=spec.period, algorithm=spec.algorithm
    )


async def test_totp_add_stores_secret_and_defaults(isolated_home):
    """`--totp` с base32-секретом: канон в `value`, лишних `meta` нет."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add OTP_PROD --totp")
        await _answer_value_modal(pilot, "jbsw y3dp ehpk 3pxp", "prod 2fa")
        assert "Saved OTP_PROD" in last_info(app).text_content
        entry = (app._vault_entries or {})["OTP_PROD"]
        assert entry["kind"] == "totp"
        assert entry["value"] == SECRET, "секрет хранится в каноне base32"
        assert "meta" not in entry, "умолчания в meta не пишем"
        assert entry["hint"] == "prod 2fa"
        # Инвариант: секрет не появляется ни в журнале, ни в файле.
        assert SECRET not in _journal_text(app)
        assert SECRET not in (isolated_home / "vault.json.enc").read_text(
            encoding="utf-8"
        )


async def test_totp_add_accepts_otpauth_link(isolated_home):
    """`--totp` со ссылкой: секрет + параметры (digits/period/algorithm/issuer)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add OTP_ACME --totp")
        await _answer_value_modal(pilot, OPAUTH, "prod 2fa;https://acme.example")
        entry = (app._vault_entries or {})["OTP_ACME"]
        assert entry["kind"] == "totp"
        assert entry["value"] == SECRET
        assert entry["meta"] == {
            "digits": 7,
            "period": 45,
            "algorithm": "sha256",
            "issuer": "ACME",
            "label": "ACME Co:john@example.com",
        }


async def test_totp_add_rejects_bad_secret(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add OTP_BAD --totp")
        await _answer_value_modal(pilot, "not-base32")
        assert "Not a TOTP secret" in last_info(app).text_content
        assert "OTP_BAD" not in (app._vault_entries or {}), "битая запись не сохраняется"


async def test_totp_list_marks_entry(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add OTP --totp")
        await _answer_value_modal(pilot, SECRET, "prod 2fa")
        await submit(pilot, ":vault add PLAIN")
        await _answer_value_modal(pilot, "just-a-value")
        await submit(pilot, ":vault list")
        text = last_info(app).text_content
        assert "OTP (totp)" in text
        assert "PLAIN" in text and "PLAIN (totp)" not in text
        assert SECRET not in text


async def test_totp_screen_copies_code_not_secret(isolated_home, clip_store):
    """Enter/`c` кладут в буфер код, а не секрет; сам секрет в журнал не идёт."""
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add OTP --totp")
        await _answer_value_modal(pilot, SECRET, "prod 2fa")
        await submit(pilot, ":vault totp OTP")
        assert type(pilot.app.screen).__name__ == "VaultTotpScreen"
        # На экране — код, не секрет.
        shown = pilot.app.screen.query_one("#totp-code", Static).content
        assert SECRET not in str(shown)

        entry = (app._vault_entries or {})["OTP"]
        await pilot.press("enter")
        await pilot.pause()
        await wait_clipboard(app)
        assert clip_store.paste() == _stored_code(entry)
        assert clip_store.paste() != SECRET
        assert app._vault_clip_pending is True
        assert SECRET not in _journal_text(app)

        # Esc — закрыть, ничего не копируя; `c` — тоже копирует.
        app._vault_clear_clipboard()
        await wait_clipboard(app)
        await submit(pilot, ":vault totp OTP")
        await pilot.press("escape")
        await pilot.pause()
        assert clip_store.paste() == "", "Esc не копирует"

        await submit(pilot, ":vault totp OTP")
        await pilot.press("c")
        await pilot.pause()
        await wait_clipboard(app)
        assert clip_store.paste() == _stored_code(entry)


async def test_totp_on_plain_entry_is_explicit(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault add PLAIN")
        await _answer_value_modal(pilot, "just-a-value")
        await submit(pilot, ":vault totp PLAIN")
        assert "is not a TOTP entry" in last_info(app).text_content
        assert type(pilot.app.screen).__name__ != "VaultTotpScreen"


async def test_totp_missing_entry_is_explicit(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 40)) as pilot:
        await _init_vault(pilot)
        await submit(pilot, ":vault totp NOPE")
        assert "No secret named NOPE" in last_info(app).text_content
