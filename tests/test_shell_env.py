"""Unit tests for extracted shell_env helpers."""
from shell_env import (
    expand_aliases,
    parse_alias_line,
    parse_bashrc_assignment,
    substitute_variables,
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


def test_expand_aliases_positional_and_classic():
    aliases = {
        "klogin": "tsh kube login $1",
        "ll": "ls -la",
    }
    assert expand_aliases("klogin my-cluster", aliases) == "tsh kube login my-cluster"
    assert "$1" not in expand_aliases("klogin my-cluster", aliases)
    assert expand_aliases("ll /tmp", aliases) == "ls -la /tmp"
    assert expand_aliases("echo hi", aliases) == "echo hi"
