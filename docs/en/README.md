# IDvjPy — ID Variables & Joiner on Python

<p align="center">
  <img src="../../idvj-all.gif" alt="IDvjPy_term: python3 app.py --demo all" width="800">
</p>

<p align="center"><em>Define your variables, join your command.</em></p>

Keyboard-driven TUI that treats **tags as command templates** and assembles them into shell lines (`!tag[tid]`, `!!`). Python **3.12+**, [Textual](https://textual.textualize.io/).

**IDvjPy_term** v1.157 — a smart terminal for building command lines from tags.

Translations: [Russian](../../README.md) · [中文](../zh/README.md).

## What is it?

IDvjPy is a terminal application (TUI) in Python (Textual) with keyboard control.
Persistent tagged command history is stored in SQLite.

**Philosophy:** tags are variables with command templates; the app assembles them into complex command lines.

The application code lives in `src/`. The working directory holds the data: `settings.yml`, the tag database, `.bashrc_term*`. When the DB is empty, the journal shows a catalog of seed handbooks (Linux, [k8s chains](../../K8S_CHAINS.md), git, ops): clicking the green `--seed` inserts the command into the input, clicking `.md` opens the handbook.

Launch: `python3 app.py` (launcher; code in `src/`). Tests: `python3 -m pytest tests/ -v` (dev dependencies: `pip install -r requirements-dev.txt`). In-app help: `:?`.

## Features

- Persistent tags and command assembly (`!tag[tid]`, `!!`)
- Command handbooks (seed): Linux, [k8s investigation chains](../../K8S_CHAINS.md), git, docker, helm, ansible, systemd, lsof/strace, sysstat, sort/jq, ip/ethtool, tcpdump/mtr/TLS, apt/rpm and other ops
- Journal by blocks: focus, collapsing, pipe `|` from the focused block; buffer labels (`:name`) — pipe from an old block without re-running the source (`|@label awk …`, `|@N …`)
- Reading mode: if you scroll the journal up (wheel/PgUp) or focus a block, new output is appended at the bottom, but the view and focus do not move — neither `:watch`, nor the `:llm` answer, nor an incoming `:send`. Follow mode returns once you scroll to the bottom or run a command (Enter)
- Autocompletion of paths, commands from the DB and lines of `history_*.txt` (including `@`/`>`; on/off — `history_completion`), and commands from this session. Invocations of `:` queries (`:llm`, `:cht`, `:rg`, `:md`, `:run`, `:send`) stay in history for ↑/`:h`, but are not suggested — the list is in `history_queries`
- Quick hints for app commands: type `:` — a list of all `:` commands with a short description (filter by letters, `Tab`/`Enter` inserts `:command `, launch — with a separate Enter); `:/text` remains a journal search. In the `:?` help, command names are clickable links: a click inserts the invocation into the input (like `!tag` in `??` and `--seed` in `:welcome`)
- Help topics: the main `:?` is an overview, details per command group live in `:? <topic>` (`:? llm`, `:? tags`, `:? calc`, `:? run`, `:? i`, `:? md`, `:? vars`, `:? kctx`, `:? send`, `:? session`; the topic list is in the "Help topics" section and in the hints after `:? `). An unknown topic is an explicit error listing the topics; a glued `:?calc` tells you to add a space
- Tag hints while typing `?`: tag name, number of commands and the tag comment (`?vault  (2)  HashiCorp Vault`), filter by letters; clicking a row inserts `?tag` and immediately runs the query. Only the `?vault` command itself becomes a link (and is highlighted) — the counter and comment remain plain text
- Line mode in block output (copying and appending to the input)
- JSON viewer (F5) with a `jq` draft and `$JSON`
- Variables `$VAR` (files `.bashrc_term` / `.bashrc_term_<instance>`); `$OUT` — the last line of the block, only at command time
- Secrets `$$VAR=value`: the value is hidden while typing and in the journal (`****`), stored in `secrets_<instance>.json` (0600) — not in `.bashrc_term`/history; in commands — `$VAR`. The `clear_clipboard_after_secret` key clears the clipboard after inserting a value into `$$NAME=…`
- Stopping a background command without waiting for the timeout: `F4` / `:kill` (SIGTERM to the whole group)
- Search across command contents: `?kubectl wide` — if there is no such tag, searches text/comments
- Monitoring with a command: `:watch 5 kubectl get pods` — re-run every N seconds in one block
- Library hygiene: `:mv tag[1] tag2` (move a command) and `:mv tag tag2` (rename)
- Metrics: run counters (use_count/last_used) and `:stats` — top by runs, tags, "never run"
- Catalog in Markdown: `:export * [file.md]` — the whole library by tags with comments
- Comparing outputs: `:diff` — unified diff of the focused block against the previous one
- Session output history: `:o [N]`, `:o /text`, `:o clear` — grep over past outputs after `:c`
- k8s autocompletion: `kubectl get pod <Tab>` — names from the cluster (`k8s_completion: true`)
- File hints — `file_completion: auto|paths|off`: by default explicit paths (`./`, `/`, `~/`) and file names after `cat`/`vim`/…, for `grep`/`sed`/`awk`/`jq` — from the second argument (the first is the pattern), without cwd noise when typing `kubectl`/`docker`/`git`; the context is computed per current segment (`cat f | grep ot` does not list cwd) (`paths` — explicit paths only, `off` — disabled). In the list **a directory is underlined like a link, a file stays plain text** (plain for `cd`, where they were easy to confuse); a click inserts either of them
- Markdown search (`:rg <pattern> [directory]`) — ripgrep over an Obsidian vault or any directory with `.md` (otherwise the built-in scanner): snippets with clickable `path:line`, opened in the built-in md viewer; `:rg <N>` — open the N-th result
- UX: `:r N` — the command of the block N back; `:cmd [N] [show]` — the block's command with values substituted (secrets included) to the clipboard; `:send <session|*> <command>` — forward a command to another window (insert into the input; `:send!` — run immediately); the `N running` counter in the header; `:alias <tag>` — commands as bash functions
- LLM from the TUI: `:llm [provider] message` (without a name — `default:`; `$OUT`/`$BLOCK` insert the block's output; `@file` embeds the file text (UTF-8, ≤200 KB; several allowed); conversation context — `history_turns: N` on the provider (`:llm reset [<provider>|*]`); queries are written to `history_*.txt` but not into the hints — which exact `:` queries are stored that way is set by `history_queries` in settings.yml). The answer is markdown and is shown formatted (`llm_render_markdown`, see settings). While the request is in flight, a spinner `⠋ thinking… 3s / 60s` spins in the block (you can see that we are waiting for an answer and how long is allowed)
- cheat.sh from the TUI: `:cht <query>` — [cht.sh](https://github.com/chubin/cheat.sh) cheat sheets in the journal (commands, questions about languages, search `~`), without ANSI; the output is a regular block (`$OUT`, `|`, F3, F7, search)
- Runbook — a semi-automatic command chain: `:run <tag|file.yml>` runs the steps in order and stops where your decision is needed (`run:manual` — the line is in the input, edit it and press Enter; `run:prompt` — you type from scratch; an empty Enter skips the step). If the tag has no `run:` directives at all, the plan warns: all steps will go `auto` (this is what an outdated seed looks like — and a mutation may go through without confirmation). A step error stops the run, `Esc` / `:run stop` does too; `--step` — stop at every step, `--dry` — plan only; help — `:? run`. A ready example — `:run vapprole` (token → role → `role_id` → `secret_id` → login → check; the token and role steps are prefix lines `$$VAULT_TOKEN=` / `$ROLE=`, the value is appended after `=`)
- Output of colored commands — as in a terminal: SGR codes (`curl wttr.in`, `ls --color=always`, colored `grep`) are drawn with the block's colors (`ansi_colors: true`) instead of flowing into the TUI frame; cursor/OSC sequences and control characters are always stripped, the `\r` redraw of progress bars (`docker build`, `pip`, `curl` with progress) is collapsed to the final line — instead of a hundred frames you see the result. Plain text (`F3`, `|`, `$OUT`/`$BLOCK`, `:log`, `@key`) is always without escape codes (F6 — plain output once)
- Clean history: typos (`command not found`, 127) are automatically removed from `history_*.txt`
- `:llm` answer language: `answer_language: Russian` on the provider — a hard rule against answers not in the user's language (e.g. Chinese)
- The wait for a `:llm` answer is visible: a spinner and time animate in the block (`⠋ thinking… 3s / 60s`, the second limit is the provider's `timeout`), so the request does not look like a hang; the entry is removed as soon as the answer or an error arrives. While the request is in flight, the block is not parsed as markdown (a service line is shown), and the input and journal remain free
- :llm ask: `:llm ask [<provider>] <task>` — the provider (the default one, or the one named first) receives the task **plus** the application cheat sheet and a digest of the tag library (tag/tid/command/comment, relevant to the task — higher, the rest — by names). The answer comes as ready-made references `!kpod[1]` / `!! kpod[1] && klog[1]`; existing references are additionally shown as a clickable line (insert into the input, launch — with a separate Enter). For a regular `:llm`, the same context is enabled by the provider key `app_context: true|N` (`N` — character budget, default 6000; no key/false — disabled). The logic is in `src/llm_context.py`
- External editor: `:ed <file>` (edits in the file), `:ed $OUT|$BLOCK` (block output), `:ed` (empty buffer). The TUI is paused (like `> cmd`). The editor is `editor:` in `settings.yml` (arguments allowed: `code --wait`), otherwise `$VISUAL`/`$EDITOR`, otherwise the system one. `$VAR`/`$OUT` are expanded in the path (`:ed $TMPDIR/pod-$OUT.json`); a one-line result edits the input (launch — Enter), a multi-line one remains a file with the path shown (`@file` / `| cmd`)
- Aliases from `~/.bashrc` (including `$1` / `$2` / `$@`), background command execution
- `> cmd` — a real TTY (htop, vim, ssh); a click and PgUp/PgDn activate the visible journal block. A background command does not get the terminal: `stdin` is `/dev/null`, so `read`, `tsh`, `kubectl`, `ssh` do not "steal" keys and the mouse (previously `:kctx` with a hung `tsh kube login` made the input unusable), and on timeout/`F4` the app returns the terminal to its own mode. Need interactivity — `> cmd`, a long task without a TTY — `@ cmd`; `:kctx <cluster>` starts login without `command_timeout`
- Calculator without special commands: a line starting with a digit (or `(` / `-`) and fully parsable as arithmetic/unit conversion is computed locally — `512Mi + 20% in Gi`, `20% of 512Mi`, `2Gi/512Mi`, `500m in cores`
- ipcalc: IPv4 networks are computed the same way, without special commands — `192.168.1.0/24`, `300 hosts` → `/23` (like jodies.de/ipcalc)
- Kubernetes cluster journal: variables from the `kctx_vars` list (by default — the stack of bundled templates: kubectl `NS POD DEPLOY SVC ING APP CTR QUOTA` and helm `RELEASE CHART VALUES`) are remembered per cluster in `kctx.json` (data directory). `:kctx` — list of clusters; `:kctx <cluster>` — login (`klogin <c> || kubectl config use-context <c>`) and previously used variable sets (if there is exactly one set, it is applied right away); `:kctx N` restores the set (variables → `.bashrc_term_*`); `:kctx <cluster> N` — login and apply in one line; `kctx_vars: []` disables the journal

## Installation

Python 3.12+ is required.

```bash
./setup.sh                 # creates .venv (checks Python 3.12+) and installs dependencies
source .venv/bin/activate
# or: pip install -r requirements.txt
# tests: pip install -r requirements-dev.txt
```

On Linux, the clipboard needs `xclip` or `xsel` (on Wayland — `wl-clipboard`).

Variables: on first start, [`src/.bashrc_term.example`](../../src/.bashrc_term.example) is copied to `.bashrc_term_<instance>`. Demo: [`DEMO.md`](../../DEMO.md) (a live scenario) and `python3 app.py --demo` (auto-typing for video recording).

### Installing as a pip package (wheel)

The built wheel can be installed into any venv and run with the `idvjpy` command without cloning the repository.

```bash
# from the repository: build the wheel (copies the current src/ into the package's nested resource)
packaging/build_wheel.sh                 # → packaging/dist/idvjpy_term-<version>-py3-none-any.whl

# in the target environment:
python3 -m venv .venv && source .venv/bin/activate
pip install packaging/dist/idvjpy_term-*.whl

idvjpy                       # launch (the same flags as python3 app.py)
idvjpy --demo short          # auto-tour from the installed package
python3 -m idvjpy_boot       # the same via python -m
```

The wheel includes the code and resources (`app.tcss`, `demos/`, config examples, `.bashrc_term.example`, and the `:md` handbooks — `docs/<lang>/*.md` plus `K8S_CHAINS.md`); the user's stores (settings/DB/history) are **not** placed into the package — on first launch they are created in the system data directory (`--data-dir` → `$IDVJPY_DATA_DIR` → the OS system directory, see "Launch"). This way the same package can be upgraded (`pip install -U`) without touching your tags and history.

The package version matches the application version (`CommandRunner.VERSION` → `MAJOR.MINOR.0`).

### Version = commit (for contributors)

The source of truth is `VERSION` in `src/app.py`. To bump the minor and update all release files at once (README, `COMPACT_SUMMARY.md`, `CLAUDE.md`, `AGENTS.md`, `test_cmd.md`, `tests/test_cmd_scenarios.py`, `DEMO.md`, as well as the `DATABASE.md` / `backup_db.md` handbooks — the marker "state as of **vX.YY**"):

```bash
python3 bump_version.py              # v1.97 → v1.98 and edits in all files
python3 bump_version.py --dry-run    # show the diff, write nothing
python3 bump_version.py --check      # check synchronicity (exit 1 on a mismatch)
python3 bump_version.py --set v2.0   # explicit version
```

The script adds a `## <new version>` section to `COMPACT_SUMMARY.md` as a stub — write the changelog text yourself. The same markers are checked for synchronicity by `tests/test_release_meta.py`.

### Installing system-wide (pipx / uv / `--user`)

To make `idvjpy` always available as a regular command, install the wheel in isolation — the system Python is not touched.

```bash
# pipx — a separate environment per application
pipx install packaging/dist/idvjpy_term-*.whl
pipx upgrade idvjpy-term        # after building a new wheel
pipx uninstall idvjpy-term

# uv (>= 0.4) — the same in uv style; installs the binary into ~/.local/bin
uv tool install packaging/dist/idvjpy_term-*.whl
uv tool list                    # idvjpy-term v1.60.0 / idvjpy
uv tool upgrade idvjpy-term
uv tool uninstall idvjpy-term

# or into the active venv via uv
uv venv && uv pip install packaging/dist/idvjpy_term-*.whl

# user install (without isolation)
python3 -m pip install --user packaging/dist/idvjpy_term-*.whl   # ~/.local/bin/idvjpy
```

Notes:
- On Debian/Ubuntu, a system `pip install` without a venv is blocked (PEP 668, `externally-managed-environment`) — use `pipx`/`uv` or `--user`.
- Installing straight from git also works: the root [`pyproject.toml`](../../pyproject.toml) + [`setup.py`](../../setup.py) embed `src/` into the package at build time (the same as `packaging/build_wheel.sh`).

```bash
# straight from GitHub — without building the wheel locally
pipx install git+https://github.com/webxed/IDvjPy
uv tool install git+https://github.com/webxed/IDvjPy
```

- Where data goes on first launch — see "Launch" below: the OS system directory (`~/.config/idvjpy` and the like), or `--data-dir` / `$IDVJPY_DATA_DIR`. When the package is upgraded/removed, tags, history and settings are preserved.

## Launch

```bash
python3 app.py [--data-dir PATH]
```

Data (settings/DB/history): `--data-dir` → `$IDVJPY_DATA_DIR` → the current directory (if it already contains `settings.yml`) → the system directory (`~/.config/idvjpy`, macOS `~/Library/Application Support/IDvjPy`, Windows `%APPDATA%\IDvjPy`). On the first launch in a new directory, `settings.yml` is created (a copy of the template for the language selected in `auto` mode: `--lang` → `$IDVJPY_LANG` → system locale → `en`, files [`src/settings/<lang>.yml`](../../src/settings)) and `llm_providers.yml` (a copy of the example). The personal `settings.yml` is **not** in git — settings do not leak into the repository.

```bash
python3 app.py
python3 app.py --instance-name=user1   # a separate .bashrc_term_user1 and history_user1.txt
python3 app.py --demo                  # auto-tour: types the commands itself (Esc — stop)
python3 app.py --demo ip               # myip → jq .cc → Wiki URL → hello pipe → echo Hello, $OUT
python3 app.py --demo features         # new commands v1.44 (see DEMO.md)
python3 app.py --demo all              # everything in a row: calc, ipcalc, JSON, tags, :stats, :diff, :watch, :kctx (no network)
python3 app.py --demo full --demo-quit
```

The application code lives in `src/`. In the root of the working copy — data: `settings.yml`, the tag database, `.bashrc_term*`, `history_<instance>.txt`, the session registry `session_<instance>.pid`. Seed handbooks: `python3 src/seed_git.py --seed` and the like. When the DB is empty, a catalog appears in the journal: clicking `--seed` inserts the command into the input, clicking `.md` or `:md file.md` opens the handbook (`terminal_mouse: true`).

| Path | Purpose |
|------|------------|
| `src/` | TUI, CSS, seed scripts, the `.bashrc_term.example` template |
| `app.py` / `backup_db.py` | launchers (do not modify data) |
| `settings.yml` | personal settings — **not in git** (`.gitignore`); a copy of `src/settings/<lang>.yml` (language `auto`), created on first launch |
| `*.db`, `.bashrc_term*`, `history_*.txt`, `inbox_*.jsonl`, `session_*.pid` | tags, variables, history, `:send` inboxes and the session registry — also outside git |

## Docker demo stand

Try the TUI without installing Python: a small image (~100 MB, `python:3.12-alpine`) with an
already populated tag library. The data is in the `idvjpy-demo-data` volume (`settings.yml`,
`mytags.db`, history), the code is in the image. What to try and how to reset —
[`docker/README.md`](../../docker/README.md).

```bash
cd docker
docker compose run --rm idvjpy                          # build and run
docker compose run --rm idvjpy --demo short --demo-quit # auto-show (the tour needs a TTY)

docker volume rm idvjpy-demo-data                       # reset to factory
```

The first launch creates `/data/settings.yml` from the template itself and populates the library
(`linux`, `k8s`, `git`, `ops` — 849 commands, ~5 s). Inside the image there are `bash`, `nano`,
`git`, `curl`, `jq`, `procps`; the `docker`/`kubectl` CLIs are deliberately not included — tags like
`dck`/`kpod` are command templates, not an installed CLI. Without compose:

```bash
docker build -f docker/Dockerfile -t idvjpy-demo .
docker run --rm -it -v idvjpy-demo-data:/data idvjpy-demo
```

CI builds this image and runs a smoke test — the `docker-demo` job in
[`.github/workflows/tests.yml`](../../.github/workflows/tests.yml): provisioning, seeding,
idempotency of a repeated launch and TUI rendering under a real pty
(`docker/tui-smoke.py`).

## Prefix system

| Prefix | Purpose | Example |
|---------|------------|--------|
| (none) | Run a shell command | `ls -la` |
| `> cmd` | Hand over a real TTY (htop, vim, ssh). After exiting — the same shell's env/$PWD | `> htop` |
| `@ cmd` | Run without `command_timeout` (long non-TTY tasks; stdin is `/dev/null`) | `@ terraform apply` |
| `#tag cmd` | Save a command with a tag (text as it is) | `#deploy rsync -av src/ host:` |
| `# command` | To history, do not run (like `# …` in bash; a space after `#`) | `# curl https://example.com` |
| `#tag=` / `#tag=ID=` | Comment on a tag / command | `#deploy=prod rsync` |
| `#tag+` / `#tag+ID` | Substitute for editing | `#deploy+1` |
| `#tag-` / `#tag-tid` | Soft delete | `#deploy-` / `#deploy-1` |
| `#name--` / `#name!!` | Hide / bring back all tags of a handbook | `#ansible--` / `#ansible!!` |
| `#tag!` / `#tag!tid` | Restore after deletion | `#deploy!` / `#deploy!1` |
| `?` / `??` / `?tag` / `?tag[tid]` | Query tags / all / by tag / preview; `?text` (2+ chars, not a tag) — search across command contents and comments. While typing `?` — a list of tags with a hint (number of commands + comment): letters filter, `Tab`/`Enter` insert `?tag`, a **click on a row** runs the query right away | `?deploy`, `?wide` |
| `!tag[tid]` / `!N` | Insert a command into the input (does not run it) | `!deploy[1]` |
| `!! …` | Assemble a line in the input | `!! deploy[1] && start[1]` |
| `:` | Application commands | `:q`, `:cd`, `:fm`, `:term`, `:session`, `:new`, `:scope`, `:send`, `:welcome`, `:backup`, `:screensaver`, `:r`, `:cmd`, `:kctx`, `:run`, `:playbook`, `:md`, `:rg`, `:lang`, `:relang`, `:?` |
| `\| cmd` | Pipe the stdout of the focused (otherwise the last) block (to history, like a regular command) | `\| grep error` |
| `\|@label cmd` | Pipe from a block labeled with `:name label` (the source is **not** re-run) | `\|@buff awk '{print $2}'` |
| `\|@N cmd` | Pipe from the N-th block back, `0` = the last one | `\|@1 jq .items` |
| `$OUT` | On request: the last non-empty line of the block (not stored) | `echo Hello, $OUT` |
| `$VAR=val` | Local variable (writes `.bashrc_term_<instance>`) | `$EDITOR=nvim` |
| `$$VAR=val` | Secret variable: input and output are masked (`****`), file `secrets_<instance>.json` (0600); in `:send` it travels **by name**, and the value — into the target's store | `$$TOKEN=…` → `curl -H "Bearer $TOKEN"` |
| `$VAR=@key` / `$$VAR=@key` | Take the value from the block's output: the line whose first token is `key` (`@last` — the last line) | `vault read …` → `$$VAULT_TOKEN=@token` |

### Secret variables (`$$VAR=value`)

Tokens, passwords and keys can be kept in the TUI without showing them on screen:

```text
$$TOKEN=...        # set a secret (the value is hidden while typing)
$$TOKEN            # status: is set (value hidden) / is not set
$$TOKEN-           # delete
curl -H "Bearer $TOKEN" https://api.example   # the usual $TOKEN substitution
```

- **Input.** From the first character of the value the input line is masked; the secret name is in the subtitle (`Secret $TOKEN: value hidden`).
- **Storage (session only).** `secrets_<instance>.json` (permissions `0600`) is created when the secret is set and **deleted on exit** from the application — values do not survive a restart. It is not written to `.bashrc_term`, `history_*.txt` or the playbook log; an already existing file is picked up at startup, by `:env` and `:session`.
- **Output.** In the journal the value is `****`: the block header, the displayed stdout/stderr, `:o` and the `TTY: …` line. Masking is **frozen when the output is recorded** (with the secrets alive at that moment), so `$$NAME-`, redefining it, `:env` or `:session` do not expose what was already shown on a re-render (space/←→, F2, F8, `:/` search, `:w`); `:o` stores already masked output. At the same time `raw_stdout` is real — `|`, `$OUT` and `F3` work with the real data.
- **Environment and sessions.** `.bashrc_term*` and `:env` cannot override a secret value (a name from the store is skipped), and on exit only your own `secrets_<instance>.json*` is purged — a neighbouring session keeps its values.
- **LLM.** Secrets do not go into `:llm`: values in the message (including those that got there via `$OUT` / `$BLOCK` / `@file`) are replaced with `****` before sending, in the block header — `secrets: hidden`.
- **Capture from output.** `$VAR=@key` / `$$VAR=@key` takes the value from the focused (or last) finished block: the line whose first token equals `key` — handy for `vault read` / `vault write` tables (`Key  Value`); `@last` — the last non-empty line (for example, after `| jq -r .field`). Example — the `vapprole` playbook ([`docs/SEED_VAULT_COMMANDS.md`](../../docs/SEED_VAULT_COMMANDS.md)).
- **Clipboard when a secret is pasted.** `clear_clipboard_after_secret: true` in `settings.yml` — after a value is pasted into a `$$NAME=…` line, CLIPBOARD/PRIMARY/the internal buffer are cleared (default `false`; a regular paste does not touch the buffer; some clipboard managers may keep a history).

Limitations (deliberate): the whole input line is masked (the name too — it is visible in the subtitle); in an interactive `> cmd` the real terminal shows the value while the TUI is paused; a line starting with `$$` is always treated as a secret; the **explicit exceptions a human asks for** — `F3`, `:log`/F7 (real output, subtitle says `secrets visible`) and `:cmd show` (prints the materialized command) — return the real data. With `clear_clipboard_after_secret: true`, `:cmd` does not copy a command containing secret values (it says so in the journal).

**Calculator (without a prefix):** a line starting with a digit (or `(` / `-`) and fully parsable as arithmetic or unit conversion is computed locally — the shell is not started, the result appears as a block headed `calc:`. Other lines (`7z …`, `(cd … && …)`, `-la`, `2>/dev/null …`) still go to the shell — they contain words that are not parsed as arithmetic. Full help in the TUI: `:? calc`.

- Arithmetic: `+ - * / ^ ( )` — `1024*3`, `(2+3)*4`, `2^10`, `-5 + 8`
- Percentages: `512Mi + 20% in Gi` (increase by 20%), `512Mi - 15%`, `512Mi * 20%` (a share), `2 + 10%`
- `of` — a share of a value: `20% of 512Mi` → `102.4Mi`, `1/3 of 1Gi`, `20% of (512Mi + 1Gi)`; same as multiplication (`512Mi * 20%`)
- Memory: `B`; `K/M/G/T` = `KB/MB/GB/TB` (×1000); `Ki/Mi/Gi/Ti` = `KiB/MiB/GiB/TiB` (×1024); k8s style without a space: `512Mi`, `1.5 Gi`
- CPU: `m` — millicores, `cores`; `500m in cores` → `0.5 cores`, `0.5 in m` → `500m`
- `1Gi/512Mi` → `2` (how many times it fits); `524288 in Mi` → `0.5Mi`; sum of resources: `512Mi + 1Gi + 256Mi in Mi`
- IP subnets (like jodies.de/ipcalc): `192.168.1.0/24`, `10.1.2.3/255.255.255.0`, a bare `8.8.8.8` (default classful mask) — address, mask (=N), wildcard, network/prefix, host range, broadcast, host count, class/RFC1918 and the binary form; the inverse task — `300 hosts` → `/23` (the minimal prefix for N hosts)

`#name--` hides all tags of a handbook (`linux`, `k8s`, `git` and the ops ones: `ansible`, `helm`, …). `#name!!` brings them back. In `??` / `?` hidden tags are visible in the Hidden block; in `!` auto-hints and completion by command text they are absent. `#tag-` still hides a single tag.

`!` and `!!` substitute text into the input. Launch — with a separate Enter. In `??`, a click on a tag inserts `!tag ` / `!tag[tid] ` **at the cursor position** (does not overwrite the line; you can click several tags in a row). **Ctrl+click** or **double click** on `!tag[tid]` — insert and run at once: the same as typing the reference and pressing Enter twice (the reference expands into the command and runs). A reference without a tid (`!tag `) has nothing to run — it is only inserted. `terminal_mouse: true` is required.

Aliases with `$1` / `$2` / `$@` substitute arguments (`alias klogin="tsh kube login $1"` → `klogin cluster` becomes `tsh kube login cluster`). Without `$n`, the rest of the line is still appended to the alias body. Arguments end at the first shell operator, and the operator itself remains an operator: `klogin prod || kubectl config use-context prod` → `tsh kube login prod || kubectl config use-context prod`, `kget pod | grep api` → `kubectl -n $NS get pod | grep api` (previously `||` / `|` / `2>&1` ended up as arguments like `'||'`).

### Application commands (`:`)

- `:q` — quit
- `:w file` — write the output to a file
- `:h [N]` — the last N lines of `history_<instance>.txt` as one block (by default from `settings.yml`; the lines can be taken with line mode). The file holds only what was saved: `:` commands (except the `history_queries` list), `#tag` saves, `?`/`!` lines and `$VAR=…` are not written to it; with ↑ you flip through **everything** typed in this session (`:` commands and so on — from the session feed), in typing order — the last typed line comes back first
- `:h /text` — search within that file in the hints (case-insensitive, newest first, identical lines once). Esc+Enter — the same search into the journal
- `:h compact` — compact the old history (unique lines); the last `history_keep` lines are not touched. At startup — only if the file is longer than `2 × history_keep`
- `:h import [shell]` — append the user's shell history to `history_<instance>.txt`: `~/.bash_history`, `~/.zsh_history`, fish (`~/.local/share/fish/fish_history`), ksh (`~/.sh_history`; `sh` is the same file), nushell (system data dir: `Application Support` / `%APPDATA%`), PowerShell PSReadLine (`%APPDATA%\Microsoft\…` on Windows, the XDG path on Linux/macOS) are searched; a set `$HISTFILE` comes first (format detected from the content even if the file name is unusual). The last 5000 lines of each file are taken (for big files — only the tail), lines that are already there are not duplicated (a repeated import adds nothing), nothing is executed. With no name — every shell found, `:h import zsh` — that one only. Failures are explicit: a locked file, a write error and an unreadable source are reported instead of looking like "0 new". After the import, ↑, `:h /text` and the hints see these commands right away
- `:c` — clear the journal blocks
- `:json` / `:json <file>` — JSON viewer (the last block or a file)
- `:md <file.md>[#L<n>]` — Markdown handbook with formatting (click the name in the welcome message; Esc closes). It also accepts a path — absolute or relative to `md_dir`/cwd; that is how files from `:rg` and an Obsidian vault are opened; `#L<n>` opens right at line n (like on GitHub). `:md` is written to history (↑ / `:h`). Files longer than `md_render_lines` (1000 lines by default) are opened as source in the Line-API viewer — fast, with `/` search and `#L` jumps (formatted rendering of large files takes tens of seconds). `y` copies the full file path to the clipboard — in the formatted view you can also click the name in the header (in the raw view only `y`)
- `:rg <pattern> [directory]` — search across markdown files: ripgrep, if installed (otherwise the built-in scanner + an install hint). The pattern is a regular expression, "smart case" (no capitals — case does not matter). The base is `[directory]`, otherwise `md_dir` from `settings.yml`, otherwise cwd. The results are snippets with clickable `path:line` (opened by the built-in md viewer right at the matching line); `:rg <N>` opens the N-th result (1-based) there too. It skips hidden and service directories (`.git`, `.obsidian`, `node_modules`, …); `:rg` is written to history (↑ / `:h`)
- `:llm [<provider>] <message>` — a request to the LLM via `llm_providers.yml` (secrets only from the environment: `$DEEPSEEK_API_KEY`). `@file` embeds text, `$OUT` / `$BLOCK` — the block's output, `history_turns: N` keeps the conversation context. The answer is drawn as formatted markdown (`llm_render_markdown: true`; F6 — disable once); the plain copy for F3/`|`/`$BLOCK`/`:w` does not depend on this
- `:llm offline <message>` / `:llm ask offline <task>` — the built-in offline provider (`mock: true`): answers without network and keys; it exists in any config until overridden by your own `offline:` (demo, wiring check)
- `:llm ask [<provider>] <task>` — the task is augmented with the application cheat sheet and a digest of the tag library; the answer consists of ready-made references `!tag[tid]` (clickable, existing ones only). The `app_context` key on the provider enables the same for a regular `:llm`
- `:llm reset [<provider>|*]` — clear the conversation context (session memory)
- `:cht <query>` — cheat.sh (cht.sh) help in the journal: `:cht tar`, `:cht python read file` (spaces → `+`), `:cht ~snapshot` (search), `:cht go/:learn` / `:list` (special pages). Options via `?`: `Q` — without comments, `T` — without colors (default `?T`). URL/options — `cheat_sh_url` / `cheat_sh_options` in `settings.yml`; the output is a regular block ($OUT, `|`, F3, F7, search)
- `:ed [<file>|$OUT|$BLOCK]` — external editor (`editor:` in `settings.yml`, otherwise `$VISUAL`/`$EDITOR`); the TUI is paused. `$VAR`/`$OUT` are expanded in the path (`:ed $TMPDIR/pod-$OUT.json`); a one-line result edits the input, a multi-line one remains a file
- `:o [N]` — the last N outputs of the session (5 by default); `:o /text` — grep over them (survives `:c`); `:o clear` — forget
- `:stats` — library summary: runs by tag, top-10, "never run"
- `:mv <tag>[<tid>] <dst>` — move a command to another tag; `:mv <tag> <dst>` — rename a tag (the comment travels along)
- `:diff` — unified diff of the focused block's stdout against the previous one
- `:kill [all]` — stop the running command; `:watch <sec> <command>` — repeat it in one block (`:watch stop`)
- `:alias <tag> [file.sh]` / `:alias * [library.sh]` — dump commands as bash functions `tag_tid()`
- `:i …` — Kubernetes Ingress Analyzer (`:i` without arguments — help)
- `:cd [path]` — show / change the cwd for shell commands (same as `cd path`). The tags DB, history and `.bashrc_term*` stay in the data directory (not in the new cwd — see "Files and settings"); an empty `mytags.db` is not created in the new folder. The current directory is always visible: in grey on the left of the input line (`~/project ❯`; clicking the path focuses the input), `~` stands for the home directory, and a long path is shortened to its tail (at most a third of the window width; the full path is in block headers)
- `:fm [path]` — the OS file manager in a new window (cwd or a path). Linux: `xdg-open`; macOS: `open`; Windows: `explorer`. Custom: `$FILEMAN`
- `:term [path]` — the system terminal in a new window. Linux: `xdg-terminal-exec` / `gnome-terminal` / …; macOS: Terminal.app; Windows: `wt` or `cmd`. Custom: `$TERMINAL`
- `:env` — re-read `.bashrc_term*` (and `~/.bashrc` aliases) in the already running application. After `> cmd`, exports of **the same** bash are picked up by themselves (a nested `> bash` + `export` inside — no)
- `:session` — the current instance (history + `.bashrc_term_*`). `:session NAME` — switch or create (the tag DB is shared). The current session name is visible in the application header and in the terminal window/tab title (`IDvjPy_term · NAME`, with running commands — `— N running`)
- `:new [NAME|-] [DIR]` (and `:session new …`) — launch a new application window in a separate terminal: its own session (`.bashrc_term_<NAME>` / `history_<NAME>.txt`), a shared data directory and tag DB. `DIR` — the working directory of the new session (the data directory by default); a name of `-`/empty — auto `sN` — the smallest free one **among running windows** (the `session_<name>.pid` registry in the data directory, see `src/session_registry.py`): files of closed sessions do not occupy a name, and once `s2` has closed, the name is free again. Secrets `$$` are not transferred. The `New session` button in the footer / `Ctrl+N`. The terminal — `$TERMINAL` (e.g. `kitty` / `alacritty -e`), otherwise from the system ones; launch — `$IDVJPY_LAUNCH`
- `:send <session|*> <command>` — forward a command to another session (a `:new` window): it is inserted into the target session's input, and the launch there happens with a separate Enter. `:send!` — run right away (`:send! <session|*> <command>`). `*` — to all sessions except yours. The command is materialized at the sender (`$VAR`/`$OUT`, aliases, and also `|@label`/`|@N` → `<source> | <command>`); secrets `$$` travel **by name** (`$TOKEN`), and a value that the target does not have is placed into its secret store (`secrets_<session>.json`, 0600, cleaned up on exit) — so the command will really run there, while the inbox, journal and history contain no value; the target's own value is not overwritten (the sender's journal shows what was transferred and what was left to the target). Buffer labels are per-session, so `|@…` expands into a full invocation (the source will run again in the target session); if the sender has no such label, the command is not sent. The exchange is via `inbox_<session>.jsonl` (0600) in the data directory; a message for a session that is not running waits for its start. It also arrives while you are typing — it is appended at the end without overwriting. Tab after `:send ` suggests session names (`*` — to all the others; the current one is marked). `:send` / `:send!` are written to `history_*.txt` (repeat with ↑, search `:h /`), but are not offered in the hints
- `:scope [add|rm|clear] …` — tag scope of **this window**: `:scope add git` keeps only the git handbook in the listings, `:scope rm k8s` hides k8s, `:scope clear` (or `:scope all`) shows everything again; with no arguments it reports the current state. It filters **lists and hints** (`?`, `??`, `?text`, `!`/Tab completions, the screensaver ticker); explicit refs and commands (`?tag`, `!tag[tid]`, `:run`, `:stats`, `:export`, `:alias`, `:send`) ignore the filter — saved chains and other windows' refs never break. A name is a handbook group (`linux`, `k8s`, `git`, …) or a single tag; an unknown name is an explicit error listing the groups. Kept per session: `scope_<session>.json` in the data directory (never written to SQLite, never travels with `:export`/`:backup`). The window title carries the marker (`IDvjPy_term · git · only git`). In full — `:? tags`
- `:welcome` — the seed catalog, as with an empty DB (click `--seed` / `.md`). At startup with a non-empty DB — a **Sections** block with live tags by handbook (`linux`, `k8s`, `git`, ops, `your own`)
- `:backup` — a snapshot of SQLite into `backups/` (like before `--seed`). It does not copy an empty database. To restore: copy the file over the working DB.
- `:screensaver` — the screensaver right away: **"matrix rain"** (default, `screensaver_matrix: true`) or the DevOps starfield (`screensaver_matrix: false`). The rain — falling columns of glyphs (the head is bright, the tail fades; the pace is slow and even — 1.8–6 lines/s at 20 fps, `TICK_SECONDS` / `MATRIX_*_SPEED` in `src/screensaver.py`); in the starfield the stars fly toward the viewer, closer — `k8s` / `git` / `!!`, along with them a live clock (`15:35:42`) and date (`2026-08-26`). The canvas switches on the fly: `:screensaver matrix` / `:screensaver stars`. Common to both canvases: at the top a bright-green ribbon across the full width with commands from the DB (`!tag[tid]  cmd`); at the bottom left — a command cheat sheet (typed left to right, indented from the edge); at the bottom right — load 1/5/15 and RAM (once a second from `/proc`), with the same indent from the right corner; in a narrow window the load may overlap the cheat sheet. Hidden handbooks (`#name--`) are not shown. Any key, click, wheel scroll or mouse movement closes/resets the idle state (it does not go into the input). A command arriving from another session (`:send`) also dismisses the screensaver — otherwise the journal would stay closed. Timeout: `screensaver_idle` in `settings.yml` (seconds, `0` = off). `:screensaver 0` / `:screensaver 120` — for this session. While the TUI is asleep (a real TTY: `> cmd`, Ctrl+O, `:ed`), the screensaver does not open, and after returning the idle time is counted anew — so `> vim` no longer meets you with the screensaver. `screensaver_stars: false` — a starfield without flying dust/tokens (does not affect the matrix canvas). Idle like in Norton Commander: stars fly toward the viewer; closer — `k8s` / `git` / `!!`. Along with them fly a live clock (`15:35:42`) and date (`2026-08-26`). At the top a bright-green ribbon across the full width with commands from the DB (`!tag[tid]  cmd`). At the bottom left — a command cheat sheet (typed left to right, indented from the edge as before); at the bottom right — load 1/5/15 and RAM (once a second from `/proc`), with the same indent from the right corner; in a narrow window the load may overlap the cheat sheet. Hidden handbooks (`#name--`) are not shown. Any key, click, wheel scroll or mouse movement closes/resets the idle state (it does not go into the input). A command arriving from another session (`:send`) also dismisses the screensaver — otherwise the journal would stay closed. Timeout: `screensaver_idle` in `settings.yml` (seconds, `0` = off). `:screensaver 0` / `:screensaver 120` — for this session. `screensaver_stars: false` — without flying dust/tokens (the clock, ribbon and load remain).
- `:r` — the focused block's command into the input; `:r N` — N blocks back (0 = the last one)
- `:cmd [N] [show]` — materialize the block's command with the current `$VAR` values (including secrets) → to the clipboard; `show` also prints it (secrets become visible)
- `:log [N]` (F7) — the full block output in a scrollable **Line-API** viewer (no 300-line truncation): arrows/PgUp/PgDn, Esc/q; text search — `/` (Enter — forward, `n`/`N` — next/previous match, Esc — close the search field), the matching line is highlighted entirely (accent background + bold); `f` — keep only lines with matches (a repeated `f` or Esc restores the whole output, the line number in the subtitle is the original one). `N` — blocks back (0 = the focused/last one). The lines are real (like F3), plus `STDERR`, if there was any. `y` copies the source file path (raw `:md` view); for block output — an explicit `No file path to copy`
- `:name [<label>|<label>-|-]` — a buffer label: labels the focused (otherwise the last finished) block so that you can pipe from it without re-running the source (`:name buff` → `|@buff awk '{...}'`). Without an argument — a list of labels, `<label>-` — remove one, `-` — all. Also a dialog via `F8`. The label is visible in the block header (`[buff]`); in history the pipe is written as a full invocation `<source> | <command>`
- `:/text` / `:g` / `:n` / `:N` — search across journal lines (from a block `/` opens `:/`; `n`/`N` — next / previous)
- `:export tag [file.json]` / `:import file.json` — one tag to JSON and back (import always assigns new `tid`; the schema is shared with the CLI, `src/db_transfer.py`); `:export * [library.md]` — the whole library as a Markdown catalog, `:export * library.json` — the whole library as canonical JSON (empty `tag_filter` — exactly the file `library_url` needs; same as `backup_db.py export` without `--tag`)
- `:import <https://…>` — fetch a shared library by URL: the journal shows a **change plan** first and the ready `:import <url> --yes` line goes into the input — the import starts on the second Enter (nothing is written without it). `--dry` — the plan only, `--yes` — no confirmation, `--insecure` — allow `http://` (by default `https://` only), a bare `:import` uses `library_url` from `settings.yml`. Limit 2 MB, timeout 10 s, a proxy with a login is the same `$PROXY_USER` / `$PROXY_PASS` as for `:update`. A payload carrying the value of a live `$$`-secret is refused, and rows with `run:auto` directives are called out in the plan. Full reference — `:? import`

**Export/import: what to use when** (one implementation of the formats — `src/db_transfer.py`, the CLI is a thin shell):

| Task | TUI | CLI (`python3 backup_db.py …`) |
|------|-----|--------------------------------|
| Move tags to another instance / machine | `:export tag file.json`, then `:import file.json` there | `export` / `import [--mode merge\|replace] [--keep-tids]` |
| Pull a shared library from a URL | `:import https://… --dry`, then `:import <url> --yes` (bare `:import` — `library_url` from `settings.yml`) | — |
| Publish your library for the team | `:export * library.json` (the file goes to the app's cwd), put it on an https host and set the link in `library_url` | `export library.json` — the file lands in `backups/`; the `backup_db.py` launcher lives in the repository directory, so from the data directory call it by path: `python3 /path/to/IDvjPy/backup_db.py …` |
| An exact snapshot of the DB (roll back "as it was") | `:backup` | `backup` (SQLite snapshot + JSON + CSV); return with `restore <file>` |
| Edit commands and comments in a spreadsheet | — | `export-csv` / `import-csv` (addressable by `tid`), `export-tags-csv` / `import-tags-csv` |
| Look at the tags without the TUI | `:stats`, `??` | `list [--show-comments]` |
| The library catalog as Markdown | `:export * library.md` | — |
| Commands as bash functions | `:alias tag\|* [file.sh]` | — |

JSON is transfer and merging (global `id`s from the file are never taken: a foreign `id` used to be able to overwrite another row; by default every row gets a new `tid`). An **exact snapshot** is only the SQLite copy. Details — [`backup_db.md`](../../backup_db.md).

The two kinds of file are told apart: a single-tag file (`tag_filter`) means "add" (new `tid`s, nothing is overwritten), a whole-library file (no `tag_filter` — produced by `backup_db.py export` and `backup`) means "update": an already taken `(tag, tid)` pair is skipped (`skip_existing`), a free one is added. A remote import runs nothing by itself, but `:run <tag>` will execute `auto` steps without confirmation — that is why the plan warns about `run:` directives. The download runs in a background thread (the UI stays responsive) and only over `https://`: the content goes straight into the tag library.
- `:playbook [file.yml]` — record the commands of this session (Enter) as YAML for `--demo` / `:run` (default `playbook.yml`). `:playbook -` — preview in the journal; `:playbook clear` — forget what was recorded. Keys (Tab/F5) and the mouse are not recorded. In the YAML: `loop: true` / `loop: N` — loop the steps (Esc — stop); see [DEMO.md](../../DEMO.md).
- `:run <tag|file.yml> [--step] [--dry]` — run a chain (runbook): `auto` steps run in a row and wait for completion, `manual` inserts the line into the input and waits for Enter (you can edit it), `prompt` waits for a typed line. A step error stops the run, `Esc` / `:run stop` too. Step modes of a tag — by directives in comments (`run:manual`, `run:prompt`, `run:pause=2`, `run:continue`); if the tag has no such directive at all, the plan warns: all steps will go `auto` (this is what an outdated seed or your own tag saved before v1.124 looks like). `--step` — every step with Enter, `--dry` — plan only. Full help — `:? run`, a ready chain — `:run vapprole`. A relative path to YAML is resolved from the process cwd (when launched via an alias from `~` — from `~`): it is more reliable to keep the chain as a tag — the DB lives in the data directory
- `:update` — compare `VERSION` with GitHub [`webxed/IDvjPy`](https://github.com/webxed/IDvjPy) `main`. At startup the same happens if `check_updates: true` (it writes to the journal only if GitHub is newer). Proxy with a login: `$PROXY_USER` / `$PROXY_PASS` in `.bashrc_term` (plus `HTTPS_PROXY` / `HTTP_PROXY`).
- `:theme [name]` — the TUI theme (`dark` / `light` / `nord` / `matrix` / …); written to `settings.yml`. The `d` key — dark/light. A custom application theme — `matrix`: green phosphor on almost black, as in the screensaver (input, hint and help borders also become green)
- `:lang [code]` — the interface language: without an argument — the current one and a list of available ones, `:lang ru` — select and save (the `language` key in `settings.yml`), `:lang auto` — follow `$LANG`/`$LC_ALL`. One-off: `--lang` / `$IDVJPY_LANG`. Shipped languages: `en`, `ru`, `zh`. The texts are in `src/locales/`: the catalog `src/locales/<lang>.yml` plus parts `src/locales/<lang>/*.yml` (`screensaver`, `seed`), the `:?` help — as files `src/locales/help/<lang>/*.txt` (`en` is the source of truth, missing keys fall back to it); what switches is messages, `:` command hints, the `:welcome` catalog, screensaver lines and the `:?` help. A new language applies to text printed after the switch (already shown blocks are not redrawn). Commands, tag names, settings keys and file names are not translated (the slogan "Define your variables…" and the logo too: they are the brand). The same `language` key selects the text layer of the demo tours (`src/demos/text/<lang>/`), seed comments (`src/seed_text/<lang>/` — that is why `--seed` writes captions in this language) and the handbook catalog (`docs/<lang>/`)
- `:relang [code]` — translate the comments of an **already seeded** library (tag captions and command hints in the DB) into another language without re-running `--seed`: without an argument — help, `:relang ru` — translate, `:relang auto` — by `$LANG`. It touches only canonical seed tags and commands; your tags, commands and **hand-edited** comments remain. Before writing — a DB snapshot into `backups/`. The same from the terminal: `python3 src/relang.py --lang ru [--db …]`
- Highlighting of the focused block is soft: 25% of the theme's primary color over the block background (previously a solid `$primary-darken-1` was blinding, especially on a large `:?`); it works in any theme
- `:kctx` — the cluster journal (`kctx.json`): a list of clusters; `:kctx <cluster>` — login (`klogin <c>` or `kubectl config use-context <c>`) and previously used `NS`/`POD`/… sets (with a single set it is applied right away: there is nothing to choose from); `:kctx N` — apply set N; `:kctx <cluster> N` — login and apply in one line. Which variables count as the journal — the `kctx_vars` key in settings.yml
- `:?` — this help inside the TUI; `:? <topic>` — details for a command group (`:? llm`, `:? tags`, `:? calc`, `:? run`, `:? i`, `:? md`, `:? vars`, `:? kctx`, `:? send`, `:? session`; the topic list is in the help's "Help topics" section and in the hints after `:? `). An unknown topic is an explicit error listing the topics; a glued `:?calc` tells you to add a space

## Hotkeys

| Key | Action |
|---------|----------|
| `Tab` | From the input — to the last journal block (`:h`, `:?`, a command); if the hint list is open — apply the candidate. With the command list open (`:` ) `Tab` inserts `:command ` instead of moving to the journal |
| `Esc` | Focus the input. In line mode: first turn the mode off, a repeated Esc — to the input |
| `↑` / `↓` | In the input: the session feed (everything typed — `:` commands, `?tags`, `!references`, `#tags`, `$VAR=…`; except `$$secrets`) + the filtered `history_<instance>.txt`; the order is as you typed, the last line comes back first; the text typed filters the matches; journal scrolling if the focus is on a block |
| `PgUp` / `PgDn` | Scroll the journal by a page; the **visible** block becomes active (without jumping to its start). From the input — go to viewing. While the view is scrolled up, new output is appended at the bottom and does **not** move the view and focus (`:watch`, an `:llm` answer, an incoming `:send`); follow mode returns when you scroll to the bottom or press Enter |
| click on a block | Focus the block without scrolling to the start (`terminal_mouse: true`). With an empty DB: clicking `--seed` — into the input; `.md` — the handbook. In `??`: clicking a tag inserts `!tag ` at the cursor position (does not overwrite the line). In the `?` hint list, clicking a row inserts `?tag` and runs the query right away |
| `Ctrl+click` / double click on `!tag[tid]` | Insert the reference and run it at once — like two Enters (expand into a command and run). A reference without a tid is only inserted; other references (`:` commands, `.md`, `--seed`) are not run |
| mouse wheel | Scroll the journal — 3 lines per click (the same in `:log`/F7 and the md viewer), the reading position is remembered (see reading mode). The arrows remain one line each |
| drag the mouse over the journal | Select text inside the application; release the button — the selection is immediately in the clipboard (CLIPBOARD/PRIMARY/OSC 52). `Shift`+drag — the terminal's native selection (if you prefer it) |
| `Space` / `←` `→` | Collapse / expand a block |
| `F3` | Copy the full stdout of the block |
| `Ctrl+C` | If there is a mouse selection — copy it; otherwise the whole input line / the whole journal block (like F3) |
| `F5` | JSON viewer for the focused (or last) block |
| `Ctrl+N` | A new application window (a separate session) in a new terminal — the same as `:new`; the `New session` button in the footer |
| `Ctrl+O` | Show the console under the application (like in Midnight Commander): the TUI steps aside and the real terminal is visible — the output of commands from `>` (`htop`/`vim`/`less`) lives there, in the scrollback. Return — any key |
| `F6` | Plain output (no Rich tags or ANSI colors, easier to select with the mouse) |
| `F7` | The full block output in the Line-API viewer — the same as `:log` (search inside — `/`, `n`/`N`, `f` — only lines with matches) |
| `F8` | The block label dialog (`:name`): enter a label, Enter — save, empty — remove, Esc — cancel; then `\|@label command` |
| `F2` | Line mode in the block |
| `Shift+Insert` / `Ctrl+V` | Paste into the input (does not overwrite what is already typed). In line mode `Ctrl+V` appends the current line. Line breaks in the pasted text become spaces (the field is single-line), and a long line is fully visible in the grey preview under the field |
| Right click | Paste the clipboard into the input line — also when the focus is in the journal or the completion list (no need to put the cursor in the input first, and the focus does not jump). Links (`--seed`, `.md`, `:commands`) are not triggered by a right click, and it does not overwrite the selection: text selected with the mouse is already in the clipboard (copied on release), and the right click pastes exactly that |
| `Ctrl+D` | Clear the whole input line |
| `Ctrl+W` / `Ctrl+Backspace` | In the input: delete the word left of the cursor (handy for trimming pasted output, e.g. from `kubectl`). `Ctrl+Backspace` works where the terminal sends it as a separate key; universally — `Ctrl+W` |
| `Ctrl+F` / `Ctrl+Delete` | In the input: delete the word right of the cursor |
| `Ctrl+←` / `Ctrl+→` | In the input: move the cursor a word left / right |
| `Ctrl+Z` | In the input: undo the last change (typing / deletion / word-delete / paste). The stack is reset after a command is submitted and by `Ctrl+D` |
| `d` | Dark / light theme (`textual-dark` / `textual-light`), saved to `settings.yml`. When the focus is in the input, `d` is typed as a letter; the theme: focus the journal or `:theme` |

### Line mode (block in focus)

Off by default. To enable: `Tab`/`PgUp` onto a block, then `Enter` or `F2`.

| Key | Action |
|---------|----------|
| `↑` / `↓` | Line up / down (at the block's edge — journal scrolling again) |
| `Home` / `End` | First / last line |
| `Enter` | Copy the line (without trailing spaces) and go to the input, cursor at the end |
| `Shift+Enter` / `Ctrl+V` | Append the line to the input with a space, stay in the block |
| `Esc` / `F2` | Turn the mode off |
| `/` | Start a search (`:/` in the input) |
| `n` / `N` | Next / previous match |

If `Shift+Enter` behaves as a regular Enter, the terminal does not distinguish the keys — use **Ctrl+V**. While the focus is in the input, `Ctrl+V` still pastes from the buffer.

### JSON viewer

- `Enter` on a node: close the viewer, set `$JSON`, the clipboard, a draft in the input: `| jq '.path'` (from a block) or `jq '.path'` (from a file).
- Example: `jq $JSON test.json`.
- Search: `/` or the field at the top; `n` / `N` — next / previous match.

## Autocompletion

- Paths: `./` `../` `/` `~`, a token with `/`, `cd`/`pushd`, or a non-flag argument after a command.
- **Tab** for a path replaces only the current token; a full command from history/DB — the whole line.
- A directory with `/` (`ls ~/`) — the first candidate is the directory itself; Enter runs it, Tab does not force a child path.
- An exact match of the whole line hides the list, Enter runs the command.
- **A trailing space** (`ls` + space): the list closes, Enter runs what is typed, not a longer candidate (`ls -la`). To take a candidate — Tab without a trailing space.
- **`!file` / `!kube`**: right after `!` a list of tags (`[file, kube, log]`). Tab selects a tag, then commands: `<139> file[1]  ls -la`, into the input — `!file[1]`. Assembly `#file !file[1] | !file[2]` with a decoding at the top of the list.
- **`?`**: you type `?` — a list of tags with a hint (`?vault  (2)  HashiCorp Vault`: the number of commands and the tag comment), letters filter, frequently used ones are higher. `Tab`/`Enter` insert `?vault` without running (launch — a separate Enter), a **click on a row** substitutes `?vault` and runs the query right away; only `?vault` is a link, the rest is plain text. `??` (all commands) does not get interrupted by the list, `?vault ` (a space) closes it.

## Configuration

Templates — [`src/settings/<lang>.yml`](../../src/settings) (`en`, `ru`, `zh`; keys and values are the same, only the comments differ; the file of the language selected in `auto` mode is copied; the personal `settings.yml` does not go into git):

```yaml
max_lines: 100000
history_lines: 20
history_keep: 500            # the history tail as a feed; older — without repeats. 0 = do not compact. :h compact
history_completion: true     # hints from history_*.txt while typing (including `@`/`>` lines); false — only ↑ and :h /
history_queries: [llm, cht, rg, md, run, send, send!]  # invocations of these `:` commands — to history (↑/:h), but not to hints; [] — do not write
md_dir: ""                   # directory of documents for `:rg` (e.g. an Obsidian vault); empty — cwd
md_render_lines: 1000        # threshold for a formatted `:md`; longer — raw view in the Line-API viewer
database_tags_file: mytags.db
backup_dir: backups          # DB snapshots (:backup, --seed)
command_timeout: 10          # 0 = no timeout
terminal_mouse: true         # true — the mouse belongs to the app (click/wheel; dragging selects and copies to the clipboard); false — selection via the terminal
theme: textual-dark          # `d` / `:theme`; saved on change (matrix — green phosphor on black)
language: en                 # interface language (en, ru, zh): :lang / --lang / $IDVJPY_LANG; `auto` — by $LANG; texts in src/locales (parts <lang>/*.yml, help in help/<lang>/)
check_updates: true          # at startup: compare VERSION with GitHub main; :update always
library_url: ""              # static source for a bare `:import` — a shared library JSON over https; empty — off
screensaver_idle: 120        # idle (keys/click/scroll/mouse) → screensaver; 0 = off. :screensaver — right away
screensaver_matrix: true     # screensaver canvas: true — "matrix rain", false — starfield (:screensaver matrix|stars — one-off)
screensaver_stars: true      # starfield: flying stars; false — black canvas (the clock/ribbon/load remain)
k8s_completion: false        # names of k8s resources from the cluster in the hints (`kubectl get pod <Tab>`)
file_completion: auto        # file hints: auto | paths | off (see below)
kctx_vars: [NS, POD, DEPLOY, SVC, ING, APP, CTR, QUOTA, RELEASE, CHART, VALUES]  # cluster journal variables (:kctx); [] — off
line_api_blocks: true        # journal blocks (commands and info blocks) on the Textual Line API (render_line); false — the previous Static
llm_render_markdown: true    # the `:llm` answer — formatted markdown; false — plain text (F6 disables it once)
ansi_colors: true            # ANSI colors of command output as in a terminal; false — plain text (F6 disables it once)
clear_clipboard_after_secret: false  # pasting a value into `$$NAME=…` clears CLIPBOARD/PRIMARY
editor: nano                 # `:ed`; arguments allowed (code --wait); empty → $VISUAL/$EDITOR
```

Variables are read from `.bashrc_term_<instance>` (priority) and `.bashrc_term` (supplements). Format: `export VAR=val` or `VAR=val`. If the files are missing, [`src/.bashrc_term.example`](../../src/.bashrc_term.example) is copied at startup. In the running application: `:env` or editing the file from `> vim .bashrc_term_default` (after exiting, the TTY re-reads the files and picks up the `export` of the same shell). TTY exports are not written into `.bashrc_term` by themselves — for that, use `$VAR=val`.

The DB file (`database_tags_file`, `mytags.db` by default) is **not** in git. On first launch an empty SQLite schema is created; the journal shows the seed script catalog (at the top, without jumping down). Clicking the green `--seed` inserts the command into the input; Enter runs it; then `??` (or ~5 s). Clicking a `.md` name or `:md file.md` opens the handbook with formatting (Esc closes). `terminal_mouse: true` is required.

The tag scope (`:scope`) lives next to the history: `scope_<session>.json` in the data directory. It is a property of the window, not of the data: the library and the run counters are untouched, so the filter never travels with `:export` / `:backup` / `:send`, and neighbouring windows keep their tags. No file — no filter.

## Architecture

- **`CommandRunner`** — the Textual application
- **`JournalScroll`** — the journal: scrolling with keys activates the visible block
- **`CommandBlock`** / **`InfoBlock`** / **`QueryResultsBlock`** — journal blocks
- **`LineNavigable`** — the line cursor in a block

Modules in [`src/`](../../src/): [`app.py`](../../src/app.py), [`database_v2.py`](../../src/database_v2.py), [`command_parser_v2.py`](../../src/command_parser_v2.py), [`json_viewer.py`](../../src/json_viewer.py), [`md_viewer.py`](../../src/md_viewer.py), [`screensaver.py`](../../src/screensaver.py), [`seed_catalog.py`](../../src/seed_catalog.py), [`ingress_analyzer.py`](../../src/ingress_analyzer.py), [`app.tcss`](../../src/app.tcss). The root [`app.py`](../../app.py) only launches the TUI.

Session and behavior details: [`COMPACT_SUMMARY.md`](../../COMPACT_SUMMARY.md). How the DB is read: [`DATABASE.md`](../../DATABASE.md).

## Tests

```bash
python3 -m pytest tests/ -v
```

## Command handbooks

Each seed overwrites **only its own** tags. The comment language comes from `language` in `settings.yml` (or `$IDVJPY_LANG`): the base text lives in `src/seed_*.py`, translations — in `src/seed_text/<lang>/<handbook>.yml` (see `src/seed_text/README.md`), so by default `--seed` writes English captions, and `language: ru` — the previous Russian ones. An already seeded library does not change language: you can change the captions without replacing tags with the `:relang <code>` command (or `python3 src/relang.py --lang ru`), while a full repeated `--seed` will replace its own tags (not the user's); before that, `:backup` is useful. If the DB already has commands, a SQLite snapshot is written into `backups/` before the replacement (`mytags-pre-git-YYYYMMDD-HHMMSS.db` and the like; the directory — `backup_dir` in `settings.yml`). The same manually: `:backup` → `mytags-manual-….db`. It does not copy an empty database. `seed_ops.py` makes **one** snapshot for all modules. To restore: copy the file over `mytags.db`.

k8s investigation chains: [`K8S_CHAINS.md`](../../K8S_CHAINS.md). `python3 src/seed_k8s_chains.py --seed` (does not touch `proc` / `file` / `net` / `kube`).

The handbooks themselves are also per language: the base ones are in `docs/` (the k8s overview — in the root), English translations — in `docs/en/`, Chinese — in `docs/zh/`. `:md SEED_GIT_COMMANDS.md` opens the text of the selected language (`handbook_md_path` first looks in `docs/<lang>/`, otherwise the base).

| Script | Documentation | Tags |
|--------|--------------|------|
| `python3 src/seed_linux_commands.py --seed` | [`SEED_LINUX_COMMANDS.md`](../../docs/SEED_LINUX_COMMANDS.md) | `proc` `file` `net` `kube` |
| `python3 src/seed_k8s_chains.py --seed` | [`K8S_CHAINS.md`](../../K8S_CHAINS.md) | `kpod` `klog` `kquota` … |
| `python3 src/seed_git.py --seed` | [`SEED_GIT_COMMANDS.md`](../../docs/SEED_GIT_COMMANDS.md) | `git` `gstat` `gsync` … |
| `python3 src/seed_ops.py --seed` | all ops below | docker + helm + ansible + http + netfw + ip + netdbg + data + host + disk + systemd + sysinfo + sysstat + vault + text + pipe + rsync + find + recon + ssh + pkg + user |
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

`seed_ops.py` does not touch linux / k8s / git. `seed_http` / `seed_netfw` / `seed_ip` / `seed_netdbg` / `seed_rsync` / `seed_recon` / `seed_ssh` do not overwrite the linux `net` tag. `seed_text` / `seed_pipe` / `seed_find` / `seed_disk` do not overwrite `file`. `seed_host` does not overwrite `smart` / `df`. `seed_systemd` / `seed_sysinfo` / `seed_sysstat` do not overwrite `proc` / `logs`.

## Dependencies

- `textual==7.3.0`, `rich==14.3.0`, `pyperclip==1.11.0`, `PyYAML==6.0.3`, `Pygments==2.19.2`, `portalocker`

## License

[MIT](../../LICENSE). Authors: markovskiy.pavel & Gemini, GLM, CLAUDE, DeepSeek, Grok.
