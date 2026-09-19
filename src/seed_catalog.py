"""Handbook seed catalog for the empty-database welcome hint and `:welcome`.

Тексты — в локалях (`catalog.*`, части `src/locales/<lang>/seed.yml`); команды,
имена скриптов и файлов справочников не переводятся.
"""

from i18n import t

# Seed scripts live in src/; data files (settings.yml, DB) stay in cwd.
SEED_DIR = "src"

# Colors match the startup banner / input border.
_ACCENT = "#b794f4"
_CMD = "#4a8c58"
_LINK = "#8a6bb5"


def seed_invoke(script: str) -> str:
    """Shell command to load a handbook into the cwd database."""
    return f"python3 {SEED_DIR}/{script} --seed"


def md_click(doc: str) -> str:
    """Rich markup: clickable handbook filename → action_open_handbook_md."""
    return (
        f"[@click=app.open_handbook_md('{doc}')]"
        f"[underline {_LINK}]{doc}[/][/]"
    )


def cmd_click(script: str) -> str:
    """Rich markup: clickable --seed line → action_insert_seed_command."""
    cmd = seed_invoke(script)
    return (
        f"[@click=app.insert_seed_command('{script}')]"
        f"[bold underline {_CMD}]{cmd}[/][/]"
    )


# script, handbook markdown (empty if none); the one-line description is the
# locale key `catalog.desc.<script without seed_/.py>`.
SEED_HANDBOOKS_CORE = (
    ("seed_linux_commands.py", "SEED_LINUX_COMMANDS.md"),
    ("seed_k8s_chains.py", "K8S_CHAINS.md"),
    ("seed_git.py", "SEED_GIT_COMMANDS.md"),
)
SEED_HANDBOOKS_OPS = (
    ("seed_docker.py", "SEED_DOCKER_COMMANDS.md"),
    ("seed_helm.py", "SEED_HELM_COMMANDS.md"),
    ("seed_ansible.py", "SEED_ANSIBLE_COMMANDS.md"),
    ("seed_http.py", "SEED_HTTP_COMMANDS.md"),
    ("seed_netfw.py", "SEED_NETFW_COMMANDS.md"),
    ("seed_ip.py", "SEED_IP_COMMANDS.md"),
    ("seed_netdbg.py", "SEED_NETDBG_COMMANDS.md"),
    ("seed_data.py", "SEED_DATA_COMMANDS.md"),
    ("seed_host.py", "SEED_HOST_COMMANDS.md"),
    ("seed_disk.py", "SEED_DISK_COMMANDS.md"),
    ("seed_systemd.py", "SEED_SYSTEMD_COMMANDS.md"),
    ("seed_sysinfo.py", "SEED_SYSINFO_COMMANDS.md"),
    ("seed_sysstat.py", "SEED_SYSTAT_COMMANDS.md"),
    ("seed_vault.py", "SEED_VAULT_COMMANDS.md"),
    ("seed_text.py", "SEED_TEXT_COMMANDS.md"),
    ("seed_pipe.py", "SEED_PIPE_COMMANDS.md"),
    ("seed_rsync.py", "SEED_RSYNC_COMMANDS.md"),
    ("seed_find.py", "SEED_FIND_COMMANDS.md"),
    ("seed_recon.py", "SEED_RECON_COMMANDS.md"),
    ("seed_ssh.py", "SEED_SSH_COMMANDS.md"),
    ("seed_pkg.py", "SEED_PKG_COMMANDS.md"),
    ("seed_user.py", "SEED_USER_COMMANDS.md"),
)


def handbook_key(script: str) -> str:
    """`seed_linux_commands.py` → `linux_commands` (ключ локали, без точек)."""
    return script.removeprefix("seed_").removesuffix(".py")


def handbook_desc(script: str) -> str:
    """Однострочное описание справочника на текущем языке."""
    return t(f"catalog.desc.{handbook_key(script)}")


def _section(title: str) -> str:
    return f"[bold {_ACCENT}]{title}[/]"


KNOWN_SEED_SCRIPTS = frozenset(
    (*(script for script, _ in SEED_HANDBOOKS_CORE),
     *(script for script, _ in SEED_HANDBOOKS_OPS),
     "seed_ops.py")
)


def _entry(script: str, doc: str) -> list[str]:
    lines = [f"  {cmd_click(script)}"]
    desc = handbook_desc(script)
    if doc:
        lines.append(f"    [dim]{desc}[/]  {md_click(doc)}")
    else:
        lines.append(f"    [dim]{desc}[/]")
    return lines


def format_empty_db_hint(db_file: str) -> str:
    """Welcome text when the command database has no live rows."""
    lines = [
        f"[bold {_ACCENT}]{t('catalog.title')}[/]  [dim]({db_file})[/]",
        "",
        t("catalog.tags_empty"),
        t("catalog.seed_note"),
        t("catalog.click_hint"),
        t("catalog.md_hint"),
        t("catalog.show_again"),
        "",
        _section(t("catalog.section_core")),
    ]
    for script, doc in SEED_HANDBOOKS_CORE:
        lines.extend(_entry(script, doc))
    lines.extend(
        [
            "",
            _section(t("catalog.section_ops_all"))
            + f" [dim]{t('catalog.section_ops_all_note')}[/]",
            f"  {cmd_click('seed_ops.py')}",
            "",
            _section(t("catalog.section_ops")),
        ]
    )
    for script, doc in SEED_HANDBOOKS_OPS:
        lines.extend(_entry(script, doc))
    return "\n".join(lines)


def _handbook_section_order() -> list[str]:
    import seed_ops

    return ["linux", "k8s", "git", *(name for name, _ in seed_ops.MODULES)]


def format_library_overview(live_tags: list[str]) -> str:
    """Compact map of loaded handbook sections (non-empty DB startup)."""
    from seed_groups import group_for_tag, handbook_groups

    live = [tag for tag in live_tags if tag]
    if not live:
        return ""
    live_set = set(live)
    groups = handbook_groups()
    lines = [
        f"[bold {_ACCENT}]{t('catalog.overview_title')}[/]  "
        f"[dim]{t('catalog.overview_hint')}[/]",
        "",
    ]
    for name in _handbook_section_order():
        tags = [tag for tag in groups.get(name, ()) if tag in live_set]
        if not tags:
            continue
        lines.append(f"  [bold]{name}[/]  [dim]{' '.join(tags)}[/]")
    custom = [tag for tag in live if group_for_tag(tag) is None]
    if custom:
        lines.append(f"  [bold]{t('catalog.custom')}[/]  [dim]{' '.join(custom)}[/]")
    return "\n".join(lines)
