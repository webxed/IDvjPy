"""Языковой слой демо-туров (`src/demos/text/<lang>/`).

Слой перекрывает только текст (титул и подписи шагов); команды и клавиши берутся
из базового `src/demos/<tour>.yml`. Проверяем, что у каждого языка есть файл на
каждый тур с тем же набором ключей, что `en`, и что он реально накладывается.
"""
from __future__ import annotations

import pytest
import yaml

import demo

TEXT_DIR = demo.BUNDLED_DEMOS_DIR / demo.DEMO_TEXT_DIRNAME
DEFAULT_LANG = "en"


def _languages() -> list[str]:
    if not TEXT_DIR.is_dir():
        return []
    return sorted(path.name for path in TEXT_DIR.iterdir() if path.is_dir())


@pytest.mark.parametrize("lang", _languages())
def test_language_layer_matches_english_keys(lang):
    """У языка есть файл на каждый тур `en`, с теми же шагами/типами."""
    for source in sorted((TEXT_DIR / DEFAULT_LANG).glob("*.yml")):
        target = TEXT_DIR / lang / source.name
        assert target.is_file(), f"нет слоя {lang}/{source.name}"
        base = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        other = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        for key in ("captions", "types"):
            assert set(base.get(key) or {}) == set(other.get(key) or {}), (
                f"{lang}/{source.name}: ключи {key} расходятся с en"
            )


@pytest.mark.parametrize("lang", _languages())
def test_language_layer_overrides_text_but_not_commands(lang):
    """Титул берётся из слоя языка; шаги и клавиши — из базового YAML."""
    base = demo.load_scenario(demo.BUNDLED_DEMOS_DIR / "short.yml")
    localized = demo.load_scenario(demo.BUNDLED_DEMOS_DIR / "short.yml", lang=lang)
    overlay = yaml.safe_load(
        (TEXT_DIR / lang / "short.yml").read_text(encoding="utf-8")
    ) or {}
    if overlay.get("title"):
        assert localized["title"] == overlay["title"]
    assert len(base["steps"]) == len(localized["steps"])
    assert [step.get("keys") for step in base["steps"]] == [
        step.get("keys") for step in localized["steps"]
    ]


def test_chinese_layer_is_actually_applied():
    """`zh` — не откат на базу: титул короткого тура по-китайски."""
    localized = demo.load_scenario(demo.BUNDLED_DEMOS_DIR / "short.yml", lang="zh")
    base = demo.load_scenario(demo.BUNDLED_DEMOS_DIR / "short.yml")
    assert localized["title"] != base["title"]
    assert any("\u4e00" <= ch <= "\u9fff" for ch in localized["title"])
