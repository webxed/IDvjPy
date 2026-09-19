# git handbook for IDvjPy

The **`git`** tag — templates with `$BRANCH`, `$COMMIT`, `$FILE`, `$MSG`, `$REMOTE`.
Playbooks: `gstat`, `gdiff`, `gsync`, `gundo`.

`--no-pager` on log/diff/show so `less` does not block the TUI.
`git add -p` / `rebase -i` — with the `>` prefix (real TTY).

```bash
python3 src/seed_git.py --seed
```

Does not touch `proc` / `file` / `net` / `kube` or k8s tags. A repeated `--seed` overwrites only `gvars`, `git`, `gstat`, `gdiff`, `gsync`, `gundo`.

Variables:

```text
$BRANCH=
$COMMIT=HEAD
$FILE=
$MSG=
$REMOTE=origin
!! gvars[1]
```

---

## git — commands (tid)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `git status` | full status |
| 2 | `git status -sb` | short status |
| 3 | `git --no-pager diff` | unstaged diff |
| 4 | `git --no-pager diff --cached` | staged diff |
| 5 | `git --no-pager diff HEAD` | all local changes vs HEAD |
| 6 | `git --no-pager log --oneline -20` | last 20 commits |
| 7 | `git --no-pager log --oneline --graph --decorate --all -20` | branch graph |
| 8 | `git --no-pager show --stat` | last commit, list of files |
| 9 | `git --no-pager show $COMMIT` | commit `$COMMIT` |
| 10 | `git --no-pager blame $FILE` | blame `$FILE` |
| 11 | `git branch -vv` | local branches + tracking |
| 12 | `git branch -a` | local and remote branches |
| 13 | `git switch $BRANCH` | switch branch `$BRANCH` |
| 14 | `git switch -c $BRANCH` | create and switch `$BRANCH` |
| 15 | `git merge $BRANCH` | merge `$BRANCH` into current |
| 16 | `git rebase $BRANCH` | rebase onto `$BRANCH` |
| 17 | `git remote -v` | remotes |
| 18 | `git fetch --all --prune` | fetch all remotes |
| 19 | `git pull --rebase` | pull with rebase |
| 20 | `git push` | push current branch |
| 21 | `git push -u origin HEAD` | push and set upstream |
| 22 | `git push --force-with-lease` | force-with-lease (not --force) |
| 23 | `git add -A` | index: all changes |
| 24 | `git add $FILE` | index: `$FILE` |
| 25 | `git restore $FILE` | discard changes in `$FILE` (not staged) |
| 26 | `git restore --staged $FILE` | unstage `$FILE` |
| 27 | `git commit -m "$MSG"` | commit with message `$MSG` |
| 28 | `git commit --amend --no-edit` | amend the last commit |
| 29 | `git stash push -u` | stash including untracked |
| 30 | `git --no-pager stash list` | list stashes |
| 31 | `git stash pop` | apply the last stash |
| 32 | `git --no-pager stash show -p` | diff of the last stash |
| 33 | `git reset --soft HEAD~1` | undo commit, changes stay staged |
| 34 | `git revert $COMMIT --no-edit` | revert commit `$COMMIT` |
| 35 | `git cherry-pick $COMMIT` | cherry-pick `$COMMIT` |
| 36 | `git --no-pager reflog -20` | reflog |
| 37 | `git tag` | list tags |
| 38 | `git --no-pager shortlog -sn -20` | who committed how much |
| 39 | `git clean -nd` | what clean will delete (dry-run) |
| 40 | `git add -p` | interactive add (`> git add -p`) |
| 41 | `git restore --staged :/` | unstage everything |
| 42 | `git rebase -i HEAD~5` | interactive rebase (`> git rebase -i HEAD~5`) |

In the app: `!git[1]` … `!git[42]`. Assembly: `!! git[2] ; git[6]`.

---

## Playbooks

| Tag | Chain | Why |
|-----|---------|--------|
| `gstat[1]` | status -sb → branch -vv → log | overview |
| `gdiff[1]` | unstaged + staged diff | what goes into the commit |
| `gsync[1]` | fetch --all --prune → status → log | synchronization |
| `gundo[1]` | reflog + status | inspection **without** reset |

```text
!! gstat[1]
!! gsync[1]
$FILE=app.py
!! git[3]
$MSG=fix pager hang
!! git[23]
!! git[27]
```

Do not put into an auto chain: `reset --hard`, `push --force`, `clean -fd`. `git[22]` / `git[33]` / `git[39]` — manually only.
