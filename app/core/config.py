from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("data")
    sqlite_path: Path = Path("data") / "gcd_v2.sqlite3"
    lancedb_dir: Path = Path("data") / "lancedb_v2"
    embedding_dim: int = 64
    api_key: str | None = None
    service_name: str = "global-context-db"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001
    mcp_path: str = "/mcp"
    require_mcp_api_key: bool = False

    class Config:
        env_prefix = "GCD_"


settings = Settings()
