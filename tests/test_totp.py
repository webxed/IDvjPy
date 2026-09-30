"""TOTP/HOTP (`src/totp.py`) — коды двухфакторной аутентификации.

Проверяем по векторам из RFC 6238 (Appendix B) и RFC 4226 (Appendix D): там
зафиксированы и секреты, и время, и ожидаемые коды — гадать не приходится.
"""
from __future__ import annotations

import pytest

import totp

# RFC 6238: секрет зависит от алгоритма (Appendix B).
RFC_SECRETS = {
    "sha1": b"12345678901234567890",
    "sha256": b"12345678901234567890123456789012",
    "sha512": b"1234567890123456789012345678901234567890123456789012345678901234",
}

# время → (sha1, sha256, sha512), 8 цифр
RFC_VECTORS = {
    59: ("94287082", "46119246", "90693936"),
    1111111109: ("07081804", "68084774", "25091201"),
    1111111111: ("14050471", "67062674", "99943326"),
    1234567890: ("89005924", "91819424", "93441116"),
    2000000000: ("69279037", "90698825", "38618901"),
    20000000000: ("65353130", "77737706", "47863826"),
}

# RFC 4226 (Appendix D): один секрет, счётчики 0..9, 6 цифр.
HOTP_VECTORS = [
    "755224", "287082", "359152", "969429", "338314",
    "254676", "287922", "162583", "399871", "520489",
]


@pytest.mark.parametrize("algorithm", ["sha1", "sha256", "sha512"])
def test_rfc6238_vectors(algorithm):
    secret = RFC_SECRETS[algorithm]
    index = {"sha1": 0, "sha256": 1, "sha512": 2}[algorithm]
    for moment, expected in RFC_VECTORS.items():
        assert totp.code_at(secret, at=moment, digits=8, algorithm=algorithm) == \
            expected[index], (algorithm, moment)


def test_rfc4226_hotp_vectors():
    secret = RFC_SECRETS["sha1"]
    assert [totp.hotp(secret, counter) for counter in range(10)] == HOTP_VECTORS


def test_counter_and_remaining_and_bar():
    assert totp.counter_at(59, period=30) == 1
    assert totp.counter_at(60, period=30) == 2
    assert totp.remaining(at=59.0, period=30) == 1
    assert totp.remaining(at=30.0, period=30) == 30  # ровно на границе — полное окно
    bar = totp.progress_bar(at=45.0, period=30)  # половина окна прожита
    assert len(bar) == totp.BAR_CELLS and set(bar) <= {"█", "░"}
    assert bar.startswith("█") and bar.endswith("░")
    # Только что сменилось окно — код свежий, полоска полная.
    assert set(totp.progress_bar(at=30.0, period=30)) == {"█"}


def test_normalize_and_decode_secret():
    assert totp.normalize_secret("jbsw y3dp ehpk 3pxp=") == "JBSWY3DPEHPK3PXP"
    assert totp.normalize_secret("jbsw-y3dp-ehpk-3pxp") == "JBSWY3DPEHPK3PXP"
    data = totp.decode_secret("JBSWY3DPEHPK3PXP")
    assert totp.encode_secret(data) == "JBSWY3DPEHPK3PXP"  # канон без паддинга
    with pytest.raises(totp.TotpError):
        totp.decode_secret("abc")  # короткий
    with pytest.raises(totp.TotpError):
        totp.decode_secret("not-base32!!")


def test_grouped_is_only_for_display():
    assert totp.grouped("123456") == "123 456"
    assert totp.grouped("12345678") == "1234 5678"
    assert totp.grouped("12345") == "12345"  # нечётное — не режем


def test_spec_from_input_accepts_secret_and_link():
    bare = totp.spec_from_input("jbsw y3dp ehpk 3pxp")
    assert bare.secret == totp.decode_secret("JBSWY3DPEHPK3PXP")
    assert (bare.digits, bare.period, bare.algorithm) == (6, 30, "sha1")

    link = totp.spec_from_input(
        "otpauth://totp/ACME%20Co:john@example.com"
        "?secret=JBSWY3DPEHPK3PXP&issuer=ACME%20Co&algorithm=SHA256&digits=7&period=45"
    )
    assert link.secret == totp.decode_secret("JBSWY3DPEHPK3PXP")
    assert (link.digits, link.period, link.algorithm) == (7, 45, "sha256")
    assert link.issuer == "ACME Co" and link.label == "ACME Co:john@example.com"


def test_otpauth_rejects_hotp_and_bad_params():
    with pytest.raises(totp.TotpError):
        totp.parse_otpauth("otpauth://hotp/x?secret=JBSWY3DPEHPK3PXP")
    with pytest.raises(totp.TotpError):
        totp.parse_otpauth("https://example.com/?secret=JBSWY3DPEHPK3PXP")
    with pytest.raises(totp.TotpError):
        totp.parse_otpauth(
            "otpauth://totp/x?secret=JBSWY3DPEHPK3PXP&algorithm=md5"
        )
    with pytest.raises(totp.TotpError):
        totp.parse_otpauth("otpauth://totp/x?secret=JBSWY3DPEHPK3PXP&digits=99")
    with pytest.raises(totp.TotpError):
        totp.parse_otpauth("otpauth://totp/x?secret=JBSWY3DPEHPK3PXP&period=0")


def test_entry_spec_round_trip():
    entry = {
        "kind": "totp",
        "value": "JBSWY3DPEHPK3PXP",
        "meta": {"digits": 7, "period": 45, "algorithm": "sha256", "issuer": "ACME"},
    }
    spec = totp.spec_from_entry(entry)
    assert spec is not None
    assert (spec.digits, spec.period, spec.algorithm, spec.issuer) == (7, 45, "sha256", "ACME")
    assert totp.meta_from_spec(spec) == {
        "digits": 7, "period": 45, "algorithm": "sha256", "issuer": "ACME",
    }
    # Секрет в записи — канон base32, код считается.
    assert totp.code_at(spec.secret, at=59, digits=7, algorithm="sha256")


def test_entry_spec_defaults_and_fallbacks():
    plain = totp.spec_from_entry({"value": "x"})
    assert plain is None, "не TOTP-запись"
    with pytest.raises(totp.TotpError):
        totp.spec_from_entry({"kind": "totp"})  # нет секрета — явная ошибка
    entry = {
        "kind": "TOTP",
        "value": "JBSWY3DPEHPK3PXP",
        "meta": {"digits": "9", "period": "-5", "algorithm": "md5"},
    }
    spec = totp.spec_from_entry(entry)
    assert spec is not None
    # Битые параметры откатываются к умолчаниям, а не ломают показ.
    assert (spec.digits, spec.period, spec.algorithm) == (6, 30, "sha1")
    assert totp.meta_from_spec(spec) == {}


def test_entry_spec_bad_secret_is_explicit():
    with pytest.raises(totp.TotpError):
        totp.spec_from_entry({"kind": "totp", "value": "не-base32!!"})
