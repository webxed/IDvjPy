# 软件包手册：apt、dnf、rpm

标签 **`apt`**、**`dnf`**、**`rpm`**。检查类剧本：`aptq`、`rpmq`。  
`install` / `remove` / `apt update` —— 不放入剧本。

```bash
python3 src/seed_pkg.py --seed
# 或与其他 ops 一起：
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

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `apt-cache policy $PKG` | 候选 / installed |
| 2 | `apt-cache show $PKG` | 描述 |
| 3 | `apt-cache search $PKG` | 搜索 |
| 4 | `apt list --installed \| grep $PKG` | 是否已安装？ |
| 5 | `apt list --upgradable` | 更新 |
| 6 | `dpkg -l $PKG` | dpkg 状态 |
| 7 | `dpkg -L $PKG` | 文件 |
| 8 | `dpkg -S $PKG` | 归属 |
| 9 | `apt update` | 更新索引 |
| 10 | `apt install $PKG` | 安装 |
| 11 | `apt remove $PKG` | 卸载 |

---

## dnf (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `dnf info $PKG` | Info |
| 2 | `dnf list installed $PKG` | 是否已安装？ |
| 3 | `dnf search $PKG` | 搜索 |
| 4 | `dnf check-update` | 更新 |
| 5 | `dnf repoquery -l $PKG` | 文件 |
| 6 | `yum info $PKG` | yum |
| 7 | `dnf install $PKG` | 安装 |
| 8 | `dnf remove $PKG` | 卸载 |

---

## rpm (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `rpm -q $PKG` | 是否已安装？ |
| 2 | `rpm -qi $PKG` | Info |
| 3 | `rpm -ql $PKG` | 文件 |
| 4 | `rpm -qc $PKG` | 配置文件 |
| 5 | `rpm -qf $PKG` | 路径 → 软件包 |
| 6 | `rpm -Va $PKG` | Verify |

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `aptq[1]` | policy → list --upgradable |
| `rpmq[1]` | `rpm -q` → `rpm -qi` |
