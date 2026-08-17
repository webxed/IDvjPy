# Справочник git для IDvjPy

Тег **`git`** — шаблоны с `$BRANCH`, `$COMMIT`, `$FILE`, `$MSG`, `$REMOTE`.
Плейбуки: `gstat`, `gdiff`, `gsync`, `gundo`.

`--no-pager` у log/diff/show, чтобы `less` не блокировал TUI.
`git add -p` / `rebase -i` — с префиксом `>` (настоящий TTY).

```bash
python3 src/seed_git.py --seed
```

Не трогает `proc` / `file` / `net` / `kube` и k8s-теги. Повторный `--seed` перезаписывает только `gvars`, `git`, `gstat`, `gdiff`, `gsync`, `gundo`.

Переменные:

```text
$BRANCH=
$COMMIT=HEAD
$FILE=
$MSG=
$REMOTE=origin
!! gvars[1]
```

---

## git — команды (tid)

| tid | Команда | Назначение |
|-----|---------|------------|
| 1 | `git status` | Полный status |
| 2 | `git status -sb` | Короткий status |
| 3 | `git --no-pager diff` | Unstaged |
| 4 | `git --no-pager diff --cached` | Staged |
| 5 | `git --no-pager diff HEAD` | Все правки vs HEAD |
| 6 | `git --no-pager log --oneline -20` | 20 коммитов |
| 7 | `git --no-pager log --oneline --graph --decorate --all -20` | Граф |
| 8 | `git --no-pager show --stat` | Последний коммит |
| 9 | `git --no-pager show $COMMIT` | Коммит `$COMMIT` |
| 10 | `git --no-pager blame $FILE` | Blame `$FILE` |
| 11 | `git branch -vv` | Ветки + tracking |
| 12 | `git branch -a` | Локальные и remote |
| 13 | `git switch $BRANCH` | Переключить `$BRANCH` |
| 14 | `git switch -c $BRANCH` | Создать `$BRANCH` |
| 15 | `git merge $BRANCH` | Merge |
| 16 | `git rebase $BRANCH` | Rebase |
| 17 | `git remote -v` | Remotes |
| 18 | `git fetch --all --prune` | Fetch |
| 19 | `git pull --rebase` | Pull rebase |
| 20 | `git push` | Push |
| 21 | `git push -u origin HEAD` | Push + upstream |
| 22 | `git push --force-with-lease` | Force-with-lease |
| 23 | `git add -A` | В индекс всё |
| 24 | `git add $FILE` | В индекс `$FILE` |
| 25 | `git restore $FILE` | Откатить файл |
| 26 | `git restore --staged $FILE` | Убрать из индекса |
| 27 | `git commit -m "$MSG"` | Коммит `$MSG` |
| 28 | `git commit --amend --no-edit` | Amend |
| 29 | `git stash push -u` | Stash + untracked |
| 30 | `git --no-pager stash list` | Список stash |
| 31 | `git stash pop` | Pop stash |
| 32 | `git --no-pager stash show -p` | Diff stash |
| 33 | `git reset --soft HEAD~1` | Снять последний коммит |
| 34 | `git revert $COMMIT --no-edit` | Revert |
| 35 | `git cherry-pick $COMMIT` | Cherry-pick |
| 36 | `git --no-pager reflog -20` | Reflog |
| 37 | `git tag` | Теги |
| 38 | `git --no-pager shortlog -sn -20` | Авторы |
| 39 | `git clean -nd` | Dry-run clean |
| 40 | `git add -p` | Interactive add (`> git add -p`) |
| 41 | `git restore --staged :/` | Убрать всё из индекса |
| 42 | `git rebase -i HEAD~5` | Interactive rebase (`> git rebase -i HEAD~5`) |

В приложении: `!git[1]` … `!git[42]`. Сборка: `!! git[2] ; git[6]`.

---

## Плейбуки

| Тег | Цепочка | Зачем |
|-----|---------|--------|
| `gstat[1]` | status -sb → branch -vv → log | обзор |
| `gdiff[1]` | unstaged + staged diff | что в коммите |
| `gsync[1]` | fetch --all --prune → status → log | синхронизация |
| `gundo[1]` | reflog + status | осмотр **без** reset |

```text
!! gstat[1]
!! gsync[1]
$FILE=app.py
!! git[3]
$MSG=fix pager hang
!! git[23]
!! git[27]
```

Не класть в автоцепочку: `reset --hard`, `push --force`, `clean -fd`. `git[22]` / `git[33]` / `git[39]` — только руками.
