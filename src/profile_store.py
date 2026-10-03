"""Safe, local storage for named runtime context profiles.

Profiles contain references to an environment, not credentials.  They are kept
outside the tag database and are intentionally limited to a small schema so a
future setting cannot accidentally persist secrets.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from tag_scope import TagScope

PREFIX = "profile_"
SUFFIX = ".json"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_ALLOWED = {"version", "name", "cwd", "scope", "namespace", "kube_context"}
_SECRET_WORDS = {"password", "secret", "token", "key", "vault", "credential"}


class ProfileError(ValueError):
    """Invalid or unsafe profile data."""


def validate_name(name: str) -> str:
    value = str(name).strip()
    if not _NAME_RE.fullmatch(value):
        raise ProfileError("profile name must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
    return value


def profile_file_for(name: str) -> str:
    return f"{PREFIX}{validate_name(name)}{SUFFIX}"


def profile_path(data_dir: str, name: str) -> Path:
    return Path(data_dir) / profile_file_for(name)


def _check_secret_names(value: object) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold()
            if any(word in normalized for word in _SECRET_WORDS):
                raise ProfileError(f"secret-like field is not allowed: {key}")
            _check_secret_names(child)
    elif isinstance(value, list):
        for child in value:
            _check_secret_names(child)


def _normalize_scope(value: object) -> dict[str, list[str] | str]:
    if value is None:
        return {"mode": "", "groups": [], "tags": []}
    if not isinstance(value, dict):
        raise ProfileError("scope must be an object")
    mode = str(value.get("mode") or "").strip().lower()
    groups = value.get("groups") or []
    tags = value.get("tags") or []
    if mode not in ("", "only", "hide"):
        raise ProfileError(f"unknown scope mode: {mode}")
    if not isinstance(groups, list) or not isinstance(tags, list):
        raise ProfileError("scope groups and tags must be arrays")
    clean_groups = [str(item).strip() for item in groups if str(item).strip()]
    clean_tags = [str(item).strip() for item in tags if str(item).strip()]
    if not clean_groups and not clean_tags:
        mode = ""
    if not mode and (clean_groups or clean_tags):
        raise ProfileError("a non-empty scope needs mode 'only' or 'hide'")
    return {"mode": mode, "groups": clean_groups, "tags": clean_tags}


def normalize(payload: object, *, expected_name: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProfileError("JSON root must be an object")
    _check_secret_names(payload)
    unknown = set(payload) - _ALLOWED
    if unknown:
        raise ProfileError(f"unknown profile field(s): {', '.join(sorted(unknown))}")
    name = validate_name(str(payload.get("name") or expected_name or ""))
    if expected_name is not None and name != validate_name(expected_name):
        raise ProfileError("profile name does not match its file name")
    version = payload.get("version", 1)
    if version != 1:
        raise ProfileError("unsupported profile version")
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ProfileError("cwd must be a non-empty string")
    result: dict[str, Any] = {
        "version": 1,
        "name": name,
        "cwd": os.path.abspath(os.path.expanduser(cwd)),
        "scope": _normalize_scope(payload.get("scope")),
    }
    for key in ("namespace", "kube_context"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise ProfileError(f"{key} must be a string")
            result[key] = value
    return result


def scope_from_profile(profile: dict[str, Any]) -> TagScope:
    scope = profile["scope"]
    return TagScope(mode=scope["mode"], groups=tuple(scope["groups"]), tags=tuple(scope["tags"]))


def load_profile(data_dir: str, name: str) -> tuple[dict[str, Any] | None, str]:
    try:
        path = profile_path(data_dir, name)
    except ProfileError as exc:
        return None, str(exc)
    if not path.is_file():
        return None, f"profile not found: {name}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return normalize(payload, expected_name=name), ""
    except (OSError, ValueError, ProfileError) as exc:
        return None, f"{path.name}: {exc}"


def list_profiles(data_dir: str) -> tuple[list[str], str]:
    try:
        paths = sorted(Path(data_dir).glob(f"{PREFIX}*{SUFFIX}"))
    except OSError as exc:
        return [], str(exc)
    names: list[str] = []
    errors: list[str] = []
    for path in paths:
        name = path.name[len(PREFIX) : -len(SUFFIX)]
        profile, error = load_profile(data_dir, name)
        if profile is not None:
            names.append(name)
        elif error:
            errors.append(error)
    return names, "; ".join(errors)


def save_profile(data_dir: str, profile: dict[str, Any]) -> str | None:
    try:
        clean = normalize(profile)
        path = profile_path(data_dir, clean["name"])
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(clean, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
    except (OSError, ProfileError) as exc:
        return str(exc)
    return None


def delete_profile(data_dir: str, name: str) -> str | None:
    try:
        path = profile_path(data_dir, name)
        path.unlink()
    except FileNotFoundError:
        return f"profile not found: {name}"
    except (OSError, ProfileError) as exc:
        return str(exc)
    return None
