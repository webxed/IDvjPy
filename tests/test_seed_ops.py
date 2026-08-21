"""Thematic seeds: docker, helm, ansible, http, netfw, ip, netdbg, data, host, disk, systemd, sysinfo, sysstat, vault, text, pipe, rsync, find, recon, ssh, pkg, user."""
from pathlib import Path

import database_v2 as database
import seed_ansible
import seed_data
import seed_disk
import seed_docker
import seed_find
import seed_helm
import seed_host
import seed_http
import seed_ip
import seed_netdbg
import seed_netfw
import seed_ops
import seed_pipe
import seed_pkg
import seed_recon
import seed_rsync
import seed_ssh
import seed_sysinfo
import seed_sysstat
import seed_systemd
import seed_text
import seed_user
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


def test_seed_ansible_inspect_playbooks(tmp_path):
    db = str(tmp_path / "ansible.db")
    assert seed_ansible.run_seed(db) == _count(seed_ansible)
    rows = database.get_commands_by_tag(db, "ansible")
    assert rows[0]["command"] == "ansible --version"
    assert "ansible-inventory" in rows[2]["command"]  # tid 3
    assert " -m ping" in rows[5]["command"]  # tid 6
    assert "--check" in rows[9]["command"]  # tid 10
    aplay = database.get_commands_by_tag(db, "aplay")
    assert "--syntax-check" in aplay[0]["command"]
    assert "--check --diff" in aplay[4]["command"]  # tid 5
    achk = database.get_command_by_tid(db, "achk", 1)
    assert "!ansible[3]" in achk["command"]
    assert "!aplay[1]" in achk["command"]
    assert "!aplay[5]" in achk["command"]
    assert "!aplay[8]" not in achk["command"]
    assert "!aplay[10]" not in achk["command"]
    aping = database.get_command_by_tid(db, "aping", 1)
    assert "!ansible[5]" in aping["command"]
    assert "!ansible[6]" in aping["command"]
    assert "-m $MODULE" not in aping["command"]
    avault = database.get_commands_by_tag(db, "avault")
    assert "ansible-vault view" in avault[0]["command"]
    assert "$VAULTFILE" in avault[0]["command"]


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
    assert database.get_command_by_tid(db, "nft", 1)["command"] == "nft list tables"
    nftstat = database.get_command_by_tid(db, "nftstat", 1)
    assert "!nft[1]" in nftstat["command"]
    assert "!nft[2]" in nftstat["command"]
    assert "flush" not in nftstat["command"]
    nft_cmds = database.get_commands_by_tag(db, "nft")
    assert all("flush" not in row["command"] for row in nft_cmds)
    assert all("delete" not in row["command"] for row in nft_cmds)


def test_seed_ip_inspect_playbooks(tmp_path):
    db = str(tmp_path / "ip.db")
    assert seed_ip.run_seed(db) == _count(seed_ip)
    rows = database.get_commands_by_tag(db, "ip")
    assert rows[0]["command"] == "ip -br link"
    assert rows[6]["command"] == "ip route"  # tid 7
    assert "link set $IFACE up" in rows[15]["command"]  # tid 16
    ilink = database.get_command_by_tid(db, "ilink", 1)
    assert "!ip[1]" in ilink["command"]
    assert "!ip[2]" in ilink["command"]
    assert "!ip[7]" in ilink["command"]
    assert "link set" not in ilink["command"]
    iiface = database.get_command_by_tid(db, "iiface", 1)
    assert "!ip[3]" in iiface["command"]
    assert "!eth[2]" in iiface["command"]
    assert database.get_command_by_tid(db, "eth", 1)["command"] == "ethtool $IFACE"


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
    zstat = database.get_command_by_tid(db, "zstat", 1)
    assert "!zip[1]" in zstat["command"]
    assert "!zip[2]" in zstat["command"]
    assert "unzip $ARCHIVE" not in zstat["command"]
    assert database.get_command_by_tid(db, "zip", 1)["command"] == "zipinfo $ARCHIVE"
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


def test_seed_systemd_inspect_playbooks(tmp_path):
    db = str(tmp_path / "systemd.db")
    assert seed_systemd.run_seed(db) == _count(seed_systemd)
    sctl = database.get_commands_by_tag(db, "sctl")
    assert sctl[0]["command"] == "systemctl --no-pager --failed"
    assert "status $UNIT" in sctl[2]["command"]  # tid 3
    assert sctl[11]["command"] == "systemctl restart $UNIT"  # tid 12
    jctl = database.get_commands_by_tag(db, "jctl")
    assert jctl[0]["command"] == "journalctl --no-pager -n 80"
    assert "-u $UNIT -n 100" in jctl[2]["command"]  # tid 3
    assert "-f -u $UNIT" in jctl[10]["command"]  # tid 11
    dmesg = database.get_commands_by_tag(db, "dmesg")
    assert dmesg[0]["command"].startswith("dmesg --color=never")
    assert "--level=err,warn" in dmesg[2]["command"]  # tid 3
    sfail = database.get_command_by_tid(db, "sfail", 1)
    assert "!sctl[1]" in sfail["command"]
    assert "!sctl[2]" in sfail["command"]
    assert "restart" not in sfail["command"]
    sstat = database.get_command_by_tid(db, "sstat", 1)
    assert "!sctl[3]" in sstat["command"]
    assert "!jctl[3]" in sstat["command"]
    assert "!sctl[12]" not in sstat["command"]
    kmsg = database.get_command_by_tid(db, "kmsg", 1)
    assert "!dmesg[3]" in kmsg["command"]
    assert "!jctl[8]" in kmsg["command"]


def test_seed_sysinfo_lsof_strace_playbooks(tmp_path):
    db = str(tmp_path / "sysinfo.db")
    assert seed_sysinfo.run_seed(db) == _count(seed_sysinfo)
    hinfo = database.get_commands_by_tag(db, "hinfo")
    assert hinfo[0]["command"] == "uname -a"
    assert hinfo[5]["command"] == "free -h"  # tid 6
    lsof = database.get_commands_by_tag(db, "lsof")
    assert "iTCP:$PORT" in lsof[0]["command"]
    assert "-p $PID" in lsof[2]["command"]  # tid 3
    st = database.get_commands_by_tag(db, "strace")
    assert st[0]["command"] == "strace -V"
    assert "strace -c -- $CMD" in st[1]["command"]
    assert "timeout 8 strace -c -p $PID" in st[5]["command"]  # tid 6
    hstat = database.get_command_by_tid(db, "hstat", 1)
    assert "!hinfo[1]" in hstat["command"]
    assert "!hinfo[6]" in hstat["command"]
    lport = database.get_command_by_tid(db, "lport", 1)
    assert "!lsof[1]" in lport["command"]
    assert "!lsof[2]" in lport["command"]
    pdbg = database.get_command_by_tid(db, "pdbg", 1)
    assert "!lsof[3]" in pdbg["command"]
    assert "!strace[6]" in pdbg["command"]
    assert "!strace[8]" not in pdbg["command"]


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


def test_seed_pipe_sort_jq_playbooks(tmp_path):
    db = str(tmp_path / "pipe.db")
    assert seed_pipe.run_seed(db) == _count(seed_pipe)
    assert database.get_command_by_tid(db, "sort", 1)["command"] == "sort $FILE"
    assert "-u" in database.get_command_by_tid(db, "sort", 2)["command"]
    uniq = database.get_commands_by_tag(db, "uniq")
    assert "uniq -c" in uniq[4]["command"]  # tid 5
    jq = database.get_commands_by_tag(db, "jq")
    assert jq[0]["command"] == "jq . $FILE"
    assert "$JSON" in jq[6]["command"]  # tid 7
    ucount = database.get_command_by_tid(db, "ucount", 1)
    assert "!uniq[5]" in ucount["command"]
    jprev = database.get_command_by_tid(db, "jprev", 1)
    assert "!jq[4]" in jprev["command"]
    assert "!jq[6]" in jprev["command"]
    tee = database.get_commands_by_tag(db, "tee")
    assert tee[0]["command"] == "tee $DEST"
    assert "tee $DEST" not in jprev["command"]


def test_seed_sysstat_finite_samples(tmp_path):
    db = str(tmp_path / "sysstat.db")
    assert seed_sysstat.run_seed(db) == _count(seed_sysstat)
    assert database.get_command_by_tid(db, "vmstat", 1)["command"] == "vmstat"
    assert database.get_command_by_tid(db, "vmstat", 4)["command"] == "vmstat $DELAY $SAMPLES"
    iostat = database.get_commands_by_tag(db, "iostat")
    assert "-xz $DELAY $SAMPLES" in iostat[1]["command"]
    oload = database.get_command_by_tid(db, "oload", 1)
    assert "!vmstat[4]" in oload["command"]
    assert "!iostat[2]" in oload["command"]
    assert "htop" not in oload["command"]
    monui = database.get_commands_by_tag(db, "monui")
    assert all(row["command"].startswith("> ") for row in monui)
    assert database.get_command_by_tid(db, "sstat", 1) is None
    assert database.get_command_by_tid(db, "proc", 1) is None


def test_seed_netdbg_bounded_capture(tmp_path):
    db = str(tmp_path / "netdbg.db")
    assert seed_netdbg.run_seed(db) == _count(seed_netdbg)
    pcap = database.get_commands_by_tag(db, "pcap")
    assert pcap[0]["command"].startswith("timeout 8 tcpdump")
    assert "-c $COUNT" in pcap[0]["command"]
    npath = database.get_command_by_tid(db, "npath", 1)
    assert "!ncat[1]" in npath["command"]
    assert "!hops[1]" in npath["command"]
    assert "!hops[4]" in npath["command"]
    assert "tcpdump" not in npath["command"]
    tlschk = database.get_command_by_tid(db, "tlschk", 1)
    assert "!tls[1]" in tlschk["command"]
    assert "!tls[2]" in tlschk["command"]
    assert database.get_command_by_tid(db, "ncat", 1)["command"] == "nc -vz $HOST $PORT"
    hops = database.get_commands_by_tag(db, "hops")
    assert "mtr -c $COUNT -r" in hops[3]["command"]
    assert database.get_command_by_tid(db, "ss", 1) is None
    assert database.get_command_by_tid(db, "net", 1) is None
    assert database.get_command_by_tid(db, "nmap", 1) is None


def test_seed_pkg_query_playbooks(tmp_path):
    db = str(tmp_path / "pkg.db")
    assert seed_pkg.run_seed(db) == _count(seed_pkg)
    assert database.get_command_by_tid(db, "apt", 1)["command"] == "apt-cache policy $PKG"
    aptq = database.get_command_by_tid(db, "aptq", 1)
    assert "!apt[1]" in aptq["command"]
    assert "!apt[5]" in aptq["command"]
    assert "install" not in aptq["command"]
    assert "remove" not in aptq["command"]
    rpmq = database.get_command_by_tid(db, "rpmq", 1)
    assert "!rpm[1]" in rpmq["command"]
    assert "!rpm[2]" in rpmq["command"]
    assert database.get_command_by_tid(db, "rpm", 1)["command"] == "rpm -q $PKG"
    assert database.get_command_by_tid(db, "dnf", 1)["command"] == "dnf info $PKG"


def test_seed_user_inspect_playbook(tmp_path):
    db = str(tmp_path / "user.db")
    assert seed_user.run_seed(db) == _count(seed_user)
    assert database.get_command_by_tid(db, "ident", 1)["command"] == "id"
    uidchk = database.get_command_by_tid(db, "uidchk", 1)
    assert "!ident[1]" in uidchk["command"]
    assert "!ident[4]" in uidchk["command"]
    assert "!ident[10]" in uidchk["command"]
    assert "chmod" not in uidchk["command"]
    assert "chown" not in uidchk["command"]
    assert "userdel" not in uidchk["command"]
    ident = database.get_commands_by_tag(db, "ident")
    assert all("userdel" not in row["command"] for row in ident)
    perm = database.get_commands_by_tag(db, "perm")
    assert perm[0]["command"] == "stat $FILE"
    assert any("chmod $MODE" in row["command"] for row in perm)


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
    assert database.get_command_by_tid(db, "ansible", 1) is not None
    assert database.get_command_by_tid(db, "curl", 1) is not None
    assert database.get_command_by_tid(db, "pg", 1) is not None
    assert database.get_command_by_tid(db, "vault", 1) is not None
    assert database.get_command_by_tid(db, "grep", 1) is not None
    assert database.get_command_by_tid(db, "rsync", 1) is not None
    assert database.get_command_by_tid(db, "find", 1) is not None
    assert database.get_command_by_tid(db, "dig", 1) is not None
    assert database.get_command_by_tid(db, "ssh", 1) is not None
    assert database.get_command_by_tid(db, "df", 1) is not None
    assert database.get_command_by_tid(db, "sctl", 1) is not None
    assert database.get_command_by_tid(db, "jctl", 1) is not None
    assert database.get_command_by_tid(db, "dmesg", 1) is not None
    assert database.get_command_by_tid(db, "hinfo", 1) is not None
    assert database.get_command_by_tid(db, "lsof", 1) is not None
    assert database.get_command_by_tid(db, "strace", 1) is not None
    assert database.get_command_by_tid(db, "ip", 1) is not None
    assert database.get_command_by_tid(db, "eth", 1) is not None
    assert database.get_command_by_tid(db, "jq", 1) is not None
    assert database.get_command_by_tid(db, "sort", 1) is not None
    assert database.get_command_by_tid(db, "vmstat", 1) is not None
    assert database.get_command_by_tid(db, "pcap", 1) is not None
    assert database.get_command_by_tid(db, "apt", 1) is not None
    assert database.get_command_by_tid(db, "ident", 1) is not None
    assert database.get_command_by_tid(db, "nft", 1) is not None
    assert database.get_command_by_tid(db, "zip", 1) is not None
    assert "inv=" in database.get_command_by_tid(db, "ansvars", 1)["command"]
    assert "archive=" in database.get_command_by_tid(db, "avars", 1)["command"]


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
    assert database.get_command_by_tid(db, "ansible", 1) is not None
    assert database.get_command_by_tid(db, "achk", 1) is not None
    assert database.get_command_by_tid(db, "smart", 1) is not None
    assert database.get_command_by_tid(db, "lsblk", 1) is not None
    assert database.get_command_by_tid(db, "ncdu", 1) is not None
    assert database.get_command_by_tid(db, "sctl", 1) is not None
    assert database.get_command_by_tid(db, "jctl", 1) is not None
    assert database.get_command_by_tid(db, "strace", 1) is not None
    assert database.get_command_by_tid(db, "lsof", 1) is not None
    assert database.get_command_by_tid(db, "ip", 1) is not None
    assert database.get_command_by_tid(db, "jq", 1) is not None
    assert database.get_command_by_tid(db, "vault", 1) is not None
    assert database.get_command_by_tid(db, "awk", 1) is not None
    assert database.get_command_by_tid(db, "rsync", 1) is not None
    assert database.get_command_by_tid(db, "find", 1) is not None
    assert database.get_command_by_tid(db, "nmap", 1) is not None
    assert database.get_command_by_tid(db, "scp", 1) is not None
    assert database.get_command_by_tid(db, "oload", 1) is not None
    assert database.get_command_by_tid(db, "npath", 1) is not None
    assert database.get_command_by_tid(db, "aptq", 1) is not None
    assert database.get_command_by_tid(db, "uidchk", 1) is not None
    assert database.get_command_by_tid(db, "nftstat", 1) is not None
    assert database.get_command_by_tid(db, "zstat", 1) is not None
