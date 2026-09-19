# 面向 IDvjPy 的管道手册

标签 **`sort`**、**`uniq`**、**`cut`**、**`tr`**、**`wc`**、**`xargs`**、**`jq`**。  
`tee` 写入磁盘——不放入剧本。作为日志块上的 `| sort -u` 或 `!! sort[2]` 很方便。

不改动 `grep` / `awk` / `sed`（`seed_text.py`）。

```bash
python3 src/seed_pipe.py --seed
# 或与其他 ops 一起：
python3 src/seed_ops.py --seed
```

```text
$FILE=data.txt
$SEP=,
$N=1
$DEST=/tmp/out.txt
$JSON=.
!! pvars[1]
```

`$JSON` —— 来自 JSON viewer（F5、Enter）的 jq-path。做管道时把 `$FILE` 留空，使用 `| jq .`。

---

## sort / uniq / cut (tid)

**sort：** 1 普通 · 2 `-u` · 3 `-n` · 4 `-h` · 5 `-r` · 6 `-nr` · 7 `-k $N` · 8 `-t $SEP -k $N` · 9 按字段去重

**uniq：** 1 压缩 · 2 `-c` · 3 `-d` · 4 `-u` · 5 `sort | uniq -c | sort -nr`

`uniq` 只查看**相邻**行——在 `-c` 之前几乎总是先 `sort`。

**cut：** 1 字段 `$N` · 2 字段 1 和 `$N` · 3 字段 1–3 · 4 字符 1–80 · 5 除 `$N` 外的全部

---

## tr / wc / xargs / jq

**tr** 读取 stdin（`< $FILE`）。在管道中：`| tr -d '\r'`。

**wc：** `-l` / `-w` / `-c` / `-lwm` / `-L`。

**xargs：** `-a $FILE`（GNU）。`-P` 会启动多条命令——剧本中没有。

**jq：** `.` · `-c` · `-r` · `keys` · `length` · `type` · `$JSON` · raw `$JSON` · JSON 校验。

**tee：** `tee $DEST` / `tee -a $DEST` —— 会修改文件。

---

## 剧本

| 标签 | 命令链 |
|-----|---------|
| `ucount[1]` | `sort \| uniq -c \| sort -nr` |
| `jprev[1]` | jq keys → length → type |

```text
$FILE=access.log
!! ucount[1]
$FILE=demo.json
!! jprev[1]
| jq -r .cc
```
