# SQLite 手册：标签库数据库的内部结构

标签 **`sqlvars`**（变量）、**`sqlite`**（schema、查询、修改）、**`sqlstat`**（概览）。

主题是**应用正在使用的库**上的 SQL：`SELECT` / `WHERE` / `GROUP BY` / `ORDER BY`、`LIKE`、
`sqlite_master`、`EXPLAIN QUERY PLAN`、`DELETE`、子查询、`VACUUM`、`PRAGMA`、`.dump`。
标签库是真正的数据库，应用在每次 `?` / `!` / `Tab` 时都会读取它，
所以这些查询不是「纸上的教学示例」：结果直接显示在日志中。

```bash
python3 src/seed_sqlite.py --seed
# 或与其他 ops 一起：
python3 src/seed_ops.py --seed
```

```text
$TAG=tegg
$TEXT=kubectl
!! sqlvars[1]
!! sqlstat[1]
```

`$DBFILE` 由**应用本身**代入 —— 它是应用打开的库文件（数据目录
+ `database_tags_file`），所以手册不去猜路径。在
`.bashrc_term*` 中的自定义值优先级更高：`export DBFILE=~/other/mytags.db`。

需要 CLI `sqlite3`（`apt install sqlite3`、`dnf install sqlite`、`brew install sqlite`）：
应用本身使用 Python 内置模块，没有它也能运行；而本手册讲的是
真正的命令行工具。本套命令的第一条会检查它是否存在。

应用中的删除是**软删除**（`#tag-` → `deleted = 1`），因此这里的硬删除是
有意设为手动操作：tid 11–13 会修改数据库，其余只做读取。

---

## sqlite (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `command -v sqlite3 \|\| echo 'sqlite3 not found: install sqlite3'` | 是否有 CLI |
| 2 | `sqlite3 $DBFILE ".tables"` | 数据库中的表 |
| 3 | `sqlite3 $DBFILE ".schema"` | schema：`commands`、`tags`、索引 |
| 4 | `sqlite3 $DBFILE "SELECT name, type FROM sqlite_master …"` | 表和索引（`sqlite_master`） |
| 5 | `sqlite3 -header -column $DBFILE "SELECT tag, COUNT(*) AS n … GROUP BY tag ORDER BY n DESC;"` | 按命令数统计标签 |
| 6 | `… "SELECT tag, tid, command FROM commands WHERE deleted = 0 ORDER BY tag, tid;"` | 带 tid 的未删除命令 |
| 7 | `… "SELECT tag, comment FROM tags ORDER BY tag;"` | 标签的注释 |
| 8 | `… "SELECT tag, tid, command FROM commands WHERE deleted = 1 …"` | 软删除的 |
| 9 | `… "SELECT command FROM commands WHERE command LIKE '%$TEXT%' AND deleted = 0 LIMIT 20;"` | 按文本搜索（`LIKE`） |
| 10 | `… "EXPLAIN QUERY PLAN SELECT command FROM commands WHERE tag = '$TAG' AND deleted = 0;"` | 查询计划（索引 `idx_tag_tid`） |
| 11 | `… "DELETE FROM commands WHERE tag = '$TAG'; DELETE FROM tags WHERE tag = '$TAG';"` | **硬删除标签**（修改数据库） |
| 12 | `… "DELETE FROM commands WHERE deleted = 1; DELETE FROM tags WHERE tag NOT IN (…);"` | **清理软删除的**（修改数据库） |
| 13 | `sqlite3 $DBFILE "VACUUM;"` | **压缩文件**（修改文件） |
| 14 | `sqlite3 $DBFILE "PRAGMA integrity_check;"` | 数据库完整性 |
| 15 | `sqlite3 $DBFILE ".dump" > mytags.sql` | SQL 转储到 `mytags.sql`（当前目录） |
| 16 | `sqlite3 $DBFILE` | 交互式 sqlite3（更好：`> sqlite3 $DBFILE`） |

---

## sqlstat (tid)

| tid | 命令链 |
|-----|---------|
| 1 | `!sqlite[5]` → `!sqlite[8]` → `!sqlite[14]`（未删除标签 → 软删除的 → 完整性） |

---

## 这里学习什么

| 技巧 | 在哪里看 | 含义 |
|-------|--------------|-------|
| `SELECT … WHERE` | tid 6, 8 | 按列过滤；`deleted = 0` 是未删除的行 |
| `GROUP BY` + `COUNT(*)` | tid 5 | 聚合：每个标签下有多少条命令 |
| `ORDER BY` | tid 5, 6 | 对结果排序（`n DESC` 表示聚合值降序） |
| `LIKE` | tid 9 | 子串搜索（`%` 表示任意数量的字符） |
| `sqlite_master` | tid 4 | 系统表：文件里到底有什么 |
| `EXPLAIN QUERY PLAN` | tid 10 | SQLite 打算如何执行查询：用 `idx_tag_tid` 代替全表扫描 |
| `DELETE … WHERE` | tid 11, 12 | 删除行（不同于 `#tag-` 的 `UPDATE deleted = 1`） |
| 子查询 | tid 12 | `tag NOT IN (SELECT DISTINCT tag FROM commands)` ——「一行都没有的标签」 |
| `VACUUM` | tid 13 | 重建文件：已删除行占用的空间归还给文件系统 |
| `PRAGMA` | tid 14 | SQLite 的系统命令（`integrity_check` 检查完整性） |
| `.dump` / `.tables` / `.schema` | tid 2, 3, 15 | 工具本身的命令（带点号）：元数据和文本快照 |
| CLI 标志 | tid 5+ | `-header -column` 显示列标题并对齐（结果更易读） |

---

## 查询所依据的 schema

两张表：`commands`（`id`、`tag`、`tid`、`command`、`timestamp`、`deleted`、`comment`、
`use_count`、`last_used`）和 `tags`（`tag`、`comment`）。唯一性由 `(tag, tid)` 保证，
在 `deleted = 0` 时按 `(tag, tid)` 建的部分索引 `idx_tag_tid`。
详见 [`DATABASE.md`](../DATABASE.md)。

在 `LIKE`（tid 9）中自己写的 `%` / `_` 是通配符，而应用中的 `?text` 会按字面搜索它们
（`_escape_like` + `ESCAPE '\'`），所以结果可能不同。

---

## 硬删除标签：操作顺序

1. `:backup` —— 把 SQLite 快照存到 `backups/`，以防出错。
2. 确认是这个标签：`?tegg`（命令列表）和 `??`。
3. `$TAG=tegg` → `!sqlite[11]`（或手动执行 [`DATABASE.md`](../DATABASE.md) 中的 SQL）。
4. `!sqlite[12]` —— 顺便清理软删除的，`!sqlite[13]` —— `VACUUM`。
5. 已经打开的窗口中的列表取自内存缓存：请重启应用（或者
   在应用关闭时操作）—— 否则在下次从 UI 发生变更前，标签仍然可见。

如果只是「不想看到它」，软删除更省事：`#tegg-`（标签）、`#tegg-2`（命令）、
`#handbook--`（整个手册），恢复用 `#tegg!` / `#tegg!2` / `#handbook!!`。

---

## 相关内容

| 任务 | 位置 |
|--------|-----|
| 数据库快照与恢复 | `:backup`、`python3 backup_db.py backup` / `restore <file>` |
| 导出/导入（JSON/CSV/Markdown） | `:export`、`:import`、`python3 backup_db.py` |
| 从 SQL 查看标签与命令的注释 | `?tag` / `??` 会显示它们；规则见 `#tag=` / `#tag=ID=` |
| 运行次数计数 | `:stats`（列 `use_count` / `last_used`） |
