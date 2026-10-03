#!/usr/bin/env python3
"""
Теги справочника git для IDvjPy_term (см. SEED_GIT_COMMANDS.md).

Не затрагивает теги обследования proc / file / net / kube / k8s.

Run: python3 src/seed_git.py --seed
"""
import sys

from seed_lib import run_seed as _run_seed
from seed_lib import seed_cli

# tag -> (комментарий тега, [(команда, комментарий команды), ...])
# Команды осмотра используют --no-pager, чтобы less не блокировал TUI.
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


# Разметка канонических тегов (машинные токены, не переводятся; см. :tagmeta).
SEED_METADATA = {
    "git": {
        "risk": "medium",
        "utilities": ["git"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "vcs",
        "example": "git status -sb",
    },
    "gstat": {
        "risk": "low",
        "utilities": ["git"],
        "os": ["linux", "macos", "windows"],
        "interactive": False,
        "topic": "inspect",
        "example": "!git[2] ; echo '--- branch ---' ; !git[11]",
    },
}


def run_seed(db_file: str) -> int:
    return _run_seed(db_file, SEED_TAGS, label="git", metadata=SEED_METADATA)


def main() -> None:
    seed_cli(
        description="Seed IDvjPy_term DB with git handbook (SEED_GIT_COMMANDS.md)",
        seed_help="Replace git/gstat/gsync/… tags (does not touch proc/file/net/kube/k*)",
        seed_tags=SEED_TAGS,
        argv=sys.argv,
        label="git",
    )


if __name__ == "__main__":
    main()
