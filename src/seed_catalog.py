"""Handbook seed catalog for the empty-database welcome hint."""

# Seed scripts live in src/; data files (settings.yml, DB) stay in cwd.
SEED_DIR = "src"


def seed_invoke(script: str) -> str:
    """Shell command to load a handbook into the cwd database."""
    return f"python3 {SEED_DIR}/{script} --seed"


# script, one-line description (shown on first launch if the DB is empty)
SEED_HANDBOOKS_CORE = (
    ("seed_linux_commands.py", "Linux: proc, file, net, kube"),
    ("seed_k8s_chains.py", "Цепочки для расследования k8s: kpod, klog, kquota, …"),
    ("seed_git.py", "git: status, diff, branches; gstat / gsync"),
)
SEED_HANDBOOKS_OPS = (
    ("seed_docker.py", "docker / compose: dck, dcmp, dps, dlog"),
    ("seed_helm.py", "helm: релизы, values, dry-run; hls"),
    ("seed_ansible.py", "ansible: inventory, playbook check, vault; achk"),
    ("seed_http.py", "HTTP: curl, nginx, traefik"),
    ("seed_netfw.py", "сокеты и firewall: ss, iptables, nft, firewalld"),
    ("seed_ip.py", "iproute2 / ethtool: ip, eth, ilink"),
    ("seed_netdbg.py", "L4/L7: tcpdump, nc, mtr, TLS; npath / tlschk"),
    ("seed_data.py", "postgres и kafka: pg, kf"),
    ("seed_host.py", "архивы: tar, gzip, zip"),
    ("seed_disk.py", "диски: df, du, lsblk, smartctl, ncdu"),
    ("seed_systemd.py", "systemd: systemctl, journalctl, dmesg; sstat"),
    ("seed_sysinfo.py", "хост, lsof, strace; hstat / lport / pdbg"),
    ("seed_sysstat.py", "sysstat: vmstat, iostat, mpstat; oload"),
    ("seed_vault.py", "HashiCorp Vault: status, kv metadata"),
    ("seed_text.py", "текст: grep, awk, sed"),
    ("seed_pipe.py", "конвейер: sort, uniq, cut, jq; ucount"),
    ("seed_rsync.py", "rsync: dry-run / copy"),
    ("seed_find.py", "find: glob, mtime, size"),
    ("seed_recon.py", "DNS и порты: dig, nmap"),
    ("seed_ssh.py", "ssh / scp, OpenSSH-сертификаты"),
    ("seed_pkg.py", "пакеты: apt, dnf, rpm; aptq / rpmq"),
    ("seed_user.py", "люди и права: ident, perm; uidchk"),
)


def format_empty_db_hint(db_file: str) -> str:
    """Welcome text when the command database has no live rows."""
    lines = [
        f"Empty command database ({db_file}).",
        "Теги пустые. Свои команды: #tag cmd",
        "Или загрузите справочник — каждый --seed перезаписывает только свои теги.",
        "Команды ниже можно ввести здесь и нажать Enter, затем ?? (или ~5 с).",
        "",
        "Ядро:",
    ]
    for script, desc in SEED_HANDBOOKS_CORE:
        lines.append(f"  {seed_invoke(script)}")
        lines.append(f"    {desc}")
    lines.extend(
        [
            "",
            "Все ops сразу (без linux / k8s / git):",
            f"  {seed_invoke('seed_ops.py')}",
            "",
            "Ops по отдельности — выберите нужное:",
        ]
    )
    for script, desc in SEED_HANDBOOKS_OPS:
        lines.append(f"  {seed_invoke(script)}")
        lines.append(f"    {desc}")
    return "\n".join(lines)
