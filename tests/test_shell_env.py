"""Unit tests for extracted shell_env helpers."""
from shell_env import (
    command_requests_placeholder,
    expand_aliases,
    last_nonempty_line,
    parse_alias_line,
    parse_bashrc_assignment,
    quote_shell_path,
    substitute_variables,
    unexpanded_variables,
)


def test_parse_bashrc_assignment():
    assert parse_bashrc_assignment("export NS=prod") == ("NS", "prod")
    assert parse_bashrc_assignment("EDITOR=nvim") == ("EDITOR", "nvim")
    assert parse_bashrc_assignment('FOO="bar baz"') == ("FOO", "bar baz")
    assert parse_bashrc_assignment("# comment") is None
    assert parse_bashrc_assignment("1BAD=x") is None


def test_parse_alias_line():
    assert parse_alias_line("alias k='kubectl'") == ("k", "kubectl")
    assert parse_alias_line('alias ll="ls -la"') == ("ll", "ls -la")
    assert parse_alias_line("echo hi") is None


def test_substitute_variables_prefers_local_env():
    out = substitute_variables("echo $NS", {"NS": "local"}, {"NS": "os"})
    assert out == "echo local"
    out = substitute_variables("echo $MISSING", {}, {})
    assert out == "echo $MISSING"
    out = substitute_variables(
        'echo "${WIKI_COUNTRY}US"',
        {"WIKI_COUNTRY": "https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2#"},
        {},
    )
    assert out == 'echo "https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2#US"'
    out = substitute_variables("echo $OUT", {}, {"OUT": "from-os"}, extra={"OUT": "US"})
    assert out == "echo US"
    assert command_requests_placeholder("echo Hello, $OUT")
    assert command_requests_placeholder("echo ${OUT}")
    assert not command_requests_placeholder("echo $OUTPUT")
    assert not command_requests_placeholder("echo hi")


def test_substitute_variables_skips_named_refs():
    """`skip` оставляет имя как есть — так `:send` пересылает `$NAME`, а не значение."""
    env = {"TOKEN": "s3cr3t", "NS": "team-a"}
    out = substitute_variables("curl -H $TOKEN -n $NS", env, {}, skip={"TOKEN"})
    assert out == "curl -H $TOKEN -n team-a"
    # Скобочная форма — тоже имя, а не значение.
    assert substitute_variables("echo ${TOKEN}", env, {}, skip={"TOKEN"}) == "echo ${TOKEN}"
    assert substitute_variables("echo $TOKEN", env, {}) == "echo s3cr3t"
    assert substitute_variables("echo $TOKEN", env, {}, skip=set()) == "echo s3cr3t"


def test_last_nonempty_line_does_not_split_whole_buffer():
    assert last_nonempty_line("") == ""
    assert last_nonempty_line("US\n") == "US"
    assert last_nonempty_line("aaa\nbbb\n") == "bbb"
    huge = ("x" * 10000 + "\n") * 50 + "tail-line\n\n"
    assert last_nonempty_line(huge) == "tail-line"


def test_unexpanded_variables_lists_leftovers():
    assert unexpanded_variables("$DIR/pod-$OUT.json") == ["DIR", "OUT"]
    assert unexpanded_variables("${A}-${B}") == ["A", "B"]
    assert unexpanded_variables("$A-$A") == ["A"]  # без повторов
    assert unexpanded_variables("plain/path.txt") == []
    assert unexpanded_variables("") == []


def test_expand_aliases_positional_and_classic():
    aliases = {
        "klogin": "tsh kube login $1",
        "ll": "ls -la",
    }
    assert expand_aliases("klogin my-cluster", aliases) == "tsh kube login my-cluster"
    assert "$1" not in expand_aliases("klogin my-cluster", aliases)
    assert expand_aliases("ll /tmp", aliases) == "ls -la /tmp"
    assert expand_aliases("echo hi", aliases) == "echo hi"


def test_expand_aliases_keeps_shell_syntax_after_args():
    """Хвост строки после аргументов — shell-синтаксис, его нельзя цитировать.

    Регрессия: `klogin prod || kubectl config use-context prod` при теле
    `tsh kube login $1` пересобиралось через shlex.quote и уходило в tsh
    аргументом «'||'» (`tsh: error: unexpected ||`) — падал вход в кластер,
    который делает `:kctx <cluster>`.
    """
    aliases = {
        "klogin": "tsh kube login $1",
        "kget": "kubectl -n $NS get $1",
        "kall": "kubectl $@",
        "ll": "ls -la",
    }
    assert (
        expand_aliases("klogin prod || kubectl config use-context prod", aliases)
        == "tsh kube login prod || kubectl config use-context prod"
    )
    assert expand_aliases("kget pod | grep api", aliases) == "kubectl -n $NS get pod | grep api"
    assert expand_aliases("kget pod > pods.txt", aliases) == "kubectl -n $NS get pod > pods.txt"
    assert (
        expand_aliases("kget pod 2>&1 | head -5", aliases)
        == "kubectl -n $NS get pod 2>&1 | head -5"
    )
    # `$@` забирает аргументы, но синтаксис после них остаётся синтаксисом
    # (shlex.quote цитирует только то, что требует кавычек).
    assert expand_aliases("kall get pod || echo no", aliases) == "kubectl get pod || echo no"
    assert expand_aliases("kall 'my pod' || echo no", aliases) == "kubectl 'my pod' || echo no"
    # Классический алиас: тело + остаток строки как есть (было так и раньше).
    assert expand_aliases("ll /tmp || echo no", aliases) == "ls -la /tmp || echo no"
    # Кавычки в неиспользованных аргументах не теряются.
    assert expand_aliases('kget pod "my pod"', aliases) == 'kubectl -n $NS get pod "my pod"'


def test_diff_exported_env_skips_shell_bookkeeping():
    from shell_env import diff_exported_env, skip_tty_env_key

    assert skip_tty_env_key("SHLVL")
    assert skip_tty_env_key("BASH_FUNC_foo%%")
    assert not skip_tty_env_key("KUBECONFIG")
    before = {"PATH": "/a", "SHLVL": "1", "KUBECONFIG": "old"}
    after = {"PATH": "/a", "SHLVL": "2", "KUBECONFIG": "/x", "NEW": "1"}
    updates, removed = diff_exported_env(before, after)
    assert updates == {"KUBECONFIG": "/x", "NEW": "1"}
    assert removed == []
    updates, removed = diff_exported_env(
        {"KEEP": "1", "GONE": "x", "SHLVL": "1"},
        {"KEEP": "1"},
    )
    assert updates == {}
    assert removed == ["GONE"]


def test_wrap_tty_command_dumps_exports(tmp_path):
    import json
    import subprocess
    import sys

    from shell_env import wrap_tty_command

    env_path = tmp_path / "env.json"
    pwd_path = tmp_path / "pwd"
    script = wrap_tty_command(
        "export IDVJOPY_TTY_VAR=from-child; exit 7",
        str(env_path),
        str(pwd_path),
        sys.executable,
    )
    completed = subprocess.run(["bash", "-c", script], check=False)
    assert completed.returncode == 7
    data = json.loads(env_path.read_text(encoding="utf-8"))
    assert data["IDVJOPY_TTY_VAR"] == "from-child"
    assert pwd_path.read_text(encoding="utf-8")


def test_parse_standalone_cd():
    from shell_env import parse_standalone_cd

    assert parse_standalone_cd("cd") == ""
    assert parse_standalone_cd("cd /tmp") == "/tmp"
    assert parse_standalone_cd("cd -- /tmp") == "/tmp"
    assert parse_standalone_cd("cd -") == "-"
    assert parse_standalone_cd("cd foo && ls") is None
    assert parse_standalone_cd("echo cd") is None


def test_quote_shell_path_quotes_only_when_needed():
    """Обычный путь — как есть; пробелы и метасимволы — в кавычках."""
    assert quote_shell_path("./plain.md") == "./plain.md"
    assert quote_shell_path("./a-b_c/d.py") == "./a-b_c/d.py"
    assert quote_shell_path("./отчёт.md") == "./отчёт.md"  # кириллица не метасимвол
    assert quote_shell_path("./my report.md") == "'./my report.md'"
    assert quote_shell_path("/tmp/a b/c.md") == "'/tmp/a b/c.md'"
    assert quote_shell_path("./a$b;c.md") == "'./a$b;c.md'"
    assert quote_shell_path("./it's.md") == "'./it'\"'\"'s.md'"  # форма shlex.quote


def test_quote_shell_path_keeps_tilde_outside_quotes():
    """Внутри кавычек тильда не раскрывается — `~` остаётся снаружи."""
    assert quote_shell_path("~") == "~"
    assert quote_shell_path("~/my report.md") == "~/'my report.md'"
    assert quote_shell_path("~user/my report.md") == "~user/'my report.md'"
