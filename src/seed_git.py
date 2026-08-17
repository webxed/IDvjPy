#!/usr/bin/env python3
"""
Seed git handbook tags for IDvjPy_term (see SEED_GIT_COMMANDS.md).

Does not touch proc / file / net / kube / k8s investigation tags.

Run: python3 src/seed_git.py --seed

Uses database_tags_file from settings.yml (same as app.py).
"""
import argparse
import os
import sys

try:
    import yaml
    import database_v2 as database
except ImportError as e:
    print(f"Error: {e}", file=sys.stderr)
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

FILE_SETTINGS = "settings.yml"
ENCODING = "utf-8"
DEFAULT_DB = "mytags.db"

# tag -> (tag comment, [(command, command comment), ...])
# Inspect commands use --no-pager so less does not block the TUI.
SEED_TAGS = {
    "gvars": (
        "переменные git",
        [
            (
                "echo branch=$BRANCH commit=$COMMIT file=$FILE msg=$MSG remote=$REMOTE",
                "проверка $BRANCH/$COMMIT/…",
            ),
        ],
    ),
    "git": (
        "git: статус, diff, ветки, remote, stash",
        [
            ("git status", "полный status"),
            ("git status -sb", "короткий status"),
            ("git --no-pager diff", "unstaged diff"),
            ("git --no-pager diff --cached", "staged diff"),
            ("git --no-pager diff HEAD", "все локальные правки vs HEAD"),
            ("git --no-pager log --oneline -20", "последние 20 коммитов"),
            (
                "git --no-pager log --oneline --graph --decorate --all -20",
                "граф веток",
            ),
            ("git --no-pager show --stat", "последний коммит, список файлов"),
            ("git --no-pager show $COMMIT", "коммит $COMMIT"),
            ("git --no-pager blame $FILE", "blame $FILE"),
            ("git branch -vv", "локальные ветки + tracking"),
            ("git branch -a", "локальные и remote ветки"),
            ("git switch $BRANCH", "переключить ветку $BRANCH"),
            ("git switch -c $BRANCH", "создать и переключить $BRANCH"),
            ("git merge $BRANCH", "слить $BRANCH в текущую"),
            ("git rebase $BRANCH", "rebase на $BRANCH"),
            ("git remote -v", "remotes"),
            ("git fetch --all --prune", "fetch всех remote"),
            ("git pull --rebase", "pull с rebase"),
            ("git push", "push текущей ветки"),
            ("git push -u origin HEAD", "push и выставить upstream"),
            ("git push --force-with-lease", "force-with-lease (не --force)"),
            ("git add -A", "индекс: все изменения"),
            ("git add $FILE", "индекс: $FILE"),
            ("git restore $FILE", "отменить правки в $FILE (не staged)"),
            ("git restore --staged $FILE", "убрать $FILE из индекса"),
            ("git commit -m \"$MSG\"", "коммит с сообщением $MSG"),
            ("git commit --amend --no-edit", "дописать в последний коммит"),
            ("git stash push -u", "stash включая untracked"),
            ("git --no-pager stash list", "список stash"),
            ("git stash pop", "применить последний stash"),
            ("git --no-pager stash show -p", "diff последнего stash"),
            ("git reset --soft HEAD~1", "отменить коммит, правки в индексе"),
            ("git revert $COMMIT --no-edit", "обратный коммит для $COMMIT"),
            ("git cherry-pick $COMMIT", "перенести $COMMIT"),
            ("git --no-pager reflog -20", "reflog"),
            ("git tag", "список тегов"),
            ("git --no-pager shortlog -sn -20", "кто сколько коммитил"),
            ("git clean -nd", "что удалит clean (dry-run)"),
            ("git add -p", "интерактивный add (лучше: > git add -p)"),
            ("git restore --staged :/", "убрать всё из индекса"),
            ("git rebase -i HEAD~5", "interactive rebase (лучше: > git rebase -i HEAD~5)"),
        ],
    ),
    "gstat": (
        "обзор репозитория",
        [
            (
                "!git[2] ; echo '--- branch ---' ; !git[11] ; echo '--- log ---' ; !git[6]",
                "status -sb → ветки → log",
            ),
        ],
    ),
    "gdiff": (
        "unstaged + staged diff",
        [
            (
                "echo '--- unstaged ---' ; !git[3] ; echo '--- staged ---' ; !git[4]",
                "diff и diff --cached",
            ),
        ],
    ),
    "gsync": (
        "fetch + status",
        [
            (
                "!git[18] ; echo '--- status ---' ; !git[2] ; echo '--- log ---' ; !git[6]",
                "fetch --all --prune → status → log",
            ),
        ],
    ),
    "gundo": (
        "осмотр перед отменой (без reset)",
        [
            (
                "!git[36] ; echo '--- status ---' ; !git[2]",
                "reflog + status; reset руками",
            ),
        ],
    ),
}


def get_db_file() -> str:
    if not os.path.exists(FILE_SETTINGS):
        return DEFAULT_DB
    try:
        with open(FILE_SETTINGS, "r", encoding=ENCODING) as f:
            settings = yaml.safe_load(f)
        if settings:
            return settings.get("database_tags_file", DEFAULT_DB)
    except Exception:
        pass
    return DEFAULT_DB


def hard_delete_commands_by_tag(db_file: str, tag: str) -> None:
    conn = database.get_db_connection(db_file)
    conn.execute("DELETE FROM commands WHERE tag = ?", (tag,))
    conn.execute("DELETE FROM tags WHERE tag = ?", (tag,))
    conn.commit()
    conn.close()


def run_seed(db_file: str) -> int:
    database.init_db(db_file)
    n = 0
    for tag, (tag_comment, commands) in SEED_TAGS.items():
        hard_delete_commands_by_tag(db_file, tag)
        for cmd, cmd_comment in commands:
            tid = database.add_command(db_file, cmd, tag)
            if cmd_comment:
                database.set_command_comment(db_file, tag, tid, cmd_comment)
            n += 1
        if tag_comment:
            database.set_tag_comment(db_file, tag, tag_comment)
    return n


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed IDvjPy_term DB with git handbook (SEED_GIT_COMMANDS.md)"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Replace git/gstat/gsync/… tags (does not touch proc/file/net/kube/k*)",
    )
    parser.add_argument(
        "--db",
        default="",
        help="SQLite file (default: settings.yml database_tags_file)",
    )
    args = parser.parse_args()
    if not args.seed:
        print("Run with --seed to populate the database.", file=sys.stderr)
        sys.exit(0)
    db_file = args.db or get_db_file()
    n = run_seed(db_file)
    print(f"Seeded {len(SEED_TAGS)} tags ({n} commands) into {db_file}")


if __name__ == "__main__":
    main()
