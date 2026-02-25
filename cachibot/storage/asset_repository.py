"""Repository for assets (file attachments)."""

from sqlalchemy import delete, select

from cachibot.models.asset import Asset
from cachibot.storage import db
from cachibot.storage.models.asset import Asset as AssetModel


class AssetRepository:
    """Repository for asset CRUD operations."""

    async def create(self, asset: Asset) -> None:
        """Create a new asset record."""
        async with db.ensure_initialized()() as session:
            obj = AssetModel(
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
            session.add(obj)
            await session.commit()

    async def get(self, asset_id: str) -> Asset | None:
        """Get an asset by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(AssetModel).where(AssetModel.id == asset_id))
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_entity(row)

    async def get_by_owner(self, owner_type: str, owner_id: str) -> list[Asset]:
        """Get all assets for an owner (room or chat)."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(AssetModel)
                .where(AssetModel.owner_type == owner_type, AssetModel.owner_id == owner_id)
                .order_by(AssetModel.created_at.desc())
            )
            rows = result.scalars().all()
        return [self._row_to_entity(row) for row in rows]

    async def delete(self, asset_id: str) -> str | None:
        """Delete an asset. Returns storage_path if deleted, None otherwise."""
        async with db.ensure_initialized()() as session:
            # Get the storage path before deleting
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
