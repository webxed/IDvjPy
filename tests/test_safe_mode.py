"""Safe-mode heuristics: pure shlex inspection, no execution.

The detector is intentionally a heuristic: these tests pin what it *does*
recognize and, just as importantly, that quoted text is data and that a clean
result is not treated as a safety guarantee.
"""
from __future__ import annotations

import pytest

from safe_mode import command_risks


@pytest.mark.parametrize(
    "command, expected",
    [
        ("rm -rf /tmp/x", ("rm",)),
        ("/bin/rm file", ("rm",)),
        ("chmod 777 x", ("chmod",)),
        ("chown root x", ("chown",)),
        ("dd if=/dev/zero of=/dev/sda", ("dd",)),
        ("mkfs.ext4 /dev/sdb1", ("mkfs",)),
        ("kubectl apply -f k.yaml", ("kubectl apply",)),
        ("kubectl delete pod api", ("kubectl delete",)),
        ("terraform apply", ("terraform apply",)),
        ("terraform destroy -auto-approve", ("terraform destroy",)),
        ("helm upgrade rel chart", ("helm upgrade",)),
        ("helm uninstall rel", ("helm uninstall",)),
        ("git push origin main", ("git push",)),
        ('sqlite3 mytags.db "DELETE FROM commands"', ("sqlite3 SQL mutation",)),
        ('sqlite3 db "DROP TABLE tags"', ("sqlite3 SQL mutation",)),
        ('sqlite3 db "UPDATE commands SET command=1"', ("sqlite3 SQL mutation",)),
    ],
)
def test_recognizes_common_destructive_operations(command, expected):
    assert command_risks(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        "kubectl get pods",
        "terraform plan",
        "helm list",
        "git status",
        "git push --dry-run",  # still push; asserted separately below
    ],
)
def test_safe_or_unknown_commands_are_not_flagged(command):
    if command == "git push --dry-run":
        assert command_risks(command) == ("git push",)
    else:
        assert command_risks(command) == ()


def test_sqlite_select_and_string_literals_are_not_mutations():
    assert command_risks('sqlite3 db "SELECT * FROM commands"') == ()
    # DELETE inside a quoted SQL literal is data, not a statement.
    assert command_risks("sqlite3 db \"SELECT 'DELETE FROM t'\"") == ()


@pytest.mark.parametrize(
    "command, expected",
    [
        ("sudo rm -rf /", ("rm",)),
        ("sudo -u root rm -rf /", ("rm",)),
        ("env FOO=1 rm x", ("rm",)),
        ("FOO=1 rm x", ("rm",)),
        ("nohup rm x", ("rm",)),
        ("bash -c 'rm -rf /'", ("rm",)),
        ("sh -c 'kubectl delete pod x'", ("kubectl delete",)),
    ],
)
def test_wrappers_and_assignments_are_unwrapped(command, expected):
    assert command_risks(command) == expected


@pytest.mark.parametrize(
    "command, expected",
    [
        ("ls; rm -rf /tmp/x", ("rm",)),
        ("kubectl get pods && kubectl delete pod x", ("kubectl delete",)),
        ("true || chmod 000 x", ("chmod",)),
        ("(cd /tmp && rm x)", ("rm",)),
    ],
)
def test_chains_are_split_into_command_positions(command, expected):
    assert command_risks(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        "echo 'rm -rf /'",
        'echo "kubectl delete pod api"',
        "printf '%s' 'git push'",
        "grep rm file",
    ],
)
def test_quoted_text_is_data_not_execution(command):
    assert command_risks(command) == ()


def test_unparsed_syntax_is_reported_honestly():
    assert command_risks("rm 'unclosed") == ("unparsed shell syntax",)


def test_result_never_contains_arguments_or_secret_values():
    risks = command_risks("sudo rm -rf /tmp/secret-token-abc123")
    assert risks == ("rm",)
    assert all("abc123" not in name for name in risks)
