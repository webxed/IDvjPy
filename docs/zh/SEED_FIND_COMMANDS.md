# 面向 IDvjPy 的 find 手册

标签 **`find`**。剧本 **`fchk`**：按 glob 匹配文件 + 计数。  
`-delete` 作为 `find[16]` 存在，不进入命令链。

本次播种不会覆盖 Linux 标签 `file`。这里的 `$PATTERN` 是用于 `-name` 的 **glob**（`*.log`），不是 grep 的正则表达式。

```bash
python3 src/seed_find.py --seed
# 或与其他 ops 一起：
python3 src/seed_ops.py --seed
```

```text
$SRC=.
$PATTERN='*.log'
$DAYS=7
$SIZE=100M
!! fvars[1]
```

GNU `find`（`-printf`）。在大型目录树上，最好用 `find[13]`（`head`）或 `find[15]`（prune）。

---

## find — 命令 (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `find "$SRC" -type f` | 文件 |
| 2 | `find "$SRC" -type d` | 目录 |
| 3 | `find "$SRC" -name "$PATTERN"` | Glob |
| 4 | `find "$SRC" -iname "$PATTERN"` | 不区分大小写的 glob |
| 5 | `find "$SRC" -type f -name "$PATTERN"` | 按 glob 匹配文件 |
| 6 | `find "$SRC" -mtime -$DAYS` | 比 `$DAYS` 天更近 |
| 7 | `find "$SRC" -mtime +$DAYS` | 比 `$DAYS` 天更早 |
| 8 | `find "$SRC" -size +$SIZE` | 大于 `$SIZE` |
| 9 | `find "$SRC" -empty` | 空文件 |
| 10 | `find "$SRC" -type l` | 符号链接 |
| 11 | `find "$SRC" -name "$PATTERN" -ls` | 类似 `ls -dils` |
| 12 | `find … -printf '%s %p\n' \| sort \| tail` | 最大的 20 个 |
| 13 | `find … -name "$PATTERN" \| head -n 50` | 前 50 个 |
| 14 | `find … -name "$PATTERN" \| wc -l` | 计数 |
| 15 | `find … -prune -o … -print` | 排除 `.git` / `.venv` / `node_modules` |
| 16 | `find … -delete` | 删除找到的项 |

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `fchk[1]` | `type f -name` → `wc -l` |

```text
$SRC=.
$PATTERN='*.py'
!! fchk[1]
$DAYS=1
!! find[6]
```
