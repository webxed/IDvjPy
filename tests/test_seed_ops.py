"""Thematic seeds: docker, helm, http, netfw, data, host, disk, vault, text, rsync, find, recon, ssh."""
from pathlib import Path

import database_v2 as database
import seed_data
import seed_disk
import seed_docker
import seed_find
import seed_helm
import seed_host
import seed_http
import seed_netfw
import seed_ops
import seed_recon
import seed_rsync
import seed_ssh
import seed_text
import seed_vault


def _count(mod) -> int:
    return sum(len(cmds) for _, cmds in mod.SEED_TAGS.values())


def test_seed_docker_tids_and_playbooks(tmp_path):
    db = str(tmp_path / "docker.db")
    assert seed_docker.run_seed(db) == _count(seed_docker)
    dck = database.get_commands_by_tag(db, "dck")
    assert dck[0]["command"] == "docker ps"
    assert "docker logs --tail=100" in dck[3]["command"]
    assert "grep -iE" in dck[13]["command"]  # tid 14
    dps = database.get_command_by_tid(db, "dps", 1)
    assert "!dck[1]" in dps["command"]
    assert "!dck[6]" in dps["command"]
    dlog = database.get_command_by_tid(db, "dlog", 1)
    assert "!dck[4]" in dlog["command"]
    assert "!dck[14]" in dlog["command"]
    dcstat = database.get_command_by_tid(db, "dcstat", 1)
    assert "!dcmp[1]" in dcstat["command"]
    assert "!dcmp[3]" in dcstat["command"]
    assert "down -v" not in dcstat["command"]


def test_seed_helm_playbook_is_inspect(tmp_path):
    db = str(tmp_path / "helm.db")
    seed_helm.run_seed(db)
    rows = database.get_commands_by_tag(db, "helm")
    assert rows[0]["command"] == "helm list -n $NS"
    assert "--dry-run" in rows[12]["command"]  # tid 13
    hls = database.get_command_by_tid(db, "hls", 1)
    assert "!helm[1]" in hls["command"]
    assert "!helm[3]" in hls["command"]
    assert "!helm[5]" in hls["command"]
    assert "uninstall" not in hls["command"]
    assert "upgrade --install" not in hls["command"]


def test_seed_http_curl_nginx_traefik(tmp_path):
    db = str(tmp_path / "http.db")
    seed_http.run_seed(db)
    curl = database.get_commands_by_tag(db, "curl")
    assert curl[0]["command"] == "curl -sI $URL"
    assert "time_namelookup" in curl[9]["command"]  # tid 10
    hchk = database.get_command_by_tid(db, "hchk", 1)
    assert "!curl[1]" in hchk["command"]
    assert "!curl[10]" in hchk["command"]
    ngxstat = database.get_command_by_tid(db, "ngxstat", 1)
    assert "!ngx[1]" in ngxstat["command"]
    assert "!ngx[10]" in ngxstat["command"]
    trfstat = database.get_command_by_tid(db, "trfstat", 1)
    assert "!trf[2]" in trfstat["command"]
    assert "!trf[4]" in trfstat["command"]
    assert database.get_command_by_tid(db, "ngx", 1)["command"] == "nginx -t"


def test_seed_netfw_inspect_playbooks(tmp_path):
    db = str(tmp_path / "netfw.db")
    seed_netfw.run_seed(db)
    ss = database.get_commands_by_tag(db, "ss")
    assert ss[0]["command"] == "ss -tulnp"
    assert "sport = :$PORT" in ss[6]["command"]
    nstat = database.get_command_by_tid(db, "nstat", 1)
    assert "!ss[1]" in nstat["command"]
    iptstat = database.get_command_by_tid(db, "iptstat", 1)
    assert "!ipt[1]" in iptstat["command"]
    assert "-F" not in iptstat["command"]
    fwstat = database.get_command_by_tid(db, "fwstat", 1)
    assert "!fwd[1]" in fwstat["command"]
    assert "--add-port" not in fwstat["command"]
    assert database.get_command_by_tid(db, "nst", 1)["command"].startswith("netstat")
    assert "firewall-cmd --state" in database.get_command_by_tid(db, "fwd", 1)["command"]


def test_seed_data_postgres_kafka(tmp_path):
    db = str(tmp_path / "data.db")
    seed_data.run_seed(db)
    assert database.get_command_by_tid(db, "pg", 1)["command"] == "pg_isready"
    pgstat = database.get_command_by_tid(db, "pgstat", 1)
    assert "!pg[1]" in pgstat["command"]
    assert "!pg[9]" in pgstat["command"]
    assert "DROP" not in pgstat["command"]
    kf = database.get_commands_by_tag(db, "kf")
    assert kf[0]["command"].startswith("kcat")
    kfstat = database.get_command_by_tid(db, "kfstat", 1)
    assert "!kf[1]" in kfstat["command"]
    assert "!kf[3]" in kfstat["command"]
    assert "--delete" not in kfstat["command"]


def test_seed_host_tar_only(tmp_path):
    db = str(tmp_path / "host.db")
    seed_host.run_seed(db)
    assert database.get_command_by_tid(db, "tar", 2)["command"] == "tar -tzf $ARCHIVE"
    tstat = database.get_command_by_tid(db, "tstat", 1)
    assert "!tar[2]" in tstat["command"]
    assert "!gz[1]" in tstat["command"]
    assert "xzvf" not in tstat["command"]
    assert database.get_command_by_tid(db, "smart", 1) is None
    assert database.get_command_by_tid(db, "df", 1) is None


def test_seed_disk_inspect_playbooks(tmp_path):
    db = str(tmp_path / "disk.db")
    assert seed_disk.run_seed(db) == _count(seed_disk)
    assert database.get_command_by_tid(db, "df", 1)["command"] == "df -h"
    assert database.get_command_by_tid(db, "du", 1)["command"].startswith("du -sh")
    assert database.get_command_by_tid(db, "mount", 1)["command"] == "findmnt"
    assert database.get_command_by_tid(db, "fdisk", 1)["command"] == "fdisk -l"
    assert database.get_command_by_tid(db, "lsblk", 1)["command"] == "lsblk"
    assert database.get_command_by_tid(db, "smart", 1)["command"] == "smartctl --scan"
    assert database.get_command_by_tid(db, "ncdu", 1)["command"].startswith("ncdu")
    dsk = database.get_command_by_tid(db, "dsk", 1)
    assert "!lsblk[1]" in dsk["command"]
    assert "!df[1]" in dsk["command"]
    assert "!smart[1]" in dsk["command"]
    assert "!smart[3]" in dsk["command"]
    assert "mkfs" not in dsk["command"]
    assert "wipefs -a" not in dsk["command"]
    dustat = database.get_command_by_tid(db, "dustat", 1)
    assert "!du[2]" in dustat["command"]
    fdisk = database.get_commands_by_tag(db, "fdisk")
    assert all("mkfs" not in row["command"] for row in fdisk)


def test_seed_host_does_not_touch_disk(tmp_path):
    db = str(tmp_path / "mixed_disk.db")
    seed_disk.run_seed(db)
    seed_host.run_seed(db)
    assert database.get_command_by_tid(db, "smart", 1)["command"] == "smartctl --scan"
    assert database.get_command_by_tid(db, "df", 1)["command"] == "df -h"
    assert database.get_command_by_tid(db, "tar", 2)["command"] == "tar -tzf $ARCHIVE"


def test_seed_vault_inspect_playbooks(tmp_path):
    db = str(tmp_path / "vault.db")
    assert seed_vault.run_seed(db) == _count(seed_vault)
    rows = database.get_commands_by_tag(db, "vault")
    assert rows[0]["command"] == "vault status"
    assert "sys/health" in rows[3]["command"]  # tid 4
    assert "metadata get" in rows[13]["command"]  # tid 14
    vvars = database.get_command_by_tid(db, "vvars", 1)
    assert "VAULT_TOKEN" in vvars["command"]
    assert "echo $VAULT_TOKEN" not in vvars["command"]
    vstat = database.get_command_by_tid(db, "vstat", 1)
    assert "!vault[1]" in vstat["command"]
    assert "!vault[5]" in vstat["command"]
    assert "kv get" not in vstat["command"]
    assert "seal" not in vstat["command"]
    vkv = database.get_command_by_tid(db, "vkv", 1)
    assert "!vault[13]" in vkv["command"]
    assert "!vault[14]" in vkv["command"]
    assert "kv get $SECRET" not in vkv["command"]
    assert "kv put" not in vkv["command"]


def test_seed_text_grep_awk_sed(tmp_path):
    db = str(tmp_path / "text.db")
    assert seed_text.run_seed(db) == _count(seed_text)
    grep = database.get_commands_by_tag(db, "grep")
    assert grep[0]["command"] == "grep -n $PATTERN $FILE"
    assert "-nc" in grep[3]["command"]  # tid 4
    awk = database.get_commands_by_tag(db, "awk")
    assert awk[0]["command"] == "awk '{print $1}' $FILE"
    assert "$SEP" in awk[1]["command"]
    sed = database.get_commands_by_tag(db, "sed")
    assert "s/$PATTERN/$REPL/g" in sed[4]["command"]  # tid 5
    assert "-i.bak" in sed[12]["command"]  # tid 13
    gchk = database.get_command_by_tid(db, "gchk", 1)
    assert "!grep[1]" in gchk["command"]
    assert "!grep[4]" in gchk["command"]
    sprev = database.get_command_by_tid(db, "sprev", 1)
    assert "!sed[5]" in sprev["command"]
    assert "!sed[3]" in sprev["command"]
    assert "-i" not in sprev["command"]


def test_seed_rsync_dry_run_playbook(tmp_path):
    db = str(tmp_path / "rsync.db")
    assert seed_rsync.run_seed(db) == _count(seed_rsync)
    rows = database.get_commands_by_tag(db, "rsync")
    assert rows[0]["command"].startswith("rsync --list-only")
    assert "-avn " in rows[1]["command"]  # tid 2
    assert "-avni " in rows[2]["command"]  # tid 3
    assert "--delete" in rows[3]["command"]  # tid 4 dry-run delete
    assert "--delete" in rows[14]["command"]  # tid 15
    rchk = database.get_command_by_tid(db, "rchk", 1)
    assert "!rsync[1]" in rchk["command"]
    assert "!rsync[3]" in rchk["command"]
    assert "--delete" not in rchk["command"]


def test_seed_find_inspect_playbook(tmp_path):
    db = str(tmp_path / "find.db")
    assert seed_find.run_seed(db) == _count(seed_find)
    rows = database.get_commands_by_tag(db, "find")
    assert rows[0]["command"].startswith("find ")
    assert "-type f" in rows[0]["command"]
    assert "-name" in rows[4]["command"]  # tid 5
    assert "wc -l" in rows[13]["command"]  # tid 14
    assert "-delete" in rows[15]["command"]  # tid 16
    fchk = database.get_command_by_tid(db, "fchk", 1)
    assert "!find[5]" in fchk["command"]
    assert "!find[14]" in fchk["command"]
    assert "-delete" not in fchk["command"]


def test_seed_recon_dig_nmap(tmp_path):
    db = str(tmp_path / "recon.db")
    assert seed_recon.run_seed(db) == _count(seed_recon)
    dig = database.get_commands_by_tag(db, "dig")
    assert dig[0]["command"] == "dig $HOST"
    assert "+short" in dig[1]["command"]
    nmap = database.get_commands_by_tag(db, "nmap")
    assert nmap[0]["command"] == "nmap -sn $HOST"
    assert "--top-ports 20" in nmap[1]["command"]
    assert "-p-" not in nmap[1]["command"]
    dchk = database.get_command_by_tid(db, "dchk", 1)
    assert "!dig[2]" in dchk["command"]
    assert "!dig[6]" in dchk["command"]
    nchk = database.get_command_by_tid(db, "nchk", 1)
    assert "!nmap[1]" in nchk["command"]
    assert "!nmap[2]" in nchk["command"]
    assert "--script" not in nchk["command"]
    assert "-A" not in nchk["command"]


def test_seed_ssh_scp_noninteractive_playbook(tmp_path):
    db = str(tmp_path / "ssh.db")
    assert seed_ssh.run_seed(db) == _count(seed_ssh)
    ssh = database.get_commands_by_tag(db, "ssh")
    assert ssh[0]["command"] == "ssh -G $HOST"
    assert "BatchMode=yes" in ssh[1]["command"]
    assert "ssh-copy-id" in ssh[12]["command"]  # tid 13
    assert "ed25519" in ssh[14]["command"]  # tid 15
    assert "test ! -e" in ssh[14]["command"]
    assert "-t rsa" in ssh[16]["command"]  # tid 17
    assert ssh[19]["command"] == "ssh -V"  # tid 20
    assert "ssh-keygen -L" in ssh[27]["command"]  # tid 28
    assert "days_left" in ssh[29]["command"]  # tid 30
    scp = database.get_commands_by_tag(db, "scp")
    assert scp[0]["command"].startswith("scp ")
    assert "$REMOTE:$DEST" in scp[0]["command"]
    schk = database.get_command_by_tid(db, "schk", 1)
    assert "!ssh[1]" in schk["command"]
    assert "!ssh[2]" in schk["command"]
    assert "!ssh[3]" in schk["command"]
    assert "ssh-copy-id" not in schk["command"]
    assert "!ssh[11]" not in schk["command"]
    assert "ed25519" not in schk["command"]
    ossh = database.get_command_by_tid(db, "ossh", 1)
    assert "!ssh[20]" in ossh["command"]
    ocert = database.get_command_by_tid(db, "ocert", 1)
    assert "!ssh[29]" in ocert["command"]
    assert "!ssh[30]" in ocert["command"]


def test_seed_ops_does_not_touch_linux_k8s_git(tmp_path):
    db = str(tmp_path / "mixed.db")
    database.init_db(db)
    database.add_command(db, "ps aux", "proc")
    database.add_command(db, "ss -tulnp", "net")
    database.add_command(db, "kubectl get pods -n $NS", "kpod")
    database.add_command(db, "git status", "git")
    n = seed_ops.run_seed(db)
    assert n == sum(_count(m) for _, m in seed_ops.MODULES)
    assert database.get_command_by_tid(db, "proc", 1)["command"] == "ps aux"
    assert database.get_command_by_tid(db, "net", 1)["command"] == "ss -tulnp"
    assert "kubectl get pods" in database.get_command_by_tid(db, "kpod", 1)["command"]
    assert database.get_command_by_tid(db, "git", 1)["command"] == "git status"
    assert database.get_command_by_tid(db, "dck", 1) is not None
    assert database.get_command_by_tid(db, "helm", 1) is not None
    assert database.get_command_by_tid(db, "curl", 1) is not None
    assert database.get_command_by_tid(db, "pg", 1) is not None
    assert database.get_command_by_tid(db, "vault", 1) is not None
    assert database.get_command_by_tid(db, "grep", 1) is not None
    assert database.get_command_by_tid(db, "rsync", 1) is not None
    assert database.get_command_by_tid(db, "find", 1) is not None
    assert database.get_command_by_tid(db, "dig", 1) is not None
    assert database.get_command_by_tid(db, "ssh", 1) is not None
    assert database.get_command_by_tid(db, "df", 1) is not None


def test_seed_ops_cli(tmp_path, monkeypatch):
    db = str(tmp_path / "cli.db")
    monkeypatch.setattr(
        seed_ops.sys,
        "argv",
        ["seed_ops.py", "--seed", "--db", db],
    )
    seed_ops.main()
    assert Path(db).exists()
    assert database.get_command_by_tid(db, "dck", 1) is not None
    assert database.get_command_by_tid(db, "smart", 1) is not None
    assert database.get_command_by_tid(db, "lsblk", 1) is not None
    assert database.get_command_by_tid(db, "ncdu", 1) is not None
    assert database.get_command_by_tid(db, "vault", 1) is not None
    assert database.get_command_by_tid(db, "awk", 1) is not None
    assert database.get_command_by_tid(db, "rsync", 1) is not None
    assert database.get_command_by_tid(db, "find", 1) is not None
    assert database.get_command_by_tid(db, "nmap", 1) is not None
    assert database.get_command_by_tid(db, "scp", 1) is not None
