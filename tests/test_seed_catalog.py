"""Empty-database welcome lists every handbook seed."""
import pytest

from i18n import t
from seed_catalog import (
    SEED_HANDBOOKS_CORE,
    SEED_HANDBOOKS_OPS,
    format_empty_db_hint,
    handbook_desc,
    seed_invoke,
)
from seed_groups import group_for_tag, group_tags, handbook_groups, known_group_names


def test_format_empty_db_hint_lists_core_ops_and_bundle():
    text = format_empty_db_hint("mytags.db")
    assert t("catalog.title") in text
    assert "(mytags.db)" in text
    assert seed_invoke("seed_ops.py") in text
    assert "open_handbook_md" in text
    assert "insert_seed_command" in text
    assert "insert_seed_command('seed_ops.py')" in text
    assert ":md" in text
    assert ":welcome" in text
    assert "backups/" in text
    assert ":backup" in text
    for script, doc in SEED_HANDBOOKS_CORE + SEED_HANDBOOKS_OPS:
        assert seed_invoke(script) in text
        assert handbook_desc(script) in text
        assert doc in text
        assert f"open_handbook_md('{doc}')" in text
        assert f"insert_seed_command('{script}')" in text


def test_format_library_overview_groups_handbook_and_custom():
    from seed_catalog import format_library_overview

    text = format_library_overview(["proc", "kpod", "mine", "hls"])
    assert t("catalog.overview_title") in text
    assert ":welcome" in text
    assert "linux" in text
    assert "proc" in text
    assert "k8s" in text
    assert "kpod" in text
    assert "helm" in text
    assert "hls" in text
    assert t("catalog.custom") in text
    assert "mine" in text
    assert "file" not in text
    assert t("catalog.title") not in text
    assert format_library_overview([]) == ""


def test_handbook_groups_cover_core_and_ops():
    groups = handbook_groups()
    assert "linux" in groups
    assert "proc" in groups["linux"]
    assert "k8s" in groups
    assert "kpod" in groups["k8s"]
    assert "git" in groups
    assert "helm" in groups
    assert "hls" in groups["helm"]
    assert "ansible" in groups
    assert group_tags("nonesuch") is None
    assert group_for_tag("hls") == "helm"
    assert group_for_tag("custom") is None
    names = known_group_names()
    assert names == sorted(groups)
    assert "linux" in names and "sysstat" in names


def test_handbook_md_path_resolves_repo_docs():
    from md_viewer import handbook_md_path

    path = handbook_md_path("SEED_LINUX_COMMANDS.md")
    assert path is not None
    assert path.name == "SEED_LINUX_COMMANDS.md"
    assert path.is_file()
    assert handbook_md_path("../etc/passwd") is None
    assert handbook_md_path("nope.txt") is None
    assert handbook_md_path("") is None


def test_handbook_md_path_prefers_language_dir(tmp_path, monkeypatch):
    """Справочник берётся из `docs/<lang>/`, если там есть; иначе — базовый."""
    from md_viewer import handbook_md_path

    docs = tmp_path / "docs"
    (docs / "ru").mkdir(parents=True)
    (docs / "SEED_MINE.md").write_text("base", encoding="utf-8")
    (docs / "ru" / "SEED_MINE.md").write_text("ru", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    ru_path = handbook_md_path("SEED_MINE.md", "ru")
    assert ru_path is not None
    assert ru_path.read_text(encoding="utf-8") == "ru"
    en_path = handbook_md_path("SEED_MINE.md", "en")
    assert en_path is not None
    assert en_path.read_text(encoding="utf-8") == "base"


def _catalog_docs() -> list[str]:
    return [doc for _script, doc in SEED_HANDBOOKS_CORE + SEED_HANDBOOKS_OPS if doc]


def _doc_language_dirs() -> list[str]:
    """Языковые каталоги справочников (`docs/<lang>/`); база — `docs/` без папки."""
    from md_viewer import REPO_ROOT

    docs = REPO_ROOT / "docs"
    if not docs.is_dir():
        return []
    return sorted(path.name for path in docs.iterdir() if path.is_dir())


@pytest.mark.parametrize("lang", _doc_language_dirs())
def test_every_handbook_has_localized_doc(lang):
    """У каждого справочника каталога есть файл языка: `docs/<lang>/<NAME>.md`.

    `handbook_md_path` умеет падать на базовый (русский) файл — этот тест требует
    именно перевод, чтобы `:md <имя>` на языке `lang` не показывал чужой язык.
    """
    from md_viewer import REPO_ROOT, handbook_md_path

    missing = [
        doc
        for doc in _catalog_docs()
        if not (REPO_ROOT / "docs" / lang / doc).is_file()
    ]
    assert not missing, f"нет справочника {lang}: {missing}"
    for doc in _catalog_docs():
        path = handbook_md_path(doc, lang)
        assert path is not None and path.parent.name == lang, doc


@pytest.mark.parametrize("lang", _doc_language_dirs())
def test_localized_handbooks_have_no_cyrillic(lang):
    """`docs/<lang>/` — переводы: кириллица там только ошибка (база — `docs/`)."""
    import re

    from md_viewer import REPO_ROOT

    cyrillic = re.compile(r"[\u0400-\u04FF]")
    bad = [
        path.name
        for path in sorted((REPO_ROOT / "docs" / lang).glob("*.md"))
        if cyrillic.search(path.read_text(encoding="utf-8"))
    ]
    assert not bad, f"кириллица в docs/{lang}: {bad}"
