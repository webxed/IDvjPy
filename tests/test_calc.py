"""Тесты встроенного калькулятора (src/calc.py) и его роутинга в приложении.

Калькулятор — без спец-команд: строка, начинающаяся с цифры и целиком
разбираемая как арифметика/перевод единиц, считается локально. Не-расчёты
(``7z …``, ``2to3 …``) возвращают None и уходят в shell.
"""
import pytest

from app import CommandBlock, CommandRunner
from calc import CalcError, evaluate
from tests.conftest import last_info, submit, wait_command_done

# --- Арифметика ---------------------------------------------------------------

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("2+2", "= 4"),
        ("1024*3", "= 3072"),
        ("10/3", "= 3.333333"),
        ("7/2", "= 3.5"),
        ("8*(2+3)", "= 40"),
        ("2+3*4", "= 14"),          # приоритет: * раньше +
        ("(2+3)*4", "= 20"),
        ("(512+512)*2", "= 2048"),
        ("2^10", "= 1024"),
        ("2^0.5", "= 1.414214"),
        ("1.5 + 0.25", "= 1.75"),
        ("10 - 7.5", "= 2.5"),
        ("0 - 2^2", "= -4"),
        ("-5 + 8", "= 3"),
        ("(-2+5)*3", "= 9"),
        ("-5", "= -5"),
        ("2 - 2", "= 0"),
    ],
)
def test_arithmetic(expr, expected):
    assert evaluate(expr) == expected


# --- Перевод единиц памяти ------------------------------------------------------

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("512Mi in Gi", "= 0.5Gi"),
        ("512Mi in B", "= 536870912B"),
        ("1Mi in B", "= 1048576B"),          # двоичный мегабайт = 2^20
        ("1M in B", "= 1000000B"),           # десятичный «мега» = 10^6 (k8s)
        ("1Gi in MB", "= 1073.741824MB"),    # 2^30 / 10^6
        ("1MB in Mi", "= 0.953674Mi"),       # 10^6 / 2^20
        ("2Ti in B", "= 2199023255552B"),
        ("1 GiB in MiB", "= 1024MiB"),
        ("512 MiB in GiB", "= 0.5GiB"),
        ("512mb in mb", "= 512MB"),          # нижний регистр — алиас
        ("524288 in Mi", "= 0.5Mi"),         # голое число трактуем как байты
        ("1GB in Gi", "= 0.931323Gi"),
        ("512Mi in B in Gi", None),          # цепочка переводов — не калькулятор
    ],
)
def test_memory_units(expr, expected):
    assert evaluate(expr) == expected


# --- Автоформат памяти (без in/to) ----------------------------------------------

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("512Mi", "= 512Mi (= 536870912B)"),
        ("512Mi*30", "= 15Gi (= 16106127360B)"),
        ("1536Mi", "= 1.5Gi (= 1610612736B)"),
        ("500B", "= 500B"),
    ],
)
def test_memory_auto(expr, expected):
    assert evaluate(expr) == expected


# --- Ключевое слово of ('20% of 512Mi', '1/3 of 1Gi') ----------------------------

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("20% of 512Mi in Mi", "= 102.4Mi"),
        ("20% of 512Mi in Gi", "= 0.1Gi"),
        ("1/3 of 1Gi in Mi", "= 341.333333Mi"),
        ("20% of (512Mi + 1Gi) in Mi", "= 307.2Mi"),
        ("512Mi * 20% in Mi", "= 102.4Mi"),   # тот же смысл без of
        ("1.5 of 512Mi in Gi", "= 0.75Gi"),
    ],
)
def test_of_keyword(expr, expected):
    assert evaluate(expr) == expected


# --- Проценты -------------------------------------------------------------------

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("512Mi + 20% in Mi", "= 614.4Mi"),      # увеличить память на 20%
        ("512Mi - 20% in Mi", "= 409.6Mi"),
        ("512Mi * 20% in Mi", "= 102.4Mi"),      # 20% от значения
        ("512Mi + 20% in Gi", "= 0.6Gi"),
        ("2 + 10%", "= 2.2"),
        ("2 - 10%", "= 1.8"),
        ("20%", "= 0.2"),
        ("512Mi + 1Gi + 20% in Gi", "= 1.8Gi"),
        ("100m + 10% in m", "= 110m"),
    ],
)
def test_percent(expr, expected):
    assert evaluate(expr) == expected


# --- CPU (миллиядро / ядра) ------------------------------------------------------

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("500m in cores", "= 0.5 cores"),
        ("0.5 in m", "= 500m"),
        ("2 in m", "= 2000m"),
        ("500m + 20% in m", "= 600m"),
        ("500m", "= 500m"),                     # < 1 ядра — авто в миллиядрах
        ("1500m", "= 1.5"),
        ("100m * 4", "= 400m"),
        ("100m * 20", "= 2"),                   # ≥ 1 — авто в ядрах
    ],
)
def test_cpu_units(expr, expected):
    assert evaluate(expr) == expected


# --- Составные выражения с размерностями ------------------------------------------

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("512Mi + 1Gi + 256Mi in Mi", "= 1792Mi"),
        ("1Gi / 512Mi", "= 2"),                 # сколько раз влезает
        ("512Mi * 3", "= 1.5Gi (= 1610612736B)"),
    ],
)
def test_dimensions(expr, expected):
    assert evaluate(expr) == expected


# --- Ошибки (строка похожа на расчёт, но неверна) ---------------------------------

@pytest.mark.parametrize(
    "expr",
    [
        "512Mi + 2",             # память + голое число
        "512Mi in cores",        # память → cpu
        "512Mi in",              # нет единицы после in
        "512Mi in Gx",           # неизвестная единица
        "512Mi % 20",            # % после единицы
        "2+2*",                  # оборванное выражение
        "8*(2+2",                # нет закрывающей скобки
        "1Gi * 2Gi",             # умножение памяти на память
        "2 / 0",                 # деление на ноль → бесконечность
        "2^2Gi",                 # степень от величины
    ],
)
def test_calc_errors(expr):
    with pytest.raises(CalcError):
        evaluate(expr)


# --- Не калькулятор: строка должна уйти в shell ------------------------------------

@pytest.mark.parametrize(
    "expr",
    [
        "7z a archive.7z files/",   # команда, начинающаяся с цифры
        "2to3 -l",                  # то же
        "512Mi foo",                # слово после выражения
        "2+2 extra",
        "2 && echo hi",             # '&' — shell-оператор
        "2>/dev/null echo hi",      # '>' — редирект
        "(cd /tmp && ls)",          # подстановка bash со словами
        "(echo hi)",
        "-la",                      # флаг, не арифметика
        "--help",
        "hello",
        "",
        "   ",
    ],
)
def test_not_calc_returns_none(expr):
    assert evaluate(expr) is None


# --- Роутинг в приложении -----------------------------------------------------------

@pytest.mark.slow
async def test_calc_line_runs_inline(isolated_home):
    """Строка с цифры считает: блок результата, без запуска shell."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "512Mi + 20% in Mi")
        blocks = list(app.query(CommandBlock))
        assert blocks, "calc block not added to the journal"
        block = blocks[-1]
        assert not block.pending
        assert "calc:" in block.header
        assert "512Mi + 20% in Mi" in block.header
        assert block.raw_stdout == "= 614.4Mi"


@pytest.mark.slow
async def test_ipcalc_line_runs_inline(isolated_home):
    """IPv4-сеть с цифры: блок результата ipcalc, без запуска shell."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "192.168.1.0/24")
        blocks = list(app.query(CommandBlock))
        assert blocks, "ipcalc block not added to the journal"
        block = blocks[-1]
        assert not block.pending
        assert "calc:" in block.header
        assert block.raw_stdout is not None
        assert "Network:   192.168.1.0/24" in block.raw_stdout
        assert "Hosts/Net: 254" in block.raw_stdout
        assert "11000000.10101000.00000001.00000000" in block.raw_stdout


@pytest.mark.slow
async def test_ipcalc_error_shows_info(isolated_home):
    """Неверный префикс в IP-строке — понятное сообщение, не shell."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "10.1.2.3/33")
        text = last_info(app).text_content
        assert "prefix out of range" in text
        assert not list(app.query(CommandBlock))


@pytest.mark.slow
async def test_ipcalc_hosts_line_runs_inline(isolated_home):
    """'300 hosts' → минимальный префикс под 300 хостов."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "300 hosts")
        blocks = list(app.query(CommandBlock))
        assert blocks
        block = blocks[-1]
        assert not block.pending
        assert block.raw_stdout is not None
        assert "300 hosts → /23" in block.raw_stdout
        assert "510 usable" in block.raw_stdout


@pytest.mark.slow
async def test_calc_help_topic(isolated_home):
    """`:? calc` показывает полный справочник калькулятора."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":? calc")
        text = last_info(app).text_content
        assert "512Mi + 20%" in text
        assert "in Gi" in text
        assert "1Gi / 512Mi" in text


@pytest.mark.slow
async def test_calc_error_shows_info(isolated_home):
    """Размерности не сошлись — понятное сообщение, а не молчаливый fallback."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "512Mi + 2")
        text = last_info(app).text_content
        assert "incompatible units" in text
        assert not list(app.query(CommandBlock))  # shell не запускался


@pytest.mark.slow
async def test_not_calc_digit_line_goes_to_shell(isolated_home):
    """2>… не похож на расчёт → выполняется bash, а не калькулятор."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "2>/dev/null echo shell-ok")
        block = await wait_command_done(app)
        assert "shell-ok" in block.raw_stdout
