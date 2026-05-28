from pathlib import Path

import pytest

from app.core.config import settings
from app.storage.bootstrap import bootstrap, reset_bootstrap


@pytest.fixture()
def mcp_audit_env(tmp_path: Path):
    original = {
        "data_dir": settings.data_dir,
        "sqlite_path": settings.sqlite_path,
        "lancedb_dir": settings.lancedb_dir,
        "api_key": settings.api_key,
        "require_mcp_api_key": settings.require_mcp_api_key,
    }
    settings.data_dir = tmp_path / "data"
    settings.sqlite_path = settings.data_dir / "gcd.sqlite3"
    settings.lancedb_dir = settings.data_dir / "lancedb"
    settings.api_key = None
    settings.require_mcp_api_key = False
    reset_bootstrap()
    bootstrap(settings)
    yield
    for key, value in original.items():
        setattr(settings, key, value)
    reset_bootstrap()


def test_mcp_high_risk_write_tools_emit_explicit_audit_action(mcp_audit_env):
    from app.mcp_server import gcd_add_memory, gcd_delete_memory, gcd_list_audit_logs

    created = gcd_add_memory(content="MCP audit target", agent_id="codex")
    gcd_delete_memory(created["memory"]["id"])

    logs = gcd_list_audit_logs(limit=20)
    mcp_logs = [log for log in logs if log["action"] == "mcp.high_risk_write"]

    assert mcp_logs
    assert mcp_logs[0]["target_id"] == "gcd_delete_memory"
    assert mcp_logs[0]["metadata"]["risk"] == "high"
    assert mcp_logs[0]["metadata"]["operation"] == "delete_memory"
    assert "api_key" not in mcp_logs[0]["metadata"]
