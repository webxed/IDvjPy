"""Статичные тексты справки TUI (:? и :i).

Вынесено из src/app.py; маркер ``VER`` подменяется версией при показе ``:?``.
"""


MAIN_HELP_TEXT = """[bold]IDvjPy_term VER - Commands Help[/bold]

[bold]Application Commands (prefix :)[/bold]
  :? [calc]   - Show this help; `:? calc` — full calculator reference
  :q          - Quit application
  :w <file>   - Write output to file
  :h [N]      - Last N lines of history_<instance>.txt (default: 20)
  :h /text    - Search that file in completions (unique lines, newest first); Enter dumps a block
  :h compact  - Unique old history; keep the last history_keep lines as a sequence
  :c          - Clear all output blocks
  :json       - Open JSON viewer (from last block)
  :json <file>- Open JSON file in viewer
  :md <file>  - Open a handbook .md with formatting (Esc closes)
  :i          - Kubernetes Ingress Analyzer (see :i for details)
  :cd [path]  - Show or change the shell cwd (tags DB / history stay at launch dir)
  :fm [path]  - Open the OS file manager in a new window (cwd or path)
  :term [path] - Open a system terminal in a new window (cwd or path)
                $FILEMAN / $TERMINAL override the OS default
  :env        - Re-read .bashrc_term* (and ~/.bashrc aliases) into this process
  :session    - Show the current instance (history + .bashrc_term files)
  :session NAME - Switch to that instance or create it (tags DB stays shared)
  :welcome      - Seed catalog (same as empty-DB welcome; click --seed / .md)
  :backup       - Copy the command DB into backups/ (same snapshot as --seed)
  :screensaver  - Starfield; full-width ticker; bottom-left help; bottom-right load/mem (idle: screensaver_idle; 0 = off; screensaver_stars: false hides flying dust)
  :r          - Put the focused (or last) block command into the input
  :r N        - Put the command N blocks back into the input (0 = last)
  :kill [all] - Stop the running background command (focused block or the last one;
                `:kill all` stops every running command). SIGTERM, then SIGKILL.
  :watch <sec> <command> - Rerun <command> every <sec> seconds in one block
                (monitor like `watch -n`; ticks replace the text, they do not pile up)
                Stop: :watch stop, F4 / :kill, :c, or quit. One watch at a time.
  :mv <tag>[<tid>] <dst> - Move one command to another tag (new tid at the end)
  :mv <tag> <dst>   - Rename a whole tag (comment moves too)
  :stats            - Library usage summary: runs per tag, top-10 commands,
                never-run count. `!tag` completion sorts by usage.
  :/text  :g  - Search journal lines; :n / n next, :N / N prev. / on a block starts :/
  :export tag [file] - Write one tag to JSON
  :export * [file.md] - Write the whole library as a Markdown catalog
                (grouped by tag; tag and command comments included)
  :diff         - Unified diff of the focused block stdout vs the previous
                CommandBlock (no focus: the last two blocks)
  :alias <tag> [file.sh] / :alias * [library.sh] - export commands as
                bash functions tag_tid() { ...; }
  :llm          - List LLM providers from llm_providers.yml (see example in src/)
  :llm <provider> <message> - Ask the given LLM via its API (headers/body from config;
                secrets come from the environment, e.g. $DEEPSEEK_API_KEY)
  :llm <message> - Ask the default provider (`default:` in llm_providers.yml)
                $OUT — last non-empty line of the focused/last CommandBlock
                $BLOCK — full stdout of that block (also ${OUT} / ${BLOCK})
                @file — attach a text file (UTF-8, ≤200 KB; several: @a.py @b.log;
                literal @ — @@). Size limit: provider key max_attachment_bytes
                Context: provider key history_turns: N keeps the last N user/assistant
                pairs in memory for this session; :llm reset [<provider>|*] clears it
                Placeholders: %MSG% (JSON-safe), %MSG_RAW%, %SYSTEM%, %MODEL%, %HISTORY%
                Tab completes provider names after `:llm `
                Proxy 407: set $PROXY_USER / $PROXY_PASS (as with :update)
  :o [N]        - Last N finished command outputs of this session (default 5)
  :o /text      - grep the stored outputs (stdout/stderr); survives :c
  :o clear      - Forget the stored outputs (memory only, not the DB)
  :kctx         - Cluster journal (kctx.json): list clusters; variables of the
                kubectl stack (NS POD DEPLOY SVC ING APP CTR QUOTA) are saved
                per cluster when set after login
  :kctx <cluster> - Log in (klogin <c> || kubectl config use-context <c>) and
                show previously used variable sets of that cluster
  :kctx <cluster> N - Log in and apply saved set N
  :kctx N       - Apply set N from the last shown list (:kctx N sets vars only)
  :import file       - Insert commands from that JSON (new tids)
  :theme [name] - Show or set TUI theme (saved in settings.yml)
  :playbook [file] - Write this session's commands as a --demo YAML (default playbook.yml)
  :playbook - / clear - Preview YAML in the journal / forget recorded lines
  :update     - Compare this VERSION with GitHub main (webxed/IDvjPy)
                Proxy 407: set $PROXY_USER / $PROXY_PASS (and HTTPS_PROXY)

[bold]Kubernetes Commands (prefix :i)[/bold]
  :i list             - List all ingresses
  :i list -n <ns>     - List ingresses in namespace
  :i ns <namespace>   - Describe namespace (JSON viewer)
  :i analyze <name>   - Analyze ingress
  :i check <service>  - Check service endpoints

[bold]Command Prefixes[/bold]
  (none)     - Execute shell command
               A line starting with a digit (or '(' / '-') is tried as a local
               calculator first:
               512Mi + 20% in Gi    (increase memory by 20% → = 0.6Gi)
               20% of 512Mi · 1/3 of 1Gi · 512Mi*30 in Gi · 1Gi/512Mi
               500m in cores · 2^10 · 524288 in Mi · (512+512)*2
               Units: B, KB/MB/GB/TB (×1000), KiB/MiB/GiB/TiB (×1024), k8s Ki/Mi/Gi, m.
               IPv4 networks too (like jodies.de/ipcalc): 192.168.1.0/24,
               10.1.2.3/255.255.255.0, or a bare 8.8.8.8 (classful default mask).
               Prefix for N hosts: 300 hosts → /23.
               Only when the whole line parses as math/units — otherwise shell
               (7z …, (cd …), 2>/dev/null …).
               Full calculator reference: type `:? calc`.
  > <cmd>    - Suspend TUI and run with a real TTY (htop, vim, ssh, less)
               After exit: import that shell's export/unset and $PWD; also :env
  @ <cmd>    - Run without command_timeout (long non-TTY jobs; stdout captured)
  #<tag>     - Save command to database with tag (`#tag cmd`, no space after #)
  # command  - Park a line in history without running (bash-style; space after #)
  #tag! / #tag!tid - Restore soft-deleted tag / command
  #name-- / #name!! - Hide / restore a handbook's tags (ansible, linux, k8s, …)
  ?          - Query database (? tags, ?<tag>, ?? grouped; ?? lists hidden tags)
               ?text (2+ chars, no such tag) = search commands/comments across all tags;
               rows: <id> tag[tid]; Esc → input, then Enter runs via !ID
               In ?? click a tag → insert `!tag ` / `!tag[tid] ` at the cursor
               (does not replace the line; terminal_mouse). Esc → input, then Enter.
  !tag / !tag[tid] - Type ! to list tags [file, kube, log]; Tab picks a tag
               Then commands show as `<id> tag[tid]  full command`; Tab inserts `!tag[tid]`
               Compose pipes/saves: `#file !file[1] | !file[2]` (preview expands refs)
  !N         - Execute command by ID from last query
  |<cmd>     - Pipe focused block output to command
  $OUT       - On demand: last non-empty line of the focused (or last) command block.
               Not stored in .bashrc_term. Type $OUT alone to peek. `$OUT=` is rejected.
  $VAR=val   - Set environment variable
  aliases    - From ~/.bashrc. If the body has $1 / $2 / $@, args are substituted
               (klogin cluster → tsh kube login cluster). Else the rest of the line
               is appended as in a classic alias.

[bold]Help topics[/bold]
  :? calc    - Calculator + ipcalc reference (syntax, units, percent, IPv4 subnets)

[bold]Navigation[/bold]
  ↑/↓        - Instance history file in input (typed text filters, case-insensitive); journal scroll when a block is focused
  Tab        - Focus last journal block (from input), including :h / :?
  Click      - Focus a journal block without jumping to its start
               (needs terminal_mouse: true in settings.yml)
  PgUp/PgDn  - Scroll the journal a page; the visible block becomes active
               (does not jump to the start of the block). From input: enter viewing.
  Esc        - Return to input (see also line-cursor mode)
  Space      - Toggle block collapse
  ← / →      - Collapse / expand focused block
  F3         - Copy full block output to clipboard
  F4         - Stop the running background command (same as :kill; SIGTERM group)
  Ctrl+C     - Copy the whole input line; if a journal block is focused, copy the block (same as F3)
  F5         - Open focused (or last command) block in JSON viewer
  F6         - Toggle simple (plain) output
  F2         - Toggle line-cursor mode (see below)
  Shift+Insert / Ctrl+V - Paste into input (does not replace existing text)
               In line-cursor mode Ctrl+V appends the current line instead
  Ctrl+D     - Clear the entire input line
  (k8s) kubectl get <res> <Tab> - live cluster resource names (k8s_completion: true)
  (JSON) Enter - Insert `jq 'path'` into input; also sets $JSON

[bold]Line-cursor mode[/bold]
  Focus a block (Tab or PgUp), then Enter or F2 to turn the mode on.
  Off by default: ↑/↓ still scroll the journal.
  On: current line is highlighted.
  ↑/↓        - Move by lines inside the block
  Home/End   - First / last line of the block
  Enter      - Copy current line (trailing spaces stripped) and jump to input
               Leading `# ` (parked history line) is removed so the command is ready
               Cursor goes to the end of the input; existing text is not selected
  Shift+Enter / Ctrl+V - Append current line to input, separated by a space
               Leading `# ` is stripped the same way
               Stay in the block (can append several lines)
               If Shift+Enter acts like Enter, the terminal does not distinguish
               the keys — use Ctrl+V. While the input is focused, Ctrl+V pastes
  Esc        - Turn mode off, stay on the block; Esc again returns to input
  F2         - Toggle mode on/off
  /          - Start journal search (:/ in the input)
  n / N      - Next / previous search hit (jumps to the matching line)

[bold]Variables[/bold]
  Use $VAR in commands for variable substitution
  $NS is auto-set when using -n in :i commands
  $JSON is set on Enter in JSON viewer (jq path of the selected node)
  Example: jq $JSON test.json
  $OUT is the last line of the focused/last command block, computed only when
  the command contains $OUT / ${OUT} (not kept in memory as a variable)
  $VAR also loaded from .bashrc_term and .bashrc_term_<instance>
  :env re-reads those files. After `> cmd`, exports from that same bash
  are imported (nested `> bash` then export inside does not: same-shell only).
  TTY exports stay in this session; `$VAR=val` still writes .bashrc_term_*

[bold]Demo mode[/bold]
  python3 app.py --demo              - Play bundled short tour (Esc stops)
  python3 app.py --demo full --demo-quit
  python3 app.py --demo path.yml --demo-speed 1.5
  Scenario YAML: src/demos/*.yml (type / keys / wait_command / loop). Manual script: DEMO.md
  loop: true / loop: N  - Repeat steps (forever or N times). Esc stops. Also a step: loop: 10
  :playbook [file.yml]  - Dump this session's typed lines as YAML; --demo that file
  :playbook -           - Preview in the journal.  :playbook clear — reset the log
  Keys (Tab/F5) and mouse are not recorded; edit the YAML if the tour needs them.

[bold]Handbooks (empty database)[/bold]
  First start with no commands lists seed scripts in the journal.
  python3 src/seed_linux_commands.py --seed
  python3 src/seed_k8s_chains.py --seed    # K8S_CHAINS.md — investigation chains
  python3 src/seed_git.py --seed
  python3 src/seed_ops.py --seed           # all ops except linux / k8s / git
  Type the command here, then ?? (or wait ~5s). Each --seed replaces only its own tags.
  Live DB is copied to backups/ first; :backup does the same snapshot by hand.
  Click a green --seed line to insert it, then Enter. Click a .md name (terminal_mouse) or :md SEED_LINUX_COMMANDS.md to read the handbook.
"""


INGRESS_HELP_TEXT = """[bold]Kubernetes Ingress Analyzer[/bold]

[bold]Usage:[/bold]
  :i list                   - List ingresses (uses $NS if set)
  :i list -n <namespace>    - List in namespace (saves to $NS)
  :i ns <namespace>         - Describe namespace (JSON viewer)
  :i analyze <name>         - Analyze ingress (uses $NS if set)
  :i analyze <name> -n <ns> - Analyze in namespace (saves to $NS)
  :i check <service>        - Check service endpoints (uses $NS)
  :i check <service> -n <ns>- Check in namespace (saves to $NS)

[bold]Namespace persistence:[/bold]
  When -n is specified, namespace is saved to $NS variable.
  Subsequent commands without -n will use $NS automatically.

[bold]Analysis includes:[/bold]
  • Ingress configuration (hosts, paths, TLS)
  • Nginx config from controller (via crossplane)
  • Service and endpoint health
  • Path-to-service mapping

[bold]Prerequisites:[/bold]
  • kubectl configured with cluster access
  • crossplane: pip install crossplane (optional, for nginx config parsing)
"""


CALC_HELP_TEXT = """[bold]Calculator — no special command or prefix[/bold]

A line that starts with a digit (or '(' / '-') is tried as a calculation first.
If the whole line parses, it is evaluated locally and shown as a journal block
with a `calc:` header (↑ repeats it; `$OUT` / `|` work on the result).
Everything that does not parse — `7z …`, `(cd … && …)`, `-la`, `2>/dev/null …` —
still runs in the shell as usual.

[bold]Arithmetic[/bold]
  1024*3 · (2+3)*4 · 10/3 · 2^10 · 1.5 + 0.25 · -5 + 8

[bold]Percent — % scales the value on the left[/bold]
  512Mi + 20%   increase by 20%   → = 614.4Mi
  512Mi - 15%   decrease by 15%
  512Mi * 20%   take 20% of it     → = 102.4Mi
  2 + 10%                          → = 2.2

[bold]of — a fraction of a value (same as *)[/bold]
  20% of 512Mi                    → = 102.4Mi
  1/3 of 1Gi in Mi                → = 341.333333Mi
  20% of (512Mi + 1Gi) in Mi      → = 307.2Mi

[bold]Unit conversion — in / to, or just type a value with a unit[/bold]
  512Mi in Gi        → = 0.5Gi
  512Mi in B         → = 536870912B
  1Gi in MB          → = 1073.741824MB
  524288 in Mi       → = 0.5Mi    (a bare number is read as bytes)
  1Gi / 512Mi        → 2          (how many times it fits)
  512Mi              → = 512Mi (= 536870912B)   (no `in`: largest unit + bytes)

[bold]Memory units[/bold] (k8s-style, attached or spaced: `512Mi`, `1.5 Gi`)
  B
  decimal (×1000):   K KB · M MB · G GB · T TB · P PB · E EB
  binary  (×1024):   Ki KiB · Mi MiB · Gi GiB · Ti TiB · Pi PiB · Ei EiB
  lowercase aliases: kb mb gb tb pb eb

[bold]CPU — milli-cores / cores[/bold]
  500m in cores      → = 0.5 cores
  0.5 in m           → = 500m
  100m * 4           → = 400m

[bold]k8s resource math[/bold]
  512Mi + 1Gi + 256Mi in Mi       → = 1792Mi
  512Mi*30 in Gi                  → = 15Gi
  512Mi + 20% in Gi               → = 0.6Gi  (limits with headroom)

[bold]IP / subnet — ipcalc (like jodies.de/ipcalc)[/bold]
  192.168.1.0/24              → network info for that prefix
  10.1.2.3/255.255.255.0      → prefix from a netmask
  8.8.8.8                     → classful default mask (class A → /8)
  300 hosts                   → smallest prefix for 300 hosts (/23, 510 usable)
  Shows: Address · Netmask (= prefix) · Wildcard · Network/prefix · HostMin ·
  HostMax · Broadcast · Hosts/Net, plus class / RFC1918 private and the binary
  form of every value. /31 = point-to-point (RFC 3021), /32 = host route.

[bold]Rules[/bold]
  • units are checked: `512Mi + 2` is an error (memory vs cpu/plain number)
  • memory ÷ memory gives a plain ratio (`1Gi / 512Mi` → 2)
  • `^` works on plain numbers only
  • a real command is never blocked: any line with words is left to the shell
"""
