"""Handbook seed catalog for the empty-database welcome hint."""

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


# script, one-line description, handbook markdown (empty if none)
SEED_HANDBOOKS_CORE = (
    ("seed_linux_commands.py", "Linux: proc, file, net, kube", "SEED_LINUX_COMMANDS.md"),
    ("seed_k8s_chains.py", "Цепочки для расследования k8s: kpod, klog, kavail, kstore, …", "K8S_CHAINS.md"),
    ("seed_git.py", "git: status, diff, branches; gstat / gsync", "SEED_GIT_COMMANDS.md"),
)
SEED_HANDBOOKS_OPS = (
    ("seed_docker.py", "docker / compose: dck, dcmp, dps, dlog", "SEED_DOCKER_COMMANDS.md"),
    ("seed_helm.py", "helm: релизы, values, dry-run; hls", "SEED_HELM_COMMANDS.md"),
    ("seed_ansible.py", "ansible: inventory, playbook check, vault; achk", "SEED_ANSIBLE_COMMANDS.md"),
    ("seed_http.py", "HTTP: curl, nginx, traefik", "SEED_HTTP_COMMANDS.md"),
    ("seed_netfw.py", "сокеты и firewall: ss, iptables, nft, firewalld", "SEED_NETFW_COMMANDS.md"),
    ("seed_ip.py", "iproute2 / ethtool: ip, eth, ilink", "SEED_IP_COMMANDS.md"),
    ("seed_netdbg.py", "L4/L7: tcpdump, nc, mtr, TLS; npath / tlschk", "SEED_NETDBG_COMMANDS.md"),
    ("seed_data.py", "postgres и kafka: pg, kf", "SEED_DATA_COMMANDS.md"),
    ("seed_host.py", "архивы: tar, gzip, zip", "SEED_HOST_COMMANDS.md"),
    ("seed_disk.py", "диски: df, du, lsblk, smartctl, ncdu", "SEED_DISK_COMMANDS.md"),
    ("seed_systemd.py", "systemd: systemctl, journalctl, dmesg; sstat", "SEED_SYSTEMD_COMMANDS.md"),
    ("seed_sysinfo.py", "хост, lsof, strace; hstat / lport / pdbg", "SEED_SYSINFO_COMMANDS.md"),
    ("seed_sysstat.py", "sysstat: vmstat, iostat, mpstat; oload", "SEED_SYSSTAT_COMMANDS.md"),
    ("seed_vault.py", "HashiCorp Vault: status, kv metadata", "SEED_VAULT_COMMANDS.md"),
    ("seed_text.py", "текст: grep, awk, sed", "SEED_TEXT_COMMANDS.md"),
    ("seed_pipe.py", "конвейер: sort, uniq, cut, jq; ucount", "SEED_PIPE_COMMANDS.md"),
    ("seed_rsync.py", "rsync: dry-run / copy", "SEED_RSYNC_COMMANDS.md"),
    ("seed_find.py", "find: glob, mtime, size", "SEED_FIND_COMMANDS.md"),
    ("seed_recon.py", "DNS и порты: dig, nmap", "SEED_RECON_COMMANDS.md"),
    ("seed_ssh.py", "ssh / scp, OpenSSH-сертификаты", "SEED_SSH_COMMANDS.md"),
    ("seed_pkg.py", "пакеты: apt, dnf, rpm; aptq / rpmq", "SEED_PKG_COMMANDS.md"),
    ("seed_user.py", "люди и права: ident, perm; uidchk", "SEED_USER_COMMANDS.md"),
)


def _section(title: str) -> str:
    return f"[bold {_ACCENT}]{title}[/]"


KNOWN_SEED_SCRIPTS = frozenset(
    (*(script for script, _, _ in SEED_HANDBOOKS_CORE),
     *(script for script, _, _ in SEED_HANDBOOKS_OPS),
     "seed_ops.py")
)


def _entry(script: str, desc: str, doc: str) -> list[str]:
    lines = [f"  {cmd_click(script)}"]
    if doc:
        lines.append(f"    [dim]{desc}[/]  {md_click(doc)}")
    else:
        lines.append(f"    [dim]{desc}[/]")
    return lines


def format_empty_db_hint(db_file: str) -> str:
    """Welcome text when the command database has no live rows."""
    lines = [
        f"[bold {_ACCENT}]Empty command database[/]  [dim]({db_file})[/]",
        "",
        f"[bold]Теги пустые.[/]  Свои команды: [bold {_CMD}]#tag cmd[/]",
        "[dim]Каждый --seed перезаписывает только свои теги; перед этим копия БД в backups/. Вручную:[/] [bold]:backup[/]",
        "Клик по зелёной команде — во ввод, [bold]Enter[/], затем [bold]??[/] [dim](или ~5 с).[/]",
        "[dim]Клик по имени .md (нужен terminal_mouse) или[/] [bold]:md файл.md[/][dim] — справочник с форматированием.[/]",
        "[dim]Показать этот каталог снова:[/] [bold]:welcome[/]",
        "",
        _section("Ядро"),
    ]
    for script, desc, doc in SEED_HANDBOOKS_CORE:
        lines.extend(_entry(script, desc, doc))
    lines.extend(
        [
            "",
            _section("Все ops сразу") + " [dim](без linux / k8s / git)[/]",
            f"  {cmd_click('seed_ops.py')}",
            "",
            _section("Ops по отдельности"),
        ]
    )
    for script, desc, doc in SEED_HANDBOOKS_OPS:
        lines.extend(_entry(script, desc, doc))
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
        f"[bold {_ACCENT}]Разделы[/]  [dim]?tag · ?? · :welcome — каталог seed[/]",
        "",
    ]
    for name in _handbook_section_order():
        tags = [tag for tag in groups.get(name, ()) if tag in live_set]
        if not tags:
            continue
        lines.append(f"  [bold]{name}[/]  [dim]{' '.join(tags)}[/]")
    custom = [tag for tag in live if group_for_tag(tag) is None]
    if custom:
        lines.append(f"  [bold]свои[/]  [dim]{' '.join(custom)}[/]")
    return "\n".join(lines)
