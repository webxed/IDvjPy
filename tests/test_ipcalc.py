"""Тесты локального ipcalc (src/ipcalc.py) — как на jodies.de/ipcalc.

Без спец-команд: строка из IPv4 с префиксом/маской считается локально;
не-IP возвращает None (уходит в shell), «похожий на IP» с ошибкой бросает
IpCalcError (показываем сообщение).
"""
import pytest

from ipcalc import IpCalcError, evaluate, looks_like


@pytest.mark.parametrize(
    "expr",
    [
        "192.168.0.1/24",
        "10.0.0.0/8",
        "192.168.1.1/255.255.255.0",
        "10.1.2.3 / 24",          # пробелы вокруг '/'
        "8.8.8.8",                # без маски — классовая по умолчанию
        "172.16.0.1/12",
        "0.0.0.0/0",
        "300 hosts",
        "1 host",
    ],
)
def test_looks_like_ip(expr):
    assert looks_like(expr) is True
    assert evaluate(expr) is not None


@pytest.mark.parametrize(
    "expr",
    [
        "1.2.3",                  # мало октетов
        "1.2.3.4.5",              # много октетов
        "192.168.1.1/abc",        # не префикс
        "hello",
        "192.168.1.0/24 extra",   # хвост — не IP
        "",
        "   ",
    ],
)
def test_not_ip_returns_none(expr):
    assert looks_like(expr) is False
    assert evaluate(expr) is None


def test_subnet_24_rows():
    out = evaluate("192.168.0.1/24")
    assert out is not None
    assert "Address:   192.168.0.1" in out
    assert "Netmask:   255.255.255.0 = 24" in out
    assert "Wildcard:  0.0.0.255" in out
    assert "Network:   192.168.0.0/24" in out
    assert "HostMin:   192.168.0.0" in out
    assert "HostMax:   192.168.0.255" in out
    assert "Broadcast: 192.168.0.255" in out
    assert "Hosts/Net: 254" in out
    assert "Class C" in out
    assert "RFC1918 private" in out
    # бинарная колонка как на сайте
    assert "11000000.10101000.00000000.00000001" in out


def test_host_range_30():
    out = evaluate("192.168.1.5/30")
    assert out is not None
    assert "Network:   192.168.1.4/30" in out
    assert "HostMax:   192.168.1.7" in out
    assert "Broadcast: 192.168.1.7" in out
    assert "Hosts/Net: 2" in out


def test_large_prefix_hosts_count():
    for expr, needle in (
        ("10.0.0.0/8", "Hosts/Net: 16777214"),
        ("172.16.0.1/16", "Hosts/Net: 65534"),
    ):
        out = evaluate(expr)
        assert out is not None
        assert needle in out


def test_point_to_point_31():
    out = evaluate("10.0.0.1/31")
    assert out is not None
    assert "Broadcast:" not in out
    assert "Hosts/Net: 2" in out
    assert "point-to-point (RFC 3021)" in out


def test_host_route_32():
    out = evaluate("10.0.0.1/32")
    assert out is not None
    assert "Broadcast:" not in out
    assert "HostMin:" not in out
    assert "Hosts/Net: 1" in out
    assert "host route" in out
    assert "Network:   10.0.0.1/32" in out


def test_netmask_form_input():
    out = evaluate("10.1.2.3/255.255.255.0")
    assert out is not None
    assert "Netmask:   255.255.255.0 = 24" in out
    assert "Network:   10.1.2.0/24" in out


def test_classful_default_mask():
    out = evaluate("8.8.8.8")          # класс A → /8 по умолчанию
    assert out is not None
    assert "Netmask:   255.0.0.0 = 8" in out
    assert "Network:   8.0.0.0/8" in out
    assert "public" in out


def test_class_b_default():
    out = evaluate("172.20.0.1")       # класс B → /16
    assert out is not None
    assert "Netmask:   255.255.0.0 = 16" in out


# --- Префикс под N хостов ('300 hosts') -----------------------------------------

@pytest.mark.parametrize(
    "expr,needle",
    [
        ("254 hosts", "254 hosts → /24"),
        ("300 hosts", "300 hosts → /23"),
        ("300 host", "300 hosts → /23"),        # единственное число тоже
        ("1000 hosts", "1000 hosts → /22"),
        ("7 hosts", "7 hosts → /28"),
        ("2 hosts", "2 hosts → /31"),           # RFC 3021 point-to-point
        ("1 host", "1 host → /32"),
        ("4,000 hosts", "4000 hosts → /20"),    # разделитель тысяч
    ],
)
def test_hosts_to_prefix(expr, needle):
    out = evaluate(expr)
    assert out is not None
    assert needle in out
    assert "netmask" in out


def test_hosts_neighbor_line():
    out = evaluate("300 hosts")
    assert out is not None
    assert "/22 → 1022 usable" in out
    assert "/24 → 254 usable" in out


def test_hosts_31_notes():
    out = evaluate("2 hosts")
    assert out is not None
    assert "point-to-point (RFC 3021)" in out
    assert "/30" in out


@pytest.mark.parametrize(
    "expr,message",
    [
        ("0 hosts", "hosts count must be >= 1"),
        ("5000000000 hosts", "too many hosts for IPv4"),
    ],
)
def test_hosts_errors(expr, message):
    assert looks_like(expr) is True
    with pytest.raises(IpCalcError, match=message):
        evaluate(expr)


@pytest.mark.parametrize(
    "expr,message",
    [
        ("999.1.1.1/24", "octet out of range"),
        ("10.1.2.3/33", "prefix out of range"),
        ("10.1.2.3/255.0.255.0", "netmask is not contiguous"),
    ],
)
def test_ip_errors(expr, message):
    assert looks_like(expr) is True
    with pytest.raises(IpCalcError, match=message):
        evaluate(expr)
