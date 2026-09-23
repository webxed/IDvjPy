# IDvjPy — ID Variables & Joiner on Python

<p align="center">
  <img src="../../idvj-all.gif" alt="IDvjPy_term: python3 app.py --demo all" width="800">
</p>

<p align="center"><em>Define your variables, join your command.</em></p>

键盘驱动的 TUI，将**标签视为命令模板**，并把它们组装成 shell 命令行（`!tag[tid]`、`!!`）。需要 Python **3.12+**、[Textual](https://textual.textualize.io/)。

**IDvjPy_term** v1.175 — 从标签生成命令行的智能终端。

其他语言：[Russian](../../README.md) · [English](../en/README.md)。

## 这是什么？

IDvjPy 是一个用 Python（Textual）编写、以键盘操作的终端应用（TUI）。
带标签的常驻命令历史存储在 SQLite 中。

**理念：**标签是带命令模板的变量；应用把它们组装成复杂的命令行。

应用代码位于 `src/`。数据存放在工作目录中：`settings.yml`、标签数据库、`.bashrc_term*`。数据库为空时，日志中会显示种子手册目录（Linux、[k8s 排查链](../../K8S_CHAINS.md)、git、ops）：点击绿色的 `--seed` 会把命令插入输入行，点击 `.md` 会打开手册。

启动：`python3 app.py`（启动器；代码在 `src/`）。测试：`python3 -m pytest tests/ -v`（开发依赖：`pip install -r requirements-dev.txt`）。应用内帮助：`:?`。

## 功能

- 常驻标签与命令组装（`!tag[tid]`、`!!`）
- 命令手册（种子）：Linux、[k8s 排查链](../../K8S_CHAINS.md)、git、docker、helm、ansible、systemd、lsof/strace、sysstat、sort/jq、ip/ethtool、tcpdump/mtr/TLS、apt/rpm 以及其他 ops
- 按块组织的日志：聚焦、折叠、从聚焦块管道 `|`；缓冲区标记（`:name`）——可从旧块管道而无需重新运行来源（`|@label awk …`、`|@N …`）
- 阅读模式：如果你把日志向上翻（滚轮/PgUp）或聚焦在块上，新输出会追加到底部，但视图和焦点不会移动——无论 `:watch`、`:llm` 的回答，还是到来的 `:send`。当滚动到底部或运行命令（Enter）时恢复跟随
- 路径、数据库中的命令和 `history_*.txt` 行（包括 `@`/`>`；开关——`history_completion`）以及本会话命令的补全。`:` 请求的调用（`:llm`、`:cht`、`:rg`、`:md`、`:run`、`:send`）会留在历史中供 ↑/`:h` 使用，但不作为提示——名单在 `history_queries`
- 应用命令的快速提示：输入 `:` 后列出所有带简短说明的 `:` 命令（按字母过滤，`Tab`/`Enter` 插入 `:命令 `，运行则另按 Enter）；`:/text` 仍用于搜索日志。在帮助 `:?` 中命令名是可点击链接：点击会把调用插入输入行（就像 `??` 中的 `!tag` 和 `:welcome` 中的 `--seed`）
- 帮助主题：总览在 `:?`，各命令组的细节在 `:? <主题>`（`:? llm`、`:? tags`、`:? calc`、`:? run`、`:? i`、`:? md`、`:? vars`、`:? kctx`、`:? send`、`:? session`；主题列表见帮助中的「帮助主题」一节和 `:? ` 之后的提示）。未知主题会明确报错并列出主题；粘连写法 `:?calc` 会提示加空格
- 输入 `?` 时的标签提示：标签名、命令数和标签注释（`?vault  (2)  HashiCorp Vault`），按字母过滤；点击某行会插入 `?tag` 并立即执行查询。只有命令本身 `?vault` 会成为链接（并高亮）——计数和注释仍是普通文本
- 块输出中的逐行模式（复制并追加到输入行）
- JSON viewer（F5），带 `jq` 草稿和 `$JSON`
- `$VAR` 变量（文件 `.bashrc_term` / `.bashrc_term_<instance>`）；`$DBFILE` 由应用设置（它打开的 SQLite 库文件，可在 `.bashrc_term` 中覆盖）；`$OUT` —— 块的最后一行，仅在命令执行时
- 秘密 `$$VAR=value`：值在输入时和日志中都会隐藏（`****`），存储在 `secrets_<instance>.json`（0600）——而不是 `.bashrc_term`/history 中；在命令中使用 `$VAR`。设置键 `clear_clipboard_after_secret` 会在把值插入 `$$NAME=…` 后清空剪贴板
- 无需等待 timeout 即可停止后台命令：`F4` / `:kill`（向整个进程组发送 SIGTERM）
- 按命令内容搜索：`?kubectl wide` —— 如果没有这样的标签，则按文本/注释搜索
- 用命令监控：`:watch 5 kubectl get pods` —— 每 N 秒在同一个块中重新运行
- 库的整理：`:mv tag[1] tag2`（移动命令）和 `:mv tag tag2`（重命名）
- 指标：运行次数（use_count/last_used）和 `:stats` —— 按运行次数排名、标签、「never run」
- Markdown 目录：`:export * [file.md]` —— 整个库按标签连同注释导出
- 输出比较：`:diff` —— 聚焦块与前一个块的 unified diff
- 会话输出历史：`:o [N]`、`:o /文本`、`:o clear` —— 在 `:c` 之后对以往输出做 grep
- k8s 补全：`kubectl get pod <Tab>` —— 从集群获取名称（`k8s_completion: true`）
- 文件提示 —— `file_completion: auto|paths|off`：默认是显式路径（`./`、`/`、`~/`）以及 `cat`/`vim`/… 之后的文件名；对 `grep`/`sed`/`awk`/`jq` 则从第二个参数开始（第一个是模式），输入 `kubectl`/`docker`/`git` 时不会混入 cwd 的杂项；上下文按当前片段计算（`cat f | grep ot` 不会列出 cwd）（`paths` —— 仅显式路径，`off` —— 关闭）。列表中**目录像链接一样带下划线，文件保持普通文本**（在 `cd` 时两者很容易混淆）；点击两者都可插入。对 shell 命令，需要转义的路径会以**引号**插入（`cat './my report.md'`）；对 `:`-命令则原样插入（`:md ./my report.md`：它们自己拆分参数，引号会成为路径的一部分）
- Markdown 搜索（`:rg <模式> [目录]`）—— 用 ripgrep 搜索 Obsidian vault 或任何含 `.md` 的目录（否则使用内置扫描器）：片段中的 `路径:行号` 可点击，并在内置 md 查看器中打开；`:rg <N>` —— 打开第 N 个结果
- UX：`:r N` —— N 个块之前那条块的命令；`:cmd [N] [show]` —— 把块命令代入当前值（含秘密）后放入剪贴板；`:send <会话|*> <命令>` —— 把命令转发到另一个窗口（插入输入行；`:send!` —— 立即执行）；标题中的 `N running` 计数器；`:alias <tag>` —— 把命令导出为 bash 函数
- 从 TUI 调用 LLM：`:llm [提供方] 消息`（不带名称则用 `default:`；`$OUT`/`$BLOCK` 插入块的输出；`@文件` 会嵌入文件文本（UTF-8，≤200 KB；可以多个）；对话上下文由提供方的 `history_turns: N` 控制（`:llm reset [<提供方>|*]`）；请求会写入 `history_*.txt`，但不进入提示——具体哪些 `:` 请求如此保存由 settings.yml 中的 `history_queries` 决定）。回答是 markdown，并以格式化方式显示（`llm_render_markdown`，见设置）。请求进行期间，块中会转动 `⠋ thinking… 3s / 60s` 加载指示（能看出正在等待回答，以及允许等待多久）
- 面向 AI 客户端的 MCP 服务器：`python3 mcp_server.py` —— 通过 stdio 提供标签库（Claude Code、Cursor 等），只读（`:? mcp`）
- 从 TUI 使用 cheat.sh：`:cht <请求>` —— 在日志中显示 [cht.sh](https://github.com/chubin/cheat.sh) 速查（命令、语言问题、`~` 搜索），不带 ANSI；输出是普通块（`$OUT`、`|`、F3、F7、搜索）
- 运行手册（runbook）—— 半自动命令链：`:run <tag|文件.yml>` 依次执行步骤，并在需要你决定的地方停下（`run:manual` —— 把命令放进输入行，你修改后按 Enter；`run:prompt` —— 从零开始输入；空 Enter 跳过该步骤）。如果标签中没有任何 `run:` 指令，计划会警告：所有步骤都将以 `auto` 执行（过期的种子就是这样——变更可能在无确认的情况下执行）。某步出错会停止运行，`Esc` / `:run stop` 也会；`--step` —— 每步都停下，`--dry` —— 只显示计划；帮助 —— `:? run`。现成示例 —— `:run vapprole`（token → role → `role_id` → `secret_id` → login → 校验；token 和 role 步骤是带前缀的行 `$$VAULT_TOKEN=` / `$ROLE=`，值在该 `=` 之后补写）
- 彩色命令的输出与终端一致：SGR 码（`curl wttr.in`、`ls --color=always`、彩色 `grep`）由块的颜色渲染（`ansi_colors: true`），而不会流进 TUI 画面；光标/OSC 序列和控制字符始终会被剔除，进度条的 `\r` 重绘（`docker build`、`pip`、带进度的 `curl`）会折叠为最终一行——于是看到的是结果，而不是上百帧。纯文本（`F3`、`|`、`$OUT`/`$BLOCK`、`:log`、`@key`）始终不带转义码（F6 —— 临时输出纯文本）
- 干净的历史：拼写错误（`command not found`，127）会自动从 `history_*.txt` 和本次会话的 ↑ 列表中移除 —— 错误仍留在日志中。可用 `history_forget_not_found: false` 关闭（此时这类行与其他命令一样保留）
- `:llm` 回答语言：提供方的 `answer_language: Russian` —— 一条硬性规则，避免给出不使用用户语言（例如中文）的回答
- `:llm` 的等待可见：块中会动画显示加载指示和时间（`⠋ thinking… 3s / 60s`，第二个上限是提供方的 `timeout`），因此请求不会看起来像卡死；一旦收到回答或错误，该记录就会被移除。请求进行期间，块不会按 markdown 解析（显示状态行），此时输入和日志仍然可用
- :llm ask：`:llm ask [<提供方>] <任务>` —— 会把任务**连同**应用速查和标签库摘要（标签/tid/命令/注释，与任务相关的排在前，其余仅列名称）发给提供方（默认提供方，或由第一个词指定）。回答会给出可直接使用的链接 `!kpod[1]` / `!! kpod[1] && klog[1]`；已有链接还会以可点击行的形式显示（插入输入行，运行则另按 Enter）。对于普通 `:llm`，同一上下文由提供方的 `app_context: true|N` 开启（`N` —— 字符数预算，默认 6000；没有该键/false —— 关闭）。逻辑在 `src/llm_context.py`
- 外部编辑器：`:ed <文件>`（编辑文件）、`:ed $OUT|$BLOCK`（块的输出）、`:ed`（空缓冲区）。TUI 暂停（如同 `> cmd`）。编辑器由 `settings.yml` 中的 `editor:` 指定（可带参数：`code --wait`），否则用 `$VISUAL`/`$EDITOR`，再否则用系统默认。路径中会展开 `$VAR`/`$OUT`（`:ed $TMPDIR/pod-$OUT.json`）；单行结果会改写输入行（运行 —— Enter），多行结果则保留为文件并显示其路径（`@文件` / `| cmd`）
- 来自 `~/.bashrc` 的别名（包括 `$1` / `$2` / `$@`），后台执行命令
- `> cmd` —— 真正的 TTY（htop、vim、ssh）；点击和 PgUp/PgDn 会激活可见的日志块。后台命令不会获得终端：`stdin` 是 `/dev/null`，因此 `read`、`tsh`、`kubectl`、`ssh` 不会「偷走」按键和鼠标（以前 `:kctx` 遇到卡住的 `tsh kube login` 会让输入失效），而超时/`F4` 后应用会把终端切回自己的模式。需要交互 —— `> cmd`；不需要 TTY 的长时间任务 —— `@ cmd`；`:kctx <cluster>` 会发起登录且不带 `command_timeout`。**这也是日志里看不到进度条的原因：**没有 TTY 时工具会自行关闭进度 —— `git clone <url>` 只打印 `Cloning into …`（以及服务器的 `remote:` 行，它们走数据通道），与普通终端里的 `git clone … | cat` 完全一样。强制打开 —— `git clone --progress …`：每个阶段（Enumerating/Counting/Receiving/…）都会单独成行。但依然不会有实时进度条：块只在命令结束时更新（`[Executing...]` → 输出），而同一行的 `\r` 重绘会折叠为最终状态（中间百分比是成百帧，故意不保留）。想看实时进度，请使用真正的 TTY：`> git clone …`（TUI 暂停；该输出不会写入日志）。
- 无需特殊命令的计算器：以数字（或 `(` / `-`）开头且能整体解析为算术/单位换算的行会在本地计算 —— `512Mi + 20% in Gi`、`20% of 512Mi`、`2Gi/512Mi`、`500m in cores`
- ipcalc：IPv4 网段同样如此计算，无需特殊命令 —— `192.168.1.0/24`、`300 hosts` → `/23`（与 jodies.de/ipcalc 一致）
- Kubernetes 集群日志：`kctx_vars` 列表中的变量（默认是 bundled 模板栈：kubectl `NS POD DEPLOY SVC ING APP CTR QUOTA` 和 helm `RELEASE CHART VALUES`）会按集群记录到 `kctx.json`（data 目录）。`:kctx` —— 集群列表；`:kctx <cluster>` —— 登录（`klogin <c> || kubectl config use-context <c>`）并显示以前用过的变量集（如果恰好只有一个集合，则立即应用）；`:kctx N` 应用集合 N（变量 → `.bashrc_term_*`）；`:kctx <cluster> N` —— 一行完成登录并应用；`kctx_vars: []` 会关闭该日志

## 安装

需要 Python 3.12+。

```bash
./setup.sh                 # 创建 .venv（检查 Python 3.12+）并安装依赖
source .venv/bin/activate
# 或：pip install -r requirements.txt
# 测试：pip install -r requirements-dev.txt
# shell 包装函数（shell 的 cwd 跟随应用）：./setup.sh --shell-helper
```

在 Linux 上，剪贴板需要 `xclip` 或 `xsel`（Wayland 下用 `wl-clipboard`）。

变量：首次启动时会把 [`src/.bashrc_term.example`](../../src/.bashrc_term.example) 复制为 `.bashrc_term_<instance>`。演示：[`DEMO.md`](../../DEMO.md)（现场脚本）和 `python3 app.py --demo`（用于录屏的自动输入）。

### 作为 pip 包安装（wheel）

构建好的 wheel 可以安装到任意 venv 中，并通过 `idvjpy` 命令运行，无需克隆仓库。

```bash
# 在仓库中：构建 wheel（把当前 src/ 复制进包的内嵌资源）
packaging/build_wheel.sh                 # → packaging/dist/idvjpy_term-<版本>-py3-none-any.whl

# 在目标环境中：
python3 -m venv .venv && source .venv/bin/activate
pip install packaging/dist/idvjpy_term-*.whl

idvjpy                       # 启动（与 python3 app.py 使用相同的参数）
idvjpy --demo short          # 从已安装的包运行自动演示
python3 -m idvjpy_boot       # 同样通过 python -m 运行
```

wheel 中包含代码和资源（`app.tcss`、`demos/`、配置示例、`.bashrc_term.example`，以及 `:md` 手册 —— `docs/<lang>/*.md` 和 `K8S_CHAINS.md`）；用户存储（settings/数据库/history）**不会**打进包——首次启动时会在系统 data 目录中创建（`--data-dir` → `$IDVJPY_DATA_DIR` → 操作系统的系统目录，见「启动」）。这样同一个包可以升级（`pip install -U`），而不影响自己的标签和历史。

包版本与应用版本一致（`CommandRunner.VERSION` → `MAJOR.MINOR.0`）。

### 版本 = 提交（面向贡献者）

唯一事实来源是 `src/app.py` 中的 `VERSION`。提升次版本号并一次性更新所有发布文件（README、`COMPACT_SUMMARY.md`、`CLAUDE.md`、`AGENTS.md`、`test_cmd.md`、`tests/test_cmd_scenarios.py`、`DEMO.md`，以及手册 `DATABASE.md` / `backup_db.md` 中的标记「状态截至 **vX.YY**」）：

```bash
python3 bump_version.py              # v1.97 → v1.98 并修改所有文件
python3 bump_version.py --dry-run    # 显示 diff，不写入任何内容
python3 bump_version.py --check      # 检查同步性（不一致时 exit 1）
python3 bump_version.py --set v2.0   # 显式指定版本
```

脚本会在 `COMPACT_SUMMARY.md` 中以占位形式添加 `## <新版本>` 小节——变更说明请自行填写。同一批标记的同步性由 `tests/test_release_meta.py` 检查。

### 安装到系统（pipx / uv / `--user`）

要让 `idvjpy` 始终作为普通命令可用，请以隔离方式安装 wheel——这样不会影响系统 Python。

```bash
# pipx —— 为每个应用单独的环境
pipx install packaging/dist/idvjpy_term-*.whl
pipx upgrade idvjpy-term        # 构建新 wheel 之后
pipx uninstall idvjpy-term

# uv (>= 0.4) —— 用 uv 的风格做同样的事；把可执行文件装到 ~/.local/bin
uv tool install packaging/dist/idvjpy_term-*.whl
uv tool list                    # idvjpy-term v1.60.0 / idvjpy
uv tool upgrade idvjpy-term
uv tool uninstall idvjpy-term

# 或者通过 uv 装进当前激活的 venv
uv venv && uv pip install packaging/dist/idvjpy_term-*.whl

# 用户级安装（无隔离）
python3 -m pip install --user packaging/dist/idvjpy_term-*.whl   # ~/.local/bin/idvjpy
```

备注：
- 在 Debian/Ubuntu 上，不带 venv 的系统级 `pip install` 会被阻止（PEP 668，`externally-managed-environment`）——请使用 `pipx`/`uv` 或 `--user`。
- 直接从 git 安装也可以：根目录的 [`pyproject.toml`](../../pyproject.toml) + [`setup.py`](../../setup.py) 会在构建阶段把 `src/` 嵌入包中（与 `packaging/build_wheel.sh` 相同）。

```bash
# 直接从 GitHub —— 无需本地构建 wheel
pipx install git+https://github.com/webxed/IDvjPy
uv tool install git+https://github.com/webxed/IDvjPy
```

- 首次启动时数据落在哪里——见下文「启动」：操作系统的系统目录（`~/.config/idvjpy` 及类似位置），或者 `--data-dir` / `$IDVJPY_DATA_DIR`。升级/卸载包时，标签、历史和设置都会保留。

## 启动

```bash
python3 app.py [--data-dir PATH]
```

数据（settings/数据库/history）：`--data-dir` → `$IDVJPY_DATA_DIR` → 当前目录（如果其中已有 `settings.yml`）→ 系统目录（`~/.config/idvjpy`，macOS `~/Library/Application Support/IDvjPy`，Windows `%APPDATA%\IDvjPy`）。首次在新目录中启动时会创建 `settings.yml`（`auto` 模式下所选语言模板的副本：`--lang` → `$IDVJPY_LANG` → 系统区域设置 → `en`，文件在 [`src/settings/<lang>.yml`](../../src/settings)）和 `llm_providers.yml`（示例的副本）。个人的 `settings.yml` **不会**进入 git——设置不会泄漏到仓库。

```bash
python3 app.py
python3 app.py --instance-name=user1   # 单独的 .bashrc_term_user1 和 history_user1.txt
python3 app.py --demo                  # 自动演示：自己打印命令（Esc — 停止）
python3 app.py --demo ip               # myip → jq .cc → Wiki URL → hello pipe → echo Hello, $OUT
python3 app.py --demo features         # v1.44 的新命令（见 DEMO.md）
python3 app.py --demo all              # 全部演示：calc、ipcalc、JSON、标签、:stats、:diff、:watch、:kctx（不联网）
python3 app.py --demo full --demo-quit
```

应用代码位于 `src/`。工作副本根目录中是数据：`settings.yml`、标签数据库、`.bashrc_term*`、`history_<instance>.txt`、会话注册表 `session_<instance>.pid`。种子手册：`python3 src/seed_git.py --seed` 等。数据库为空时，日志中会显示目录：点击 `--seed` 会把命令插入输入行，点击 `.md` 或 `:md 文件.md` 会打开手册（`terminal_mouse: true`）。

| 路径 | 用途 |
|------|------------|
| `src/` | TUI、CSS、种子脚本、`.bashrc_term.example` 模板 |
| `app.py` / `backup_db.py` | 启动器（不修改数据） |
| `settings.yml` | 个人设置 —— **不在 git 中**（`.gitignore`）；`src/settings/<lang>.yml` 的副本（`auto` 语言），首次启动时创建 |
| `*.db`、`.bashrc_term*`、`history_*.txt`、`inbox_*.jsonl`、`session_*.pid` | 标签、变量、历史、`:send` 信箱和会话注册表 —— 同样不在 git 中 |

## Docker 演示环境

无需安装 Python 就能体验 TUI：一个小镜像（约 100 MB，`python:3.12-alpine`），其中标签库已填充好。数据在卷 `idvjpy-demo-data` 中（`settings.yml`、`mytags.db`、history），代码在镜像里。可以试什么、如何重置 —— [`docker/README.md`](../../docker/README.md)。

```bash
cd docker
docker compose run --rm idvjpy                          # 构建并运行
docker compose run --rm idvjpy --demo short --demo-quit # 自动演示（演示需要 TTY）

docker volume rm idvjpy-demo-data                       # 重置为出厂状态
```

首次启动会自己从模板创建 `/data/settings.yml` 并填充库（`linux`、`k8s`、`git`、`ops` —— 849 条命令，约 5 秒）。镜像内有 `bash`、`nano`、`git`、`curl`、`jq`、`procps`；`docker`/`kubectl` CLI 有意不包含——`dck`/`kpod` 这类标签是命令模板，而不是已安装的 CLI。不用 compose 时：

```bash
docker build -f docker/Dockerfile -t idvjpy-demo .
docker run --rm -it -v idvjpy-demo-data:/data idvjpy-demo
```

CI 会构建该镜像并运行冒烟测试 —— [`.github/workflows/tests.yml`](../../.github/workflows/tests.yml) 中的 `docker-demo` job：准备、种子、重复运行的幂等性，以及真实 pty 下的 TUI 渲染（`docker/tui-smoke.py`）。

## 前缀系统

| 前缀 | 用途 | 示例 |
|---------|------------|--------|
| （无） | 执行 shell 命令 | `ls -la` |
| `> cmd` | 交给真正的 TTY（htop、vim、ssh）。退出后仍是同一个 shell 的 env/$PWD | `> htop` |
| `@ cmd` | 不带 `command_timeout` 执行（长时间的非 TTY 任务；stdin —— `/dev/null`） | `@ terraform apply` |
| `& cmd` | 在**新的终端窗口**中执行（TUI 继续运行；输出留在那个窗口，日志只记录已启动） | `& kubectl logs -f pod/api-1`、`& htop` |
| `#tag cmd` | 保存带标签的命令（文本原样） | `#deploy rsync -av src/ host:` |
| `# command` | 写入历史，不执行（如同 bash 中的 `# …`；`#` 后有空格） | `# curl https://example.com` |
| `#tag=` / `#tag=ID=` | 标签 / 命令的注释 | `#deploy=prod rsync` |
| `#tag+` / `#tag+ID` | 插入以供编辑 | `#deploy+1` |
| `#tag-` / `#tag-tid` | 软删除 | `#deploy-` / `#deploy-1` |
| `#name--` / `#name!!` | 隐藏 / 恢复手册的所有标签 | `#ansible--` / `#ansible!!` |
| `#tag!` / `#tag!tid` | 删除后恢复 | `#deploy!` / `#deploy!1` |
| `?` / `??` / `?tag` / `?tag[tid]` | 查询标签 / 全部 / 按标签 / 预览；`?text`（2 个以上字符且不是标签）—— 按命令和注释内容搜索。输入 `?` 时显示带提示的标签列表（命令数 + 注释）：字母用于过滤，`Tab`/`Enter` 插入 `?tag`，**点击某行**立即执行查询 | `?deploy`、`?wide` |
| `!tag[tid]` / `!N` | 把命令插入输入行（不运行） | `!deploy[1]` |
| `!! …` | 在输入行中组装字符串 | `!! deploy[1] && start[1]` |
| `:` | 应用命令 | `:q`、`:cd`、`:fm`、`:term`、`:session`、`:new`、`:scope`、`:send`、`:welcome`、`:backup`、`:screensaver`、`:r`、`:cmd`、`:kctx`、`:run`、`:playbook`、`:md`、`:rg`、`:lang`、`:relang`、`:?` |
| `\| cmd` | 管道聚焦（否则最后一个）块的 stdout（作为普通命令写入历史） | `\| grep error` |
| `\|@label cmd` | 从带 `:name label` 标记的块管道（来源**不会**重新运行） | `\|@buff awk '{print $2}'` |
| `\|@N cmd` | 从倒数第 N 个块管道，`0` = 最后一个 | `\|@1 jq .items` |
| `$OUT` | 按需取用：块的最后一行非空行（不存储） | `echo Hello, $OUT` |
| `$VAR=val` | 局部变量（写入 `.bashrc_term_<instance>`） | `$EDITOR=nvim` |
| `$$VAR=val` | 秘密变量：输入和输出都会遮蔽（`****`），文件 `secrets_<instance>.json`（0600）；在 `:send` 中以**名称**传输，而值进入目标的存储 | `$$TOKEN=…` → `curl -H "Bearer $TOKEN"` |
| `$VAR=@key` / `$$VAR=@key` | 从块输出取值：第一个 token 为 `key` 的行（`@last` —— 最后一行） | `vault read …` → `$$VAULT_TOKEN=@token` |
| `$DBFILE` | 由应用设置：它打开的 SQLite 库文件（数据目录 + `database_tags_file`）；`sqlite` 手册用它工作。`.bashrc_term` 中的值优先 | `sqlite3 $DBFILE ".tables"` |

### 秘密变量（`$$VAR=value`）

令牌、密码和密钥可以保存在 TUI 中，而不显示在屏幕上：

```text
$$TOKEN=...        # 设置秘密（输入时值会被隐藏）
$$TOKEN            # 状态：is set (value hidden) / is not set
$$TOKEN-           # 删除
curl -H "Bearer $TOKEN" https://api.example   # 普通的 $TOKEN 替换
```

- **输入。**从值的第一个字符起，输入行被遮蔽；秘密名称显示在副标题中（`Secret $TOKEN: value hidden`）。
- **存储（仅会话）。** `secrets_<instance>.json`（权限 `0600`）在设置时创建，并在退出应用时**删除**——值不会在重启后保留。不会写入 `.bashrc_term`、`history_*.txt` 和 playbook 日志；已存在的文件会在启动时、以及通过 `:env` 和 `:session` 重新读取。
- **输出。** 日志中值显示为 `****`：块头部、显示的 stdout/stderr、`:o` 以及 `TTY: …` 行。遮蔽在**写入输出时就冻结**（用当时仍有效的秘密），因此 `$$NAME-`、重定义、`:env` 或 `:session` 都不会在重新渲染时（space/←→、F2、F8、`:/` 搜索、`:w`）泄露已显示的内容；`:o` 保存的已经是遮蔽过的输出。同时 `raw_stdout` 是真实的——`|`、`$OUT` 和 `F3` 操作真实数据。
- **环境与会话。** `.bashrc_term*` 和 `:env` 不能替换秘密的值（来自存储的名称会被跳过）；退出时只清理自己的 `secrets_<instance>.json*` —— 相邻会话不会丢失自己的值。
- **LLM。** 秘密不会发送到 `:llm`：消息中的值（包括通过 `$OUT` / `$BLOCK` / `@文件` 进入的值）在发送前会被替换为 `****`，块头部显示 `secrets: hidden`。
- **从输出中捕获。** `$VAR=@key` / `$$VAR=@key` 从聚焦（或最后一个）已完成的块中取值：第一个 token 等于 `key` 的那一行——对 `vault read` / `vault write` 的表格（`Key  Value`）很方便；`@last` —— 最后一行非空行（例如 `| jq -r .field` 之后）。示例 —— `vapprole` 剧本（[`docs/SEED_VAULT_COMMANDS.md`](../../docs/SEED_VAULT_COMMANDS.md)）。
- **插入秘密时的剪贴板。** `settings.yml` 中的 `clear_clipboard_after_secret: true` —— 把值插入 `$$NAME=…` 行之后，CLIPBOARD/PRIMARY/内部缓冲区会被清空（默认 `false`；普通插入不会动缓冲区；某些剪贴板管理器可能仍会保留历史）。开启该键时，`:cmd` 也不会把含秘密值的命令放入剪贴板——日志中会给出说明。

限制（有意为之）：整行输入都会被遮蔽（名称也一样——它在副标题中可见）；在交互式 `> cmd` 中，只要 TUI 处于暂停状态，真实终端会显示该值；以 `$$` 开头的行始终被视为秘密；**由人主动请求的明确例外** —— `F3`、`:log`/F7（真实输出，副标题显示 `secrets visible`）和 `:cmd show`（打印具体化后的命令）会给出真实数据。

**计算器（无前缀）：** 以数字（或 `(` / `-`）开头且能整体解析为算术或单位换算的行会在本地计算——不会启动 shell，结果以标题为 `calc:` 的块出现。其余的行（`7z …`、`(cd … && …)`、`-la`、`2>/dev/null …`）仍然交给 shell——其中含有无法按算术解析的词。TUI 中的完整帮助：`:? calc`。

- 算术：`+ - * / ^ ( )` —— `1024*3`、`(2+3)*4`、`2^10`、`-5 + 8`
- 百分比：`512Mi + 20% in Gi`（增加 20%）、`512Mi - 15%`、`512Mi * 20%`（占比）、`2 + 10%`
- `of` —— 值的占比：`20% of 512Mi` → `102.4Mi`、`1/3 of 1Gi`、`20% of (512Mi + 1Gi)`；等同于乘法（`512Mi * 20%`）
- 内存：`B`；`K/M/G/T` = `KB/MB/GB/TB`（×1000）；`Ki/Mi/Gi/Ti` = `KiB/MiB/GiB/TiB`（×1024）；k8s 风格可连写：`512Mi`、`1.5 Gi`
- CPU：`m` —— 毫核，`cores`；`500m in cores` → `0.5 cores`、`0.5 in m` → `500m`
- `1Gi/512Mi` → `2`（能容纳几次）；`524288 in Mi` → `0.5Mi`；资源求和：`512Mi + 1Gi + 256Mi in Mi`
- IP 子网（与 jodies.de/ipcalc 一致）：`192.168.1.0/24`、`10.1.2.3/255.255.255.0`、裸 `8.8.8.8`（默认按类别掩码）—— 地址、掩码（=N）、wildcard、网络/前缀、主机范围、broadcast、主机数、类别/RFC1918 以及二进制形式；反向问题 —— `300 hosts` → `/23`（容纳 N 台主机的最小前缀）

`#name--` 隐藏手册的所有标签（`linux`、`k8s`、`git` 和 ops：`ansible`、`helm`、…）。`#name!!` 恢复它们。在 `??` / `?` 中，被隐藏的标签显示在 Hidden 块里；在 `!` 自动提示和按命令文本的补全中没有它们。`#tag-` 仍然只隐藏一个标签。

`!` 和 `!!` 把文本插入输入行。运行则另按 Enter。在 `??` 中点击标签会把 `!tag ` / `!tag[tid] ` 插入**光标位置**（不会覆盖整行；可以连续点击多个标签）。**Ctrl+点击**或**双击** `!tag[tid]` —— 插入并立即执行：等同于输入链接后连按两次 Enter（链接展开为命令并运行）。不带 tid 的链接（`!tag `）没什么可执行——它只会被插入。需要 `terminal_mouse: true`。

带 `$1` / `$2` / `$@` 的别名会代入参数（`alias klogin="tsh kube login $1"` → `klogin cluster` 变成 `tsh kube login cluster`）。没有 `$n` 时，行中剩余部分仍会追加到别名主体之后。参数在第一个 shell 操作符处结束，而操作符本身仍是操作符：`klogin prod || kubectl config use-context prod` → `tsh kube login prod || kubectl config use-context prod`、`kget pod | grep api` → `kubectl -n $NS get pod | grep api`（以前 `||` / `|` / `2>&1` 会作为 `'||'` 之类的参数被带走）。

### 应用命令（`:`）

- `:q` —— 退出
- `:w file` —— 把输出写入文件
- `:h [N]` —— `history_<instance>.txt` 的最后 N 行显示为一个块（默认值来自 `settings.yml`；这些行可以用逐行模式取用）。文件中只有被保存的内容：`:` 命令（`history_queries` 名单之外的）、`#tag` 保存、`?`/`!` 行和 `$VAR=…` 都不会写入其中；而按 ↑ 则会翻遍本会话中**所有**输入过的内容（`:` 命令等来自会话记录），按输入顺序——最后输入的行最先返回
- `:h /text` —— 在提示中搜索该文件（不区分大小写，最新的在前，相同行只出现一次）。Esc+Enter —— 用同样的搜索写入日志
- `:h compact` —— 压缩旧历史（去重为唯一行）；不动最后 `history_keep` 行。启动时——仅在文件长度超过 `2 × history_keep` 时才执行
- `:h import [shell]` —— 把用户的 shell 历史追加到 `history_<instance>.txt`：会查找 `~/.bash_history`、`~/.zsh_history`、fish（`~/.local/share/fish/fish_history`）、ksh（`~/.sh_history`；`sh` 是同一个文件）、nushell（系统数据目录：`Application Support` / `%APPDATA%`）、PowerShell PSReadLine（Windows 上是 `%APPDATA%\Microsoft\…`，Linux/macOS 上是 XDG 路径），以及 **atuin** 数据库（`history.db`：atuin 数据目录 —— 所有系统都是 `~/.local/share/atuin`，可用 `$ATUIN_DB_PATH` 或 `config.toml` 中的 `db_path`/`data_dir` 覆盖；已软删除的记录不会导入）；已设置的 `$HISTFILE` 排在最前（格式按其内容判断，即使文件名不常见）。每个文件取最后 5000 行（大文件只读尾部）或 atuin 的 5000 条命令，已有的行不会重复（再次导入不会添加任何内容），不会执行任何命令。不带名称——所有找到的来源，`:h import zsh` —— 只导入它，`:h import atuin` —— 只导入 atuin 数据库。失败会明确显示：文件被占用、写入错误和无法读取的来源都会被报告，而不会看起来像「新增 0 行」。导入后 ↑、`:h /text` 和提示会立即看到这些命令
- `:c` —— 清空日志中的块
- `:json` / `:json <file>` —— JSON viewer（最后一个块或文件）
- `:md <file.md>[#L<n>]` —— 带格式的 Markdown 手册（在欢迎信息中点击名称；Esc 关闭）。也接受路径——绝对路径或相对于 `md_dir`/cwd 的路径，`:rg` 和 Obsidian vault 中的文件就是这样打开的；`#L<n>` 会直接打开到第 n 行（如同 GitHub）。`:md` 会写入历史（↑ / `:h`）。长度超过 `md_render_lines`（默认 1000 行）的文件会在 Line-API 查看器中以源码打开——速度快，支持 `/` 搜索和 `#L` 跳转（对超大文件做格式化渲染要耗费数十秒）。`y` 会把文件的完整路径复制到剪贴板——在格式化视图中还可以点击头部中的名称（raw 视图下只有 `y`）。不是 markdown 的文件（docx、xlsx、pptx、doc/ppt/xls、rtf、epub、odt、pdf）？`:md` 会转换它：转换器取自 `settings.yml` 的 `md_converter`，否则用第一个找到的（`anydoc` → `markitdown` → `pandoc`；推荐 `pip install firecrawl-anydoc` —— 无依赖、PDF 本地解析、也支持旧版 `.doc`/`.xls`）。转换结果缓存在数据目录的 `mdcache/`，所以查看器里的 `#L<n>`、`/` 搜索和 `y` 依然可用。没有转换器时会提示安装。**扫描版 PDF 在本地识别**：没有文本层时 `:md` 用 `ocrmypdf` 加上文本层（apt/dnf/apk/brew install ocrmypdf，它需要 tesseract）—— 不会发送到任何地方；settings.yml 中的 `md_ocr` 可关闭（`off`）或指定自定义命令（`ocrmypdf -l rus+eng`），没有引擎时仍显示明确的「需要 OCR」提示。文件是文本还是文档按内容判断，而不是按扩展名
- `:rg <模式> [目录]` —— 搜索 markdown 文件：如果安装了 ripgrep 就用它（否则用内置扫描器 + 安装提示）。模式是正则表达式，「智能大小写」（不含大写字母时大小写不敏感）。搜索基准是 `[目录]`，否则用 `settings.yml` 中的 `md_dir`，再否则用 cwd。结果是带可点击 `路径:行号` 的片段（在内置 md 查看器中直接打开到匹配行）；`:rg <N>` 在同一处打开第 N 个结果（从 1 开始）。会跳过隐藏和辅助目录（`.git`、`.obsidian`、`node_modules`、…）；`:rg` 会写入历史（↑ / `:h`）
- `:llm [<提供方>] <消息>` —— 按 `llm_providers.yml` 向 LLM 发请求（秘密只来自环境：`$DEEPSEEK_API_KEY`）。`@文件` 会嵌入文本，`$OUT` / `$BLOCK` —— 块的输出，`history_turns: N` 保持对话上下文。回答以格式化 markdown 呈现（`llm_render_markdown: true`；F6 —— 临时关闭）；供 F3/`|`/`$BLOCK`/`:w` 使用的纯文本副本不受此影响
- `:llm offline <消息>` / `:llm ask offline <任务>` —— 内置离线提供方（`mock: true`）：无需网络和密钥即可回答；在任何配置中都存在，直到被自定义的 `offline:` 覆盖（用于演示、验证接线）
- `:llm ask [<提供方>] <任务>` —— 会往任务上附加应用速查和标签库摘要；回答给出可直接使用的链接 `!tag[tid]`（可点击，仅限已存在的）。提供方中的 `app_context` 键会为普通 `:llm` 开启同样的功能
- `:llm reset [<提供方>|*]` —— 清除对话上下文（会话记忆）
- `:cht <请求>` —— 在日志中显示 cheat.sh (cht.sh) 速查：`:cht tar`、`:cht python read file`（空格 → `+`）、`:cht ~snapshot`（搜索）、`:cht go/:learn` / `:list`（特殊页面）。通过 `?` 传选项：`Q` —— 不带注释，`T` —— 不带颜色（默认 `?T`）。URL/选项 —— `settings.yml` 中的 `cheat_sh_url` / `cheat_sh_options`；输出是普通块（$OUT、`|`、F3、F7、搜索）
- `:ed [<文件>|$OUT|$BLOCK]` —— 外部编辑器（`settings.yml` 中的 `editor:`，否则 `$VISUAL`/`$EDITOR`）；TUI 暂停。路径中会展开 `$VAR`/`$OUT`（`:ed $TMPDIR/pod-$OUT.json`）；单行结果会改写输入行，多行结果保留为文件
- `:o [N]` —— 本会话最近 N 次输出（默认 5）；`:o /text` —— 对它们做 grep（不受 `:c` 影响）；`:o clear` —— 遗忘
- `:stats` —— 库摘要：按标签统计运行、前 10、「never run」
- `:mv <tag>[<tid>] <dst>` —— 把命令移到另一个标签；`:mv <tag> <dst>` —— 重命名标签（注释随之迁移）
- `:diff` —— 聚焦块与前一个块的 stdout unified diff
- `:kill [all]` —— 停止正在运行的命令；`:watch <秒> <命令>` —— 在同一个块中重复它（`:watch stop`）
- `:alias <tag> [file.sh]` / `:alias * [library.sh]` —— 把命令导出为 bash 函数 `tag_tid()`
- `:i …` —— Kubernetes Ingress Analyzer（`:i` 不带参数时显示帮助）
- `:cd [path]` —— 显示 / 切换 shell 命令的 cwd（`cd path` 也一样）。**只含路径的一行**等同于不带 `cd` 的 `cd`：`~/src`、`../lib`、`/var/log`、`docs/`；`-` 等同于 `cd -`（回到上一个目录；没有时给出明确的 `cd: OLDPWD not set`）。变量代入后也同样有效 —— `$PROJ`。规则不制造意外：`$PATH` 中的名称仍是命令（即使旁边有同名目录，`test`、`time`、`ls` 仍会执行），而不是目录的路径照旧交给 shell —— `./build.sh` 仍然**执行**脚本，而不是进入。退出时终端会收到窗口的当前目录（OSC 7 —— 与 shell 的做法相同：新标签页/新窗口会在该目录打开）；若目录确实改变，stderr 会打印现成的 `cd '…'` —— 父 shell 不会自动跟随子进程。用 shell 包装函数可自动完成（如同 ranger/nnn）：

```bash
idvjpy() {                     # shell 的 cwd 跟随应用
  local f; f=$(mktemp)
  IDVJPY_CWD_FILE=$f command idvjpy "$@"   # pip 包；从克隆运行 —— python3 ~/WibeCoding/Idivjopy/app.py
  cd "$(cat "$f")" 2>/dev/null
  command rm -f "$f"          # command —— 避免 alias/函数 rm 干扰清理
}
```

`./setup.sh --shell-helper` 会自动装好：代码块写入当前 shell 的 rc（`zsh` → `~/.zshrc`，否则 `~/.bashrc`；可用 `$IDVJPY_RC` 指定），原有内容保留，旧文件备份为 `<rc>.idvjpy.bak`，再次运行只更新标记之间的自己的代码块。`command idvjpy` 避免函数调用自身；没有 pip 包时，代码块里写入本克隆 `app.py` 的绝对路径。标签库、历史和 `.bashrc_term*` 仍留在数据目录中（而不是新的 cwd —— 见「文件和设置」）；不会在新目录中创建空的 `mytags.db`。当前目录始终可见：在输入行左侧以灰色显示（`~/项目 ❯`，点击路径可把焦点返回输入行）；`~` 表示主目录，过长的路径会截取尾部（不超过窗口宽度的三分之一；完整路径见块标题）。**在 git 仓库内，路径旁会显示分支**（`~/项目 (main) ❯`；分离 HEAD 显示短 SHA，`(@1a2b3c4)`），过长的分支名截取尾部。它直接从 `.git/HEAD` 读取，不调用 `git`（worktree/submodule 的 `.git` 文件同样支持），并在每条命令后更新 —— `git switch` 不改变目录也能换分支。关闭：`git_prompt: false`。
- `:fm [path]` —— 在新窗口中打开系统文件管理器（cwd 或路径）。Linux：`xdg-open`；macOS：`open`；Windows：`explorer`。自定义：`$FILEMAN`
- `:term [path]` —— 在新窗口中打开系统终端。Linux：`xdg-terminal-exec` / `gnome-terminal` / …；macOS：Terminal.app；Windows：`wt` 或 `cmd`。自定义：`$TERMINAL`。**用标签页代替窗口** —— `settings.yml` 中的 `term_open: tab`（或 `$IDVJPY_TERM_OPEN=tab`）：`gnome-terminal --tab`、`konsole --new-tab`、`kgx`/`xfce4-terminal`/`mate-terminal`；不支持标签页的终端（`alacritty`、`xterm`、`kitty`——后者的标签页只能通过其服务端）会给出明确错误，而不是默默打开窗口。该模式对 `:term`、`:new`、`& cmd` 共通
- `:env` —— 在已运行的应用中重新读取 `.bashrc_term*`（以及 `~/.bashrc` 的别名）。在 `> cmd` 之后，**同一个** bash 的导出会被自动采纳（嵌套的 `> bash` 里面再 `export` —— 则不会）
- `:session` —— 当前实例（历史 + `.bashrc_term_*`）。`:session NAME` —— 切换或创建（标签数据库是共用的）。当前会话名称可在应用头部和终端窗口/标签标题中看到（`IDvjPy_term · NAME`，有命令运行时为 `— N running`）
- `:new [NAME|-] [DIR]`（以及 `:session new …`）—— 在独立终端中启动一个新的应用窗口：自己的会话（`.bashrc_term_<NAME>` / `history_<NAME>.txt`），共用的 data 目录和标签数据库。`DIR` —— 新会话的工作目录（默认是 data 目录）；名称为 `-`/空时自动取 `sN` —— **正在运行的窗口之间**最小的空闲编号（data 目录中的 `session_<名称>.pid` 注册表，见 `src/session_registry.py`）：已关闭会话的文件不会占用名称，而 `s2` 关闭后该名称又空闲了。`$$` 秘密不会迁移。页脚中的 `New session` 按钮 / `Ctrl+N`。终端 —— `$TERMINAL`（例如 `kitty` / `alacritty -e`），否则从系统终端中选择；启动 —— `$IDVJPY_LAUNCH`
- `:send <会话|*> <命令>` —— 把命令转发到另一个会话（`:new` 窗口）：插入目标会话的输入行，在那里另按 Enter 运行。`:send!` —— 立即执行（`:send! <会话|*> <命令>`）。`*` —— 发给除自己以外的所有会话。命令在发送方就完成物化（`$VAR`/`$OUT`、别名，以及 `|@label`/`|@N` → `<来源> | <命令>`）；`$$` 秘密以**名称**传输（`$TOKEN`），而目标没有的值会写入它的秘密存储（`secrets_<会话>.json`，0600，退出时清理）——因此命令在那里确实能执行，而信箱、日志和历史中都不会有该值；目标已有的值不会被覆盖（发送方日志中能看到什么被传递了、什么留在了目标那边）。缓冲区标记在每个会话中各自独立，因此 `|@…` 会展开为完整调用（来源会在目标会话中重新执行）；发送方没有该标记——命令不会发送。交换通过 data 目录中的 `inbox_<会话>.jsonl`（0600）进行；发给未启动会话的消息会等它启动。即使正在输入文本时收到也会追加到末尾，不会覆盖。在 `:send ` 之后按 Tab 会提示会话名称（`*` —— 发给其余所有会话；当前会话有标记）。`:send` / `:send!` 会写入 `history_*.txt`（可用 ↑ 重复、`:h /` 搜索），但不会作为提示给出
- `:scope [add|rm|clear] …` —— **本窗口**的标签范围：`:scope add git` 在列表中只保留 git 手册，`:scope rm k8s` —— 隐藏 k8s，`:scope clear`（或 `:scope all`）—— 重新显示全部；不带参数时显示当前状态。它过滤**列表与提示**（`?`、`??`、`?text`、`!`/Tab 补全、屏保滚动条）；显式引用与命令（`?tag`、`!tag[tid]`、`:run`、`:stats`、`:export`、`:alias`、`:send`）不看过滤器 —— 已保存的链条和其他窗口的引用不会被破坏。名称可以是手册组（`linux`、`k8s`、`git` …）或单个标签；未知名称会明确报错并列出可用的组。按会话保存：数据目录中的 `scope_<会话>.json`（不会写入 SQLite，也不会随 `:export`/`:backup` 一起走）。窗口标题带有标记（`IDvjPy_term · git · only git`）。详见 `:? tags`
- `:welcome` —— 如同空数据库时的种子目录（点击 `--seed` / `.md`）。数据库非空时启动会显示**分区**块，列出各 handbook 的现成标签（`linux`、`k8s`、`git`、ops、`自有`）
- `:backup` —— 把 SQLite 快照保存到 `backups/`（就像 `--seed` 之前那样）。空的数据库不复制。恢复：把文件复制覆盖到工作数据库上。
- `:screensaver` —— 立即显示屏保：**「矩阵雨」**（默认，`screensaver_matrix: true`）或 DevOps 星空（`screensaver_matrix: false`）。雨——下落的一列列字符（头部明亮、尾部渐暗；节奏缓慢均匀，20 fps 下每秒 1.8–6 行，`src/screensaver.py` 中的 `TICK_SECONDS` / `MATRIX_*_SPEED`）；在星空中，星星飞向观众，越近的越大，写着 `k8s` / `git` / `!!`，还有随行的实时时钟（`15:35:42`）和日期（`2026-08-26`）。画布可临时切换：`:screensaver matrix` / `:screensaver stars`。两种画布共有：顶部是横贯全宽的亮绿色条带，显示数据库中的命令（`!tag[tid]  cmd`）；左下是命令速查（从左向右打印，距边缘有缩进）；右下是 load 1/5/15 和 RAM（每秒从 `/proc` 读取），距右角有同样的缩进；窗口较窄时 load 可能压到速查上。被隐藏的手册（`#name--`）不会显示。任何按键、点击、滚轮滚动或鼠标移动都会关闭/重置空闲状态（不会进入输入行）。从其他会话发来的命令（`:send`）也会解除屏保——否则日志会一直关着。超时：`settings.yml` 中的 `screensaver_idle`（秒，`0` = 关闭）。`:screensaver 0` / `:screensaver 120` —— 仅对本会话。TUI 休眠期间（真正的 TTY：`> cmd`、Ctrl+O、`:ed`）不会打开屏保，返回后空闲时间重新计时——这样 `> vim` 就不会再遇到屏保了。`screensaver_stars: false` —— 星空不显示飞舞的尘埃/令牌（不影响矩阵画布）。空闲如同 Norton Commander：星星飞向观众；越近的写着 `k8s` / `git` / `!!`。随行的还有实时时钟（`15:35:42`）和日期（`2026-08-26`）。顶部是横贯全宽的亮绿色条带，显示数据库中的命令（`!tag[tid]  cmd`）。左下是命令速查（从左向右打印，距边缘缩进一如从前）；右下是 load 1/5/15 和 RAM（每秒从 `/proc` 读取），距右角有同样的缩进；窗口较窄时 load 可能压到速查上。被隐藏的手册（`#name--`）不会显示。任何按键、点击、滚轮滚动或鼠标移动都会关闭/重置空闲状态（不会进入输入行）。从其他会话发来的命令（`:send`）也会解除屏保——否则日志会一直关着。超时：`settings.yml` 中的 `screensaver_idle`（秒，`0` = 关闭）。`:screensaver 0` / `:screensaver 120` —— 仅对本会话。`screensaver_stars: false` —— 没有飞舞的尘埃/令牌（时钟、条带和 load 仍保留）。
- `:r` —— 聚焦块的命令放入输入行；`:r N` —— 倒数 N 个块（0 = 最后一个）
- `:cmd [N] [show]` —— 用当前 `$VAR` 值（含秘密）物化块命令 → 放入剪贴板；`show` 还会打印出来（秘密会变得可见）
- `:log [N]`（F7）—— 在可滚动的 **Line-API** 查看器中显示块的完整输出（不再截断到 300 行）：行用 ↑/↓，翻页用 PgUp/PgDn，Esc/q；文本搜索 —— `/`（Enter —— 向前，`n`/`N` —— 下一个/上一个匹配，Esc —— 关闭搜索框），匹配行整行高亮（强调色背景 + bold）；`f` —— 只保留有匹配的行（再次 `f` 或 Esc 恢复全部输出，副标题中的行号会恢复为原始行号），此时用 ↑/↓ 在匹配之间移动；Enter 和 Ctrl+C 把选中的（高亮的）行复制到剪贴板 —— 如同 F2 逐行模式中的 Enter（没有搜索时无选中项：查看器会明确说明，而不是复制第一行；在搜索框中 Ctrl+C 复制框内文本）。`N` —— 倒数第几个块（0 = 聚焦/最后一个）。行是真实的（如同 F3），如有 `STDERR` 也会包含。`y` 会复制来源文件的路径（raw 视图 `:md`）；对块输出则明确显示 `No file path to copy`
- `:name [<label>|<label>-|-]` —— 缓冲区标记：为聚焦（否则最后一个已完成）块打标记，以便从中管道而无需重新运行来源（`:name buff` → `|@buff awk '{...}'`）。不带参数时列出标记，`<label>-` —— 取消一个，`-` —— 全部。也可通过 `F8` 打开对话框。标记显示在块的头部（`[buff]`）；写入历史时管道记录为完整调用 `<来源> | <命令>`
- `:/text` / `:g` / `:n` / `:N` —— 按日志行搜索（在块上按 `/` 会打开 `:/`；`n`/`N` —— 下一个 / 上一个）
- `:export tag [file.json]` / `:import file.json` —— 单个标签与 JSON 互转（导入总是分配新的 `tid`；格式与 CLI 共用，`src/db_transfer.py`）；`:export * [library.md]` —— 整个库导出为 Markdown 目录，`:export * library.json` —— 整个库的规范 JSON（`tag_filter` 为空 —— 这正是 `library_url` 需要的文件；等同于不带 `--tag` 的 `backup_db.py export`）
- `:import <https://…>` —— 按链接获取共享库：日志中先显示**变更计划**，并把现成的 `:import <url> --yes` 放入输入行——第二次 Enter 才开始导入（没有它则不会写入任何内容）。`--dry` —— 只显示计划，`--yes` —— 不再确认，`--insecure` —— 允许 `http://`（默认仅 `https://`），不带参数的 `:import` 使用 `settings.yml` 中的 `library_url`。上限 2 MB、超时 10 秒、带登录的代理与 `:update` 相同：`$PROXY_USER` / `$PROXY_PASS`。payload 含仍有效的 `$$` 密钥值会被拒绝；带 `run:auto` 指令的行会在计划中单独提示。完整参考 —— `:? import`

**导出/导入：什么场景用什么**（格式只有一份实现 —— `src/db_transfer.py`，CLI 只是薄壳）：

| 任务 | TUI | CLI（`python3 backup_db.py …`） |
|------|-----|--------------------------------|
| 把标签搬到另一个实例/机器 | `:export tag file.json`，在那里 `:import file.json` | `export` / `import [--mode merge\|replace] [--keep-tids]` |
| 按链接获取共享库 | `:import https://… --dry`，然后 `:import <url> --yes`（不带参数时用 `settings.yml` 的 `library_url`） | — |
| 发布自己的库给团队 | `:export * library.json`（文件写到应用的 cwd），放到 https 主机上，并把链接写进 `library_url` | `export library.json` —— 文件写入 `backups/`；`backup_db.py` 启动脚本位于仓库目录，因此在数据目录下请用路径调用：`python3 /path/to/IDvjPy/backup_db.py …` |
| 数据库的精确快照（回滚到「原样」） | `:backup` | `backup`（SQLite 快照 + JSON + CSV），用 `restore <文件>` 还原 |
| 在表格里改命令和注释 | — | `export-csv` / `import-csv`（按 `tid` 定位），`export-tags-csv` / `import-tags-csv` |
| 不开 TUI 看标签 | `:stats`、`??` | `list [--show-comments]` |
| 库目录导出为 Markdown | `:export * library.md` | — |
| 命令导出为 bash 函数 | `:alias tag\|* [file.sh]` | — |

JSON 用于搬运和合并（**绝不用**文件里的全局 `id`：以前外来的 `id` 可能覆盖另一行；默认每行都会拿到新的 `tid`）。**精确快照**只有 SQLite 副本。详见 [`backup_db.md`](../../backup_db.md)。

两种文件要分清：单标签文件（带 `tag_filter`）是「添加」（新的 `tid`，不覆盖任何内容），整库文件（无 `tag_filter`——由 `backup_db.py export` 和 `backup` 生成）是「更新」：已占用的 `(标签, tid)` 对会被跳过（`skip_existing`），空闲的则加入。外部导入本身不会执行任何命令，但 `:run <标签>` 会无确认地执行 `auto` 步骤——所以计划会提示 `run:` 指令。下载在后台线程中完成（不阻塞 UI），且只允许 `https://`：内容会直接进入标签库。
- `:playbook [file.yml]` —— 把本会话的命令（Enter）记录为供 `--demo` / `:run` 使用的 YAML（默认 `playbook.yml`）。`:playbook -` —— 在日志中预览；`:playbook clear` —— 遗忘已记录的内容。按键（Tab/F5）和鼠标不会被记录。YAML 中：`loop: true` / `loop: N` —— 循环步骤（Esc —— 停止）；见 [DEMO.md](../../DEMO.md)。
- `:run <tag|文件.yml> [--step] [--dry]` —— 运行命令链（runbook）：`auto` 步骤依次执行并等待完成，`manual` 把命令插入输入行并等待 Enter（可以修改），`prompt` 等待你输入的字符串。某步出错会停止运行，`Esc` / `:run stop` 也会。标签的步骤模式由注释中的指令决定（`run:manual`、`run:prompt`、`run:pause=2`、`run:continue`）；如果标签中没有任何这类指令，计划会警告：所有步骤都将以 `auto` 执行（过期的种子或 v1.124 之前保存的自有标签就是这样）。`--step` —— 每步都等 Enter，`--dry` —— 只显示计划。完整帮助 —— `:? run`，现成命令链 —— `:run vapprole`。YAML 的相对路径按进程的 cwd 计算（用别名从 `~` 启动时则从 `~` 算）：命令链更稳妥的做法是保存在标签里——数据库位于数据目录中
- `:update` —— 把 `VERSION` 与 GitHub [`webxed/IDvjPy`](https://github.com/webxed/IDvjPy) `main` 比较。启动时如果 `check_updates: true` 也会做同样的事（仅当 GitHub 上更新时才写入日志）。带认证的代理：`.bashrc_term` 中的 `$PROXY_USER` / `$PROXY_PASS`（外加 `HTTPS_PROXY` / `HTTP_PROXY`）。
- `:theme [name]` —— TUI 主题（`dark` / `light` / `nord` / `matrix` / …）；会写入 `settings.yml`。按键 `d` —— dark/light。应用自带主题 —— `matrix`：近乎黑底上的绿色荧光，如同屏保（输入框、提示和帮助的边框也会变绿）
- `:lang [code]` —— 界面语言：不带参数时显示当前语言和可用列表，`:lang ru` —— 选择并保存（`settings.yml` 中的 `language` 键），`:lang auto` —— 跟随 `$LANG`/`$LC_ALL`。临时指定：`--lang` / `$IDVJPY_LANG`。随附语言：`en`、`ru`、`zh`。文本位于 `src/locales/`：目录 `src/locales/<lang>.yml` 加上分片 `src/locales/<lang>/*.yml`（`screensaver`、`seed`），`:?` 帮助则是文件 `src/locales/help/<lang>/*.txt`（`en` —— 唯一事实来源，缺失的键回退到它）；会切换消息、`:` 命令提示、`:welcome` 目录、屏保文本和 `:?` 帮助。新语言应用于切换之后打印的文本（已显示的块不会重绘）。命令、标签名、设置键和文件名不翻译（口号「Define your variables…」和 logo 也是：它们是品牌）。同一个 `language` 键还决定演示游走的文本层（`src/demos/text/<lang>/`）、种子注释（`src/seed_text/<lang>/` —— 因此 `--seed` 会用该语言写入说明）和手册目录（`docs/<lang>/`）
- `:relang [code]` —— 把**已播种**库的注释（数据库中的标签说明和命令提示）翻译为另一种语言，而无需重新 `--seed`：不带参数时显示帮助，`:relang ru` —— 翻译，`:relang auto` —— 按 `$LANG`。只处理种子的规范标签和命令；你自己的标签、命令以及**手工修改过**的注释保持不变。写入前会先把数据库快照保存到 `backups/`。在终端中也是如此：`python3 src/relang.py --lang ru [--db …]`
- 聚焦块的高亮很柔和：在块背景上叠加主题主色的 12%（以前实心的 `$primary-darken-1` 很刺眼，尤其是在很大的 `:?` 上；相对块背景的亮度增量 65 → 25% 时的 19 → 约 9）；在任何主题中都有效
- `:kctx` —— 集群日志（`kctx.json`）：集群列表；`:kctx <cluster>` —— 登录（`klogin <c>` 或 `kubectl config use-context <c>`）并显示以前用过的 `NS`/`POD`/… 集合（只有一个集合时立即应用：别无选择）；`:kctx N` —— 应用集合 N；`:kctx <cluster> N` —— 一行完成登录并应用。哪些变量算作日志 —— settings.yml 中的 `kctx_vars` 键
- `:?` —— TUI 内的这份帮助；`:? <主题>` —— 某组命令的详细说明（`:? llm`、`:? tags`、`:? calc`、`:? run`、`:? i`、`:? md`、`:? vars`、`:? kctx`、`:? send`、`:? session`；主题列表见帮助中的「帮助主题」一节以及 `:? ` 之后的提示）。未知主题会明确报错并列出主题；粘连写法 `:?calc` 会提示加空格

## 快捷键

| 按键 | 操作 |
|---------|----------|
| `Tab` | 从输入行跳到最后一个日志块（`:h`、`:?`、命令）；如果打开了提示列表——则应用候选项。当命令列表（`:`）打开时，`Tab` 插入 `:命令 `，而不是跳到日志 |
| `Esc` | 焦点回到输入行。在逐行模式下：先关闭该模式，再按 Esc 才回到输入行 |
| `↑` / `↓` | 在输入行中：会话记录（所有输入过的内容——`:` 命令、`?标签`、`!链接`、`#标签`、`$VAR=…`；`$$` 秘密除外）+ 过滤后的 `history_<instance>.txt`；顺序按输入先后，最后输入的行最先返回；已输入的文本会过滤匹配项；如果焦点在块上则滚动日志 |
| `PgUp` / `PgDn` | 将日志翻动一页；**可见**的块成为活动块（不会跳到它的开头）。从输入行——进入查看模式。只要视图被上移，新输出就追加到底部且**不会移动**视图和焦点（`:watch`、`:llm` 的回答、到来的 `:send`）；滚动到底部或按 Enter 时恢复跟随 |
| 点击块 | 聚焦该块且不滚动到开头（`terminal_mouse: true`）。空数据库中：点击 `--seed` —— 插入输入行；点击 `.md` —— 打开手册。在 `??` 中：点击标签会把 `!tag ` 插入光标位置（不覆盖整行）。在 `?` 提示列表中点击某行会插入 `?tag` 并立即执行查询 |
| `Ctrl+点击` / 双击 `!tag[tid]` | 插入链接并立即执行它——如同两次 Enter（展开为命令并运行）。不带 tid 的链接只会被插入；其他链接（`:` 命令、`.md`、`--seed`）不会执行 |
| 鼠标滚轮 | 滚动日志——每格 3 行（`:log`/F7 和 md 查看器中相同），阅读位置会被记住（见阅读模式）。方向键仍是一行一行 |
| 在日志上拖动鼠标 | 在应用内选择文本；松开按钮后所选内容立即进入缓冲区（CLIPBOARD/PRIMARY/OSC 52）。`Shift`+拖动——终端原生选择（如果你更喜欢它） |
| `Space` / `←` `→` | 折叠 / 展开块 |
| `F3` | 复制块的完整 stdout |
| `Ctrl+C` | 如果有鼠标选择——复制它；否则复制整行输入 / 整个日志块（如同 F3） |
| `F5` | 聚焦（或最后一个）块的 JSON viewer |
| `Ctrl+N` | 在新终端中打开新的应用窗口（独立会话）——等同于 `:new`；页脚中的 `New session` 按钮 |
| `Ctrl+O` | 显示应用下方的控制台（如同 Midnight Commander）：TUI 让到一边，可以看到真正的终端——来自 `>` 的命令输出（`htop`/`vim`/`less`）就留在那里的滚动缓冲中。返回——任意按键 |
| `F6` | 纯文本输出（不带 Rich 标记和 ANSI 颜色，更方便用鼠标选择） |
| `F7` | 在 Line-API 查看器中显示块的完整输出——等同于 `:log`（内部搜索——`/`、`n`/`N`、`f` —— 仅显示有匹配的行） |
| `F8` | 块标记对话框（`:name`）：输入标记，Enter —— 保存，留空 —— 取消标记，Esc —— 取消；之后用 `\|@标记 命令` |
| `F2` | 块中的逐行模式 |
| `Shift+Insert` / `Ctrl+V` | 插入到输入行（不会覆写已输入的内容）。在逐行模式下 `Ctrl+V` 会追加当前行。粘贴文本中的换行会变成空格（输入行只有一行），长行在输入行下方的灰色预览中完整可见 |
| 右键点击 | 将剪贴板内容粘贴到输入行 —— 即使焦点在日志或提示列表中（无需先把光标放进输入行，焦点也不会跳走）。右键不会触发链接（`--seed`、`.md`、`:命令`），也不会覆盖选区：用鼠标选中的文本在松开时已进入剪贴板，右键粘贴的正是它 |
| `Ctrl+D` | 清空整行输入 |
| `Ctrl+W` / `Ctrl+Backspace` | 在输入行中：删除光标左侧的词（便于清理粘贴进来的输出，例如来自 `kubectl` 的）。`Ctrl+Backspace` 只在终端把它作为单独按键发送时有效；通用的做法是 `Ctrl+W` |
| `Ctrl+F` / `Ctrl+Delete` | 在输入行中：删除光标右侧的词 |
| `Ctrl+←` / `Ctrl+→` | 在输入行中：光标向左 / 向右移动一个词 |
| `Ctrl+Z` | 在输入行中：撤销上一次改动（输入 / 删除 / 删词 / 粘贴）。发送命令后以及按 `Ctrl+D` 后栈会被重置 |
| `d` | 深色 / 浅色主题（`textual-dark` / `textual-light`），保存在 `settings.yml` 中。当焦点在输入行时，`d` 会作为字母输入；要切换主题：焦点放在日志上或使用 `:theme` |

### 逐行模式（聚焦的块）

默认关闭。开启方式：先 `Tab`/`PgUp` 到块上，然后 `Enter` 或 `F2`。

| 按键 | 操作 |
|---------|----------|
| `↑` / `↓` | 上一行 / 下一行（到达块边缘时——重新变为滚动日志） |
| `Home` / `End` | 第一行 / 最后一行 |
| `Enter` | 复制该行（不含行尾空格）并转到输入行，光标在末尾 |
| `Shift+Enter` / `Ctrl+V` | 用空格把该行追加到输入行，并留在块中 |
| `Esc` / `F2` | 关闭该模式 |
| `/` | 开始搜索（输入行中为 `:/`） |
| `n` / `N` | 下一个 / 上一个匹配 |

如果 `Shift+Enter` 表现得像普通 Enter，说明终端无法区分这两个按键——请使用 **Ctrl+V**。当焦点在输入行时，`Ctrl+V` 仍然是从缓冲区粘贴。

### JSON viewer

- 在节点上按 `Enter`：关闭 viewer，设置 `$JSON`，复制到剪贴板，并在输入行留下草稿：`\| jq '.path'`（来自块）或 `jq '.path'`（来自文件）。
- 示例：`jq $JSON test.json`。
- 搜索：`/` 或顶部的输入框；`n` / `N` —— 下一个 / 上一个匹配。

## 补全

- 路径：`./` `../` `/` `~`，含 `/` 的 token，`cd`/`pushd`，或命令后非 flag 的参数。
- **Tab** 对路径只替换当前 token；来自历史/数据库的完整命令——替换整行。
- 带 `/` 的目录（`ls ~/`）—— 第一个候选项就是该目录本身；Enter 执行它，Tab 不会强制进入子路径。
- 整行精确匹配会隐藏列表，Enter 执行该命令。
- 文件提示描述的是行中**最后一个** token，因此当光标位于其他单词（修改命令名）时，它们既不显示也不会被应用 —— 否则 Enter 会把路径参数插入到第一个单词（`bar ~/f.txt` → `~/f.txt ~/f.txt`）。
- 来自数据库和历史的完整命令（`↺`）会替换**整行**，因此它们的位置在行尾：光标位于行中间时既不显示，Enter/Tab 也不会应用（中间的修改不会被覆盖）。`!tag` / `?tag` / `:` 提示基于光标所在的 token，行为不变。
- **行尾空格**（`ls` + 空格）：列表关闭，Enter 运行已输入的内容，而不是更长的候选项（`ls -la`）。要采用候选项——按不带末尾空格的 Tab。
- **`!file` / `!kube`**：输入 `!` 后立即显示标签列表（`[file, kube, log]`）。Tab 选择标签，然后选择命令：`<139> file[1]  ls -la`，插入输入行的是 `!file[1]`。组装 `#file !file[1] | !file[2]`，并在列表上方给出展开说明。
- **`?`**：输入 `?` 后——带提示的标签列表（`?vault  (2)  HashiCorp Vault`：命令数和标签注释），字母用于过滤，常用标签排在前面。`Tab`/`Enter` 插入 `?vault` 但不运行（运行——另按 Enter），**点击某行**会填入 `?vault` 并立即执行查询；只有 `?vault` 是链接，其余是普通文本。`??`（所有命令）不会打断列表，`?vault `（空格）会关闭它。

## 配置

模板 —— [`src/settings/<lang>.yml`](../../src/settings)（`en`、`ru`、`zh`；键和值相同，只有注释不同；会复制 `auto` 模式下所选语言的文件；个人的 `settings.yml` 不会进入 git）：

```yaml
max_lines: 100000
history_lines: 20
history_keep: 500            # 历史尾部作为记录；更早的不去重。0 = 不压缩。:h compact
history_completion: true     # 输入时来自 history_*.txt 的提示（包括 `@`/`>` 行）；false —— 仅 ↑ 和 :h /
history_forget_not_found: true  # 拼写错误（`command not found`，127）会从 history_*.txt 和 ↑ 列表中移除（错误仍留在日志中）；false —— 与其他命令一样保留
history_queries: [llm, cht, rg, md, run, send, send!]  # 这些 `:` 命令的调用——写入历史（↑/:h），但不作为提示；[] —— 不写入
md_dir: ""                   # `:rg` 的文档目录（例如 Obsidian vault）；留空 —— cwd
md_render_lines: 1000        # 格式化 `:md` 的阈值；更长则以 raw 视图在 Line-API 查看器中显示
md_converter: ""             # `:md` 的文档转换器（docx/pdf/…）；留空 —— 自动 anydoc → markitdown → pandoc
md_ocr: ""                   # 扫描版 PDF 的本地 OCR（ocrmypdf，需要 tesseract）；留空 —— 自动，off —— 关闭
database_tags_file: mytags.db
backup_dir: backups          # 数据库快照（:backup、--seed）
command_timeout: 10          # 0 = 无超时
terminal_mouse: true         # true —— 鼠标由应用处理（点击/滚轮；拖动选择并复制到缓冲区）；false —— 用终端自带的选择方式
term_open: window            # 终端在哪里打开（`:term`、`:new`、`& cmd`）：window —— 新窗口，tab —— 已打开窗口中的标签页（gnome-terminal --tab、konsole --new-tab 等）；$IDVJPY_TERM_OPEN=tab
theme: textual-dark          # `d` / `:theme`；切换时保存（matrix —— 黑底绿色荧光）
language: en                 # 界面语言（en、ru、zh）：:lang / --lang / $IDVJPY_LANG；`auto` —— 按 $LANG；文本在 src/locales（分片 <lang>/*.yml，帮助在 help/<lang>/）
check_updates: true          # 启动时：把 VERSION 与 GitHub main 比较；:update 则总是比较
library_url: ""              # 不带参数的 `:import` 的静态来源 —— 通过 https 的共享库 JSON；留空即关闭
screensaver_idle: 120        # 空闲（按键/点击/滚动/鼠标）→ 屏保；0 = 关闭。:screensaver —— 立即显示
screensaver_matrix: true     # 屏保画布：true —— 「矩阵雨」，false —— 星空（:screensaver matrix|stars —— 临时切换）
screensaver_stars: true      # 星空：飞舞的星星；false —— 黑色画布（时钟/条带/load 仍保留）
git_prompt: true            # cwd 位于仓库内时，输入行提示中的 git 分支（`~/proj (main) ❯`）；false —— 仅路径
k8s_completion: false        # 提示中来自集群的 k8s 资源名称（`kubectl get pod <Tab>`）
file_completion: auto        # 文件提示：auto | paths | off（见下文）
kctx_vars: [NS, POD, DEPLOY, SVC, ING, APP, CTR, QUOTA, RELEASE, CHART, VALUES]  # 集群日志的变量（:kctx）；[] —— 关闭
line_api_blocks: true        # 日志块（命令和信息块）使用 Textual Line API（render_line）；false —— 旧的 Static
llm_render_markdown: true    # `:llm` 的回答 —— 格式化 markdown；false —— 纯文本（F6 可临时关闭）
ansi_colors: true            # 命令输出的 ANSI 颜色，与终端一致；false —— 纯文本（F6 可临时关闭）
clear_clipboard_after_secret: false  # 把值插入 `$$NAME=…` 后清空 CLIPBOARD/PRIMARY
editor: nano                 # `:ed`；可带参数（code --wait）；留空 → $VISUAL/$EDITOR
```

变量从 `.bashrc_term_<instance>`（优先）和 `.bashrc_term`（补充）读取。格式：`export VAR=val` 或 `VAR=val`。如果没有这些文件，启动时会复制 [`src/.bashrc_term.example`](../../src/.bashrc_term.example)。在运行中的应用里：`:env`，或用 `> vim .bashrc_term_default` 编辑文件（TTY 退出后会重新读取文件并采纳同一个 shell 的 `export`）。TTY 的导出不会自动写入 `.bashrc_term`——需要 `$VAR=val` 才能做到。

数据库文件（`database_tags_file`，默认 `mytags.db`）**不会进入 git**。首次启动时会创建空的 SQLite 架构；日志中显示种子脚本目录（在顶部，不会跳到下方）。点击绿色的 `--seed` 会把命令插入输入行；Enter 运行；然后 `??`（或约 5 秒）。点击 `.md` 名称或 `:md 文件.md` 会打开带格式的手册（Esc 关闭）。需要 `terminal_mouse: true`。

标签范围（命令 `:scope`）与历史放在一起：数据目录中的 `scope_<会话>.json`。它是窗口的属性，而不是数据的属性：库和运行计数不变，所以过滤器不会随 `:export` / `:backup` / `:send` 一起走，相邻窗口也不会丢失自己的标签。没有文件 —— 就没有过滤。

## 架构

- **`CommandRunner`** —— Textual 应用
- **`JournalScroll`** —— 日志：用按键滚动会激活可见的块
- **`CommandBlock`** / **`InfoBlock`** / **`QueryResultsBlock`** —— 日志块
- **`LineNavigable`** —— 块中的逐行光标

[`src/`](../../src/) 中的模块：[`app.py`](../../src/app.py)、[`database_v2.py`](../../src/database_v2.py)、[`command_parser_v2.py`](../../src/command_parser_v2.py)、[`json_viewer.py`](../../src/json_viewer.py)、[`md_viewer.py`](../../src/md_viewer.py)、[`screensaver.py`](../../src/screensaver.py)、[`seed_catalog.py`](../../src/seed_catalog.py)、[`ingress_analyzer.py`](../../src/ingress_analyzer.py)、[`app.tcss`](../../src/app.tcss)。根目录的 [`app.py`](../../app.py) 只负责启动 TUI。

会话和行为的细节：[`COMPACT_SUMMARY.md`](../../COMPACT_SUMMARY.md)。数据库如何读取：[`DATABASE.md`](../../DATABASE.md)。

## 测试

```bash
python3 -m pytest tests/ -v
```

## 命令手册

每个种子**只会重写自己的**标签。注释语言取自 `settings.yml` 中的 `language`（或 `$IDVJPY_LANG`）：基础文本位于 `src/seed_*.py`，翻译位于 `src/seed_text/<lang>/<handbook>.yml`（见 `src/seed_text/README.md`），因此默认情况下 `--seed` 会写入英文说明，而 `language: ru` 则写入以前的俄文。已播种的库不会改变语言：想在不替换标签的情况下更换说明，可以用 `:relang <代码>` 命令（或 `python3 src/relang.py --lang ru`），而完整地重新 `--seed` 会替换自己的标签（用户标签不会）；在此之前建议先 `:backup`。如果数据库中已有命令，替换前会先把 SQLite 快照写入 `backups/`（`mytags-pre-git-YYYYMMDD-HHMMSS.db` 等；目录为 `settings.yml` 中的 `backup_dir`）。手动操作也一样：`:backup` → `mytags-manual-….db`。空的数据库不复制。`seed_ops.py` 对所有模块只做**一次**快照。恢复：把文件复制覆盖到 `mytags.db` 上。

k8s 排查链：[`K8S_CHAINS.md`](../../K8S_CHAINS.md)。`python3 src/seed_k8s_chains.py --seed`（不会影响 `proc` / `file` / `net` / `kube`）。

手册本身也按语言划分：基础版本位于 `docs/`（k8s 概览在根目录），英文翻译在 `docs/en/`，中文在 `docs/zh/`。`:md SEED_GIT_COMMANDS.md` 会打开所选语言的文本（`handbook_md_path` 先查找 `docs/<lang>/`，否则用基础版本）。

| 脚本 | 文档 | 标签 |
|--------|--------------|------|
| `python3 src/seed_linux_commands.py --seed` | [`SEED_LINUX_COMMANDS.md`](../../docs/SEED_LINUX_COMMANDS.md) | `proc` `file` `net` `kube` |
| `python3 src/seed_k8s_chains.py --seed` | [`K8S_CHAINS.md`](../../K8S_CHAINS.md) | `kpod` `klog` `kquota` … |
| `python3 src/seed_git.py --seed` | [`SEED_GIT_COMMANDS.md`](../../docs/SEED_GIT_COMMANDS.md) | `git` `gstat` `gsync` … |
| `python3 src/seed_ops.py --seed` | 下面所有 ops | docker + helm + ansible + http + netfw + ip + netdbg + data + host + disk + systemd + sysinfo + sysstat + vault + text + pipe + rsync + find + recon + ssh + pkg + user + sqlite |
| `python3 src/seed_docker.py --seed` | [`SEED_DOCKER_COMMANDS.md`](../../docs/SEED_DOCKER_COMMANDS.md) | `dck` `dcmp` `dps` `dlog` |
| `python3 src/seed_helm.py --seed` | [`SEED_HELM_COMMANDS.md`](../../docs/SEED_HELM_COMMANDS.md) | `helm` `hls` |
| `python3 src/seed_ansible.py --seed` | [`SEED_ANSIBLE_COMMANDS.md`](../../docs/SEED_ANSIBLE_COMMANDS.md) | `ansible` `aplay` `avault` `agalaxy` `achk` `aping` |
| `python3 src/seed_http.py --seed` | [`SEED_HTTP_COMMANDS.md`](../../docs/SEED_HTTP_COMMANDS.md) | `curl` `ngx` `trf` |
| `python3 src/seed_netfw.py --seed` | [`SEED_NETFW_COMMANDS.md`](../../docs/SEED_NETFW_COMMANDS.md) | `ss` `nst` `ipt` `nft` `fwd` |
| `python3 src/seed_ip.py --seed` | [`SEED_IP_COMMANDS.md`](../../docs/SEED_IP_COMMANDS.md) | `ip` `eth` `ilink` `iiface` |
| `python3 src/seed_netdbg.py --seed` | [`SEED_NETDBG_COMMANDS.md`](../../docs/SEED_NETDBG_COMMANDS.md) | `pcap` `ncat` `hops` `tls` `npath` `tlschk` |
| `python3 src/seed_data.py --seed` | [`SEED_DATA_COMMANDS.md`](../../docs/SEED_DATA_COMMANDS.md) | `pg` `kf` |
| `python3 src/seed_host.py --seed` | [`SEED_HOST_COMMANDS.md`](../../docs/SEED_HOST_COMMANDS.md) | `tar` `gz` `zip` `tstat` `zstat` |
| `python3 src/seed_disk.py --seed` | [`SEED_DISK_COMMANDS.md`](../../docs/SEED_DISK_COMMANDS.md) | `df` `du` `mount` `fdisk` `lsblk` `smart` `ncdu` |
| `python3 src/seed_systemd.py --seed` | [`SEED_SYSTEMD_COMMANDS.md`](../../docs/SEED_SYSTEMD_COMMANDS.md) | `sctl` `jctl` `dmesg` `sstat` `sfail` `kmsg` |
| `python3 src/seed_sysinfo.py --seed` | [`SEED_SYSINFO_COMMANDS.md`](../../docs/SEED_SYSINFO_COMMANDS.md) | `hinfo` `lsof` `strace` `hstat` `lport` `pdbg` |
| `python3 src/seed_sysstat.py --seed` | [`SEED_SYSSTAT_COMMANDS.md`](../../docs/SEED_SYSSTAT_COMMANDS.md) | `vmstat` `iostat` `mpstat` `oload` |
| `python3 src/seed_vault.py --seed` | [`SEED_VAULT_COMMANDS.md`](../../docs/SEED_VAULT_COMMANDS.md) | `vault` `vstat` `vkv` |
| `python3 src/seed_text.py --seed` | [`SEED_TEXT_COMMANDS.md`](../../docs/SEED_TEXT_COMMANDS.md) | `grep` `awk` `sed` |
| `python3 src/seed_pipe.py --seed` | [`SEED_PIPE_COMMANDS.md`](../../docs/SEED_PIPE_COMMANDS.md) | `sort` `uniq` `cut` `tr` `wc` `xargs` `tee` `jq` |
| `python3 src/seed_rsync.py --seed` | [`SEED_RSYNC_COMMANDS.md`](../../docs/SEED_RSYNC_COMMANDS.md) | `rsync` `rchk` |
| `python3 src/seed_find.py --seed` | [`SEED_FIND_COMMANDS.md`](../../docs/SEED_FIND_COMMANDS.md) | `find` `fchk` |
| `python3 src/seed_recon.py --seed` | [`SEED_RECON_COMMANDS.md`](../../docs/SEED_RECON_COMMANDS.md) | `dig` `nmap` |
| `python3 src/seed_ssh.py --seed` | [`SEED_SSH_COMMANDS.md`](../../docs/SEED_SSH_COMMANDS.md) | `ssh` `scp` `schk` `ossh` `ocert` |
| `python3 src/seed_pkg.py --seed` | [`SEED_PKG_COMMANDS.md`](../../docs/SEED_PKG_COMMANDS.md) | `apt` `dnf` `rpm` `aptq` `rpmq` |
| `python3 src/seed_user.py --seed` | [`SEED_USER_COMMANDS.md`](../../docs/SEED_USER_COMMANDS.md) | `ident` `perm` `uidchk` |
| `python3 src/seed_sqlite.py --seed` | [`SEED_SQLITE_COMMANDS.md`](../../docs/SEED_SQLITE_COMMANDS.md) | `sqlvars` `sqlite` `sqlstat` |

`seed_ops.py` 不会影响 linux / k8s / git。`seed_http` / `seed_netfw` / `seed_ip` / `seed_netdbg` / `seed_rsync` / `seed_recon` / `seed_ssh` 不会覆盖 linux 标签 `net`。`seed_text` / `seed_pipe` / `seed_find` / `seed_disk` 不会覆盖 `file`。`seed_host` 不会覆盖 `smart` / `df`。`seed_systemd` / `seed_sysinfo` / `seed_sysstat` 不会覆盖 `proc` / `logs`。

## MCP 服务器（面向 AI 客户端）

`mcp_server.py` 是一个 Model Context Protocol 服务器：AI 客户端（Claude Code、Cursor 等）可以直接查询标签库 —— 「我有没有查看 pod 日志的命令」。传输方式为 stdio：由客户端启动该进程，不开放任何端口。只读：库不会被修改，命令不会被执行，密钥不会被读取。

```bash
claude mcp add idvjpy -- python3 /path/to/IDvjPy/mcp_server.py
idvjpy mcp                                # pip 安装后等价（console script）
python3 mcp_server.py                     # stdio；通常由客户端启动
python3 mcp_server.py --shell-history     # + shell 自身的历史（bash/zsh/fish/atuin）
```

```json
{"mcpServers": {"idvjpy": {"command": "python3",
                           "args": ["/path/to/IDvjPy/mcp_server.py"]}}}
```

工具：`search_commands`（在命令与注释中做子串匹配，如同 `?text`）、`list_tags`、`get_tag`（如同 `?tag`）、`search_history`（`session` —— 仅本窗口，`sessions` —— 所有 `history_*.txt`，`shells` / `all` 需配合 `--shell-history`；每行前标注会话名）、`library_stats`（运行计数：真正在用的是哪些）。库与历史与 TUI 相同（`--data-dir` / `--db` / `--instance`；默认取 `settings.yml`、`$IDVJPY_DATA_DIR`、系统目录）。细节与边界 —— 应用内的 `:? mcp` 主题。

服务器刻意做不到的事：写入（外部没有 `#tag` / `#tag-`）与执行（`:run`、`!tag[tid]` —— 执行留在需要人按 Enter 的地方）。工具返回的一切都会发给接入的 AI 客户端，因此不要把密钥写进标签（用 `$$`）；`$$` 的值只存在于会话中，不会进入库。

## 依赖

必需（在 `requirements.txt` 中）：`textual==7.3.0`、`rich==14.3.0`、`pyperclip==1.11.0`、`PyYAML==6.0.3`、`Pygments==2.19.2`、`portalocker`。

可选 —— 由应用自行查找的外部工具（也可在 `md_converter` / `md_ocr` / `editor` 中显式指定）。它们不在 `requirements.txt` 中：没有它们一切照常，`:md` 会说明缺少什么。

| 提供的能力 | 工具 | 安装 |
|------------|------|------|
| `:md` 中的文档：docx/xlsx/pptx/doc/ppt/xls/rtf/epub/odt/pdf | `anydoc` —— 推荐 | `pip install firecrawl-anydoc`（Rust，无依赖，PDF 本地解析） |
| 同上，若 anydoc 不合适 | `markitdown` | `pip install "markitdown[all]"`（会带来 pandas/lxml/pdfplumber） |
| 同上，通用转换器 | `pandoc` | `apt/dnf/apk/brew install pandoc` |
| 扫描版 PDF：本地文本层 | `ocrmypdf` + `tesseract` | `apt/dnf/apk/brew install ocrmypdf`；语言 —— `tesseract-ocr-<语言>` |
| `:rg` 的 markdown 搜索 | `ripgrep`（`rg`） | `apt/dnf/brew/pacman install ripgrep`（否则用内置扫描器） |
| 外部编辑器 `:ed` | `nano` 或 `$EDITOR` / `$VISUAL` | `apt/dnf/apk/brew install nano` |
| 文件管理器与终端 `:fm` / `:term` | `ranger` / `nnn` / `mc`、终端模拟器 | `$FILEMAN` / `$TERMINAL`，否则按列表查找 |

`:md` 的细节（转换器、OCR、参数、缓存、每条消息的含义）—— `:? md`。

## 许可证

[MIT](../../LICENSE)。作者：markovskiy.pavel & Gemini、GLM、CLAUDE、DeepSeek、Grok。
