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
    ("seed_http.py", "HTTP: curl, nginx, traefik"),
    ("seed_netfw.py", "сокеты и firewall: ss, netstat, iptables, firewalld"),
    ("seed_data.py", "postgres и kafka: pg, kf"),
    ("seed_host.py", "архивы: tar, gzip"),
    ("seed_disk.py", "диски: df, du, lsblk, smartctl, ncdu"),
    ("seed_vault.py", "HashiCorp Vault: status, kv metadata"),
    ("seed_text.py", "текст: grep, awk, sed"),
    ("seed_rsync.py", "rsync: dry-run / copy"),
    ("seed_find.py", "find: glob, mtime, size"),
    ("seed_recon.py", "DNS и порты: dig, nmap"),
    ("seed_ssh.py", "ssh / scp, OpenSSH-сертификаты"),
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
