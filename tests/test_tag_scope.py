"""`:scope` — область видимости тегов в сессии (фильтр представления).

Модуль без Textual: разбор режимов, сопоставление тегов, файл сессии. Логика
инварианта («scope влияет только на списки, не на команды») проверяется здесь;
в TUI за это отвечают `tests/test_scope_command.py`.
"""
from __future__ import annotations

import json
import os

import pytest

import tag_scope as scope_mod
from tag_scope import (
    MODE_HIDE,
    MODE_ONLY,
    ScopeModeError,
    TagScope,
    classify,
    load_scope,
    save_scope,
    scope_file_for,
    scope_path,
    split_names,
)


def test_split_names_by_space_and_comma():
    assert split_names(["git,k8s", "api"]) == ["git", "k8s", "api"]
    assert split_names(["git git", " git"]) == ["git"]


def test_classify_groups_tags_and_unknowns():
    groups, tags, unknown = classify(["git", "api", "nope"], ["api", "logs"])
    assert groups == ["git"]
    assert tags == ["api"]
    assert unknown == ["nope"]


def test_group_wins_over_same_named_tag():
    """`ip` есть и группой, и тегом: группа шире, значит это набор."""
    groups, tags, _ = classify(["ip"], ["ip", "eth"])
    assert groups == ["ip"] and tags == []


def test_only_mode_hides_everything_else():
    scope = TagScope().add(["git"])
    assert scope.mode == MODE_ONLY
    assert scope.matches("gstat") is True  # тег группы git
    assert scope.matches("kpod") is False
    assert scope.matches("my-own-tag") is False
    assert scope.label == "only git"


def test_only_mode_with_explicit_tag():
    scope = TagScope().add(["api"])
    assert scope.matches("api") is True
    assert scope.matches("gstat") is False
    assert scope.label == "only api"


def test_first_rm_switches_to_hide_mode():
    scope = TagScope().drop(["docker"])
    assert scope.mode == MODE_HIDE
    assert scope.matches("dck") is False  # тег группы docker
    assert scope.matches("gstat") is True
    assert scope.matches("my-own-tag") is True
    assert scope.label == "hide docker"


def test_rm_from_only_list_removes_name():
    scope = TagScope().add(["git", "k8s"]).drop(["k8s"])
    assert scope.mode == MODE_ONLY
    assert scope.matches("gstat") is True  # git остался
    assert scope.matches("kpod") is False  # k8s убран


def test_last_rm_clears_the_filter():
    """Убрали последнее — scope пуст, видно всё (без сюрпризов)."""
    assert TagScope().drop(["docker"]).drop(["docker"]).is_empty
    assert TagScope().add(["git"]).drop(["git"]).is_empty


def test_mixing_add_and_rm_is_an_explicit_error():
    with pytest.raises(ScopeModeError):
        TagScope().drop(["docker"]).add(["git"])


def test_split_keeps_order_and_partitions():
    scope = TagScope().add(["git"])
    visible, hidden = scope.split(["kpod", "gstat", "api"])
    assert visible == ["gstat"]
    assert hidden == ["kpod", "api"]


def test_describe_lists_group_tags():
    text = TagScope().add(["git"]).describe()
    assert text.startswith("only: git (")
    assert "gstat" in text
    assert TagScope().describe() == "no filter"


def test_empty_scope_file_is_removed(tmp_path):
    scope = TagScope().add(["git"])
    assert save_scope(str(tmp_path), "default", scope)
    path = scope_path(str(tmp_path), "default")
    assert scope_file_for("default") == "scope_default.json"
    assert json.loads(open(path, encoding="utf-8").read())["mode"] == MODE_ONLY

    assert save_scope(str(tmp_path), "default", TagScope())
    assert not os.path.exists(path)
    loaded, error = load_scope(str(tmp_path), "default")
    assert loaded.is_empty and not error


def test_scope_round_trip_and_sessions_are_isolated(tmp_path):
    save_scope(str(tmp_path), "git", TagScope().add(["git"]))
    save_scope(str(tmp_path), "ops", TagScope().drop(["docker"]))

    git_scope, error = load_scope(str(tmp_path), "git")
    ops_scope, _ = load_scope(str(tmp_path), "ops")
    other, _ = load_scope(str(tmp_path), "other")
    assert not error
    assert (git_scope.mode, git_scope.groups) == (MODE_ONLY, ("git",))
    assert (ops_scope.mode, ops_scope.groups) == (MODE_HIDE, ("docker",))
    assert other.is_empty


def test_broken_scope_file_is_reported_not_guessed(tmp_path):
    path = scope_path(str(tmp_path), "default")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{not json")
    scope, error = load_scope(str(tmp_path), "default")
    assert scope.is_empty and "scope_default.json" in error

    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"mode": "sometimes", "groups": ["git"]}, handle)
    scope, error = load_scope(str(tmp_path), "default")
    assert scope.is_empty and "unknown mode" in error


def test_load_missing_file_is_not_an_error(tmp_path):
    scope, error = load_scope(str(tmp_path), "nothing-here")
    assert scope.is_empty and error == ""


def test_module_constants_match_expected_filenames():
    assert scope_mod.SCOPE_PREFIX == "scope_"
    assert scope_mod.MODE_ONLY == "only"
    assert scope_mod.MODE_HIDE == "hide"
