"""Локальный ipcalc в духе https://jodies.de/ipcalc (IPv4).

Без спец-команд: строка, состоящая из IPv4-адреса с опциональным префиксом
или маской (``192.168.1.0/24``, ``10.0.0.0/8``, ``192.168.1.1/255.255.255.0``,
или просто ``192.168.0.1`` — тогда классовая маска по умолчанию), считается
локально и показывает: адрес, маску (= префикс), wildcard, сеть/префикс,
диапазон хостов, broadcast и число хостов.

Обратная задача — префикс под N хостов — строкой ``<N> hosts``:
``300 hosts`` → /23 (510 usable), ``2 hosts`` → /31 (RFC 3021) или /30.

Всё, что не похоже на IPv4, возвращает None и уходит в shell.
Ошибки (октет/префикс вне диапазона, неконтигуальная маска) — IpCalcError,
строку «похожую на IP» пользователю надо показать, а не молча уронить в shell.
"""
from __future__ import annotations

import re

_IP_RE = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})(?:\s*/\s*(\d{1,2}|\d{1,3}(?:\.\d{1,3}){3}))?$"
)
# '300 hosts', '1 host' — подобрать префикс под N хостов (запятая-разделитель тысяч ok)
_HOSTS_RE = re.compile(r"^(\d{1,12}(?:,\d{1,3})*)\s+hosts?$")

_MAX_HOSTS = 2**32 - 2  # всё адресное пространство IPv4 минус network/broadcast


class IpCalcError(Exception):
    """Строка похожа на IPv4-сеть, но посчитать её нельзя."""


def looks_like(text: str) -> bool:
    """Форма IPv4(-сети) или запроса ``<N> hosts`` — стоит пробовать ipcalc."""
    t = (text or "").strip()
    return bool(_IP_RE.match(t)) or bool(_HOSTS_RE.match(t))


def _parse_addr(addr_str: str) -> int:
    """'a.b.c.d' → int. Октет вне 0-255 — IpCalcError."""
    octets = [int(part) for part in addr_str.split(".")]
    if any(o < 0 or o > 255 for o in octets):
        raise IpCalcError(f"octet out of range in {addr_str} (0-255)")
    value = 0
    for o in octets:
        value = (value << 8) | o
    return value


def _to_addr(value: int) -> str:
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def _to_binary(value: int) -> str:
    """'11000000.10101000.00000000.00000001' — колонка как на jodies.de."""
    return ".".join(f"{(value >> shift) & 0xFF:08b}" for shift in (24, 16, 8, 0))


def _is_private(value: int) -> bool:
    o1 = (value >> 24) & 0xFF
    o2 = (value >> 16) & 0xFF
    if o1 == 10:
        return True
    if o1 == 172 and 16 <= o2 <= 31:
        return True
    if o1 == 192 and o2 == 168:
        return True
    return False


def _parse_prefix(prefix_str: str, addr: int) -> int:
    """'/24' или '/255.255.255.0' → длина префикса. Классовая — по умолчанию."""
    if prefix_str is None:
        o1 = (addr >> 24) & 0xFF
        if o1 <= 127:
            return 8
        if o1 <= 191:
            return 16
        if o1 <= 223:
            return 24
        return 32
    if "." not in prefix_str:
        prefix = int(prefix_str)
        if not 0 <= prefix <= 32:
            raise IpCalcError(f"prefix out of range: {prefix_str} (0-32)")
        return prefix
    mask = _parse_addr(prefix_str)
    bits = mask.bit_count()
    expected = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF if bits else 0
    if mask != expected:
        raise IpCalcError(f"netmask is not contiguous: {prefix_str}")
    return bits


def _annotations(value: int, prefix: int) -> list[str]:
    """Примечания в строке Hosts/Net: класс, RFC1918/loopback/public, /31 /32."""
    notes: list[str] = []
    o1 = (value >> 24) & 0xFF
    if o1 == 0:
        pass  # 0.0.0.0/8 «this network» — без класса
    elif o1 < 128:
        notes.append("Class A")
    elif o1 < 192:
        notes.append("Class B")
    elif o1 < 224:
        notes.append("Class C")
    elif o1 < 240:
        notes.append("Class D (multicast)")
    else:
        notes.append("Class E (reserved)")

    if _is_private(value):
        notes.append("RFC1918 private")
    elif o1 == 127:
        notes.append("loopback")
    elif 1 <= o1 <= 223:
        notes.append("public")

    if prefix == 31:
        notes.append("point-to-point (RFC 3021)")
    elif prefix == 32:
        notes.append("host route")
    return notes


def _hosts_count(prefix: int) -> int:
    if prefix == 32:
        return 1
    if prefix == 31:
        return 2
    return 2 ** (32 - prefix) - 2


def _prefix_for_hosts(hosts: int) -> int:
    """Минимальный префикс, в который влезает N хостов (usable >= N).

    /32 = 1 usable (host route), /31 = 2 usable (RFC 3021 point-to-point);
    для больших N — классика: p = 32 - ceil(log2(N + 2)).
    """
    if hosts == 1:
        return 32
    if hosts == 2:
        return 31
    return 32 - (hosts + 1).bit_length()


def _netmask_int(prefix: int) -> int:
    if prefix >= 32:
        return 0xFFFFFFFF
    return (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF


def _format_hosts(hosts: int) -> str:
    if hosts < 1:
        raise IpCalcError("hosts count must be >= 1")
    if hosts > _MAX_HOSTS:
        raise IpCalcError(f"too many hosts for IPv4 (max {_MAX_HOSTS})")
    prefix = _prefix_for_hosts(hosts)
    usable = _hosts_count(prefix)
    total = 2 ** (32 - prefix) if prefix < 32 else 1

    rows = [f"{hosts} {'host' if hosts == 1 else 'hosts'} → /{prefix}"]
    rows.append(
        f"  netmask {_to_addr(_netmask_int(prefix))} · {total} "
        f"{'address' if total == 1 else 'addresses'}, {usable} usable"
    )
    if prefix == 32:
        rows.append("  /32 is a host route (1 address)")
    elif prefix == 31:
        rows.append("  /31 = point-to-point (RFC 3021); classic subnets use /30")
    elif prefix > 1:
        rows.append(
            f"  /{prefix - 1} → {_hosts_count(prefix - 1)} usable · "
            f"/{prefix + 1} → {_hosts_count(prefix + 1)} usable"
        )
    return "\n".join(rows)


def _format_rows(addr: int, prefix: int) -> str:
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF if prefix < 32 else 0xFFFFFFFF
    if prefix == 0:
        mask = 0
    wildcard = mask ^ 0xFFFFFFFF
    network = addr & mask
    broadcast = network | wildcard

    rows: list[str] = []
    rows.append(f"{'Address:':<10} {_to_addr(addr):<18} {_to_binary(addr)}")
    netmask_val = f"{_to_addr(mask)} = {prefix}"
    rows.append(f"{'Netmask:':<10} {netmask_val:<18} {_to_binary(mask)}")
    rows.append(f"{'Wildcard:':<10} {_to_addr(wildcard):<18} {_to_binary(wildcard)}")
    rows.append("=>")
    rows.append(
        f"{'Network:':<10} {f'{_to_addr(network)}/{prefix}':<18} {_to_binary(network)}"
    )
    if prefix <= 31:
        rows.append(f"{'HostMin:':<10} {_to_addr(network):<18} {_to_binary(network)}")
        rows.append(f"{'HostMax:':<10} {_to_addr(broadcast):<18} {_to_binary(broadcast)}")
    if prefix <= 30:
        rows.append(
            f"{'Broadcast:':<10} {_to_addr(broadcast):<18} {_to_binary(broadcast)}"
        )

    notes = " · ".join(_annotations(addr, prefix))
    hosts_line = f"{'Hosts/Net:':<10} {_hosts_count(prefix):<18}"
    if notes:
        hosts_line += " " + notes
    rows.append(hosts_line.rstrip())
    return "\n".join(rows)


def evaluate(text: str) -> str | None:
    """Посчитать IPv4-сеть или подобрать префикс под N хостов.

    ``192.168.1.0/24`` — таблица подсети как на jodies.de/ipcalc;
    ``300 hosts`` — минимальный префикс под 300 хостов. Возвращает None,
    если строка не похожа ни на то, ни на другое (её выполнит shell).

    Raises:
        IpCalcError: строка похожа на IP/hosts, но неверна.
    """
    text = (text or "").strip()
    m = _IP_RE.match(text)
    if m:
        addr = _parse_addr(m.group(1))
        prefix = _parse_prefix(m.group(2), addr)
        return _format_rows(addr, prefix)
    m = _HOSTS_RE.match(text)
    if m:
        hosts = int(m.group(1).replace(",", ""))
        return _format_hosts(hosts)
    return None
