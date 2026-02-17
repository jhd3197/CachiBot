"""
Repository for custom instructions — CRUD, versioning, and rollback.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from cachibot.models.instruction import InstructionModel, InstructionVersionModel
from cachibot.storage import db
from cachibot.storage.models.instruction import InstructionRecord, InstructionVersion


class InstructionRepository:
    """Async CRUD for custom instructions with version history."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        data: dict,
        bot_id: str,
        author: str,
    ) -> InstructionModel:
        """Create a new instruction and its initial version."""
        now = datetime.now(timezone.utc)
        instr_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        async with db.ensure_initialized()() as session:
            record = InstructionRecord(
                id=instr_id,
                bot_id=bot_id,
                name=data["name"],
                description=data.get("description"),
                prompt=data["prompt"],
                system_prompt=data.get("system_prompt"),
                output_format=data.get("output_format", "text"),
                model_hint=data.get("model_hint"),
                temperature=data.get("temperature"),
                max_tokens=data.get("max_tokens"),
                input_variables=data.get("input_variables", []),
                few_shot_examples=data.get("few_shot_examples"),
                created_by=author,
                version=1,
                is_active=True,
                category=data.get("category", "custom"),
                tags=data.get("tags", []),
                created_at=now,
                updated_at=now,
            )
            session.add(record)

            version = InstructionVersion(
                id=version_id,
                instruction_id=instr_id,
                version=1,
                prompt=data["prompt"],
                system_prompt=data.get("system_prompt"),
                output_format=data.get("output_format", "text"),
                model_hint=data.get("model_hint"),
                temperature=data.get("temperature"),
                max_tokens=data.get("max_tokens"),
                input_variables=data.get("input_variables", []),
                few_shot_examples=data.get("few_shot_examples"),
                author=author,
                commit_message="Initial version",
                created_at=now,
            )
            session.add(version)
            await session.commit()

        return self._row_to_model(record)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, instruction_id: str) -> InstructionModel | None:
        """Get a single instruction by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(InstructionRecord).where(InstructionRecord.id == instruction_id)
            )
            row = result.scalar_one_or_none()
        return self._row_to_model(row) if row else None

    async def get_by_bot(self, bot_id: str) -> list[InstructionModel]:
        """Get all instructions for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(InstructionRecord)
                .where(InstructionRecord.bot_id == bot_id)
                .order_by(InstructionRecord.updated_at.desc())
            )
            rows = result.scalars().all()
        return [self._row_to_model(r) for r in rows]

    async def get_by_name(self, bot_id: str, name: str) -> InstructionModel | None:
        """Look up an instruction by bot_id + name."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(InstructionRecord).where(
                    InstructionRecord.bot_id == bot_id,
                    InstructionRecord.name == name,
                )
            )
            row = result.scalar_one_or_none()
        return self._row_to_model(row) if row else None

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        instruction_id: str,
        changes: dict,
        author: str,
        commit_message: str | None = None,
    ) -> InstructionModel | None:
        """Update an instruction and create a new version."""
        now = datetime.now(timezone.utc)

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(InstructionRecord).where(
                    InstructionRecord.id == instruction_id
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                return None

            # Apply changes
            for key, value in changes.items():
                if value is not None and hasattr(record, key):
                    setattr(record, key, value)

            new_version_num = record.version + 1
            record.version = new_version_num
            record.updated_at = now

            # Create version snapshot
            version = InstructionVersion(
                id=str(uuid.uuid4()),
                instruction_id=instruction_id,
                version=new_version_num,
                prompt=record.prompt,
                system_prompt=record.system_prompt,
                output_format=record.output_format,
                model_hint=record.model_hint,
                temperature=record.temperature,
                max_tokens=record.max_tokens,
                input_variables=record.input_variables,
                few_shot_examples=record.few_shot_examples,
                author=author,
                commit_message=commit_message or f"Updated to v{new_version_num}",
                created_at=now,
            )
            session.add(version)
            await session.commit()
            await session.refresh(record)

        return self._row_to_model(record)

    # ------------------------------------------------------------------
    # Delete (soft)
    # ------------------------------------------------------------------

    async def delete(self, instruction_id: str) -> bool:
        """Soft-delete an instruction by setting is_active=False."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(InstructionRecord)
                .where(InstructionRecord.id == instruction_id)
                .values(is_active=False, updated_at=datetime.now(timezone.utc))
            )
            await session.commit()
            return result.rowcount > 0

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    async def get_versions(
        self, instruction_id: str
    ) -> list[InstructionVersionModel]:
        """Get version history for an instruction."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(InstructionVersion)
                .where(InstructionVersion.instruction_id == instruction_id)
                .order_by(InstructionVersion.version.desc())
            )
            rows = result.scalars().all()
        return [self._version_to_model(r) for r in rows]

    async def rollback(
        self,
        instruction_id: str,
        version_number: int,
        author: str,
    ) -> InstructionModel | None:
        """Rollback an instruction to a previous version."""
        async with db.ensure_initialized()() as session:
            # Find the target version
            result = await session.execute(
                select(InstructionVersion).where(
                    InstructionVersion.instruction_id == instruction_id,
                    InstructionVersion.version == version_number,
                )
            )
            target = result.scalar_one_or_none()
            if not target:
                return None

            # Load current record
            result = await session.execute(
                select(InstructionRecord).where(
                    InstructionRecord.id == instruction_id
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                return None

            now = datetime.now(timezone.utc)
            new_version_num = record.version + 1

            # Restore fields from the target version
            record.prompt = target.prompt
            record.system_prompt = target.system_prompt
            record.output_format = target.output_format
            record.model_hint = target.model_hint
            record.temperature = target.temperature
            record.max_tokens = target.max_tokens
            record.input_variables = target.input_variables
            record.few_shot_examples = target.few_shot_examples
            record.version = new_version_num
            record.updated_at = now

            # Create rollback version
            version = InstructionVersion(
                id=str(uuid.uuid4()),
                instruction_id=instruction_id,
                version=new_version_num,
                prompt=target.prompt,
                system_prompt=target.system_prompt,
                output_format=target.output_format,
                model_hint=target.model_hint,
                temperature=target.temperature,
                max_tokens=target.max_tokens,
                input_variables=target.input_variables,
                few_shot_examples=target.few_shot_examples,
                author=author,
                commit_message=f"Rollback to v{version_number}",
                created_at=now,
            )
            session.add(version)
            await session.commit()
            await session.refresh(record)

        return self._row_to_model(record)

    # ------------------------------------------------------------------
    # Converters
    # ------------------------------------------------------------------

    def _row_to_model(self, row: InstructionRecord) -> InstructionModel:
        return InstructionModel(
            id=row.id,
            bot_id=row.bot_id,
            name=row.name,
            description=row.description,
            prompt=row.prompt,
            system_prompt=row.system_prompt,
            output_format=row.output_format,
            model_hint=row.model_hint,
            temperature=row.temperature,
            max_tokens=row.max_tokens,
            input_variables=row.input_variables or [],
            few_shot_examples=row.few_shot_examples,
            created_by=row.created_by,
            version=row.version,
            is_active=row.is_active,
            category=row.category,
            tags=row.tags or [],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _version_to_model(self, row: InstructionVersion) -> InstructionVersionModel:
        return InstructionVersionModel(
            id=row.id,
            instruction_id=row.instruction_id,
            version=row.version,
            prompt=row.prompt,
            system_prompt=row.system_prompt,
            output_format=row.output_format,
            model_hint=row.model_hint,
            temperature=row.temperature,
            max_tokens=row.max_tokens,
            input_variables=row.input_variables or [],
            few_shot_examples=row.few_shot_examples,
            author=row.author,
            commit_message=row.commit_message,
            created_at=row.created_at,
        )
