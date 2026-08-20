"""Unit tests for extracted shell_env helpers."""
from shell_env import (
    expand_aliases,
    last_nonempty_line,
    parse_alias_line,
    parse_bashrc_assignment,
    substitute_variables,
    command_requests_placeholder,
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


def test_last_nonempty_line_does_not_split_whole_buffer():
    assert last_nonempty_line("") == ""
    assert last_nonempty_line("US\n") == "US"
    assert last_nonempty_line("aaa\nbbb\n") == "bbb"
    huge = ("x" * 10000 + "\n") * 50 + "tail-line\n\n"
    assert last_nonempty_line(huge) == "tail-line"


def test_expand_aliases_positional_and_classic():
    aliases = {
        "klogin": "tsh kube login $1",
        "ll": "ls -la",
    }
    assert expand_aliases("klogin my-cluster", aliases) == "tsh kube login my-cluster"
    assert "$1" not in expand_aliases("klogin my-cluster", aliases)
    assert expand_aliases("ll /tmp", aliases) == "ls -la /tmp"
    assert expand_aliases("echo hi", aliases) == "echo hi"


def test_parse_standalone_cd():
    from shell_env import parse_standalone_cd

    assert parse_standalone_cd("cd") == ""
    assert parse_standalone_cd("cd /tmp") == "/tmp"
    assert parse_standalone_cd("cd -- /tmp") == "/tmp"
    assert parse_standalone_cd("cd -") == "-"
    assert parse_standalone_cd("cd foo && ls") is None
    assert parse_standalone_cd("echo cd") is None
