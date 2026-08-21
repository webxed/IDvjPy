"""Handbook name → tags for #name-- / #name!! group hide/restore."""
from __future__ import annotations

_GROUPS: dict[str, tuple[str, ...]] | None = None
_TAG_TO_GROUP: dict[str, str] | None = None


def handbook_groups() -> dict[str, tuple[str, ...]]:
    """Seed module names (plus linux / k8s / git) mapped to their tags."""
    global _GROUPS, _TAG_TO_GROUP
    if _GROUPS is None:
        import seed_git
        import seed_k8s_chains
        import seed_linux_commands
        import seed_ops

        groups: dict[str, tuple[str, ...]] = {
            "linux": tuple(seed_linux_commands.SEED_COMMANDS),
            "k8s": tuple(seed_k8s_chains.SEED_TAGS),
            "git": tuple(seed_git.SEED_TAGS),
        }
        for name, mod in seed_ops.MODULES:
            groups[name] = tuple(mod.SEED_TAGS)
        tag_to_group: dict[str, str] = {}
        for name, tags in groups.items():
            for tag in tags:
                tag_to_group.setdefault(tag, name)
        _GROUPS = groups
        _TAG_TO_GROUP = tag_to_group
    return _GROUPS


def group_tags(name: str) -> tuple[str, ...] | None:
    """Tags for a handbook, or None if the name is unknown."""
    return handbook_groups().get(name)


def group_for_tag(tag: str) -> str | None:
    """Handbook that owns this tag, if any."""
    handbook_groups()
    assert _TAG_TO_GROUP is not None
    return _TAG_TO_GROUP.get(tag)


def known_group_names() -> list[str]:
    return sorted(handbook_groups())
