---
name: tui-workflow
description: Implement or debug IDvjPy_term Textual TUI commands, input, journal, modals, and keyboard/mouse interactions while preserving the app's interaction and secret-handling contracts.
---

# IDvjPy_term TUI workflow

Use this skill for changes to the Textual UI, command routing, input/completion, journal blocks, modal behavior, or terminal interaction. `AGENTS.md` is the source of project-wide invariants; read its relevant sections before editing.

## Workflow

1. Map the relevant symbol and callers with `codegraph_explore` before reading or editing. Most UI orchestration is in `src/app.py`; put substantial new behavior in a focused module and leave `app.py` as routing/orchestration.
2. Preserve the teaching-terminal model: ordinary Enter runs a command; `!tag[tid]`, `!N`, and `!!` only assemble text. Do not expand tag references when saving `#tag command`.
3. Preserve keyboard operation first. Mouse actions may accelerate but must not be the only path. Follow existing Textual patterns for modal focus, journal scroll/focus, and worker-based shell execution; never block the UI thread.
4. For new user-facing text, add an English source key in `src/locales/en.yml`; add Russian text when changing behavior/text in the base Russian layer. Keep YAML boolean-like keys such as `off`, `on`, `n`, and `N` quoted.
5. Treat `$$` secrets and `:vault` values as sensitive data. Never add secret values to command history, journal, exports, audit, mailbox, or process argv. Keep output masking frozen at record time and preserve explicitly documented user-requested exceptions.
6. Add focused tests under `tests/`, preferably using existing Textual Pilot helpers in `tests/conftest.py`. Cover keyboard behavior and safety invariants as well as the visible result.
7. Run the smallest relevant test files, then `ruff` and `basedpyright` when available. Do not run the full suite unless requested; it takes a long time. Do not commit or push unless explicitly requested.
