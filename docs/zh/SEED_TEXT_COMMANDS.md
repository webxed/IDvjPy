# IDvjPy 文本手册：grep、awk、sed

**`grep`**、**`awk`**、**`sed`** 标签。playbook 写入 stdout。  
`sed -i` 以 `sed[13]` 存在，不进入命令链。

Linux 标签 `file`（`cat`/`head`/`tail`）不会被此种子覆盖。

```bash
python3 src/seed_text.py --seed
# 或连同其他 ops：
python3 src/seed_ops.py --seed
```

```text
$FILE=
$PATTERN=
$REPL=
$SEP=,
$N=1
!! tvars[1]
```

对于 `sed s/$PATTERN/$REPL/`，`$PATTERN` 和 `$REPL` 中不能有未转义的 `/`。使用其他分隔符：把命令改为 `s|$PATTERN|$REPL|g`。

---

## grep (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `grep -n $PATTERN $FILE` | 带行号输出 |
| 2 | `grep -ni $PATTERN $FILE` | 不区分大小写 |
| 3 | `grep -nv $PATTERN $FILE` | 反向过滤 |
| 4 | `grep -nc $PATTERN $FILE` | 匹配计数 |
| 5 | `grep -nE $PATTERN $FILE` | 扩展正则 |
| 6 | `grep -nF $PATTERN $FILE` | 固定字符串 |
| 7 | `grep -nC 3 $PATTERN $FILE` | 上下文 ±3 |
| 8 | `grep -nA 5 $PATTERN $FILE` | 后 5 行 |
| 9 | `grep -nB 5 $PATTERN $FILE` | 前 5 行 |
| 10 | `grep -oE $PATTERN $FILE` | 仅匹配内容 |
| 11 | `grep -nH $PATTERN $FILE` | 带文件名 |
| 12 | `grep -l $PATTERN $FILE` | 仅文件名（有匹配时） |
| 13 | `grep -Rn --exclude-dir=.git --exclude-dir=.venv $PATTERN .` | 从 cwd 递归 |
| 14 | `zgrep -n $PATTERN $FILE` | 在 `.gz` 中搜索 |

---

## awk (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `awk '{print $1}' $FILE` | 第一个字段（FS=空格） |
| 2 | `awk -F "$SEP" '{print $1}' $FILE` | 第一个字段，FS=`$SEP` |
| 3 | `awk -F "$SEP" '{print $1,$NF}' $FILE` | 第一个和最后一个字段 |
| 4 | `awk '{print NR, $0}' $FILE` | 行号 |
| 5 | `awk 'NR==1 {print}' $FILE` | 第一行（表头） |
| 6 | `awk -v n="$N" 'NR==n {print}' $FILE` | 第 `$N` 行 |
| 7 | `awk 'NF' $FILE` | 丢弃空行 |
| 8 | `awk '!seen[$0]++' $FILE` | 唯一行，保持文件顺序 |
| 9 | `awk '{s+=$1} END {print s}' $FILE` | 第一个字段求和 |
| 10 | `awk -v p="$PATTERN" '$0 ~ p {print NR, $0}' $FILE` | 匹配 `$PATTERN` 的行 |
| 11 | `awk -F "$SEP" '{print NF}' $FILE` | 每行字段数 |
| 12 | `awk 'END {print NR}' $FILE` | 行数 |

---

## sed (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `sed -n '1,20p' $FILE` | 前 20 行 |
| 2 | `sed -n "$N"p $FILE` | 第 `$N` 行 |
| 3 | `sed -n "/$PATTERN/p" $FILE` | 按正则 `$PATTERN` 匹配的行 |
| 4 | `sed "s/$PATTERN/$REPL/" $FILE` | 每行第一次替换 |
| 5 | `sed "s/$PATTERN/$REPL/g" $FILE` | 每行全部替换 |
| 6 | `sed "s/$PATTERN/$REPL/gI" $FILE` | 不区分大小写替换 |
| 7 | `sed -n "s/$PATTERN/$REPL/gp" $FILE` | 仅打印有改动的行 |
| 8 | `sed '/^$/d' $FILE` | 丢弃空行 |
| 9 | `sed 's/[[:space:]]*$//' $FILE` | 去除行尾空格 |
| 10 | `sed 's/\r$//' $FILE` | 去掉 CR（CRLF→LF）到 stdout |
| 11 | `sed '1d' $FILE` | 去掉第一行 |
| 12 | `sed '$d' $FILE` | 去掉最后一行 |
| 13 | `sed -i.bak "s/$PATTERN/$REPL/g" $FILE` | 编辑文件 + `.bak`（不在 playbook 中） |

---

## playbook

| 标签 | 命令链 |
|-----|---------|
| `gchk[1]` | `grep -n` + `grep -c` |
| `sprev[1]` | `s///g` 输出到 stdout + 按 `$PATTERN` 匹配的行 |

```text
$FILE=app.py
$PATTERN=TODO
!! gchk[1]
$SEP=,
!! awk[2]
$PATTERN=foo
$REPL=bar
!! sprev[1]
```
