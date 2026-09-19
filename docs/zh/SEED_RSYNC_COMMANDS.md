# 面向 IDvjPy 的 rsync 手册

标签 **`rsync`**。剧本 **`rchk`**：list-only + dry-run（不带 `--delete`）。

基础 `rsync -avz` 已存在于 linux 标签 `net[6]`——本次播种不会覆盖它。

`$SRC` 末尾的斜杠很重要：`dir/` 复制*内容*，`dir` 复制目录本身。

```bash
python3 src/seed_rsync.py --seed
# 或与其他 ops 一起：
python3 src/seed_ops.py --seed
```

```text
$SRC=./
$DEST=/backup/app/
$REMOTE=user@host
$EXCL=.git
!! rvars[1]
```

---

## rsync — 命令 (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `rsync --list-only "$SRC"` | 源列表 |
| 2 | `rsync -avn "$SRC" "$DEST"` | Dry-run |
| 3 | `rsync -avni "$SRC" "$DEST"` | Dry-run + itemize |
| 4 | `rsync -avzn --delete "$SRC" "$DEST"` | 带 `--delete` 的 dry-run |
| 5 | `rsync -avzn --exclude="$EXCL" …` | 带 exclude 的 dry-run |
| 6 | `rsync -avn "$SRC" "$REMOTE:$DEST"` | 到 `$REMOTE` 的 dry-run |
| 7 | `rsync -avn "$REMOTE:$SRC" "$DEST"` | 从 `$REMOTE` 的 dry-run |
| 8 | `rsync -av "$SRC" "$DEST"` | 本地复制 |
| 9 | `rsync -avz "$SRC" "$DEST"` | 带压缩 |
| 10 | `rsync -avzP "$SRC" "$DEST"` | Progress + partial |
| 11 | `rsync -avz --exclude="$EXCL" …` | 带 exclude 的复制 |
| 12 | `rsync -avz "$SRC" "$REMOTE:$DEST"` | 到 `$REMOTE` |
| 13 | `rsync -avz "$REMOTE:$SRC" "$DEST"` | 从 `$REMOTE` |
| 14 | `rsync -avz --bwlimit=5000 …` | 限速约 5 MB/s |
| 15 | `rsync -avz --delete "$SRC" "$DEST"` | 复制并删除 dest 上多余项 |

`--delete`（tid 15）甚至它的 dry-run（tid 4）都不属于 `rchk`。先 `!! rchk[1]`，如果需要查看删除项，再用 `!rsync[4]`。

SSH：需要密钥/agent。交互式密码输入——`> rsync …`。

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `rchk[1]` | list-only → `-avni` dry-run |

```text
$SRC=./
$DEST=/backup/app/
!! rchk[1]
$REMOTE=user@host
!! rsync[6]
!! rsync[12]
```
