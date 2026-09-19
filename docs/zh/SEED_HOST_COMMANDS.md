# 主机手册：tar / gzip / zip

标签 **`tar`**、**`gz`**、**`zip`**。剧本 **`tstat`** / **`zstat`** 检查归档，不向 `/` 解包。

磁盘与空间：[`SEED_DISK_COMMANDS.md`](SEED_DISK_COMMANDS.md)（`python3 src/seed_disk.py --seed`）。

```bash
python3 src/seed_host.py --seed
```

不改动 linux 标签 `file` 和磁盘标签（`df` / `smart` / …）。

```text
$SRC=.
$DEST=backup.tar.gz
$ARCHIVE=backup.tar.gz
$PATTERN=error
!! avars[1]
```

---

## tar (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `tar -tf $ARCHIVE` | 文件列表 |
| 2 | `tar -tzf $ARCHIVE` | `.tar.gz` 列表 |
| 3 | `tar -tvf $ARCHIVE \| head` | 带权限的列表 |
| 4 | `tar -czvf $DEST $SRC` | 打包 |
| 5 | `tar -czvf $DEST --exclude='.git' $SRC` | 排除 `.git` |
| 6 | `tar -xzvf $ARCHIVE` | 解包到 cwd |
| 7 | `tar -xzvf $ARCHIVE -C $DEST` | 解包到 `$DEST` |
| 8 | `tar -df $ARCHIVE $SRC` | 与目录树比较 |

`6`–`7` 会覆盖文件——不放入剧本。

---

## gz — gzip (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `gzip -l $ARCHIVE` | 大小 / 压缩比 |
| 2 | `gzip -dk $ARCHIVE` | 解压，保留 `.gz` |
| 3 | `gunzip -c $ARCHIVE \| head` | 前几行 |
| 4 | `zcat $ARCHIVE \| head` | 同上 |
| 5 | `gzip -k $SRC` | 压缩，保留源文件 |
| 6 | `zgrep -n $PATTERN $ARCHIVE` | 在 `.gz` 内 grep |

---

## zip (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `zipinfo $ARCHIVE` | 列表与权限 |
| 2 | `unzip -l $ARCHIVE` | 文件列表 |
| 3 | `unzip -v $ARCHIVE` | 详细列表 |
| 4 | `zip -r $DEST $SRC` | 打包 |
| 5 | `unzip $ARCHIVE` | 解包到 cwd |
| 6 | `unzip $ARCHIVE -d $DEST` | 解包到 `$DEST` |
| 7 | `zipgrep $PATTERN $ARCHIVE` | 在 `.zip` 内 grep |

`5`–`6` 会覆盖文件——不放入剧本。

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `tstat[1]` | `tar -tzf` + `gzip -l` |
| `zstat[1]` | `zipinfo` + `unzip -l` |

```text
$ARCHIVE=backup.tar.gz
!! tstat[1]
$ARCHIVE=backup.zip
!! zstat[1]
```
