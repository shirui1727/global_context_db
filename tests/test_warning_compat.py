from pathlib import Path

from app.core.config import Settings
from app.storage import vector_store


def test_settings_uses_pydantic_v2_model_config():
    assert hasattr(Settings, "model_config")
    assert Settings.model_config.get("env_prefix") == "GCD_"


def test_init_vector_store_uses_list_tables_when_available(monkeypatch, tmp_path: Path):
    calls: list[str] = []

    class FakeDb:
        def list_tables(self):
            calls.append("list_tables")
            return []

        def table_names(self):
            calls.append("table_names")
            raise AssertionError("deprecated table_names should not be used")

        def create_table(self, name, data, mode):
            calls.append(f"create_table:{name}:{mode}")

    monkeypatch.setattr(vector_store.lancedb, "connect", lambda _: FakeDb())

    vector_store.init_vector_store(tmp_path / "lancedb")

    assert "list_tables" in calls
    assert "table_names" not in calls
