"""Встроенный калькулятор без спец-команд.

Правило входа: строка начинается с цифры (или '(' / '-') И целиком
разбирается как арифметика/перевод единиц — тогда считается локально. Всё,
что не похоже на вычисление (например ``7z …``, ``(cd … && …)``, ``2to3 …``),
содержит слова/символы вне грамматики, возвращает None и уходит в shell как
обычно.

Возможности:
- арифметика: ``+ - * / ^ ( )``, десятичные числа;
- величины с единицами (k8s-стиль, слитно или через пробел):
  память ``B``, десятичные ``K/M/G/T/P/E`` = ``KB/MB/GB/…`` (×1000),
  двоичные ``Ki/Mi/Gi/Ti/Pi/Ei`` = ``KiB/MiB/GiB/…`` (×1024);
  CPU: ``m`` (миллиядро), ``cores``/``core``/``cpu``;
- проценты: ``512Mi + 20%`` / ``512Mi - 20%`` (прибавить/отнять долю),
  ``512Mi * 20%`` (взять долю), ``2 + 10%`` → 2.2;
- ``of`` — доля от значения: ``20% of 512Mi``, ``1/3 of 1Gi``, ``(512+512)*2``;
- перевод: ``… in Gi`` / ``… to MB``; чистая величина ``512Mi`` — эквиваленты;
- безразмерные числа: ``524288 in Mi`` → 0.5Mi; ``1Gi / 512Mi`` → 2.

Безопасность: свой токенизатор + рекурсивный спуск, никакого eval/exec.
Смешивание памяти и CPU/чисел в ``+``/``-`` — явная ошибка CalcError.

Ошибки двух видов:
- ``CalcError`` — строка «похожа на расчёт», но неверна (например, размерности
  не сходятся) — показываем сообщение;
- None — строка калькулятором не является, отдаём shell.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


class CalcError(Exception):
    """Строка похожа на вычисление, но посчитать её нельзя."""


class _NotCalc(Exception):
    """Строка калькулятором не является — должен выполниться shell."""


# --- Единицы ---------------------------------------------------------------

@dataclass(frozen=True)
class Unit:
    dim: str        # 'memory' | 'number'
    factor: float   # множитель к базе (байт / «один»)
    cpu: bool = False   # явная cpu-единица (m, cores) — для автоформата
    label: str = ""     # как показывать в выводе (пусто — по имени ключа)


def _u(dim: str, factor: float, cpu: bool = False, label: str = "") -> Unit:
    return Unit(dim, factor, cpu, label or "")


_UNITS: dict[str, Unit] = {
    # Память: байт и десятичные (SI, ×1000)
    "B": _u("memory", 1.0, label="B"),
    "K": _u("memory", 1e3, label="K"),
    "M": _u("memory", 1e6, label="M"),
    "G": _u("memory", 1e9, label="G"),
    "T": _u("memory", 1e12, label="T"),
    "P": _u("memory", 1e15, label="P"),
    "E": _u("memory", 1e18, label="E"),
    "KB": _u("memory", 1e3, label="KB"),
    "MB": _u("memory", 1e6, label="MB"),
    "GB": _u("memory", 1e9, label="GB"),
    "TB": _u("memory", 1e12, label="TB"),
    "PB": _u("memory", 1e15, label="PB"),
    "EB": _u("memory", 1e18, label="EB"),
    # Крошечные алиасы для SI-форм с буквой B (kb = KB, …)
    "kb": _u("memory", 1e3, label="KB"),
    "mb": _u("memory", 1e6, label="MB"),
    "gb": _u("memory", 1e9, label="GB"),
    "tb": _u("memory", 1e12, label="TB"),
    "pb": _u("memory", 1e15, label="PB"),
    "eb": _u("memory", 1e18, label="EB"),
    # Память: двоичные IEC (×1024) — k8s-форма и форма с буквой B
    "Ki": _u("memory", 2.0**10, label="Ki"),
    "Mi": _u("memory", 2.0**20, label="Mi"),
    "Gi": _u("memory", 2.0**30, label="Gi"),
    "Ti": _u("memory", 2.0**40, label="Ti"),
    "Pi": _u("memory", 2.0**50, label="Pi"),
    "Ei": _u("memory", 2.0**60, label="Ei"),
    "KiB": _u("memory", 2.0**10, label="KiB"),
    "MiB": _u("memory", 2.0**20, label="MiB"),
    "GiB": _u("memory", 2.0**30, label="GiB"),
    "TiB": _u("memory", 2.0**40, label="TiB"),
    "PiB": _u("memory", 2.0**50, label="PiB"),
    "EiB": _u("memory", 2.0**60, label="EiB"),
    # CPU
    "m": _u("number", 1e-3, cpu=True, label="m"),
    "core": _u("number", 1.0, cpu=True, label="cores"),
    "cores": _u("number", 1.0, cpu=True, label="cores"),
    "cpu": _u("number", 1.0, cpu=True, label="cores"),
}

# Автовыбор главной единицы для памяти (самая крупная двоичная, где ≥ 1)
_MEM_MAIN: list[tuple[str, float]] = [
    ("Ti", 2.0**40),
    ("Gi", 2.0**30),
    ("Mi", 2.0**20),
    ("Ki", 2.0**10),
]

_KEYWORDS = {"in", "to", "of"}  # слова после числа, не единицы
_CONV_WORDS = {"in", "to"}       # перевод результата: '512Mi in Gi'

_DIM_NAME = {"memory": "memory", "number": "cpu/plain number"}


# --- Величина ---------------------------------------------------------------

@dataclass
class Q:
    """Результат вычисления: значение в базовых единицах + размерность."""
    dim: str
    value: float
    cpu: bool = False  # в выражении была явная cpu-единица


def _dim_err(op: str, a: Q, b: Q) -> CalcError:
    return CalcError(
        f"incompatible units in '{op}': {_DIM_NAME[a.dim]} vs {_DIM_NAME[b.dim]} "
        f"(e.g. 512Mi + 20% scales by a fraction)"
    )


# --- Форматирование чисел ---------------------------------------------------

def _fmt(v: float) -> str:
    """Число без лишнего «мусора»: целые без точки, иначе ~6 знаков."""
    if not math.isfinite(v):
        raise CalcError("result is too large")
    r = round(v, 6)
    if r == 0:
        r = 0.0
    if abs(r - round(r)) < 1e-9:
        return str(int(round(r)))
    return repr(r)


# --- Токенизация --------------------------------------------------------------

def _tokenize(text: str) -> list[tuple]:
    """Токены (kind, value, start, end) — start/end нужны, чтобы отличать
    слитное ``512Mi``/``2to3`` от раздельного ``1 Gi`` / ``2 in cores``."""
    tokens: list[tuple] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit():
            m = _NUM_RE.match(text, i)
            assert m is not None  # на символе-цифре match не бывает None
            tokens.append(("num", float(m.group(0)), i, m.end()))
            i = m.end()
        elif ch.isalpha():
            j = i
            while j < n and text[j].isalpha():
                j += 1
            tokens.append(("let", text[i:j], i, j))
            i = j
        elif ch in "+-*/^()%":
            tokens.append(("op", ch, i, i + 1))
            i += 1
        else:
            raise _NotCalc  # любой незнакомый символ — не калькулятор
    return tokens


# --- Парсер (рекурсивный спуск) ----------------------------------------------

class _Parser:
    def __init__(self, tokens: list[tuple]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> tuple | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> tuple:
        tok = self.peek()
        if tok is None:
            raise CalcError("unexpected end of expression")
        self.pos += 1
        return tok

    # sum := product (('+' | '-') product)*
    def parse_sum(self):
        node = self.parse_product()
        while True:
            tok = self.peek()
            if tok and tok[0] == "op" and tok[1] in "+-":
                self.next()
                node = (tok[1], node, self.parse_product())
            else:
                return node

    # product := power (('*' | '/') power)*
    def parse_product(self):
        node = self.parse_power()
        while True:
            tok = self.peek()
            if tok is None:
                return node
            if tok[0] == "op" and tok[1] in "*/":
                self.next()
                node = (tok[1], node, self.parse_power())
            elif tok[0] == "let" and tok[1] == "of":
                # '20% of 512Mi', '1/3 of 1Gi' — умножение тем же приоритетом
                self.next()
                node = ("of", node, self.parse_power())
            else:
                return node

    # power := primary ['^' power]  (правая ассоциативность)
    def parse_power(self):
        node = self.parse_primary()
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] == "^":
            self.next()
            node = ("^", node, self.parse_power())
        return node

    def parse_primary(self):
        tok = self.peek()
        if tok is None:
            raise CalcError("unexpected end of expression")
        kind = tok[0]
        if kind == "num":
            self.next()
            return self._after_number(tok[1], tok[3])
        if kind == "op" and tok[1] == "(":
            self.next()
            node = self.parse_sum()
            nxt = self.peek()
            if not (nxt and nxt[0] == "op" and nxt[1] == ")"):
                raise CalcError("missing closing ')'")
            self.next()
            return node
        if kind == "op" and tok[1] in "+-":
            # унарный знак перед числом/скобкой: '-(2+3)', '-5'
            self.next()
            return ("neg", self.parse_primary())
        if kind == "let":
            # слово там, где ожидалось число — это не калькулятор ((cd …))
            raise _NotCalc
        raise CalcError(f"unexpected {self._describe(tok)}")

    def _after_number(self, value: float, num_end: int):
        """Число, за которым может идти единица и/или знак процента."""
        tok = self.peek()
        if tok and tok[0] == "let":
            word = tok[1]
            attached = tok[2] == num_end  # '512Mi' — слитно, '512 Mi' — раздельно
            if attached and word in _KEYWORDS:
                # '2to3', '2in Gi' — слово приклеено к числу, это не перевод
                raise _NotCalc
            if word not in _KEYWORDS:
                unit = _UNITS.get(word)
                if unit is None:
                    raise _NotCalc  # слово после цифры, не единица (7z, 2to3, …)
                self.next()
                node = ("quant", value, unit)
                if self._is_percent_next():
                    raise CalcError(
                        f"'%' applies to a number, not a unit ({word}) — "
                        f"e.g. {_fmt(value)}{word} + 20%"
                    )
                return node
        if self._is_percent_next():
            self.next()
            return ("pct", value)
        return ("num", value)

    def _is_percent_next(self) -> bool:
        tok = self.peek()
        return bool(tok and tok[0] == "op" and tok[1] == "%")

    @staticmethod
    def _describe(tok: tuple) -> str:
        kind, val = tok[0], tok[1]
        if kind == "op":
            return f"'{val}'"
        if kind == "let":
            return f"'{val}'"
        return str(val)


# --- Вычисление AST -----------------------------------------------------------

def _eval(node) -> Q:
    op = node[0]

    if op == "num":
        return Q("number", node[1])
    if op == "pct":
        return Q("number", node[1] / 100.0)
    if op == "quant":
        unit = node[2]
        return Q(unit.dim, node[1] * unit.factor, cpu=unit.cpu)
    if op == "neg":
        q = _eval(node[1])
        return Q(q.dim, -q.value, cpu=q.cpu)

    if op in ("+", "-"):
        return _add_sub(op, node[1], node[2])
    if op in ("*", "of"):
        left, right = node[1], node[2]
        if _is_pct(left):
            return _mul(Q("number", left[1] / 100.0), _eval(right))
        if _is_pct(right):
            return _mul(_eval(left), Q("number", right[1] / 100.0))
        return _mul(_eval(left), _eval(right))
    if op == "/":
        left, right = node[1], node[2]
        if _is_pct(right):
            ql = _eval(left)
            if right[1] == 0:
                raise CalcError("division by zero")
            return Q(ql.dim, ql.value / (right[1] / 100.0), cpu=ql.cpu)
        return _div(_eval(left), _eval(right))
    if op == "^":
        base, exp = _eval(node[1]), _eval(node[2])
        if base.dim != "number" or base.cpu or exp.dim != "number" or exp.cpu:
            raise CalcError("'^' works on plain numbers only")
        return Q("number", base.value ** exp.value)

    raise CalcError("internal error")  # pragma: no cover


def _is_pct(node) -> bool:
    return bool(isinstance(node, tuple) and node and node[0] == "pct")


def _add_sub(op: str, lnode, rnode):
    if _is_pct(lnode) and _is_pct(rnode):
        lv = lnode[1] / 100.0
        rv = rnode[1] / 100.0
        return Q("number", lv + rv if op == "+" else lv - rv)
    # Сахар для процентов: '512Mi + 20%' — увеличить/уменьшить на долю.
    if _is_pct(rnode) and not _is_pct(lnode):
        ql = _eval(lnode)
        factor = 1.0 + rnode[1] / 100.0 if op == "+" else 1.0 - rnode[1] / 100.0
        return Q(ql.dim, ql.value * factor, cpu=ql.cpu)
    ql, qr = _eval(lnode), _eval(rnode)
    if ql.dim != qr.dim:
        raise _dim_err(op, ql, qr)
    return Q(ql.dim, ql.value + qr.value if op == "+" else ql.value - qr.value,
             cpu=ql.cpu or qr.cpu)


def _mul(a: Q, b: Q) -> Q:
    if a.dim == "memory":
        if b.dim == "memory":
            raise CalcError("cannot multiply two memory values (use / for a ratio)")
        return Q("memory", a.value * b.value, cpu=b.cpu)
    if b.dim == "memory":
        return Q("memory", b.value * a.value, cpu=a.cpu)
    return Q("number", a.value * b.value, cpu=a.cpu or b.cpu)


def _div(a: Q, b: Q) -> Q:
    if a.dim == "memory" and b.dim == "number":
        if b.value == 0:
            raise CalcError("division by zero")
        return Q("memory", a.value / b.value, cpu=b.cpu)
    if a.dim == "number" and b.dim == "memory":
        raise CalcError(f"cannot divide {_DIM_NAME['number']} by memory")
    if a.dim == "memory":
        if b.value == 0:
            raise CalcError("division by zero")
        # 1Gi / 512Mi = 2 — сколько раз влезает
        return Q("number", a.value / b.value)
    if b.value == 0:
        raise CalcError("division by zero")
    return Q("number", a.value / b.value, cpu=a.cpu or b.cpu)


# --- Вывод ---------------------------------------------------------------------

def _render(q: Q, target: Unit | None) -> str:
    if q.dim == "memory":
        if target is None:
            return _render_memory(q.value)
        return f"= {_fmt(q.value / target.factor)}{target.label}"
    # number / cpu
    if target is not None:
        value = q.value / target.factor
        if target.dim == "memory":
            return f"= {_fmt(value)}{target.label}"  # голое число как байты
        if target.label == "m":
            return f"= {_fmt(value)}m"
        return f"= {_fmt(value)} {target.label}"
    if q.cpu and q.value != 0 and abs(q.value) < 1:
        return f"= {_fmt(q.value * 1000)}m"  # 500m вместо 0.5
    return f"= {_fmt(q.value)}"


def _render_memory(bytes_value: float) -> str:
    """Авто-вывод памяти: крупнейшая двоичная единица (≥1) + байты."""
    main = None
    for name, factor in _MEM_MAIN:
        if abs(bytes_value) >= factor:
            main = (bytes_value / factor, name)
            break
    if main is None:
        return f"= {_fmt(bytes_value)}B"
    value, name = main
    return f"= {_fmt(value)}{name} (= {_fmt(bytes_value)}B)"


# --- Публичный вход --------------------------------------------------------------

_CALC_START = set("0123456789(-")


def is_calc_like(text: str) -> bool:
    """Стоит ли пробовать калькулятор для этой строки.

    Триггер без спец-команд: первая буква — цифра, либо '(' или '-'.
    Это безопасно: конструкции вроде '(cd … && …)' или '-la' содержат слова,
    не разбираются как арифметика и уходят в shell.
    """
    t = (text or "").strip()
    return bool(t) and t[0] in _CALC_START


def evaluate(text: str) -> str | None:
    """Посчитать строку.

    Возвращает отформатированный результат (например ``= 0.5Gi``) или None,
    если строка не похожа на вычисление (её выполнит shell).

    Raises:
        CalcError: строка похожа на расчёт, но содержит ошибку.
    """
    if not is_calc_like(text):
        return None
    try:
        tokens = _tokenize(text)
    except _NotCalc:
        return None
    if not tokens:
        return None

    parser = _Parser(tokens)
    try:
        node = parser.parse_sum()
    except _NotCalc:
        return None

    target: Unit | None = None
    tok = parser.peek()
    if tok and tok[0] == "let" and tok[1] in _CONV_WORDS:
        parser.next()
        nxt = parser.peek()
        if not (nxt and nxt[0] == "let"):
            raise CalcError(f"missing unit after '{tok[1]}' (e.g. 512Mi in Gi)")
        unit = _UNITS.get(nxt[1])
        if unit is None:
            raise CalcError(f"unknown unit '{nxt[1]}'")
        parser.next()
        target = unit
        tok = parser.peek()

    if tok is not None:
        if tok[0] == "let":
            return None  # слово после выражения — не калькулятор, отдаём shell
        raise CalcError(f"unexpected {_Parser._describe(tok)} after expression")

    q = _eval(node)
    if target is not None:
        if q.dim == "number" and target.dim == "memory":
            pass  # '524288 in Mi' — голое число как байты
        elif q.dim == "memory" and target.dim == "number":
            raise CalcError(
                f"cannot convert memory to {_DIM_NAME['number']} "
                f"(use a memory unit: B, KB, MB, KiB, MiB, …)"
            )
    return _render(q, target)
