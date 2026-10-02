"""Opt-in shell risk hints. Pure token inspection, not a shell or a sandbox.

Only recognizable command positions and common wrappers are inspected. Shell
functions, scripts, substitutions, eval, dynamic executable names and SQL from
files/stdin cannot be reliably classified. A clean result is NOT a safety proof.
"""
from __future__ import annotations

import os
import re
import shlex

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_MUTATIONS = {
    "kubectl": {"apply", "delete", "create", "replace", "patch", "edit", "scale", "drain"},
    "terraform": {"apply", "destroy"},
    "helm": {"upgrade", "uninstall", "install", "rollback", "delete"},
    "git": {"push"},
}
_VALUE_FLAGS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-T", "--user", "--group", "--host", "--prompt"},
    "env": {"-u", "--unset", "-C", "--chdir"},
    "kubectl": {"-n", "--namespace", "--context", "--kubeconfig", "--server", "--cluster", "--user", "--token"},
    "git": {"-C", "-c", "--git-dir", "--work-tree"},
    "helm": {"-n", "--namespace", "--kube-context", "--kubeconfig"},
}


def _skip_options(words: list[str], program: str) -> list[str]:
    i = 0
    while i < len(words):
        word = words[i]
        if word == "--":
            return words[i + 1:]
        if _ASSIGNMENT.match(word) and program == "env":
            i += 1
        elif word.startswith("-"):
            i += 2 if word in _VALUE_FLAGS.get(program, set()) else 1
        else:
            break
    return words[i:]


def _command_risks(words: list[str], depth: int) -> set[str]:
    while words and _ASSIGNMENT.match(words[0]):
        words = words[1:]
    if not words:
        return set()
    program = os.path.basename(words[0])
    args = words[1:]
    if program in {"sudo", "env", "command", "exec", "nohup"}:
        return _command_risks(_skip_options(args, program), depth)
    if program in {"bash", "sh", "dash", "zsh", "ksh"} and depth < 8:
        for index, word in enumerate(args):
            if word.startswith("-") and "c" in word[1:] and index + 1 < len(args):
                return set(command_risks(args[index + 1], _depth=depth + 1))
        return set()
    if program in {"rm", "chmod", "chown", "dd", "mkfs"} or program.startswith("mkfs."):
        return {program.split(".")[0]}
    if program in _MUTATIONS:
        rest = _skip_options(args, program)
        if rest and rest[0] in _MUTATIONS[program]:
            return {f"{program} {rest[0]}"}
    if program == "sqlite3":
        # Inspect inline SQL only, stripping SQL string literals and comments.
        sql = " ".join(args)
        sql = re.sub(r"'([^']|'')*'|--[^\n]*|/\*.*?\*/", " ", sql, flags=re.S)
        if re.search(r"\b(DELETE|DROP|UPDATE)\b", sql, re.I):
            return {"sqlite3 SQL mutation"}
    return set()


def command_risks(command: str, *, _depth: int = 0) -> tuple[str, ...]:
    """Recognized risks (stable names, never command arguments/secrets).

    Quotes remain single tokens, so echo 'rm -rf /' is data, not execution.
    Unsupported or malformed syntax is not claimed to be safe.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        tokens = list(lexer)
    except ValueError:
        return ("unparsed shell syntax",)
    risks: set[str] = set()
    segment: list[str] = []
    for token in [*tokens, ";"]:
        if token and all(char in ";&|()\n" for char in token):
            risks.update(_command_risks(segment, _depth))
            segment = []
        else:
            segment.append(token)
    return tuple(sorted(risks))
