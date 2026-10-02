"""Offline explanation of a shell command for ``:explain``.

This is deliberately a small, deterministic catalogue rather than a shell parser or
an LLM.  It never starts a process, resolves a command from PATH, reads a file, or
makes a network request.  Unknown syntax and programs are reported plainly.
"""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass

from rich.markup import escape

from i18n import t
from safe_mode import command_risks

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = frozenset({"sudo", "env", "command", "exec", "nohup"})
# Wrapper options that take a separate value; skipping only the flag would treat
# the value (a user or variable name) as the program.
_WRAPPER_VALUE_FLAGS = frozenset({
    "-u", "-g", "-h", "-p", "-C", "-T",
    "--user", "--group", "--host", "--prompt", "--unset", "--chdir",
})
_REDIRECTIONS = frozenset({">", ">>", "<", "<<"})
# find actions that write or execute; a plain find only reads.
_FIND_MUTATORS = frozenset({
    "-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf", "-fls",
})

# Program → a deliberately short purpose key.  The catalogue teaches commonly
# encountered DevOps tools without pretending that all shell commands are known.
_PURPOSES = {
    "git": "git",
    "kubectl": "kubectl",
    "helm": "helm",
    "terraform": "terraform",
    "sqlite3": "sqlite3",
    "docker": "docker",
    "systemctl": "systemctl",
    "journalctl": "journalctl",
    "ss": "ss",
    "lsof": "lsof",
    "rg": "rg",
    "grep": "grep",
    "find": "find",
    "curl": "curl",
    "wget": "wget",
    "ssh": "ssh",
    "scp": "scp",
    "rsync": "rsync",
    "tar": "tar",
    "df": "df",
    "du": "du",
    "ps": "ps",
    "ls": "ls",
    "cat": "cat",
    "less": "less",
    "bat": "bat",
    "cd": "cd",
}

# Subcommands that only read; anything else is treated as potentially mutating.
_READ_SUBCOMMANDS = {
    "git": frozenset({"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "grep"}),
    "kubectl": frozenset({"get", "describe", "logs", "explain", "version", "cluster-info", "api-resources", "api-versions", "auth"}),
    "helm": frozenset({"list", "status", "history", "show", "search", "template", "get", "env", "version"}),
    "terraform": frozenset({"show", "version", "graph", "output"}),
    "docker": frozenset({"ps", "images", "inspect", "logs", "stats", "version", "info"}),
    "systemctl": frozenset({"status", "is-active", "is-enabled", "list-units", "list-unit-files", "show"}),
    "sqlite3": frozenset(),
}

_FLAG_KEYS = {
    "git": {"--short": "short", "--branch": "branch", "--porcelain": "porcelain", "--stat": "stat", "--oneline": "oneline", "--all": "all", "--no-pager": "no_pager"},
    "kubectl": {"-A": "all_namespaces", "--all-namespaces": "all_namespaces", "-n": "namespace", "--namespace": "namespace", "-o": "output", "--output": "output", "--context": "context"},
    "curl": {"-I": "head", "--head": "head", "-s": "silent", "--silent": "silent", "-L": "location", "--location": "location", "-o": "output_file", "--output": "output_file"},
    "rg": {"-n": "line_numbers", "--line-number": "line_numbers", "-i": "ignore_case", "--ignore-case": "ignore_case", "-l": "files_with_matches", "--files-with-matches": "files_with_matches"},
}


@dataclass(frozen=True)
class CommandExplanation:
    """Safe-to-display structural summary; it deliberately keeps no arguments."""

    program: str | None
    purpose: str | None
    effect: str
    flags: tuple[tuple[str, str], ...]
    risks: tuple[str, ...]
    parse_error: bool = False


def _words(command: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = "#"
        return list(lexer)
    except ValueError:
        return None


def _program_and_args(words: list[str]) -> tuple[str | None, list[str]]:
    """Find the first executable after simple assignments and wrappers.

    A pipeline or a compound expression is rejected by the caller before this is
    reached, so a single segment is described at a time.
    """
    index = 0
    while index < len(words) and _ASSIGNMENT.match(words[index]):
        index += 1
    while index < len(words):
        token = words[index]
        if token and all(char in ";&|()\n" for char in token):
            return None, []
        program = os.path.basename(token)
        index += 1
        if program not in _WRAPPERS:
            return program, words[index:]
        while index < len(words) and words[index].startswith("-"):
            if words[index] == "--":
                index += 1
                break
            index += 2 if words[index] in _WRAPPER_VALUE_FLAGS else 1
        while index < len(words) and program == "env" and _ASSIGNMENT.match(words[index]):
            index += 1
    return None, []


def _effect(program: str, args: list[str]) -> str:
    if program == "sqlite3":
        sql = " ".join(args)
        if re.search(r"\b(DELETE|DROP|UPDATE|INSERT|CREATE|ALTER|VACUUM)\b", sql, re.I):
            return "changes_data"
        # Without a narrowly recognizable inline SELECT, the CLI may create a
        # database, run dot commands, or read SQL interactively.
        if args and re.match(r"^\s*SELECT\b", args[-1], re.I):
            return "reads_data"
        return "unknown_effect"
    if any(arg in _REDIRECTIONS for arg in args):
        return "unknown_effect"
    if program == "find" and any(arg in _FIND_MUTATORS for arg in args):
        return "may_change"
    subcommand = next((arg for arg in args if not arg.startswith("-")), "")
    if program in _READ_SUBCOMMANDS:
        return "reads_state" if subcommand in _READ_SUBCOMMANDS[program] else "may_change"
    if program in {"curl", "wget", "ssh", "scp"}:
        return "remote_connection"
    if program == "rsync":
        return "copies_files"
    if program == "tar":
        return "archives"
    if program in {"find", "rg", "grep", "journalctl", "ss", "lsof", "df", "du", "ps", "ls", "cat", "less", "bat"}:
        return "reads_state"
    if program == "cd":
        return "changes_directory"
    return "unknown_effect"


def analyse(command: str) -> CommandExplanation:
    """Return a local structural explanation, without executing ``command``."""
    words = _words(command)
    if words is None:
        return CommandExplanation(None, None, "unknown_effect", (), command_risks(command), True)
    # A compound shell expression has several execution paths; do not present its
    # first segment as the whole command.
    if any(token and all(char in ";&|()\n" for char in token) for token in words):
        return CommandExplanation(None, None, "unknown_effect", (), command_risks(command))
    program, args = _program_and_args(words)
    if program is None:
        return CommandExplanation(None, None, "unknown_effect", (), command_risks(command))
    flag_keys = _FLAG_KEYS.get(program, {})
    flags = tuple((flag, flag_keys[flag]) for flag in args if flag in flag_keys)
    return CommandExplanation(
        program=program,
        purpose=_PURPOSES.get(program),
        effect=_effect(program, args),
        flags=flags,
        risks=command_risks(command),
    )


def format_explanation(command: str) -> str:
    """Format a localized Rich block without reproducing command arguments."""
    result = analyse(command)
    lines = [t("explain.header"), t("explain.no_execution"), ""]
    if result.parse_error:
        lines.append(t("explain.parse_error"))
    if result.program is None:
        lines.append(t("explain.no_program"))
    else:
        purpose = t(f"explain.purpose.{result.purpose}") if result.purpose else t("explain.purpose.unknown")
        lines.append(t("explain.program", name=escape(result.program), purpose=purpose))
        lines.append(t(f"explain.effect.{result.effect}"))
        if result.flags:
            lines.extend(("", t("explain.flags")))
            for flag, key in result.flags:
                lines.append(t("explain.flag_row", flag=escape(flag), meaning=t(f"explain.flag.{key}")))
    if result.risks:
        lines.extend(("", t("explain.risks", risks=escape(", ".join(result.risks)))))
    lines.extend(("", t("explain.footer")))
    return "\n".join(lines)
