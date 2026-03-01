"""Repository for assets (file attachments)."""

from sqlalchemy import delete, select

from cachibot.models.asset import Asset
from cachibot.storage.base import BaseRepository
from cachibot.storage.models.asset import Asset as AssetModel


class AssetRepository(BaseRepository[AssetModel, Asset]):
    """Repository for asset CRUD operations."""

    _model = AssetModel

    async def create(self, asset: Asset) -> None:
        """Create a new asset record."""
        await self._add(
            AssetModel(
                id=asset.id,
                owner_type=asset.owner_type,
                owner_id=asset.owner_id,
                name=asset.name,
                original_filename=asset.original_filename,
                content_type=asset.content_type,
                size_bytes=asset.size_bytes,
                storage_path=asset.storage_path,
                uploaded_by_user_id=asset.uploaded_by_user_id,
                uploaded_by_bot_id=asset.uploaded_by_bot_id,
                metadata_json=asset.metadata,
                created_at=asset.created_at,
            )
        )

    async def get(self, asset_id: str) -> Asset | None:
        """Get an asset by ID."""
        return await self.get_by_id(asset_id)

    async def get_by_owner(self, owner_type: str, owner_id: str) -> list[Asset]:
        """Get all assets for an owner (room or chat)."""
        return await self._fetch_all(
            select(AssetModel)
            .where(AssetModel.owner_type == owner_type, AssetModel.owner_id == owner_id)
            .order_by(AssetModel.created_at.desc())
        )

    async def delete(self, asset_id: str) -> str | None:
        """Delete an asset. Returns storage_path if deleted, None otherwise."""
        async with self._session() as session:
            result = await session.execute(
                select(AssetModel.storage_path).where(AssetModel.id == asset_id)
            )
            path = result.scalar_one_or_none()
            if path is None:
                return None

            await session.execute(delete(AssetModel).where(AssetModel.id == asset_id))
            await session.commit()
            return path

    def _row_to_entity(self, row: AssetModel) -> Asset:
        """Convert a database row to an Asset entity."""
        return Asset(
            id=row.id,
            owner_type=row.owner_type,
            owner_id=row.owner_id,
            name=row.name,
            original_filename=row.original_filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            storage_path=row.storage_path,
            uploaded_by_user_id=row.uploaded_by_user_id,
            uploaded_by_bot_id=row.uploaded_by_bot_id,
            metadata=row.metadata_json if row.metadata_json else {},
            created_at=row.created_at,
        )
