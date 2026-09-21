# SQLite handbook: the library database from the inside

Tags **`sqlvars`** (variables), **`sqlite`** (schema, queries, editing), **`sqlstat`** (overview).

The topic is SQL on the **live application database**: `SELECT` / `WHERE` / `GROUP BY` / `ORDER BY`,
`LIKE`, `sqlite_master`, `EXPLAIN QUERY PLAN`, `DELETE`, a subquery, `VACUUM`, `PRAGMA`, `.dump`.
The tag library is a real database that the application reads on every `?` / `!` / `Tab`,
so the queries are not "textbook on paper": the result is visible in the journal.

```bash
python3 src/seed_sqlite.py --seed
# or together with the other ops:
python3 src/seed_ops.py --seed
```

```text
$TAG=tegg
$TEXT=kubectl
!! sqlvars[1]
!! sqlstat[1]
```

`$DBFILE` is substituted by **the application itself** — it is the library file it opened (data
directory + `database_tags_file`), so the handbook does not guess the path. Your own value in
`.bashrc_term*` wins: `export DBFILE=~/other/mytags.db`.

The `sqlite3` CLI is needed (`apt install sqlite3`, `dnf install sqlite`, `brew install sqlite`):
the application itself runs on the built-in Python module and works without it, while the handbook is about
the real utility. The first command of the set checks that it is there.

Deleting in the application is **soft** (`#tag-` → `deleted = 1`), so the hard wipe here is
deliberately manual: tid 11–13 change the database, the rest only read.

---

## sqlite (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `command -v sqlite3 \|\| echo 'sqlite3 not found: install sqlite3'` | Is the CLI there |
| 2 | `sqlite3 $DBFILE ".tables"` | Tables of the database |
| 3 | `sqlite3 $DBFILE ".schema"` | Schema: `commands`, `tags`, index |
| 4 | `sqlite3 $DBFILE "SELECT name, type FROM sqlite_master …"` | Tables and index (`sqlite_master`) |
| 5 | `sqlite3 -header -column $DBFILE "SELECT tag, COUNT(*) AS n … GROUP BY tag ORDER BY n DESC;"` | Tags by number of commands |
| 6 | `… "SELECT tag, tid, command FROM commands WHERE deleted = 0 ORDER BY tag, tid;"` | Live commands with tid |
| 7 | `… "SELECT tag, comment FROM tags ORDER BY tag;"` | Tag comments |
| 8 | `… "SELECT tag, tid, command FROM commands WHERE deleted = 1 …"` | Soft-deleted |
| 9 | `… "SELECT command FROM commands WHERE command LIKE '%$TEXT%' AND deleted = 0 LIMIT 20;"` | Text search (`LIKE`) |
| 10 | `… "EXPLAIN QUERY PLAN SELECT command FROM commands WHERE tag = '$TAG' AND deleted = 0;"` | Query plan (index `idx_tag_tid`) |
| 11 | `… "DELETE FROM commands WHERE tag = '$TAG'; DELETE FROM tags WHERE tag = '$TAG';"` | **Wipe the tag for good** (changes the database) |
| 12 | `… "DELETE FROM commands WHERE deleted = 1; DELETE FROM tags WHERE tag NOT IN (…);"` | **Purge the soft-deleted** (changes the database) |
| 13 | `sqlite3 $DBFILE "VACUUM;"` | **Shrink the file** (changes the file) |
| 14 | `sqlite3 $DBFILE "PRAGMA integrity_check;"` | Integrity of the database |
| 15 | `sqlite3 $DBFILE ".dump" > mytags.sql` | SQL dump to `mytags.sql` (current directory) |
| 16 | `sqlite3 $DBFILE` | Interactive sqlite3 (better: `> sqlite3 $DBFILE`) |

---

## sqlstat (tid)

| tid | Chain |
|-----|---------|
| 1 | `!sqlite[5]` → `!sqlite[8]` → `!sqlite[14]` (live tags → soft-deleted → integrity) |

---

## What is studied here

| Technique | Where to look | Meaning |
|-----------|--------------|-------|
| `SELECT … WHERE` | tid 6, 8 | Filter by column; `deleted = 0` — live rows |
| `GROUP BY` + `COUNT(*)` | tid 5 | Aggregate: how many commands in each tag |
| `ORDER BY` | tid 5, 6 | Sort the result (`n DESC` — by descending aggregate) |
| `LIKE` | tid 9 | Substring search (`%` — any number of characters) |
| `sqlite_master` | tid 4 | Service table: what the file actually holds |
| `EXPLAIN QUERY PLAN` | tid 10 | How SQLite is going to run the query: `idx_tag_tid` instead of a full scan |
| `DELETE … WHERE` | tid 11, 12 | Deleting rows (as opposed to `UPDATE deleted = 1` in `#tag-`) |
| Subquery | tid 12 | `tag NOT IN (SELECT DISTINCT tag FROM commands)` — "tags without a single row" |
| `VACUUM` | tid 13 | Rebuild the file: the space of deleted rows goes back to the filesystem |
| `PRAGMA` | tid 14 | Service commands of SQLite (`integrity_check` — integrity check) |
| `.dump` / `.tables` / `.schema` | tid 2, 3, 15 | Commands of the utility itself (with a dot): metadata and a text snapshot |
| CLI flags | tid 5+ | `-header -column` — column headers and alignment (the result is more readable) |

---

## Schema the queries follow

Two tables: `commands` (`id`, `tag`, `tid`, `command`, `timestamp`, `deleted`, `comment`,
`use_count`, `last_used`) and `tags` (`tag`, `comment`). Uniqueness of `(tag, tid)`,
a partial index `idx_tag_tid` on `(tag, tid)` where `deleted = 0`.
In detail — [`DATABASE.md`](../DATABASE.md).

Your own `%` / `_` in `LIKE` (tid 9) are a pattern, while `?text` in the application searches for them literally
(`_escape_like` + `ESCAPE '\'`), so the results may differ.

---

## Hard delete of a tag: the order of steps

1. `:backup` — a SQLite snapshot in `backups/` in case of a mistake.
2. Make sure it is the right tag: `?tegg` (command list) and `??`.
3. `$TAG=tegg` → `!sqlite[11]` (or the SQL from [`DATABASE.md`](../DATABASE.md) by hand).
4. `!sqlite[12]` — purge the soft-deleted along the way, `!sqlite[13]` — `VACUUM`.
5. Lists in an already open window come from the in-memory cache: restart the application (or do
   this while it is closed) — otherwise the tag stays visible until the next mutation from the UI.

Soft delete for "just get it out of sight" stays cheaper: `#tegg-` (tag), `#tegg-2` (command),
`#handbook--` (a whole handbook), to bring it back — `#tegg!` / `#tegg!2` / `#handbook!!`.

---

## Related

| Task | Where |
|--------|-----|
| Database snapshot and restore | `:backup`, `python3 backup_db.py backup` / `restore <file>` |
| Export/import (JSON/CSV/Markdown) | `:export`, `:import`, `python3 backup_db.py` |
| Tag and command comments from SQL | `?tag` / `??` show them; the rules — `#tag=` / `#tag=ID=` |
| Run counters | `:stats` (columns `use_count` / `last_used`) |
