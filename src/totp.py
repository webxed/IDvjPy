"""TOTP (RFC 6238) и HOTP (RFC 4226) — коды двухфакторной аутентификации.

Генератор, как в Google Authenticator: секрет (base32) лежит в зашифрованном
`:key`, наружу уходит только короткий одноразовый код на текущее окно времени.
Только stdlib (`hmac`/`hashlib`/`base64`/`struct`/`time`) и никакой сети — счётчик
берётся из системных часов, поэтому важно, чтобы они шли верно.

Модуль намеренно не знает про UI: `:key` передаёт ему секрет и параметры, а
`code_at()`/`remaining()` — чистая арифметика (в тестах время подставляется).
"""
from __future__ import annotations

import base64
import binascii
import hmac
import struct
import time
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_DIGITS = 6
DEFAULT_PERIOD = 30
DEFAULT_ALGORITHM = "sha1"
MIN_DIGITS = 6
MAX_DIGITS = 8
MIN_SECRET_CHARS = 8

ALGORITHMS: dict[str, str] = {
    "sha1": "sha1",
    "sha256": "sha256",
    "sha512": "sha512",
}

# Сколько клеток в полоске «сколько ещё живёт код».
BAR_CELLS = 24


class TotpError(Exception):
    """Понятная человеку ошибка TOTP (секрет/URI/параметры)."""


@dataclass(frozen=True)
class TotpSpec:
    """Параметры кода: секрет (уже декодированный) и настройки окна."""

    secret: bytes
    digits: int = DEFAULT_DIGITS
    period: int = DEFAULT_PERIOD
    algorithm: str = DEFAULT_ALGORITHM
    issuer: str = ""
    label: str = ""


def normalize_secret(text: str) -> str:
    """Привести base32-секрет к каноническому виду (`abcd efgh=` → `ABCDEFGH`)."""
    raw = "".join((text or "").split()).replace("-", "").rstrip("=").upper()
    return raw


def decode_secret(text: str) -> bytes:
    """base32-секрет → байты. Ошибка — явная, а не мусорный ключ."""
    raw = normalize_secret(text)
    if len(raw) < MIN_SECRET_CHARS:
        raise TotpError("The TOTP secret looks too short.")
    padded = raw + "=" * (-len(raw) % 8)
    try:
        return base64.b32decode(padded, casefold=True)
    except (binascii.Error, ValueError):
        raise TotpError("Not a base32 secret (letters A-Z and digits 2-7).") from None


def encode_secret(data: bytes) -> str:
    """Байты → канонический base32 (без паддинга): как храним секрет в vault."""
    return base64.b32encode(data).decode("ascii").rstrip("=")


def _validated(digits: int, period: int, algorithm: str) -> None:
    if not MIN_DIGITS <= int(digits) <= MAX_DIGITS:
        raise TotpError(f"digits must be {MIN_DIGITS}..{MAX_DIGITS}.")
    if int(period) <= 0:
        raise TotpError("period must be positive.")
    if algorithm not in ALGORITHMS:
        raise TotpError(f"unknown algorithm '{algorithm}' (known: sha1, sha256, sha512).")


def hotp(
    secret: bytes,
    counter: int,
    digits: int = DEFAULT_DIGITS,
    algorithm: str = DEFAULT_ALGORITHM,
) -> str:
    """HOTP из RFC 4226: HMAC-SHAx по счётчику + динамическое усечение."""
    _validated(digits, DEFAULT_PERIOD, algorithm)
    digest = hmac.new(secret, struct.pack(">Q", int(counter)), algorithm).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10 ** int(digits))).zfill(int(digits))


def counter_at(at: float | None, period: int = DEFAULT_PERIOD) -> int:
    """Номер окна времени (T / period) для момента `at` (по умолчанию — сейчас)."""
    if int(period) <= 0:
        raise TotpError("period must be positive.")
    moment = time.time() if at is None else float(at)
    return int(moment // int(period))


def code_at(
    secret: bytes,
    at: float | None = None,
    digits: int = DEFAULT_DIGITS,
    period: int = DEFAULT_PERIOD,
    algorithm: str = DEFAULT_ALGORITHM,
) -> str:
    """TOTP-код на момент `at` (RFC 6238)."""
    _validated(digits, period, algorithm)
    return hotp(secret, counter_at(at, period), digits, algorithm)


def remaining(at: float | None = None, period: int = DEFAULT_PERIOD) -> int:
    """Сколько целых секунд код ещё живёт (до конца текущего окна)."""
    if int(period) <= 0:
        raise TotpError("period must be positive.")
    moment = time.time() if at is None else float(at)
    left = int(period) - (moment % int(period))
    # Ровно на границе показываем полное окно, а не 0.
    seconds = int(left) if left < int(period) else int(period)
    return max(1, min(int(period), seconds))


def progress_bar(at: float | None = None, period: int = DEFAULT_PERIOD) -> str:
    """Полоска «сколько окна осталось»: заполнено то, что ещё живёт."""
    total = int(period)
    fraction = remaining(at, total) / total
    filled = max(0, min(BAR_CELLS, int(round(BAR_CELLS * fraction))))
    return "█" * filled + "░" * (BAR_CELLS - filled)


def grouped(code: str) -> str:
    """`123456` → `123 456` (удобнее читать и диктовать)."""
    text = str(code or "")
    half = len(text) // 2
    return f"{text[:half]} {text[half:]}" if half and len(text) % 2 == 0 else text


# --- параметры из записи хранилища ------------------------------------------


def spec_from_entry(entry: Mapping[str, object]) -> TotpSpec | None:
    """Прочитать TOTP-параметры записи `:key`; None — запись не TOTP.

    Параметры лежат в `meta` (плоские скаляры), секрет — в `value`.
    """
    if not entry or str(entry.get("kind") or "").strip().lower() != "totp":
        return None
    meta = entry.get("meta")
    values = meta if isinstance(meta, Mapping) else {}

    def number(name: str, default: int) -> int:
        value = values.get(name)
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
        return parsed

    digits = number("digits", DEFAULT_DIGITS)
    period = number("period", DEFAULT_PERIOD)
    algorithm = str(values.get("algorithm") or DEFAULT_ALGORITHM).strip().lower()
    if algorithm not in ALGORITHMS:
        algorithm = DEFAULT_ALGORITHM
    if not MIN_DIGITS <= digits <= MAX_DIGITS:
        digits = DEFAULT_DIGITS
    if period <= 0:
        period = DEFAULT_PERIOD
    secret = decode_secret(str(entry.get("value") or ""))
    return TotpSpec(
        secret=secret,
        digits=digits,
        period=period,
        algorithm=algorithm,
        issuer=str(values.get("issuer") or "").strip(),
        label=str(values.get("label") or "").strip(),
    )


def meta_from_spec(spec: TotpSpec) -> dict[str, object]:
    """`meta` для записи: только нестандартные параметры (по умолчанию — пусто)."""
    meta: dict[str, object] = {}
    if spec.digits != DEFAULT_DIGITS:
        meta["digits"] = spec.digits
    if spec.period != DEFAULT_PERIOD:
        meta["period"] = spec.period
    if spec.algorithm != DEFAULT_ALGORITHM:
        meta["algorithm"] = spec.algorithm
    if spec.issuer:
        meta["issuer"] = spec.issuer
    if spec.label:
        meta["label"] = spec.label
    return meta


# --- разбор того, что ввёл человек ------------------------------------------


def spec_from_input(text: str) -> TotpSpec:
    """Секрет или `otpauth://`-ссылка → параметры. Ошибка — явный текст.

    Сервисы рядом с QR-кодом дают либо base32-ключ, либо ссылку вида
    `otpauth://totp/Issuer:account?secret=…&issuer=…&digits=…&period=…`.
    """
    raw = (text or "").strip()
    if raw.lower().startswith("otpauth://"):
        return parse_otpauth(raw)
    return TotpSpec(secret=decode_secret(raw))


def parse_otpauth(uri: str) -> TotpSpec:
    """`otpauth://totp/…` → параметры (поддерживаем только TOTP)."""
    raw = (uri or "").strip()
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme.lower() != "otpauth":
        raise TotpError("Not an otpauth:// link.")
    if (parsed.netloc or "").strip().lower() != "totp":
        raise TotpError("Only otpauth://totp is supported (HOTP has a counter).")
    query = urllib.parse.parse_qs(parsed.query)

    def field(name: str, default: str = "") -> str:
        values = query.get(name) or []
        return (values[0] if values else default).strip()

    secret = decode_secret(field("secret"))
    algorithm = field("algorithm", DEFAULT_ALGORITHM).lower()
    if algorithm not in ALGORITHMS:
        raise TotpError(f"unknown algorithm '{algorithm}' in the link.")
    try:
        digits = int(field("digits", str(DEFAULT_DIGITS)))
        period = int(field("period", str(DEFAULT_PERIOD)))
    except ValueError:
        raise TotpError("Bad digits/period in the link.") from None
    _validated(digits, period, algorithm)
    label = urllib.parse.unquote(parsed.path.lstrip("/"))
    return TotpSpec(
        secret=secret,
        digits=digits,
        period=period,
        algorithm=algorithm,
        issuer=field("issuer") or (label.split(":", 1)[0] if ":" in label else ""),
        label=label,
    )
