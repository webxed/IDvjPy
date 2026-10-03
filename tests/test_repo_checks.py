"""Read-only helpers: protected data, focused pytest plan and local docs links."""

from repo_checks import (
    APP_CONTRACT_TESTS,
    ROOT,
    TUI_CONTRACT_GROUPS,
    focused_tests_for_path,
    focused_tests_for_paths,
    local_link_error,
    markdown_links,
    protected_data_paths,
    untracked_paths_from_porcelain,
)


def test_protected_data_paths_cover_session_state_without_templates():
    paths = [
        "settings.yml",
        "mytags.db",
        "history_default.txt",
        "secrets_default.json",
        "inbox_default.jsonl",
        "session_default.pid",
        ".bashrc_term_default",
        "demo_cmd.txt",
        "playbook.yml",
        ".codegraph/index",
        "backups/seed.db",
        "src/.bashrc_term.example",
        "src/settings/ru.yml",
    ]
    assert protected_data_paths(paths) == paths[:11]


def test_focused_tests_map_conventional_and_special_surfaces():
    tests = focused_tests_for_paths(
        [
            "src/system_complete.py",
            "src/app.py",
            "src/locales/en.yml",
            "src/seed_ssh.py",
            "src/db_transfer.py",
            ".github/workflows/tests.yml",
            "docker/Dockerfile",
        ]
    )
    assert "tests/test_system_command_completion.py" in tests
    assert set(APP_CONTRACT_TESTS).issubset(tests)
    assert {"tests/test_i18n.py", "tests/test_seed_catalog.py", "tests/test_db_transfer.py"}.issubset(tests)
    assert {"tests/test_ci_shards.py", "tests/test_docker_stand.py"}.issubset(tests)
    assert len(tests) == len(set(tests))


def test_untracked_paths_from_porcelain_extracts_only_untracked_entries():
    status = " M src/app.py\0?? check_docs.py\0?? docs/new.md\0"
    assert untracked_paths_from_porcelain(status) == ["check_docs.py", "docs/new.md"]


def test_focused_tests_for_path_keeps_unmapped_module_empty():
    assert focused_tests_for_path("src/not_covered_by_a_test.py") == []
    assert focused_tests_for_path("src/app.py")


def test_contract_groups_reference_existing_tests_and_are_not_empty():
    assert TUI_CONTRACT_GROUPS
    for name, tests in TUI_CONTRACT_GROUPS.items():
        assert tests, name
        assert all((ROOT / test).is_file() for test in tests), name


def test_markdown_link_parser_ignores_image_and_external_url(tmp_path):
    text = "[local](guide.md) ![image](image.png) [site](https://example.test)"
    assert markdown_links(text) == ["guide.md", "https://example.test"]
    markdown = tmp_path / "doc.md"
    markdown.write_text(text, encoding="utf-8")
    assert local_link_error(markdown, "https://example.test") is None


def test_local_link_error_rejects_missing_target_and_escape(tmp_path, monkeypatch):
    import repo_checks

    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    markdown = docs / "doc.md"
    markdown.write_text("", encoding="utf-8")
    monkeypatch.setattr(repo_checks, "ROOT", root)
    assert local_link_error(markdown, "missing.md") == "target does not exist"
    assert local_link_error(markdown, "../../outside.md") == "link leaves repository"
