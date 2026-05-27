
from dataclasses import dataclass

from app.assets import service as asset_service
from app.core.schemas import AssetCreate, AssetSearchRequest, AssetUpdate
from app.runtime.components import RuntimeComponents


@dataclass(frozen=True)
class AssetHandler:
    components: RuntimeComponents

    def create_asset(self, payload: AssetCreate) -> dict:
        return asset_service.create_asset(payload)

    def get_asset(self, asset_id: str) -> dict:
        return asset_service.get_asset(asset_id)

    def list_assets(self, limit: int = 100, status: str | None = None, asset_kind: str | None = None, trust_level: str | None = None) -> list[dict]:
        return asset_service.list_assets(limit=limit, status=status, asset_kind=asset_kind, trust_level=trust_level)

    def update_asset(self, asset_id: str, payload: AssetUpdate) -> dict:
        return asset_service.update_asset(asset_id, payload)

    def search_assets(self, payload: AssetSearchRequest) -> dict:
        return asset_service.search_assets(payload)
