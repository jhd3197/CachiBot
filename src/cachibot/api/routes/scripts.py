"""
Script API Routes

Endpoints for managing scripts, versions, and running scripts.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.automations import (
    AuthorType,
    Script,
    ScriptStatus,
    ScriptVersion,
)
from cachibot.models.group import BotAccessLevel
from cachibot.storage.automations_repository import (
    ScriptRepository,
    ScriptVersionRepository,
    TimelineEventRepository,
)

router = APIRouter(prefix="/api/bots/{bot_id}", tags=["scripts"])

# Repository instances
script_repo = ScriptRepository()
version_repo = ScriptVersionRepository()
timeline_repo = TimelineEventRepository()


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class ScriptResponse(BaseModel):
    """Response model for a script."""

    id: str
    botId: str
    name: str
    description: str | None
    sourceCode: str
    language: str
    status: str
    currentVersion: int
    tags: list[str]
    createdAt: str
    updatedAt: str
    createdBy: str
    timeoutSeconds: int
    maxMemoryMb: int
    allowedImports: list[str]
    runCount: int
    lastRunAt: str | None
    successRate: float

    @classmethod
    def from_script(cls, s: Script) -> "ScriptResponse":
        return cls(
            id=s.id,
            botId=s.bot_id,
            name=s.name,
            description=s.description,
            sourceCode=s.source_code,
            language=s.language,
            status=s.status.value if isinstance(s.status, ScriptStatus) else s.status,
            currentVersion=s.current_version,
            tags=s.tags,
            createdAt=s.created_at.isoformat(),
            updatedAt=s.updated_at.isoformat(),
            createdBy=s.created_by,
            timeoutSeconds=s.timeout_seconds,
            maxMemoryMb=s.max_memory_mb,
            allowedImports=s.allowed_imports,
            runCount=s.run_count,
            lastRunAt=s.last_run_at.isoformat() if s.last_run_at else None,
            successRate=s.success_rate,
        )


class ScriptVersionResponse(BaseModel):
    """Response model for a script version."""

    id: str
    scriptId: str
    versionNumber: int
    sourceCode: str
    diffFromPrevious: str | None
    authorType: str
    authorId: str | None
    commitMessage: str
    approved: bool
    approvedBy: str | None
    approvedAt: str | None
    createdAt: str

    @classmethod
    def from_version(cls, v: ScriptVersion) -> "ScriptVersionResponse":
        return cls(
            id=v.id,
            scriptId=v.script_id,
            versionNumber=v.version_number,
            sourceCode=v.source_code,
            diffFromPrevious=v.diff_from_previous,
            authorType=v.author_type.value
            if isinstance(v.author_type, AuthorType)
            else v.author_type,
            authorId=v.author_id,
            commitMessage=v.commit_message,
            approved=v.approved,
            approvedBy=v.approved_by,
            approvedAt=v.approved_at.isoformat() if v.approved_at else None,
            createdAt=v.created_at.isoformat(),
        )


# =============================================================================
# REQUEST MODELS
# =============================================================================


class CreateScriptBody(BaseModel):
    """Request body for creating a script."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sourceCode: str = Field(min_length=1)
    language: str = "python"
    tags: list[str] = Field(default_factory=list)
    timeoutSeconds: int = 300
    maxMemoryMb: int = 256
    allowedImports: list[str] = Field(default_factory=list)
    commitMessage: str = "Initial version"


class UpdateScriptBody(BaseModel):
    """Request body for updating a script."""

    name: str | None = None
    description: str | None = None
    sourceCode: str | None = None
    tags: list[str] | None = None
    timeoutSeconds: int | None = None
    maxMemoryMb: int | None = None
    allowedImports: list[str] | None = None
    commitMessage: str | None = None


# =============================================================================
# SCRIPT CRUD
# =============================================================================


@router.get("/scripts")
async def list_scripts(
    bot_id: str,
    status: str | None = None,
    limit: int = 50,
    user: User = Depends(require_bot_access),
) -> list[ScriptResponse]:
    """List all scripts for a bot."""
    script_status = ScriptStatus(status) if status else None
    scripts = await script_repo.get_by_bot(bot_id, status=script_status, limit=limit)
    return [ScriptResponse.from_script(s) for s in scripts]


@router.post("/scripts", status_code=201)
async def create_script(
    bot_id: str,
    body: CreateScriptBody,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ScriptResponse:
    """Create a new script with initial version."""
    from cachibot.models.automations import TimelineEvent
    from cachibot.services.script_sandbox import validate_script_before_save

    # Validate script code
    validation = validate_script_before_save(body.sourceCode)
    if not validation.allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Script validation failed: {validation.reason}",
        )

    now = datetime.now(timezone.utc)
    script_id = str(uuid.uuid4())

    script = Script(
        id=script_id,
        bot_id=bot_id,
        name=body.name,
        description=body.description,
        source_code=body.sourceCode,
        language=body.language,
        status=ScriptStatus.DRAFT,
        current_version=1,
        tags=body.tags,
        created_at=now,
        updated_at=now,
        created_by=f"user:{user.id}",
        timeout_seconds=body.timeoutSeconds,
        max_memory_mb=body.maxMemoryMb,
        allowed_imports=body.allowedImports,
    )
    await script_repo.save(script)

    # Create initial version
    version = ScriptVersion(
        id=str(uuid.uuid4()),
        script_id=script_id,
        version_number=1,
        source_code=body.sourceCode,
        author_type=AuthorType.USER,
        author_id=user.id,
        commit_message=body.commitMessage,
        approved=True,
        approved_by=user.id,
        approved_at=now,
        created_at=now,
    )
    await version_repo.save(version)

    # Create timeline event
    await timeline_repo.save(
        TimelineEvent(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            source_type="script",
            source_id=script_id,
            event_type="created",
            title=f"Script created: {body.name}",
            actor_type="user",
            actor_id=user.id,
            actor_name=user.username if hasattr(user, "username") else user.id,
            version_number=1,
            commit_message=body.commitMessage,
        )
    )

    return ScriptResponse.from_script(script)


@router.get("/scripts/{script_id}")
async def get_script(
    bot_id: str,
    script_id: str,
    user: User = Depends(require_bot_access),
) -> ScriptResponse:
    """Get a script by ID."""
    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")
    return ScriptResponse.from_script(script)


@router.patch("/scripts/{script_id}")
async def update_script(
    bot_id: str,
    script_id: str,
    body: UpdateScriptBody,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ScriptResponse:
    """Update a script. If source code changed, creates a new version."""
    from cachibot.models.automations import TimelineEvent

    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")

    # Update fields
    if body.name is not None:
        script.name = body.name
    if body.description is not None:
        script.description = body.description
    if body.tags is not None:
        script.tags = body.tags
    if body.timeoutSeconds is not None:
        script.timeout_seconds = body.timeoutSeconds
    if body.maxMemoryMb is not None:
        script.max_memory_mb = body.maxMemoryMb
    if body.allowedImports is not None:
        script.allowed_imports = body.allowedImports

    # If source code changed, validate and create new version
    if body.sourceCode is not None and body.sourceCode != script.source_code:
        from cachibot.services.script_sandbox import validate_script_before_save

        validation = validate_script_before_save(body.sourceCode)
        if not validation.allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Script validation failed: {validation.reason}",
            )

        now = datetime.now(timezone.utc)
        new_version_num = script.current_version + 1
        script.source_code = body.sourceCode
        script.current_version = new_version_num

        version = ScriptVersion(
            id=str(uuid.uuid4()),
            script_id=script_id,
            version_number=new_version_num,
            source_code=body.sourceCode,
            author_type=AuthorType.USER,
            author_id=user.id,
            commit_message=body.commitMessage or f"Updated to v{new_version_num}",
            approved=True,
            approved_by=user.id,
            approved_at=now,
            created_at=now,
        )
        await version_repo.save(version)

        await timeline_repo.save(
            TimelineEvent(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                source_type="script",
                source_id=script_id,
                event_type="version",
                title=f"v{new_version_num}: {version.commit_message}",
                actor_type="user",
                actor_id=user.id,
                version_number=new_version_num,
                commit_message=version.commit_message,
            )
        )

    script.updated_at = datetime.now(timezone.utc)
    await script_repo.update(script)
    return ScriptResponse.from_script(script)


@router.delete("/scripts/{script_id}", status_code=204)
async def delete_script(
    bot_id: str,
    script_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> None:
    """Delete a script and all its versions."""
    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")
    await script_repo.delete(script_id)


@router.post("/scripts/{script_id}/run")
async def run_script(
    bot_id: str,
    script_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> dict:
    """Run a script manually by creating a Work item."""
    from cachibot.models.work import Priority, Work, WorkStatus

    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")
    if script.status != ScriptStatus.ACTIVE:
        raise HTTPException(status_code=422, detail="Script must be active to run")

    from cachibot.storage.work_repository import TaskRepository, WorkRepository

    work_repo = WorkRepository()
    task_repo_local = TaskRepository()

    now = datetime.now(timezone.utc)
    work_id = str(uuid.uuid4())

    work = Work(
        id=work_id,
        bot_id=bot_id,
        title=f"Run script: {script.name}",
        description=f"Manual execution of script '{script.name}' v{script.current_version}",
        status=WorkStatus.PENDING,
        priority=Priority.NORMAL,
        context={"script_run": True},
        tags=["script"],
        created_at=now,
    )
    # Set script tracking fields if they exist on the model
    if hasattr(work, "script_id"):
        work.script_id = script_id
    if hasattr(work, "script_version"):
        work.script_version = script.current_version

    await work_repo.save(work)

    from cachibot.models.work import Task, TaskStatus

    task = Task(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        work_id=work_id,
        title=f"Execute {script.name}",
        action=f"Execute script: {script.name}",
        status=TaskStatus.PENDING,
        created_at=now,
    )
    await task_repo_local.save(task)

    return {"workId": work_id, "message": f"Script '{script.name}' queued for execution"}


@router.post("/scripts/{script_id}/activate")
async def activate_script(
    bot_id: str,
    script_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> ScriptResponse:
    """Set a script's status to active."""
    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")

    await script_repo.update_status(script_id, ScriptStatus.ACTIVE)
    script.status = ScriptStatus.ACTIVE
    return ScriptResponse.from_script(script)


@router.post("/scripts/{script_id}/disable")
async def disable_script(
    bot_id: str,
    script_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> ScriptResponse:
    """Set a script's status to disabled."""
    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")

    await script_repo.update_status(script_id, ScriptStatus.DISABLED)
    script.status = ScriptStatus.DISABLED
    return ScriptResponse.from_script(script)


# =============================================================================
# SCRIPT VERSIONS
# =============================================================================


@router.get("/scripts/{script_id}/versions")
async def list_versions(
    bot_id: str,
    script_id: str,
    user: User = Depends(require_bot_access),
) -> list[ScriptVersionResponse]:
    """List all versions of a script."""
    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")

    versions = await version_repo.get_by_script(script_id)
    return [ScriptVersionResponse.from_version(v) for v in versions]


@router.get("/scripts/{script_id}/versions/{version_number}")
async def get_version(
    bot_id: str,
    script_id: str,
    version_number: int,
    user: User = Depends(require_bot_access),
) -> ScriptVersionResponse:
    """Get a specific version of a script."""
    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")

    version = await version_repo.get_version(script_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return ScriptVersionResponse.from_version(version)


@router.post("/scripts/{script_id}/versions/{version_number}/approve")
async def approve_version(
    bot_id: str,
    script_id: str,
    version_number: int,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> ScriptVersionResponse:
    """Approve a bot-created script version."""
    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")

    version = await version_repo.get_version(script_id, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    if version.approved:
        raise HTTPException(status_code=422, detail="Version already approved")

    await version_repo.approve(script_id, version_number, approved_by=user.id)

    # Update script source code to the approved version
    script.source_code = version.source_code
    script.current_version = version_number
    script.updated_at = datetime.now(timezone.utc)
    if script.status == ScriptStatus.DRAFT:
        script.status = ScriptStatus.ACTIVE
    await script_repo.update(script)

    version.approved = True
    version.approved_by = user.id
    return ScriptVersionResponse.from_version(version)


@router.post("/scripts/{script_id}/versions/{version_number}/rollback")
async def rollback_to_version(
    bot_id: str,
    script_id: str,
    version_number: int,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> ScriptResponse:
    """Rollback a script to a previous version."""
    from cachibot.models.automations import TimelineEvent

    script = await script_repo.get(script_id)
    if not script or script.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Script not found")

    target_version = await version_repo.get_version(script_id, version_number)
    if not target_version:
        raise HTTPException(status_code=404, detail="Version not found")

    now = datetime.now(timezone.utc)
    new_version_num = script.current_version + 1

    # Create new version with code from target version
    rollback_version = ScriptVersion(
        id=str(uuid.uuid4()),
        script_id=script_id,
        version_number=new_version_num,
        source_code=target_version.source_code,
        author_type=AuthorType.USER,
        author_id=user.id,
        commit_message=f"Rollback to v{version_number}",
        approved=True,
        approved_by=user.id,
        approved_at=now,
        created_at=now,
    )
    await version_repo.save(rollback_version)

    # Update script
    script.source_code = target_version.source_code
    script.current_version = new_version_num
    script.updated_at = now
    await script_repo.update(script)

    await timeline_repo.save(
        TimelineEvent(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            source_type="script",
            source_id=script_id,
            event_type="version",
            title=f"Rolled back to v{version_number}",
            actor_type="user",
            actor_id=user.id,
            version_number=new_version_num,
            commit_message=f"Rollback to v{version_number}",
        )
    )

    return ScriptResponse.from_script(script)


# =============================================================================
# TIMELINE
# =============================================================================


@router.get("/timeline/{source_type}/{source_id}")
async def get_timeline(
    bot_id: str,
    source_type: str,
    source_id: str,
    event_types: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_bot_access),
) -> list[dict]:
    """Get combined timeline for a source entity."""

    type_list = event_types.split(",") if event_types else None
    events = await timeline_repo.get_timeline(
        source_type=source_type,
        source_id=source_id,
        event_types=type_list,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": e.id,
            "botId": e.bot_id,
            "sourceType": e.source_type,
            "sourceId": e.source_id,
            "eventType": e.event_type,
            "eventAt": e.event_at.isoformat(),
            "actorType": e.actor_type,
            "actorId": e.actor_id,
            "actorName": e.actor_name,
            "title": e.title,
            "description": e.description,
            "diff": e.diff,
            "executionLogId": e.execution_log_id,
            "versionNumber": e.version_number,
            "commitMessage": e.commit_message,
        }
        for e in events
    ]
