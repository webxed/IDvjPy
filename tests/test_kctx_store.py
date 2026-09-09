"""Юнит-тесты кластерного журнала kubectl-стека (src/kctx_store.py)."""
from __future__ import annotations

import json

import pytest

from kctx_store import (
    add_snapshot,
    cluster_summary,
    format_vars,
    load_snapshots,
    parse_cluster_login,
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
    kwargs = {"per_cluster_limit": 3, "total_limit": 10}
    for i in range(5):
        add_snapshot(str(path), "prod", {"NS": f"ns{i}"}, now=float(i), **kwargs)
    for i in range(3):
        add_snapshot(str(path), "staging", {"NS": f"d{i}"}, now=float(i), **kwargs)
    add_snapshot(str(path), "prod", {"NS": "fresh"}, now=100.0, **kwargs)
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
