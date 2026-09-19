# Packages handbook: apt, dnf, rpm

Tags **`apt`**, **`dnf`**, **`rpm`**. Inspection playbooks: `aptq`, `rpmq`.  
`install` / `remove` / `apt update` — not in the playbook.

```bash
python3 src/seed_pkg.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

```text
$PKG=curl
!! pkvars[1]
!! aptq[1]
!! rpmq[1]
```

---

## apt / dpkg (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `apt-cache policy $PKG` | Candidate and installed version |
| 2 | `apt-cache show $PKG` | Package description |
| 3 | `apt-cache search $PKG` | Search |
| 4 | `apt list --installed \| grep $PKG` | Installed? |
| 5 | `apt list --upgradable` | Updates |
| 6 | `dpkg -l $PKG` | dpkg status |
| 7 | `dpkg -L $PKG` | Package files |
| 8 | `dpkg -S $PKG` | Which package owns a path/name |
| 9 | `apt update` | Update indexes (changes the cache) |
| 10 | `apt install $PKG` | Install $PKG (changes the system) |
| 11 | `apt remove $PKG` | Remove $PKG |

---

## dnf (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `dnf info $PKG` | Info |
| 2 | `dnf list installed $PKG` | Installed? |
| 3 | `dnf search $PKG` | Search |
| 4 | `dnf check-update` | Any updates? |
| 5 | `dnf repoquery -l $PKG` | Package files |
| 6 | `yum info $PKG` | yum info (old hosts) |
| 7 | `dnf install $PKG` | Install $PKG (changes the system) |
| 8 | `dnf remove $PKG` | Remove $PKG |

---

## rpm (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `rpm -q $PKG` | Installed? |
| 2 | `rpm -qi $PKG` | Info |
| 3 | `rpm -ql $PKG` | Files |
| 4 | `rpm -qc $PKG` | Configs |
| 5 | `rpm -qf $PKG` | $PKG as a path → package |
| 6 | `rpm -Va $PKG` | Verify package files |

---

## Playbooks

| Tag | Chain |
|-----|---------|
| `aptq[1]` | policy → list --upgradable |
| `rpmq[1]` | `rpm -q` → `rpm -qi` |
