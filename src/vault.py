"""Хранилище секретов с шифрованием по паролю (`:vault`).

Файл (`vault.json.enc` в data-каталоге, 0600) — JSON-конверт: открытый заголовок
с параметрами плюс base64-зашифрованные данные. В заголовке нет ни имён, ни
значений (это не секрет), зато он позволяет менять схему, не ломая старые файлы, и
попадает в AAD: подмена параметров/соли ломает проверку целостности.

    {"format": "idvjpy-vault", "version": 1,
     "kdf": {"name": "scrypt", "n": 32768, "r": 8, "p": 1, "salt": "…"},
     "cipher": {"name": "aes-256-gcm", "nonce": "…"},
     "data": "…"}

Ключ: scrypt от пароля и случайной соли. Данные: AES-256-GCM — неверный пароль и
испорченный файл дают явную ошибку, а не мусор на выходе.

Почему так, а не «только stdlib»: KDF взят из stdlib (`hashlib.scrypt` — у него
явный `maxmem`, тогда как у `cryptography` лимит фиксирован OpenSSL и для
n=2^15 упирается в потолок), а шифр — из проверенной `cryptography`: собирать
AEAD из кубиков самим ради экономии одной зависимости не стоит. Отсутствие
библиотеки — явное сообщение с командой установки (как у `:md` → `ocrmypdf`).

Записи — словарь `{имя: {"value": …, "hint": …, "prompt": …, "uses": …}}`.
`prompt` (шаблон приглашения) и `uses` (сколько раз можно подставить) сейчас
только хранятся: режим подстановки в чужое приглашение — отдельный шаг.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import tempfile
from collections.abc import Mapping, Sequence, Set

VAULT_FORMAT = "idvjpy-vault"
VAULT_VERSION = 1
DEFAULT_VAULT_FILE = "vault.json.enc"

# scrypt: ~32 МиБ памяти, ~0.1 с на обычной машине. Это не «на глазок»: параметры
# лежат в заголовке файла, поэтому старые хранилища читаются и после их смены.
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SCRYPT_MAXMEM = 128 * 1024 * 1024
SALT_BYTES = 16
NONCE_BYTES = 12
MIN_PASSWORD_LEN = 8
DEFAULT_GENERATED_LEN = 24

# Имя записи — как имя переменной: им же пользуются `:vault use`/`exec`.
RE_ENTRY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

# Программы, которые ждут пароль/токен в своей переменной окружения: с ними
# `:vault exec NAME -- <программа> …` работает без явного `NAME=VAR`.
ENV_PRESETS: dict[str, str] = {
    "sshpass": "SSHPASS",
    "psql": "PGPASSWORD",
    "mysql": "MYSQL_PWD",
    "mysqldump": "MYSQL_PWD",
    "vault": "VAULT_TOKEN",
    "restic": "RESTIC_PASSWORD",
    "borg": "BORG_PASSPHRASE",
    "redis-cli": "REDISCLI_AUTH",
}

INSTALL_HINT = "pip install cryptography"


class VaultError(Exception):
    """Понятная человеку ошибка хранилища (пароль, формат, доступ)."""


def crypto_available() -> bool:
    """Есть ли `cryptography` (без неё шифровать нечем)."""
    try:
        import cryptography  # noqa: F401
    except ImportError:
        return False
    return True


def unavailable_hint() -> str:
    """Что делать, если библиотеки нет."""
    return (
        f"vault needs the `cryptography` package — {INSTALL_HINT} "
        "(the core app keeps working without it)"
    )


def check_password(password: str) -> str | None:
    """Требования к паролю хранилища на `init`. None — можно, иначе текст ошибки."""
    if len(password or "") < MIN_PASSWORD_LEN:
        return f"Too short: a vault password needs at least {MIN_PASSWORD_LEN} characters."
    return None


def normalize_name(name: str) -> str:
    """Имя записи как имя переменной (`[A-Za-z_][A-Za-z0-9_]*`, до 64)."""
    return (name or "").strip()


def validate_name(name: str) -> str | None:
    """None — имя годится, иначе текст ошибки."""
    if not RE_ENTRY_NAME.match(normalize_name(name)):
        return "Name: letters, digits, _ (letter/underscore first, max 64)."
    return None


def generate_value(length: int = DEFAULT_GENERATED_LEN) -> str:
    """Случайное значение (`secrets.token_urlsafe`) — для `:vault gen`."""
    size = max(8, min(int(length or DEFAULT_GENERATED_LEN), 256))
    return secrets.token_urlsafe(size)


def preset_env(command: str | Sequence[str]) -> str | None:
    """Какая переменная окружения нужна программе (`:vault exec NAME -- cmd`)."""
    if isinstance(command, str):
        parts = command.split()
    else:
        parts = [str(part) for part in command]
    for part in parts:
        base = os.path.basename(part)
        if base in ENV_PRESETS:
            return ENV_PRESETS[base]
        if part.startswith("-"):
            continue
        if base:
            return None
    return None


def existing_names(entries: Mapping[str, Mapping[str, object]]) -> list[str]:
    return sorted(entries)


def _as_int(value: object, default: int) -> int:
    """Целое из заголовка/записи: чужая или битая форма не должна ронять чтение."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _derive_key(password: str, salt: bytes, params: Mapping[str, object]) -> bytes:
    n = _as_int(params.get("n"), SCRYPT_N)
    r = _as_int(params.get("r"), SCRYPT_R)
    p = _as_int(params.get("p"), SCRYPT_P)
    dklen = _as_int(params.get("dklen"), SCRYPT_DKLEN)
    return hashlib.scrypt(
        (password or "").encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=dklen,
        maxmem=SCRYPT_MAXMEM,
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    try:
        return base64.b64decode(str(text or ""), validate=True)
    except (binascii.Error, ValueError):
        raise VaultError("Vault file is damaged: bad base64 in the header.") from None


def _canonical(header: Mapping[str, object]) -> bytes:
    """Заголовок как AAD: те же байты, что подписывались при записи."""
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _encrypt(password: str, payload: bytes) -> dict[str, object]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(SALT_BYTES)
    params: dict[str, object] = {
        "name": "scrypt",
        "n": SCRYPT_N,
        "r": SCRYPT_R,
        "p": SCRYPT_P,
        "dklen": SCRYPT_DKLEN,
        "salt": _b64(salt),
    }
    header: dict[str, object] = {
        "format": VAULT_FORMAT,
        "version": VAULT_VERSION,
        "kdf": params,
        "cipher": {"name": "aes-256-gcm", "nonce": _b64(os.urandom(NONCE_BYTES))},
    }
    key = _derive_key(password, salt, params)
    nonce = _unb64(str(header["cipher"]["nonce"]))  # type: ignore[index]
    data = AESGCM(key).encrypt(nonce, payload, _canonical(header))
    header["data"] = _b64(data)
    return header


def _decrypt(password: str, raw: Mapping[str, object]) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    header = {key: value for key, value in raw.items() if key != "data"}
    kdf = header.get("kdf") or {}
    cipher = header.get("cipher") or {}
    if not isinstance(kdf, Mapping) or not isinstance(cipher, Mapping):
        raise VaultError("Vault file is damaged: bad header.")
    salt = _unb64(str(kdf.get("salt") or ""))
    nonce = _unb64(str(cipher.get("nonce") or ""))
    key = _derive_key(password, salt, kdf)
    payload = _unb64(str(raw.get("data") or ""))
    from cryptography.exceptions import InvalidTag

    try:
        return AESGCM(key).decrypt(nonce, payload, _canonical(header))
    except InvalidTag:
        # Отличить «неверный пароль» от «файл испорчен» криптографически нельзя:
        # и то, и другое не проходит тег. Говорим честно оба варианта.
        raise VaultError("Wrong password — or the vault file is damaged.") from None


def _load_file(path: str) -> dict[str, object]:
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        raise VaultError(f"No vault file: {path} (create one with :vault init)") from None
    except (OSError, json.JSONDecodeError):
        raise VaultError(f"Vault file is damaged: {path}") from None
    if not isinstance(raw, dict):
        raise VaultError(f"Not a vault file: {path}")
    if raw.get("format") != VAULT_FORMAT:
        raise VaultError(f"Not a vault file: {path} (another format)")
    if _as_int(raw.get("version"), 0) > VAULT_VERSION:
        raise VaultError(
            f"Vault file was written by a newer version ({raw.get('version')}); update the app."
        )
    return raw


def dump_entries(entries: Mapping[str, Mapping[str, object]]) -> list[str]:
    """Имена записей в стабильном порядке (для `:vault list`)."""
    return sorted(entries)


def sanitize_entry(raw: Mapping[str, object]) -> dict[str, object]:
    """Запись в том виде, в котором её храним (лишнее — прочь)."""
    entry: dict[str, object] = {"value": str(raw.get("value") or "")}
    hint = str(raw.get("hint") or "").strip()
    if hint:
        entry["hint"] = hint
    prompt = str(raw.get("prompt") or "").strip()
    if prompt:
        entry["prompt"] = prompt
    try:
        uses = _as_int(raw.get("uses"), 0)
    except (TypeError, ValueError):
        uses = 0
    if uses > 0:
        entry["uses"] = uses
    return entry


def read_entries(path: str, password: str) -> dict[str, dict[str, object]]:
    """Расшифровать хранилище. VaultError — нет файла/не тот пароль/порча."""
    if not crypto_available():
        raise VaultError(unavailable_hint())
    raw = _load_file(path)
    payload = _decrypt(password, raw)
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise VaultError("Vault file is damaged: bad payload.") from None
    entries = document.get("entries") if isinstance(document, dict) else None
    if not isinstance(entries, dict):
        raise VaultError("Vault file is damaged: no entries section.")
    return {
        str(name): sanitize_entry(entry)
        for name, entry in entries.items()
        if isinstance(entry, Mapping)
    }


def write_entries(
    path: str,
    password: str,
    entries: Mapping[str, Mapping[str, object]],
    *,
    created: str | None = None,
) -> None:
    """Записать хранилище атомарно и только для владельца (0600)."""
    if not crypto_available():
        raise VaultError(unavailable_hint())
    document = {
        "app": "IDvjPy_term",
        "created": created or "",
        "entries": {name: sanitize_entry(entry) for name, entry in entries.items()},
    }
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
    raw = _encrypt(password, payload)
    directory = os.path.dirname(os.path.abspath(path)) or "."
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise VaultError(f"Cannot create {directory}: {exc}") from None
    handle = None
    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".vault-", dir=directory)
        handle = os.fdopen(fd, "w", encoding="utf-8")
        os.chmod(tmp_path, 0o600)
        json.dump(raw, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
        handle.close()
        handle = None
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    except OSError as exc:
        raise VaultError(f"Cannot write {path}: {exc}") from None
    finally:
        if handle is not None:
            handle.close()
        if tmp_path and os.path.exists(tmp_path) and tmp_path != path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def vault_name_set(names: Set[str] | Sequence[str]) -> Set[str]:
    """Имена, взятые из хранилища, — их значения живут только в env процесса."""
    return {normalize_name(name) for name in names if normalize_name(name)}
