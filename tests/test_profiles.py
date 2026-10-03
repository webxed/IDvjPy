from __future__ import annotations

from app import CommandRunner
from profile_store import load_profile, save_profile
from tag_scope import TagScope
from tests.conftest import last_info, submit


def test_profile_round_trip_is_private_and_does_not_store_secrets(tmp_path):
    payload = {
        "version": 1,
        "name": "prod",
        "cwd": str(tmp_path),
        "scope": {"mode": "only", "groups": ["git"], "tags": ["deploy"]},
        "namespace": "production",
        "kube_context": "prod-cluster",
    }
    assert save_profile(str(tmp_path), payload) is None
    loaded, error = load_profile(str(tmp_path), "prod")
    assert error == ""
    assert loaded == payload
    path = tmp_path / "profile_prod.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert "password" not in path.read_text(encoding="utf-8")


def test_profile_rejects_secret_like_fields(tmp_path):
    payload = {"name": "prod", "cwd": str(tmp_path), "password": "do-not-save"}
    error = save_profile(str(tmp_path), payload)
    assert error is not None
    assert "secret-like" in error


def test_profile_rejects_unknown_fields(tmp_path):
    payload = {"name": "prod", "cwd": str(tmp_path), "unexpected": "value"}
    error = save_profile(str(tmp_path), payload)
    assert error is not None
    assert "unknown profile field" in error


def test_profile_bad_json_is_reported(tmp_path):
    (tmp_path / "profile_prod.json").write_text("[]", encoding="utf-8")
    profile, error = load_profile(str(tmp_path), "prod")
    assert profile is None
    assert "JSON root" in error


async def test_profile_commands_save_use_and_remove(isolated_home, tmp_path):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        app._data_dir = str(tmp_path)
        app._tag_scope = TagScope(mode="only", groups=("git",), tags=())
        app.local_env["NS"] = "staging"
        await submit(pilot, ":profile save staging")
        assert "Profile saved" in last_info(app).text_content

        app._tag_scope = TagScope()
        app.local_env.pop("NS")
        await submit(pilot, ":profile use staging")
        assert "Profile applied" in last_info(app).text_content
        assert app._tag_scope.groups == ("git",)
        assert app.local_env["NS"] == "staging"

        await submit(pilot, ":profile rm staging")
        assert "Profile removed" in last_info(app).text_content
        assert not (tmp_path / "profile_staging.json").exists()
