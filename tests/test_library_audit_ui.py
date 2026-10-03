"""TUI audit records cover explicit user mutations only."""
from __future__ import annotations

import json

from app import CommandRunner
from library_audit import AUDIT_FILE
from tests.conftest import info_texts, submit


async def test_save_delete_restore_and_audit_command(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#demo echo PRIVATE_COMMAND")
        audit_path = isolated_home / AUDIT_FILE
        records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
        assert records[-1]["action"] == "save"
        assert records[-1]["tags"] == ["demo"]
        assert "PRIVATE_COMMAND" not in audit_path.read_text(encoding="utf-8")

        await submit(pilot, "#demo=PRIVATE_COMMENT")
        await submit(pilot, "#demo-")
        await submit(pilot, "#demo!")
        await submit(pilot, ":audit 10")

        raw = audit_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in raw.splitlines()]
        assert [record["action"] for record in records] == [
            "save", "comment", "soft-delete", "restore"
        ]
        assert "PRIVATE_COMMAND" not in raw
        assert "PRIVATE_COMMENT" not in raw
        output = "\n".join(info_texts(app))
        assert "Recent library audit events" in output
        assert "soft-delete" in output and "restore" in output
