---
name: localization
description: Localize IDvjPy_term UI, settings, LLM provider examples, seed comments, demos, and documentation while preserving the project's English UI catalog and Russian content source of truth.
---

# IDvjPy_term localization workflow

Use for language selection, locale keys, translated seed/demo text, localized configuration examples, and README/docs. `AGENTS.md` owns the full localization policy; follow it rather than aiming for blanket translation parity.

## Sources of truth

- UI catalog: `src/locales/en.yml` is authoritative and must contain every active UI key. Russian and Chinese UI catalogs may fall back to English.
- Content: Russian is the base for `docs/*.md`, root `README.md`, built-in seed comments, base demo YAML, and `src/settings/ru.yml` / `src/llm_providers/ru.yml`. Update English/Chinese content only when requested or needed for a touched localized layer.
- Seed translations: `src/seed_text/<lang>/<handbook>.yml`; demo text: `src/demos/text/<lang>/`; docs: `docs/<lang>/`; settings/provider templates: `src/settings/<lang>.yml` and `src/llm_providers/<lang>.yml`.

## Workflow

1. Find the locale-loading/fallback path in `src/i18n.py`, `src/seed_lib.py`, `src/demo.py`, or `src/example_config.py` before changing it.
2. Add UI keys to English first and keep placeholders and Rich/Textual markup identical across translations. User-facing app messages must use locale keys, not hardcoded strings.
3. Preserve command names, tag names, settings keys, filenames, shell syntax, flags, environment variable names, and the product tagline. Quote YAML keys that resolve as booleans (`"off"`, `"on"`, `"n"`, `"N"`).
4. Do not duplicate built-in Russian seed/demo content into the English layer. For an already-seeded DB, use/update `:relang` behavior rather than re-seeding or overwriting user-edited comments.
5. Keep `README.md` Russian; translations belong in `docs/<lang>/README.md`. Do not translate content broadly unless requested.
6. Run focused checks: `python3 -m pytest tests/test_i18n.py -q`, `tests/test_seed_i18n.py`, `tests/test_demo_i18n.py`, or related config-template tests. If strict parity tests fail on unrelated known gaps, report that rather than adding unnecessary translations.
