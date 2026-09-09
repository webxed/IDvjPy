"""Кластерный журнал :kctx — UI-сценарии (списки, вход, применение снимков)."""
import json

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner, InfoBlock
from kctx_store import add_snapshot, load_snapshots
from tests.conftest import submit


async def test_assignment_records_snapshot_for_login_cluster(isolated_home, monkeypatch):
    """Вход `klogin prod` запоминает кластер; `$NS=` пишет снимок в kctx.json."""
    app = CommandRunner()
    recorder: list[str] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "run_command", lambda cmd, stdin_data=None, *, no_timeout=False: recorder.append(cmd))
        await submit(pilot, "klogin prod")
        assert app._current_kube_cluster == "prod"
        await submit(pilot, "$NS=team-a")
        await submit(pilot, "$POD=api-7f")
        await submit(pilot, "$EDITOR=nvim")  # не из kubectl-стека
        items = load_snapshots(app.FILE_KCTX)
        # NS=… и NS+POD=… — два разных состояния кластера (оба полезны)
        assert len(items) == 2
        assert all(item["cluster"] == "prod" for item in items)
        assert items[0]["vars"] == {"NS": "team-a", "POD": "api-7f"}  # свежайший
        assert all("EDITOR" not in item["vars"] for item in items)


async def test_kctx_lists_clusters(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        add_snapshot(app.FILE_KCTX, "prod", {"NS": "team-a"}, now=100.0)
        add_snapshot(app.FILE_KCTX, "prod", {"NS": "legacy"}, now=200.0)
        add_snapshot(app.FILE_KCTX, "staging", {"NS": "default"}, now=150.0)
        await submit(pilot, ":kctx")
        texts = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "prod" in texts and "staging" in texts
        assert "2 сн." in texts
        assert ":kctx <cluster>" in texts


async def test_kctx_open_cluster_shows_snapshots_and_apply(isolated_home, monkeypatch):
    app = CommandRunner()
    recorder: list[str] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "run_command", lambda cmd, stdin_data=None, *, no_timeout=False: recorder.append(cmd))
        add_snapshot(app.FILE_KCTX, "prod", {"NS": "team-a", "POD": "api-7f"}, now=100.0)
        add_snapshot(app.FILE_KCTX, "prod", {"NS": "legacy"}, now=200.0)

        await submit(pilot, ":kctx prod")
        texts = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "NS=legacy" in texts
        assert "NS=team-a POD=api-7f" in texts
        assert recorder[-1] == "klogin prod || kubectl config use-context prod"

        await submit(pilot, ":kctx 1")  # свежайший снимок prod
        assert app.local_env.get("NS") == "legacy"
        await submit(pilot, ":kctx 2")
        assert app.local_env.get("NS") == "team-a"
        assert app.local_env.get("POD") == "api-7f"
        bashrc = (isolated_home / app.FILE_BASHRC).read_text(encoding="utf-8")
        assert 'export NS="team-a"' in bashrc
        assert 'export POD="api-7f"' in bashrc


async def test_kctx_digit_guards(isolated_home, monkeypatch):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "run_command", lambda cmd, stdin_data=None, *, no_timeout=False: None)
        await submit(pilot, ":kctx 99")  # списка ещё не открывали
        texts = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "нет открытого списка" in texts
        add_snapshot(app.FILE_KCTX, "staging", {"NS": "default"}, now=100.0)
        await submit(pilot, ":kctx staging")
        await submit(pilot, ":kctx 99")  # индекс вне диапазона
        texts = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "набора 99 нет" in texts


async def test_kctx_cluster_n_applies_in_one_go(isolated_home, monkeypatch):
    app = CommandRunner()
    recorder: list[str] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app, "run_command", lambda cmd, stdin_data=None, *, no_timeout=False: recorder.append(cmd))
        add_snapshot(app.FILE_KCTX, "prod", {"NS": "team-a", "POD": "api-7f"}, now=100.0)
        add_snapshot(app.FILE_KCTX, "staging", {"NS": "default"}, now=200.0)
        await submit(pilot, ":kctx staging 1")
        assert recorder[-1] == "klogin staging || kubectl config use-context staging"
        assert app.local_env.get("NS") == "default"
        assert app.local_env.get("POD") is None  # снимок staging не содержит POD
        assert app._current_kube_cluster == "staging"


async def test_kctx_json_file_shape(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app._current_kube_cluster = "prod"
        app.handle_variable_assignment("$NS=team-a")
        path = isolated_home / "kctx.json"
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == [
            {"cluster": "prod", "vars": {"NS": "team-a"}, "ts": data[0]["ts"]}
        ]
        assert isinstance(data[0]["ts"], float)
