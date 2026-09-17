"""Юнит-тесты кластерного журнала kubectl-стека (src/kctx_store.py)."""
from __future__ import annotations

import json

import pytest

from kctx_store import (
    KUBE_STACK_VARS,
    add_snapshot,
    cluster_summary,
    format_vars,
    load_snapshots,
    parse_cluster_login,
    parse_kctx_vars,
    snapshots_for_cluster,
    stack_vars,
)

# --- parse_cluster_login -------------------------------------------------

@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("klogin prod", "prod"),
        ("klogin   aws-prod ", "aws-prod"),
        ("tsh kube login staging", "staging"),
        ("tsh  kube  login  tc-1 ", "tc-1"),
        ("kubectl config use-context legacy", "legacy"),
        ("kubectl   config   use-context   aws/team-a", "aws/team-a"),
        ("klogin prod && kubectl get ns", "prod"),
        ("kubectl get pods", None),
        ("tsh kube login", None),
        ("kubectl config use-context", None),
        ("kubectl config get-contexts", None),
        ("echo klogin demo", None),
        ("$NS=team-a", None),
        ("", None),
    ],
)
def test_parse_cluster_login(line: str, expected: str | None) -> None:
    assert parse_cluster_login(line) == expected


# --- parse_kctx_vars -----------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (["NS", "RELEASE"], ("NS", "RELEASE")),
        ("NS, RELEASE", ("NS", "RELEASE")),
        ("NS RELEASE", ("NS", "RELEASE")),
        # Ведущие `$` / `:` — как в settings.yml их пишут руками — отбрасываются.
        (["$NS", ":RELEASE", " NS "], ("NS", "RELEASE")),
        (["NS, CHART", "VALUES"], ("NS", "CHART", "VALUES")),
        # Повторы — один раз (порядок первого вхождения сохраняется).
        (["NS", "NS", "POD"], ("NS", "POD")),
        # Негодные имена (дефис, с цифры) и пустые элементы — мимо.
        (["bad-name", "2X", "NS", ""], ("NS",)),
        # Явное «выключено».
        ([], ()),
        (None, ()),
        (False, ()),
        ("", ()),
        # Непонятное значение — как по умолчанию.
        (True, KUBE_STACK_VARS),
        (42, KUBE_STACK_VARS),
        ({"NS": 1}, KUBE_STACK_VARS),
    ],
)
def test_parse_kctx_vars(raw, expected) -> None:
    assert parse_kctx_vars(raw) == expected


def test_default_kctx_vars_cover_bundled_templates() -> None:
    """Дефолт — стек bundled-шаблонов: kubectl (seed_k8s_chains) + helm (seed_helm)."""
    assert set(KUBE_STACK_VARS) == {
        "NS", "POD", "DEPLOY", "SVC", "ING", "APP", "CTR", "QUOTA",
        "RELEASE", "CHART", "VALUES",
    }


# --- stack_vars / format_vars -------------------------------------------

def test_stack_vars_keeps_only_kube_stack() -> None:
    env = {
        "NS": "team-a",
        "POD": "api-7f",
        "DEPLOY": "api",
        "EDITOR": "nvim",
        "HOST": "example.com",
        "SVC": "api-svc",
        "QUOTA": "",
    }
    assert stack_vars(env) == {"NS": "team-a", "POD": "api-7f", "DEPLOY": "api", "SVC": "api-svc"}
    assert format_vars({"NS": "team-a", "POD": "api-7f", "EDITOR": "x"}) == "NS=team-a POD=api-7f"


def test_stack_vars_empty_when_nothing_set() -> None:
    assert stack_vars({"EDITOR": "nvim", "QUOTA": ""}) == {}


def test_stack_vars_and_format_vars_respect_custom_names() -> None:
    """Список имён задаётся снаружи (kctx_vars); порядок строки — как в нём."""
    env = {"NS": "team-a", "RELEASE": "myapp", "EDITOR": "nvim"}
    assert stack_vars(env, ("RELEASE",)) == {"RELEASE": "myapp"}
    assert stack_vars(env, ()) == {}  # журнал выключен ключом kctx_vars: []
    assert stack_vars(env)["RELEASE"] == "myapp"  # дефолт включает helm
    assert format_vars(env, ("RELEASE", "NS")) == "RELEASE=myapp NS=team-a"


# --- add_snapshot / load -------------------------------------------------

def test_add_snapshot_creates_file_with_stack_subset(tmp_path) -> None:
    path = tmp_path / "kctx.json"
    env = {"NS": "team-a", "POD": "api-7f", "EDITOR": "nvim"}
    assert add_snapshot(str(path), "prod", env, now=1000.0) is True
    items = load_snapshots(str(path))
    assert len(items) == 1
    assert items[0] == {
        "cluster": "prod",
        "ts": 1000.0,
        "vars": {"NS": "team-a", "POD": "api-7f"},
    }


def test_add_snapshot_skips_without_cluster_or_vars(tmp_path) -> None:
    path = tmp_path / "kctx.json"
    assert add_snapshot(str(path), "", {"NS": "x"}, now=1.0) is False
    assert add_snapshot(str(path), "prod", {"EDITOR": "nvim"}, now=1.0) is False
    assert not path.exists()


def test_add_snapshot_dedupes_identical_last(tmp_path) -> None:
    path = tmp_path / "kctx.json"
    env = {"NS": "team-a", "POD": "api-7f"}
    assert add_snapshot(str(path), "prod", env, now=1000.0) is True
    assert add_snapshot(str(path), "prod", env, now=2000.0) is True
    items = load_snapshots(str(path))
    assert len(items) == 1
    assert items[0]["ts"] == 2000.0  # только bump времени, без дубля


def test_add_snapshot_appends_on_var_change_and_orders_newest_first(tmp_path) -> None:
    path = tmp_path / "kctx.json"
    add_snapshot(str(path), "prod", {"NS": "team-a"}, now=1000.0)
    add_snapshot(str(path), "prod", {"NS": "legacy", "POD": "db-2"}, now=2000.0)
    add_snapshot(str(path), "staging", {"NS": "default"}, now=1500.0)
    items = load_snapshots(str(path))
    assert len(items) == 3
    rows = snapshots_for_cluster(items, "prod")
    assert [row["vars"] for row in rows] == [
        {"NS": "legacy", "POD": "db-2"},
        {"NS": "team-a"},
    ]
    summary = cluster_summary(items)
    assert [(s["cluster"], s["count"]) for s in summary] == [("prod", 2), ("staging", 1)]


def test_add_snapshot_respects_per_cluster_and_total_limits(tmp_path) -> None:
    path = tmp_path / "kctx.json"
    per_cluster, total = 3, 10
    for i in range(5):
        add_snapshot(
            str(path), "prod", {"NS": f"ns{i}"}, now=float(i),
            per_cluster_limit=per_cluster, total_limit=total,
        )
    for i in range(3):
        add_snapshot(
            str(path), "staging", {"NS": f"d{i}"}, now=float(i),
            per_cluster_limit=per_cluster, total_limit=total,
        )
    add_snapshot(
        str(path), "prod", {"NS": "fresh"}, now=100.0,
        per_cluster_limit=per_cluster, total_limit=total,
    )
    items = load_snapshots(str(path))
    # per-cluster лимит 3: у prod остаются свежайшие 3
    prod_rows = snapshots_for_cluster(items, "prod")
    assert len(prod_rows) == 3
    assert prod_rows[0]["vars"] == {"NS": "fresh"}
    assert prod_rows[-1]["vars"] == {"NS": "ns3"}  # ns0..ns2 вытеснены

    # после per-cluster лимита 3: prod 3 + staging 3 = 6 записей (total 10 не режет)
    assert len(items) == 6


def test_load_snapshots_tolerates_garbage(tmp_path) -> None:
    path = tmp_path / "kctx.json"
    path.write_text("not json {{{", encoding="utf-8")
    assert load_snapshots(str(path)) == []
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert load_snapshots(str(path)) == []
    path.write_text(json.dumps([{"cluster": 1}]), encoding="utf-8")
    assert load_snapshots(str(path)) == []
    assert load_snapshots(str(tmp_path / "missing.json")) == []


def test_add_snapshot_repairs_garbage_file(tmp_path) -> None:
    path = tmp_path / "kctx.json"
    path.write_text("garbage", encoding="utf-8")
    assert add_snapshot(str(path), "prod", {"NS": "team-a"}, now=1000.0) is True
    items = load_snapshots(str(path))
    assert len(items) == 1
    assert items[0]["vars"] == {"NS": "team-a"}


def test_add_snapshot_honours_custom_var_names(tmp_path) -> None:
    """`var_names` (ключ kctx_vars) решает, что попадёт в снимок."""
    path = tmp_path / "kctx.json"
    env = {"NS": "team-a", "RELEASE": "myapp"}
    assert add_snapshot(
        str(path), "prod", env, now=1000.0, var_names=("RELEASE",)
    ) is True
    items = load_snapshots(str(path))
    assert items[0]["vars"] == {"RELEASE": "myapp"}
    # Пустой список — журнал выключен: новая запись не появляется.
    assert add_snapshot(str(path), "prod", env, now=2000.0, var_names=()) is False
    assert len(load_snapshots(str(path))) == 1
