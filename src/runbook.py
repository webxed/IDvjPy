"""Runbook: полуавтоматический прогон цепочки команд (`:run`).

Задача: цепочки вида `vapprole` (role_id → secret_id → login → проверка) должны
идти подряд, без `!tag[N]` на каждый шаг, но там, где нужно решение человека
(имя роли, подтверждение выпуска секрета), прогон обязан остановиться и ждать.

Из TUI:
  :run vapprole          — шаги тега по порядку (режимы — из директив `run:`)
  :run vapprole --step   — пошаговый полуавтомат: каждый шаг ждёт Enter
  :run chain.yml         — шаги из YAML (`manual:` / `prompt:` в шаге)
  :run vapprole --dry    — показать план и ничего не выполнять
  :run stop              — остановить прогон

Режимы шагов:

- ``auto``   — вставить строку во ввод, выполнить, дождаться завершения и идти
  дальше; ошибка (`exit ≠ 0`) останавливает прогон;
- ``manual`` — вставить строку и ждать Enter человека (строку можно править);
  пустой Enter — пропустить шаг;
- ``prompt`` — ввод пуст: ждать, пока человек наберёт строку целиком.

Директивы в комментарии команды тега (в начале, до текста подсказки):

- ``run:auto`` / ``run:manual`` / ``run:prompt`` — режим этого шага;
- ``run:pause=SEC`` — пауза после шага;
- ``run:continue`` — ошибка шага не останавливает прогон;
- ``run:stop`` — ошибка шага останавливает (по умолчанию и так).

Пример: ``#vapprole=4=run:manual выпуск secret_id`` — шаг вставляет строку и
ждёт Enter, а в ``??`` видно «выпуск secret_id». Директивы в комментарии тега
задают значения по умолчанию для всех его шагов (пауза, реакция на ошибку).

Движение по шагам и ввод — общие с демо (`src/demo.py`): тот же аккуратный
Enter (подсказки, попадание в блок журнала) и то же ожидание завершения команды.
Esc останавливает прогон; сама команда останавливается F4 / `:kill`.
"""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

import database_v2 as database
from demo import session_line_needs_wait, submit_line

MODE_AUTO = "auto"
MODE_MANUAL = "manual"
MODE_PROMPT = "prompt"
MODES = {MODE_AUTO: MODE_AUTO, MODE_MANUAL: MODE_MANUAL, MODE_PROMPT: MODE_PROMPT}

# Пауза между авто-шагами: команда уже завершена, но глазу нужно время, чтобы
# увидеть её вывод до следующей подстановки.
DEFAULT_PAUSE = 0.3
# Шаг без командного блока (`:cmd`, `# tag`, `$VAR=…`): даём приложению время
# обработать отправку, прежде чем идти дальше.
NO_BLOCK_SETTLE = 0.4
# Как часто проверять состояние шага (завершение команды, отправку человеком).
POLL = 0.05

# `run:имя` или `run:имя=значение` — только в начале комментария команды.
RE_DIRECTIVE = re.compile(r"^run:([A-Za-z]+)(?:=(\S+))?$")

# Ключи шага YAML, которые понимает `:run`. Демо-формат (`:playbook`) пишет ещё
# `wait_command` — прогон и так всегда ждёт команду, поэтому ключ принимается
# молча; остальные ключи шага попадают в предупреждения плана.
STEP_KEYS = {"type", "text", "manual", "prompt", "hint", "caption",
             "pause", "stop_on_error", "wait_command"}
# Ключи сценария: `:run` берёт отсюда только паузу; демо-ключи не мешают.
PLAN_KEYS = {"title", "steps", "pause", "stop_on_error",
             "start_pause", "type_delay", "command_timeout", "reset_tags", "loop"}

MODES_HELP = (
    "auto — выполнить и ждать завершения · manual — вставить и ждать Enter "
    "(пустой Enter — пропустить) · prompt — набрать строку"
)

# Тег без единой `run:`-директивы: прогон пойдёт целиком auto. Молчать нельзя —
# так выглядит устаревший сид (директивы появились в v1.124): `:run vapprole`
# старого набора сам выполнял `$ROLE=custom-role` и падал на следующем шаге, а
# мутирующий `vault write -force` ушёл бы без подтверждения. Поэтому в план
# печатается замечание (`format_plan` показывает его как `note:`).
NO_DIRECTIVES_NOTE = (
    "в теге нет run:-директив — все шаги пойдут auto; мутирующий шаг "
    "безопаснее пометить run:manual (см. :? run)"
)


class RunbookError(Exception):
    """Ошибка плана прогона: нет тега/файла, пустой или неверный YAML."""


@dataclass
class RunSpec:
    """Директивы `run:…`: режим шага, подсказка, пауза, политика ошибок."""

    mode: str = MODE_AUTO
    hint: str = ""
    pause: float | None = None
    stop_on_error: bool = True


@dataclass
class RunStep:
    """Один шаг прогона."""

    text: str
    mode: str = MODE_AUTO
    hint: str = ""
    pause: float | None = None
    stop_on_error: bool = True
    origin: str = ""

    @property
    def label(self) -> str:
        """Короткое имя шага для сообщений (`tag[tid]` или `файл:строка`)."""
        return self.origin or (self.text or "").strip()[:60]


@dataclass
class RunPlan:
    """Что и в каком порядке выполнять."""

    title: str
    steps: list[RunStep] = field(default_factory=list)
    pause: float = DEFAULT_PAUSE
    source: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class StepResult:
    """Итог шага: выполнилось ли, каким блоком и не остановлен ли прогон."""

    ran: bool = False
    block: Any = None
    stopped: bool = False


# --- разбор плана ------------------------------------------------------------


def _pause_value(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_directives(comment: str, base: RunSpec | None = None) -> tuple[RunSpec, list[str]]:
    """Разобрать `run:`-директивы в начале комментария команды/тега.

    Возвращает (спецификация, предупреждения). Токены `run:…` идут первыми,
    всё после них — подсказка (для команды это её обычный комментарий в `??`).
    `base` задаёт значения по умолчанию: директивы комментария тега действуют
    на все его шаги (пауза, реакция на ошибку), режим шага — только свой.
    """
    spec = RunSpec(
        pause=base.pause if base is not None else None,
        stop_on_error=base.stop_on_error if base is not None else True,
    )
    warnings: list[str] = []
    tokens = (comment or "").strip().split()
    index = 0
    while index < len(tokens):
        match = RE_DIRECTIVE.match(tokens[index])
        if not match:
            break
        name, value = match.group(1).lower(), match.group(2)
        if name in MODES:
            spec.mode = MODES[name]
        elif name == "pause":
            pause = _pause_value(value) if value else None
            if pause is None:
                warnings.append(f"{tokens[index]}: нужна пауза > 0 секунды — пропущено")
            else:
                spec.pause = pause
        elif name == "continue":
            spec.stop_on_error = False
        elif name == "stop":
            spec.stop_on_error = True
        else:
            # Неизвестная директива: остаток комментария остаётся подсказкой.
            warnings.append(f"unknown runbook directive: {tokens[index]}")
            break
        index += 1
    spec.hint = " ".join(tokens[index:]).strip()
    return spec, warnings


def has_run_directive(comment: str | None) -> bool:
    """Есть ли в начале комментария директива `run:…` (токены идут первыми)."""
    tokens = (comment or "").strip().split()
    return bool(tokens) and bool(RE_DIRECTIVE.match(tokens[0]))


def steps_from_tag(db_file: str, tag: str) -> RunPlan:
    """Шаги тега по порядку tid; режимы — из `run:`-директив комментариев."""
    name = (tag or "").strip()
    rows = database.get_commands_by_tag(db_file, name)
    if not rows:
        raise RunbookError(
            f"Runbook: tag '{name}' not found or has no live commands. "
            "`?tag` — библиотека, `:run` — usage."
        )
    tag_comment = database.get_tag_comment(db_file, name)
    base, base_warnings = parse_directives(tag_comment)
    directed = has_run_directive(tag_comment)
    plan = RunPlan(
        title=name,
        source=name,
        pause=base.pause if base.pause is not None else DEFAULT_PAUSE,
        warnings=list(base_warnings),
    )
    for row in rows:
        comment = row["comment"] or ""
        spec, warnings = parse_directives(comment, base=base)
        directed = directed or has_run_directive(comment)
        origin = f"{name}[{row['tid']}]"
        plan.warnings.extend(f"{origin}: {w}" for w in warnings)
        plan.steps.append(
            RunStep(
                text=row["command"] or "",
                mode=spec.mode,
                hint=spec.hint,
                pause=spec.pause,
                stop_on_error=spec.stop_on_error,
                origin=origin,
            )
        )
    if not directed:
        plan.warnings.insert(0, NO_DIRECTIVES_NOTE)
    return plan


def _step_from_mapping(raw: dict[str, Any], index: int, plan: RunPlan) -> RunStep:
    text = raw.get("type", raw.get("text", "")) or ""
    if not isinstance(text, str):
        text = str(text)
    prompt = raw.get("prompt")
    manual = bool(raw.get("manual"))
    mode = MODE_AUTO
    hint = str(raw.get("hint") or raw.get("caption") or "")
    if prompt not in (None, False):
        mode = MODE_PROMPT
        if isinstance(prompt, str) and prompt.strip():
            hint = prompt.strip()
    elif manual:
        mode = MODE_MANUAL
    if not text and mode == MODE_AUTO:
        raise RunbookError(f"Runbook: step {index}: no 'type'/'text' and no manual/prompt")
    unknown = sorted(set(raw) - STEP_KEYS)
    if unknown:
        plan.warnings.append(f"step {index}: ignored key(s) {', '.join(unknown)}")
    pause = raw.get("pause")
    stop_on_error = raw.get("stop_on_error")
    return RunStep(
        text=text,
        mode=mode,
        hint=hint,
        pause=None if pause is None else float(pause),
        stop_on_error=True if stop_on_error is None else bool(stop_on_error),
        origin=f"{plan.title}:{index}",
    )


def steps_from_yaml(path: str) -> RunPlan:
    """Шаги из YAML: строка — авто-шаг, словарь — с `manual` / `prompt` / …"""
    target = Path(os.path.expanduser(path))
    try:
        with open(target, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise RunbookError(f"Runbook: file not found: {path}") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise RunbookError(f"Runbook: cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RunbookError(f"Runbook: {path} must be a mapping with 'steps:'")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise RunbookError(f"Runbook: {path} has no non-empty 'steps:' list")
    title = str(data.get("title") or target.stem)
    plan = RunPlan(
        title=title,
        source=str(target),
        pause=DEFAULT_PAUSE if data.get("pause") is None else float(data["pause"]),
    )
    unknown = sorted(set(data) - PLAN_KEYS)
    if unknown:
        plan.warnings.append(f"ignored key(s): {', '.join(unknown)}")
    for index, raw in enumerate(raw_steps, start=1):
        if isinstance(raw, str):
            if not raw.strip():
                raise RunbookError(f"Runbook: step {index} is empty")
            plan.steps.append(RunStep(text=raw, origin=f"{title}:{index}"))
            continue
        if not isinstance(raw, dict):
            raise RunbookError(f"Runbook: step {index} must be a string or mapping")
        plan.steps.append(_step_from_mapping(raw, index, plan))
    return plan


def build_plan(db_file: str, target: str, *, step: bool = False) -> RunPlan:
    """Собрать план по цели `:run`: файл (`.yml`, путь) или тег библиотеки.

    `step=True` (`--step`) переводит все авто-шаги в manual: пошаговый
    полуавтомат — каждый шаг ждёт Enter.
    """
    text = (target or "").strip()
    if not text:
        raise RunbookError("Runbook: usage — `:run <tag|file.yml> [--step] [--dry]`")
    is_file = (
        text.lower().endswith((".yml", ".yaml"))
        or os.sep in text
        or "/" in text
        or text.startswith(("~", "."))
    )
    plan = steps_from_yaml(text) if is_file else steps_from_tag(db_file, text)
    if step:
        for item in plan.steps:
            if item.mode == MODE_AUTO:
                item.mode = MODE_MANUAL
        # `--step` переводит всё в manual — замечание об auto-шагах больше не нужно.
        plan.warnings = [w for w in plan.warnings if w != NO_DIRECTIVES_NOTE]
    return plan


def tags_with_directives(db_file: str) -> list[tuple[str, int]]:
    """Теги, у которых есть `run:`-директивы: [(tag, сколько шагов), …]."""
    rows, _total = database.search_commands_by_content(db_file, "run:", limit=500)
    counts: dict[str, int] = {}
    for row in rows:
        comment = (row["comment"] or "").strip()
        if not comment.startswith("run:"):
            continue
        counts[row["tag"]] = counts.get(row["tag"], 0) + 1
    return sorted(counts.items())


def format_plan(plan: RunPlan, *, dry: bool = False) -> str:
    """Человеческий план прогона: шаги, режимы, подсказки, предупреждения."""
    total = len(plan.steps)
    head = (
        f"[bold]Runbook {plan.title}[/bold] · {total} step(s) · "
        + ("[yellow]dry run — nothing executed[/yellow]" if dry else "Esc — остановить")
    )
    lines = [head, f"[dim]{MODES_HELP}[/dim]"]
    for index, step in enumerate(plan.steps, start=1):
        hint = f"  [dim]# {step.hint}[/dim]" if step.hint else ""
        lines.append(f"  {index:>2}. [bold]{step.mode:<6}[/bold] {step.text}{hint}")
    if plan.source:
        lines.append(f"[dim]source: {plan.source} · pause {plan.pause:g}s[/dim]")
    for warning in plan.warnings:
        lines.append(f"[yellow]note: {warning}[/yellow]")
    return "\n".join(lines)


def usage_text(db_file: str) -> str:
    """Подсказка для `:run` без аргументов (вместе со списком готовых тегов)."""
    lines = [
        "Usage: :run <tag|file.yml> [--step] [--dry]   |   :run stop",
        "  auto-шаги идут подряд, manual/prompt ждут человека, Esc — остановить.",
        "  Режим шага тега — директивы в комментарии команды: run:manual,",
        "  run:prompt, run:pause=2, run:continue (см. :? run).",
    ]
    found = tags_with_directives(db_file)
    if found:
        lines.append("")
        lines.append("[bold]Runbook tags in the library:[/bold]")
        lines.extend(f"  [bold]{tag}[/bold]  ({count} step(s))" for tag, count in found)
    else:
        lines.append("")
        lines.append("[dim]No tag carries run: directives yet.[/dim]")
    return "\n".join(lines)


# --- проигрывание ------------------------------------------------------------


def _info(text: str) -> Any:
    """InfoBlock для сообщений прогона.

    Импорт ленивый: `app` импортирует этот модуль на старте, поэтому обратный
    импорт допустим только в момент вызова.
    """
    from app import InfoBlock

    return InfoBlock(text)


def _blocks(app: Any) -> list[Any]:
    return list(app.query("CommandBlock"))


def _last_block(app: Any) -> Any:
    blocks = _blocks(app)
    return blocks[-1] if blocks else None


def _submits(app: Any) -> int:
    return int(getattr(app, "_run_submits", 0) or 0)


def _running(app: Any) -> bool:
    return bool(getattr(app, "_run_active", False))


def _block_done(block: Any) -> bool:
    return not getattr(block, "pending", False) and getattr(block, "raw_stdout", "") != "[Executing...]"


async def _wait_step(app: Any, before: Any, *, human: bool) -> StepResult:
    """Дождаться командного блока шага и его завершения.

    Без таймаута: у команды свой `command_timeout`, а человеку в manual/prompt
    никто не назначает дедлайн (остановка — Esc). `human=True` дополнительно
    принимает отправку без нового блока (пустой Enter) как пропуск шага.
    """
    submits_before = _submits(app)
    while _running(app):
        block = _last_block(app)
        if block is not None and block is not before:
            if _block_done(block):
                await asyncio.sleep(0.2)
                return StepResult(ran=True, block=block)
        elif human and _submits(app) != submits_before:
            # Человек отправил строку без командного блока: пустой Enter
            # (пропуск шага) или команда приложения (`:cmd`, `#…`).
            await asyncio.sleep(NO_BLOCK_SETTLE)
            if not _running(app):
                break
            return StepResult()
        await asyncio.sleep(POLL)
    return StepResult(stopped=True)


def _banner(app: Any, plan: RunPlan, step: RunStep, index: int, total: int) -> None:
    app.sub_title = f"RUN {plan.title} · {index}/{total} · {step.mode} · Esc stops"


def _arm_human_step(app: Any, step: RunStep, index: int, total: int) -> None:
    """Подготовить ввод к шагу человека: строка в буфере (manual) или пусто (prompt)."""
    app.set_input_draft(step.text if step.mode == MODE_MANUAL else "")
    hint = f" — {step.hint}" if step.hint else ""
    if step.mode == MODE_MANUAL:
        app.add_block(_info(
            f"[bold]RUN {index}/{total} · manual[/bold]{hint}\n"
            "Enter — выполнить · пустой Enter — пропустить шаг · Esc — остановить прогон"
        ))
    else:
        app.add_block(_info(
            f"[bold]RUN {index}/{total} · prompt[/bold]{hint}\n"
            "Наберите строку и нажмите Enter · Esc — остановить прогон"
        ))


def _end(app: Any, state: Any, message: str = "") -> bool:
    """Снять признак прогона и (если прогон наш) показать сообщение.

    Возвращает True, если признак снял именно этот вызов: иначе прогон уже
    остановлен приложением (`:run stop` / Esc) и печатать второй итог нельзя.
    """
    if getattr(app, "_run_state", None) is not state:
        return False
    app._run_state = None
    app._run_active = False
    app.sub_title = ""
    if message:
        app.add_block(_info(message))
    return True


async def play_runbook(app: Any, plan: RunPlan) -> None:
    """Проиграть план: auto-шаги идут подряд, manual/prompt ждут человека.

    Прогон завершается сам (итог в журнале), останавливается по ошибке
    авто-шага (`stop_on_error`) или по Esc — тогда сообщение печатает
    `_stop_runbook` приложения, а эта функция просто прекращает работу.
    """
    state = getattr(app, "_run_state", None)
    total = len(plan.steps)
    for index, step in enumerate(plan.steps, start=1):
        if not _running(app):
            return
        if state is not None:
            state["index"] = index
        _banner(app, plan, step, index, total)
        before = _last_block(app)
        if step.mode == MODE_AUTO:
            await submit_line(app, step.text)
            if session_line_needs_wait(step.text):
                result = await _wait_step(app, before, human=False)
            else:
                # Команда приложения / сохранение тега: командного блока не будет.
                await asyncio.sleep(NO_BLOCK_SETTLE)
                result = StepResult()
        else:
            _arm_human_step(app, step, index, total)
            result = await _wait_step(app, before, human=True)
        if result.stopped:
            return
        if step.mode == MODE_AUTO and result.block is not None and step.stop_on_error:
            code = int(getattr(result.block, "return_code", 0) or 0)
            if code != 0:
                _end(app, state, (
                    f"[bold red]Runbook {plan.title} stopped[/bold red] · "
                    f"step {index}/{total} exited {code}\n  {step.text}\n"
                    f"[dim]{step.label} · дальше — вручную или `:run {plan.source} --step`[/dim]"
                ))
                return
        pause = plan.pause if step.pause is None else step.pause
        if step.mode == MODE_AUTO:
            if pause > 0:
                await asyncio.sleep(pause)
        elif step.pause:
            await asyncio.sleep(step.pause)
    if state is None:
        return
    _end(app, state, f"Runbook {plan.title}: {total} step(s) done.")
