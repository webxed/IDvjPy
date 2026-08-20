"""Play a YAML scenario as if a person is typing in the TUI.

Used by ``python3 app.py --demo`` so a tour can be recorded (asciinema, OBS)
or shown live. Esc cancels playback; the session stays open unless ``--demo-quit``.
"""
from __future__ import annotations

import asyncio
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

import yaml
from textual import events
from textual.keys import REPLACED_KEYS, _character_to_key, _get_unicode_name_from_key

BUNDLED_DEMOS_DIR = Path(__file__).resolve().parent / "demos"
RE_DEMO_SAVE_TAG = re.compile(r"^#([A-Za-z_][A-Za-z0-9]*)")

KEY_ALIASES = {
    "esc": "escape",
    "return": "enter",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "page-down": "pagedown",
    "page-up": "pageup",
}

DEFAULTS = {
    "start_pause": 1.4,
    "type_delay": 0.12,
    "pause": 1.1,
    "command_timeout": 12.0,
}


def bundled_demo_names() -> List[str]:
    if not BUNDLED_DEMOS_DIR.is_dir():
        return []
    return sorted(path.stem for path in BUNDLED_DEMOS_DIR.glob("*.yml"))


def resolve_demo_path(name: str) -> Optional[Path]:
    """Resolve a bundled name (``short``) or a filesystem path."""
    raw = (name or "").strip()
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if candidate.is_file():
        return candidate.resolve()
    if candidate.suffix.lower() not in {".yml", ".yaml"}:
        with_ext = candidate.with_suffix(".yml")
        if with_ext.is_file():
            return with_ext.resolve()
    bundled = BUNDLED_DEMOS_DIR / raw
    if bundled.is_file():
        return bundled.resolve()
    bundled_yml = BUNDLED_DEMOS_DIR / f"{raw}.yml"
    if bundled_yml.is_file():
        return bundled_yml.resolve()
    cwd_demo = Path.cwd() / "demos" / raw
    if cwd_demo.is_file():
        return cwd_demo.resolve()
    cwd_yml = Path.cwd() / "demos" / f"{raw}.yml"
    if cwd_yml.is_file():
        return cwd_yml.resolve()
    return None


def load_scenario(path: Union[str, Path]) -> Dict[str, Any]:
    """Load and normalize a demo YAML file."""
    demo_path = Path(path)
    with demo_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Demo scenario must be a mapping: {demo_path}")
    data.setdefault("title", demo_path.stem)
    data["steps"] = [normalize_step(step) for step in (data.get("steps") or [])]
    if not data["steps"]:
        raise ValueError(f"Demo scenario has no steps: {demo_path}")
    return data


def collect_reset_tags(scenario: Dict[str, Any]) -> List[str]:
    """Tags the scenario will `#tag cmd`-save. Cleared before playback so tids restart at 1."""
    tags: List[str] = []
    seen = set()
    for raw in scenario.get("reset_tags") or []:
        name = str(raw).strip()
        if name and name not in seen:
            seen.add(name)
            tags.append(name)
    for step in scenario.get("steps") or []:
        if isinstance(step, str):
            text = step.strip()
        else:
            text = (step.get("type") or "").strip()
        if len(text) < 2 or not text.startswith("#"):
            continue
        if text[1] in " \t":
            continue
        match = RE_DEMO_SAVE_TAG.match(text)
        if not match:
            continue
        tag = match.group(1)
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def _reset_demo_tags(app: Any, tags: List[str]) -> None:
    if not tags:
        return
    db_file = getattr(app, "db_file", None)
    if not db_file:
        return
    import database_v2 as database

    for tag in tags:
        database.hard_delete_commands_by_tag(db_file, tag)
    if hasattr(app, "_populate_query_results"):
        app._populate_query_results()


def load_demo_for_cli(name: str) -> Dict[str, Any]:
    """Resolve ``--demo`` for the launcher; exit with a hint on failure."""
    path = resolve_demo_path(name)
    if path is None:
        available = ", ".join(bundled_demo_names()) or "(none)"
        print(
            f"Demo not found: {name!r}\n"
            f"Bundled scenarios: {available}\n"
            "Pass a name (short, full) or a path to a .yml file.",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        return load_scenario(path)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        print(f"Cannot load demo {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def normalize_step(raw: Any) -> Dict[str, Any]:
    """Turn a YAML step (string or mapping) into a playback dict."""
    if isinstance(raw, str):
        return {
            "caption": "",
            "type": raw,
            "keys": [],
            "enter": True,
            "clear": True,
            "wait_command": False,
            "paste": False,
            "pause": None,
            "type_delay": None,
        }
    if not isinstance(raw, dict):
        raise ValueError(f"Demo step must be a string or mapping, got {type(raw).__name__}")

    type_text = raw.get("type", raw.get("text", "")) or ""
    if not isinstance(type_text, str):
        type_text = str(type_text)

    keys_raw = raw.get("keys", [])
    if isinstance(keys_raw, str):
        keys_raw = [part.strip() for part in keys_raw.split(",") if part.strip()]
    keys = [_normalize_key(key) for key in (keys_raw or [])]

    enter = raw.get("enter")
    if enter is None:
        enter = bool(type_text) and not keys and not raw.get("paste")

    pause = raw.get("pause", raw.get("wait"))
    step_delay = raw.get("type_delay")
    return {
        "caption": str(raw.get("caption", raw.get("say", "")) or ""),
        "type": type_text,
        "keys": keys,
        "enter": bool(enter),
        "clear": bool(raw.get("clear", bool(type_text))),
        "wait_command": bool(raw.get("wait_command", False)),
        "paste": bool(raw.get("paste", False)),
        "pause": None if pause is None else float(pause),
        "type_delay": None if step_delay is None else float(step_delay),
    }


def _normalize_key(key: str) -> str:
    name = str(key).strip().lower().replace(" ", "")
    return KEY_ALIASES.get(name, name)


def _delay(seconds: float, speed: float) -> float:
    if seconds <= 0:
        return 0.0
    return max(0.0, seconds / max(speed, 0.05))


async def play_demo(app: Any, scenario: Dict[str, Any], speed: float = 1.0, quit_when_done: bool = False) -> None:
    """Drive ``CommandRunner`` with simulated keypresses."""
    title = str(scenario.get("title") or "demo")
    start_pause = float(scenario.get("start_pause", DEFAULTS["start_pause"]))
    type_delay = float(scenario.get("type_delay", DEFAULTS["type_delay"]))
    default_pause = float(scenario.get("pause", DEFAULTS["pause"]))
    command_timeout = float(scenario.get("command_timeout", DEFAULTS["command_timeout"]))
    steps: List[Dict[str, Any]] = list(scenario.get("steps") or [])

    app._demo_active = True
    app.sub_title = f"DEMO · {title} · Esc stops"
    try:
        _reset_demo_tags(app, collect_reset_tags(scenario))
        await asyncio.sleep(_delay(start_pause, speed))
        for index, step in enumerate(steps, start=1):
            if not getattr(app, "_demo_active", False):
                return
            caption = step.get("caption") or f"step {index}/{len(steps)}"
            app.sub_title = f"DEMO · {caption} · Esc stops"
            step_delay = step.get("type_delay")
            delay = type_delay if step_delay is None else float(step_delay)
            await _play_step(
                app,
                step,
                type_delay=_delay(delay, speed),
                command_timeout=command_timeout,
            )
            app._demo_pressing = False
            if not getattr(app, "_demo_active", False):
                return
            pause = default_pause if step.get("pause") is None else float(step["pause"])
            await asyncio.sleep(_delay(pause, speed))
        app.sub_title = "Demo finished. You can type now."
        if quit_when_done or scenario.get("quit"):
            await asyncio.sleep(_delay(1.2, speed))
            app.exit()
            return
        app.set_timer(4, app.clear_subtitle)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        app.sub_title = f"Demo error: {exc}"
    finally:
        app._demo_active = False


async def _play_step(
    app: Any,
    step: Dict[str, Any],
    *,
    type_delay: float,
    command_timeout: float,
) -> None:
    key_gap = 0.08 if type_delay > 0.01 else 0.02
    typed = step.get("type") or ""
    app._demo_pressing = True
    prior = _last_command_block(app) if step.get("wait_command") else None
    if typed:
        _prepare_input(app, clear=bool(step.get("clear")))
        await _ensure_input_focus(app)
        await _type_text(app, typed, type_delay)
        if step.get("enter") and type_delay > 0:
            # Give the viewer time to read the finished line before Enter.
            await asyncio.sleep(min(0.7, max(0.35, type_delay * 4)))
    if step.get("enter"):
        # Enter on a journal block turns on line-cursor (looks like F2) and
        # never submits `| jq`. Retry only when that happened.
        _hide_completion(app)
        await _ensure_input_focus(app)
        await _press(app, ["enter"], gap=key_gap)
        cleared_timeout = 0.5 if type_delay > 0.01 else 0.2
        if not await _wait_input_cleared(app, timeout=cleared_timeout):
            focused = getattr(app, "focused", None)
            if getattr(focused, "line_nav_active", False):
                _exit_line_nav(app)
                await _ensure_input_focus(app)
                await _press(app, ["enter"], gap=key_gap)
                await _wait_input_cleared(app, timeout=0.8)
    keys = step.get("keys") or []
    if keys:
        await _press(app, keys, gap=key_gap)
    if step.get("paste"):
        await _ensure_input_focus(app)
        if hasattr(app, "action_paste_clipboard"):
            app.action_paste_clipboard()
        await asyncio.sleep(0.05)
    if step.get("wait_command"):
        await _wait_command_done(app, command_timeout, after=prior)


def _hide_completion(app: Any) -> None:
    completion = getattr(app, "_completion_list", None)
    if completion is not None:
        completion.hide()


def _prepare_input(app: Any, *, clear: bool) -> None:
    """Focus the prompt without synthesizing Esc (that would abort the demo)."""
    _hide_completion(app)
    inp = app.query_one("#command-input")
    inp.focus()
    if clear:
        inp.value = ""
        inp.cursor_position = 0
    else:
        inp.cursor_position = len(inp.value or "")


async def _wait_input_focus(app: Any, timeout: float = 1.0) -> None:
    """focus() is applied on the next refresh; don't type before that."""
    await _ensure_input_focus(app, timeout=timeout)


def _exit_line_nav(app: Any) -> None:
    focused = getattr(app, "focused", None)
    if focused is not None and getattr(focused, "line_nav_active", False):
        if hasattr(focused, "exit_line_nav"):
            focused.exit_line_nav(notify=False)


async def _ensure_input_focus(app: Any, timeout: float = 2.0) -> bool:
    """Focus the prompt so Enter submits a command instead of line-cursor."""
    _exit_line_nav(app)
    _hide_completion(app)
    inp = app.query_one("#command-input")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if inp.has_focus:
            await asyncio.sleep(0.02)
            if inp.has_focus:
                return True
        inp.focus()
        await asyncio.sleep(0.03)
    return bool(inp.has_focus)


async def _wait_input_cleared(app: Any, timeout: float = 0.6) -> bool:
    """True when Enter actually submitted the prompt (input became empty)."""
    inp = app.query_one("#command-input")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not (inp.value or "").strip():
            await asyncio.sleep(0.04)
            return True
        await asyncio.sleep(0.03)
    return not (inp.value or "").strip()


def _type_gap(type_delay: float, text: str) -> float:
    """Per-character pause; long lines type faster so URLs don't crawl."""
    if type_delay <= 0:
        return 0.005
    scale = min(1.0, 28.0 / max(len(text), 1))
    return max(0.028, type_delay * scale)


async def _type_text(app: Any, text: str, type_delay: float) -> None:
    """Insert characters into the prompt so completion still updates.

    Key events are easy to drop while focus is settling; setting ``value``
    is visible in the TUI and matches what a person would see being typed.
    """
    inp = app.query_one("#command-input")
    gap = _type_gap(type_delay, text)
    for char in text:
        if not getattr(app, "_demo_active", False):
            return
        if not inp.has_focus:
            _exit_line_nav(app)
            inp.focus()
        # Suppress completion so a later Enter is not eaten by a candidate.
        inp._applying_completion = True
        pos = inp.cursor_position or 0
        current = inp.value or ""
        inp.value = current[:pos] + char + current[pos:]
        inp.cursor_position = pos + 1
        inp._applying_completion = True
        await asyncio.sleep(gap)


async def _press(app: Any, keys: Iterable[str], gap: float = 0.08) -> None:
    """Send keys through the app queue without waiting on Textual's animator.

    ``App._press_keys`` calls ``wait_until_complete``, which can deadlock when
    the demo itself is running as a worker (completion list / screen animations).

    Do not use ``driver.send_message`` from this worker: it posts via
    ``run_coroutine_threadsafe``, so Tab/F2/Enter arrive late — often while the
    next step is typing ``| jq``. Enter on a journal block is line-cursor (F2).
    """
    batch = [key for key in keys if key]
    if not batch:
        return
    app._demo_pressing = True
    settle = gap if gap > 0 else 0.02
    for key in batch:
        key_name = key
        if len(key_name) == 1 and not key_name.isalnum():
            key_name = _character_to_key(key_name)
        original_key = REPLACED_KEYS.get(key_name, key_name)
        try:
            char: Optional[str] = unicodedata.lookup(
                _get_unicode_name_from_key(original_key)
            )
        except KeyError:
            char = key_name if len(key_name) == 1 else None
        event = events.Key(key_name, char)
        event.set_sender(app)
        app.post_message(event)
        await asyncio.sleep(settle)


async def _wait_command_done(app: Any, timeout: float, after: Any = None) -> None:
    """Wait until a *new* CommandBlock appears and finishes.

    If we only look at the last block, a pipe/jq step can return immediately
    because the previous curl/echo block is already done.
    """
    deadline = time.monotonic() + max(timeout, 0.5)
    block = None
    while time.monotonic() < deadline:
        if not getattr(app, "_demo_active", False):
            return
        blocks = list(app.query("CommandBlock"))
        if blocks and blocks[-1] is not after:
            block = blocks[-1]
            break
        await asyncio.sleep(0.05)
    if block is None:
        return
    while time.monotonic() < deadline:
        if not getattr(app, "_demo_active", False):
            return
        if (
            not getattr(block, "pending", False)
            and getattr(block, "raw_stdout", "") != "[Executing...]"
        ):
            await asyncio.sleep(0.2)
            return
        await asyncio.sleep(0.05)
    app.sub_title = "DEMO · command still running · Esc stops"


def _last_command_block(app: Any) -> Any:
    blocks = list(app.query("CommandBlock"))
    return blocks[-1] if blocks else None
