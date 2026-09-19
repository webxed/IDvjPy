# IDvjPy git 手册

**`git`** 标签 — 带有 `$BRANCH`、`$COMMIT`、`$FILE`、`$MSG`、`$REMOTE` 的模板。
playbook：`gstat`、`gdiff`、`gsync`、`gundo`。

log/diff/show 使用 `--no-pager`，以免 `less` 阻塞 TUI。
`git add -p` / `rebase -i` — 加 `>` 前缀（真正的 TTY）。

```bash
python3 src/seed_git.py --seed
```

不触碰 `proc` / `file` / `net` / `kube` 和 k8s 标签。重复 `--seed` 只覆盖 `gvars`、`git`、`gstat`、`gdiff`、`gsync`、`gundo`。

变量：

```text
$BRANCH=
$COMMIT=HEAD
$FILE=
$MSG=
$REMOTE=origin
!! gvars[1]
```

---

## git — 命令 (tid)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `git status` | 完整状态 |
| 2 | `git status -sb` | 短状态 |
| 3 | `git --no-pager diff` | 未暂存差异 |
| 4 | `git --no-pager diff --cached` | 已暂存差异 |
| 5 | `git --no-pager diff HEAD` | 全部本地改动对比 HEAD |
| 6 | `git --no-pager log --oneline -20` | 最近 20 次提交 |
| 7 | `git --no-pager log --oneline --graph --decorate --all -20` | 分支图 |
| 8 | `git --no-pager show --stat` | 最近提交及文件列表 |
| 9 | `git --no-pager show $COMMIT` | 提交 `$COMMIT` |
| 10 | `git --no-pager blame $FILE` | blame `$FILE` |
| 11 | `git branch -vv` | 本地分支及跟踪 |
| 12 | `git branch -a` | 本地和远程分支 |
| 13 | `git switch $BRANCH` | 切换分支 `$BRANCH` |
| 14 | `git switch -c $BRANCH` | 创建并切换 `$BRANCH` |
| 15 | `git merge $BRANCH` | 将 `$BRANCH` 合并到当前分支 |
| 16 | `git rebase $BRANCH` | rebase 到 `$BRANCH` |
| 17 | `git remote -v` | 远程仓库 |
| 18 | `git fetch --all --prune` | 拉取所有远程 |
| 19 | `git pull --rebase` | 以 rebase 方式 pull |
| 20 | `git push` | 推送当前分支 |
| 21 | `git push -u origin HEAD` | 推送并设置上游 |
| 22 | `git push --force-with-lease` | force-with-lease（不用 --force） |
| 23 | `git add -A` | index: 全部改动 |
| 24 | `git add $FILE` | index: `$FILE` |
| 25 | `git restore $FILE` | 丢弃 `$FILE` 中的改动（未暂存） |
| 26 | `git restore --staged $FILE` | 取消暂存 `$FILE` |
| 27 | `git commit -m "$MSG"` | 以消息 `$MSG` 提交 |
| 28 | `git commit --amend --no-edit` | 修正最近一次提交 |
| 29 | `git stash push -u` | 暂存包括未跟踪文件 |
| 30 | `git --no-pager stash list` | 列出 stash |
| 31 | `git stash pop` | 应用最近的 stash |
| 32 | `git --no-pager stash show -p` | 最近 stash 的差异 |
| 33 | `git reset --soft HEAD~1` | 撤销提交，改动保持暂存 |
| 34 | `git revert $COMMIT --no-edit` | 回退提交 `$COMMIT` |
| 35 | `git cherry-pick $COMMIT` | cherry-pick `$COMMIT` |
| 36 | `git --no-pager reflog -20` | reflog |
| 37 | `git tag` | 列出标签 |
| 38 | `git --no-pager shortlog -sn -20` | 谁提交了多少 |
| 39 | `git clean -nd` | clean 将删除什么（dry-run） |
| 40 | `git add -p` | 交互式 add（更好: `> git add -p`） |
| 41 | `git restore --staged :/` | 取消暂存全部 |
| 42 | `git rebase -i HEAD~5` | 交互式 rebase（更好: `> git rebase -i HEAD~5`） |

在应用中：`!git[1]` … `!git[42]`。组装：`!! git[2] ; git[6]`。

---

## playbook

| 标签 | 命令链 | 原因 |
|-----|---------|--------|
| `gstat[1]` | status -sb → branch -vv → log | 概览 |
| `gdiff[1]` | unstaged + staged diff | 提交内容 |
| `gsync[1]` | fetch --all --prune → status → log | 同步 |
| `gundo[1]` | reflog + status | **不**做 reset 的检查 |

```text
!! gstat[1]
!! gsync[1]
$FILE=app.py
!! git[3]
$MSG=fix pager hang
!! git[23]
!! git[27]
```

不要放入自动命令链：`reset --hard`、`push --force`、`clean -fd`。`git[22]` / `git[33]` / `git[39]` — 仅手动执行。
