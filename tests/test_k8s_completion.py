"""Автодополнение ресурсов k8s из живого кластера (фича k8s-completion).

Без сети: kubectl заменяется заглушками. Проверяем парсинг контекста,
фильтр по префиксу, fallback и гейтинг флагом k8s_completion.
"""
import pytest

pytestmark = pytest.mark.slow

import k8s_complete
from k8s_complete import (
    RESOURCE_ALIASES,
    kubectl_resource_candidates,
    parse_kubectl_get_context,
)


def test_parse_context_variants():
    assert parse_kubectl_get_context("kubectl get pod te") == ("pods", None, "te")
    assert parse_kubectl_get_context("kubectl get svc -n prod web") == (
        "services", "prod", "web",
    )
    assert parse_kubectl_get_context("kubectl get pods -A") == ("pods", "", "")
    assert parse_kubectl_get_context("kubectl get deploy --all-namespaces api") == (
        "deployments", "", "api",
    )
    assert parse_kubectl_get_context("echo kubectl get pod te") is None
    assert parse_kubectl_get_context("kubectl describe pod te") is None
    assert parse_kubectl_get_context("kubectl get") is None
    assert parse_kubectl_get_context("kubectl get unknownres x") is None


def test_candidates_filter_and_cap(monkeypatch):
    monkeypatch.setattr(
        k8s_complete,
        "_run_kubectl",
        lambda resource, namespace, timeout: [
            "pod/nginx-1", "pod/nginx-2", "service/web", "pod/nginx-1",
        ],
    )
    names = kubectl_resource_candidates("kubectl get pod nginx")
    assert names == ["nginx-1", "nginx-2"]


def test_candidates_return_none_outside_context(monkeypatch):
    monkeypatch.setattr(
        k8s_complete,
        "_run_kubectl",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert kubectl_resource_candidates("ls -la") is None


def test_candidates_empty_on_kubectl_failure(monkeypatch):
    def boom(*a, **k):
        raise k8s_complete.subprocess.TimeoutExpired("kubectl", 1.0)

    monkeypatch.setattr(k8s_complete, "_run_kubectl", boom)
    assert kubectl_resource_candidates("kubectl get pod te") == []


def test_aliases_cover_common_resources():
    for alias in ("pod", "po", "svc", "deploy", "cm", "ns", "pvc", "sts", "ds"):
        assert alias in RESOURCE_ALIASES


async def test_completion_gated_by_flag(isolated_home, monkeypatch):
    import app as app_module

    (isolated_home / "settings.yml").write_text(
        "k8s_completion: true\ncheck_updates: false\ncommand_timeout: 5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        app_module,
        "kubectl_resource_candidates",
        lambda text: ["pod-alpha", "pod-beta"] if text.startswith("kubectl") else None,
    )
    app = app_module.CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.k8s_completion is True
        assert app.get_completion_candidates("kubectl get pod") == [
            "pod-alpha", "pod-beta",
        ]
        # Некубектл-контекст: обычное дополнение не перехватывается.
        assert app.get_completion_candidates("ls ") != ["pod-alpha", "pod-beta"]


async def test_completion_disabled_by_default(isolated_home):
    import app as app_module

    app = app_module.CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.k8s_completion is False
        # Без флага возвращается пустой список (не список имён кластера).
        assert app.get_completion_candidates("kubectl get pod") == []
