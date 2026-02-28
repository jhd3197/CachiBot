"""Bot creation endpoints with AI assistance."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cachibot.api.auth import get_current_user
from cachibot.models.auth import BotOwnership, User
from cachibot.models.bot import Bot
from cachibot.models.room import Room, RoomBot, RoomMember, RoomMemberRole, RoomSettings
from cachibot.services.bot_creation_service import (
    FullBotContext,
    PersonalityConfig,
    analyze_creation_context,
    classify_purpose,
    compose_system_prompt_with_personality,
    generate_follow_up_questions,
    generate_project_follow_up_questions,
    generate_project_proposal,
    generate_system_prompt,
    generate_system_prompt_full,
    preview_bot_response,
    refine_system_prompt,
)
from cachibot.services.name_generator import (
    generate_bot_names,
    generate_bot_names_with_meanings,
)
from cachibot.storage.repository import BotRepository
from cachibot.storage.room_repository import RoomBotRepository, RoomMemberRepository, RoomRepository
from cachibot.storage.user_repository import OwnershipRepository

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# NAME GENERATION
# =============================================================================


class NameSuggestionsRequest(BaseModel):
    """Request for name suggestions."""

    count: int = 4
    exclude: list[str] = []


class NameSuggestionsResponse(BaseModel):
    """Response with name suggestions."""

    names: list[str]


@router.post("/creation/names", response_model=NameSuggestionsResponse)
async def suggest_names(
    request: NameSuggestionsRequest,
    user: User = Depends(get_current_user),
) -> NameSuggestionsResponse:
    """
    Generate AI-powered bot name suggestions.

    Uses Prompture to generate creative, memorable names.
    Pass existing bot names in 'exclude' to avoid duplicates.
    """
    try:
        names = await generate_bot_names(
            count=request.count,
            exclude=request.exclude if request.exclude else None,
        )
        return NameSuggestionsResponse(names=names)
    except Exception:
        logger.exception("Failed to generate names")
        raise HTTPException(status_code=500, detail="Failed to generate names")


class NameWithMeaningModel(BaseModel):
    """A name with its meaning."""

    name: str
    meaning: str


class NamesWithMeaningsRequest(BaseModel):
    """Request for name suggestions with meanings."""

    count: int = 4
    exclude: list[str] = []
    purpose: str | None = None
    personality: str | None = None


class NamesWithMeaningsResponse(BaseModel):
    """Response with name suggestions and their meanings."""

    names: list[NameWithMeaningModel]


@router.post("/creation/names-with-meanings", response_model=NamesWithMeaningsResponse)
async def suggest_names_with_meanings(
    request: NamesWithMeaningsRequest,
    user: User = Depends(get_current_user),
) -> NamesWithMeaningsResponse:
    """
    Generate AI-powered bot name suggestions with meanings.

    Each name includes its origin, meaning, and why it's suitable for an AI assistant.
    Context like purpose and personality help generate more relevant suggestions.
    """
    try:
        names = await generate_bot_names_with_meanings(
            count=request.count,
            exclude=request.exclude if request.exclude else None,
            purpose=request.purpose,
            personality=request.personality,
        )
        return NamesWithMeaningsResponse(
            names=[NameWithMeaningModel(name=n.name, meaning=n.meaning) for n in names]
        )
    except Exception:
        logger.exception("Failed to generate names with meanings")
        raise HTTPException(status_code=500, detail="Failed to generate names")


class FollowUpQuestionModel(BaseModel):
    """A follow-up question."""

    id: str
    question: str
    placeholder: str


class GenerateQuestionsRequest(BaseModel):
    """Request for follow-up questions."""

    category: str = Field(description="The purpose category")
    description: str = Field(description="The user's initial description")
    mode: Literal["user-focused", "task-focused"] = Field(
        default="user-focused", description="Question generation mode"
    )


class GenerateQuestionsResponse(BaseModel):
    """Response with follow-up questions."""

    questions: list[FollowUpQuestionModel]


# =============================================================================
# SSE STREAMING ENDPOINTS
# =============================================================================


def _sse_event(event: str, data: dict[str, object]) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/creation/names-with-meanings/stream")
async def stream_names_with_meanings(
    request: NamesWithMeaningsRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream bot name suggestions with meanings via SSE.

    Events:
    - name: {name, meaning} — one per generated name
    - done: {} — generation complete
    - error: {error} — if generation fails
    """

    async def generate() -> AsyncGenerator[str, None]:
        try:
            names = await generate_bot_names_with_meanings(
                count=request.count,
                exclude=request.exclude if request.exclude else None,
                purpose=request.purpose,
                personality=request.personality,
            )
            for name in names:
                yield _sse_event("name", {"name": name.name, "meaning": name.meaning})
                await asyncio.sleep(0.05)  # Small delay for visual staggering
            yield _sse_event("done", {})
        except Exception as e:
            logger.exception("SSE name generation failed")
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/creation/follow-up-questions/stream")
async def stream_follow_up_questions(
    request: GenerateQuestionsRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream follow-up questions via SSE.

    Events:
    - question: {id, question, placeholder} — one per question
    - done: {} — generation complete
    - error: {error} — if generation fails
    """

    async def generate() -> AsyncGenerator[str, None]:
        try:
            questions = await generate_follow_up_questions(
                category=request.category,
                description=request.description,
                mode=request.mode,
            )
            for q in questions:
                yield _sse_event(
                    "question",
                    {
                        "id": q.id,
                        "question": q.question,
                        "placeholder": q.placeholder,
                    },
                )
                await asyncio.sleep(0.05)
            yield _sse_event("done", {})
        except Exception as e:
            logger.exception("SSE question generation failed")
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# FOLLOW-UP QUESTIONS (non-streaming)
# =============================================================================


@router.post("/creation/follow-up-questions", response_model=GenerateQuestionsResponse)
async def get_follow_up_questions(
    request: GenerateQuestionsRequest,
    user: User = Depends(get_current_user),
) -> GenerateQuestionsResponse:
    """
    Generate follow-up questions based on category and description.

    These questions help gather more context for creating a personalized bot.
    """
    try:
        questions = await generate_follow_up_questions(
            category=request.category,
            description=request.description,
            mode=request.mode,
        )
        return GenerateQuestionsResponse(
            questions=[
                FollowUpQuestionModel(id=q.id, question=q.question, placeholder=q.placeholder)
                for q in questions
            ]
        )
    except Exception:
        logger.exception("Failed to generate follow-up questions")
        raise HTTPException(status_code=500, detail="Failed to generate questions")


# =============================================================================
# AI-ASSISTED PROMPT GENERATION
# =============================================================================


class SuggestPromptResponse(BaseModel):
    """Response with AI-generated system prompt."""

    system_prompt: str
    suggested_name: str
    suggested_description: str


class FollowUpAnswer(BaseModel):
    """A question-answer pair."""

    question: str
    answer: str


class GenerateFullPromptRequest(BaseModel):
    """Request for full system prompt generation."""

    name: str = Field(description="The bot's chosen name")
    name_meaning: str = Field(description="Why this name was chosen")
    purpose_category: str = Field(description="Category like fitness, cooking, coding")
    purpose_description: str = Field(description="What the user wants the bot to do")
    follow_up_answers: list[FollowUpAnswer] = Field(
        default=[], description="Answered follow-up questions"
    )
    communication_style: str = Field(default="friendly")
    use_emojis: Literal["yes", "no", "sometimes"] = Field(default="sometimes")


@router.post("/creation/generate-prompt", response_model=SuggestPromptResponse)
async def generate_full_prompt(
    request: GenerateFullPromptRequest,
    user: User = Depends(get_current_user),
) -> SuggestPromptResponse:
    """
    Generate a comprehensive system prompt with full context.

    Uses all gathered information (name, purpose, follow-up answers, style)
    to create a highly personalized system prompt.
    """
    try:
        context = FullBotContext(
            name=request.name,
            name_meaning=request.name_meaning,
            purpose_category=request.purpose_category,
            purpose_description=request.purpose_description,
            follow_up_answers=[(fa.question, fa.answer) for fa in request.follow_up_answers],
            communication_style=request.communication_style,
            use_emojis=request.use_emojis,
        )
        result = await generate_system_prompt_full(context)
        return SuggestPromptResponse(
            system_prompt=result.system_prompt,
            suggested_name=result.suggested_name,
            suggested_description=result.suggested_description,
        )
    except Exception:
        logger.exception("Failed to generate full prompt")
        raise HTTPException(status_code=500, detail="Failed to generate prompt")


class SuggestPromptRequest(BaseModel):
    """Request for AI-generated system prompt."""

    purpose_category: str = Field(
        description="Category of bot purpose (e.g., coding, writing, analysis)"
    )
    purpose_description: str = Field(description="Detailed description of what the bot should do")
    communication_style: str = Field(
        default="professional", description="How the bot should communicate"
    )
    use_emojis: Literal["yes", "no", "sometimes"] = Field(
        default="sometimes", description="Whether the bot should use emojis"
    )
    model: str | None = Field(
        default=None, description="Model to use for generation (uses default if not specified)"
    )


@router.post("/creation/suggest-prompt", response_model=SuggestPromptResponse)
async def suggest_prompt(
    request: SuggestPromptRequest,
    user: User = Depends(get_current_user),
) -> SuggestPromptResponse:
    """
    Generate an AI-powered system prompt based on bot personality.

    Takes the purpose, style, and preferences to generate a complete
    system prompt, along with name and description suggestions.
    """
    try:
        personality = PersonalityConfig(
            purpose_category=request.purpose_category,
            purpose_description=request.purpose_description,
            communication_style=request.communication_style,
            use_emojis=request.use_emojis,
        )
        result = await generate_system_prompt(personality, model=request.model)
        return SuggestPromptResponse(
            system_prompt=result.system_prompt,
            suggested_name=result.suggested_name,
            suggested_description=result.suggested_description,
        )
    except Exception:
        logger.exception("Failed to suggest prompt")
        raise HTTPException(status_code=500, detail="Failed to generate prompt")


class RefinePromptRequest(BaseModel):
    """Request to refine an existing system prompt."""

    current_prompt: str = Field(description="The current system prompt to refine")
    feedback: str = Field(description="User feedback on what to change")
    model: str | None = Field(default=None, description="Model to use for generation")


class RefinePromptResponse(BaseModel):
    """Response with refined system prompt."""

    system_prompt: str
    changes_made: str


@router.post("/creation/refine-prompt", response_model=RefinePromptResponse)
async def refine_prompt(
    request: RefinePromptRequest,
    user: User = Depends(get_current_user),
) -> RefinePromptResponse:
    """
    Refine an existing system prompt based on user feedback.

    Takes the current prompt and feedback to generate an improved version.
    """
    try:
        result = await refine_system_prompt(
            current_prompt=request.current_prompt,
            feedback=request.feedback,
            model=request.model,
        )
        return RefinePromptResponse(
            system_prompt=result.system_prompt,
            changes_made=result.changes_made,
        )
    except Exception:
        logger.exception("Failed to refine prompt")
        raise HTTPException(status_code=500, detail="Failed to refine prompt")


class PreviewBotRequest(BaseModel):
    """Request to preview bot response."""

    system_prompt: str = Field(description="The system prompt to test")
    test_message: str = Field(description="A test user message to respond to")
    model: str | None = Field(default=None, description="Model to use for generation")


class PreviewBotResponse(BaseModel):
    """Response from bot preview."""

    response: str


@router.post("/creation/preview-bot", response_model=PreviewBotResponse)
async def preview_bot(
    request: PreviewBotRequest,
    user: User = Depends(get_current_user),
) -> PreviewBotResponse:
    """
    Preview how a bot would respond with the given system prompt.

    Useful for testing the bot's personality before creating it.
    """
    try:
        result = await preview_bot_response(
            system_prompt=request.system_prompt,
            test_message=request.test_message,
            model=request.model,
        )
        return PreviewBotResponse(response=result.response)
    except Exception:
        logger.exception("Failed to generate bot preview")
        raise HTTPException(status_code=500, detail="Failed to generate preview")


# =============================================================================
# CREATION CONTEXT ANALYSIS
# =============================================================================


class AnalyzeContextRequest(BaseModel):
    """Request to analyze creation context for user info extraction."""

    purpose_category: str = Field(description="The bot's purpose category")
    purpose_description: str = Field(description="What the user wants the bot to do")
    follow_up_answers: list[FollowUpAnswer] = Field(
        default=[], description="Answered follow-up questions"
    )
    system_prompt: str = Field(description="The generated system prompt")
    bot_name: str = Field(description="The bot's name")


class SuggestedTodoModel(BaseModel):
    """A suggested todo item."""

    title: str
    notes: str = ""


class SuggestedScheduleModel(BaseModel):
    """A suggested recurring schedule."""

    name: str
    description: str = ""
    frequency: str


class AnalyzeContextResponse(BaseModel):
    """Response with extracted user context and suggestions."""

    user_context: str
    suggested_todos: list[SuggestedTodoModel]
    suggested_schedules: list[SuggestedScheduleModel]


@router.post("/creation/analyze-context", response_model=AnalyzeContextResponse)
async def analyze_context(
    request: AnalyzeContextRequest,
    user: User = Depends(get_current_user),
) -> AnalyzeContextResponse:
    """
    Analyze all wizard data to extract user context, todos, and schedules.

    This endpoint runs a second AI pass on the creation data to extract:
    - User context (for Custom Instructions)
    - Suggested todos (one-time tasks)
    - Suggested schedules (recurring tasks)
    """
    try:
        result = await analyze_creation_context(
            purpose_category=request.purpose_category,
            purpose_description=request.purpose_description,
            follow_up_answers=[(fa.question, fa.answer) for fa in request.follow_up_answers],
            system_prompt=request.system_prompt,
            bot_name=request.bot_name,
        )
        return AnalyzeContextResponse(
            user_context=result.user_context,
            suggested_todos=[
                SuggestedTodoModel(title=t.title, notes=t.notes) for t in result.suggested_todos
            ],
            suggested_schedules=[
                SuggestedScheduleModel(
                    name=s.name, description=s.description, frequency=s.frequency
                )
                for s in result.suggested_schedules
            ],
        )
    except Exception:
        logger.exception("Failed to analyze creation context")
        raise HTTPException(status_code=500, detail="Failed to analyze context")


# =============================================================================
# PURPOSE CLASSIFICATION
# =============================================================================


class ClassifyPurposeRequest(BaseModel):
    """Request to classify whether a description needs a single bot or a project."""

    category: str = Field(description="The purpose category")
    description: str = Field(description="The user's initial description")


class ClassifyPurposeResponse(BaseModel):
    """Response with purpose classification."""

    classification: str
    reason: str
    confidence: float


@router.post("/creation/classify-purpose", response_model=ClassifyPurposeResponse)
async def classify_purpose_endpoint(
    request: ClassifyPurposeRequest,
    user: User = Depends(get_current_user),
) -> ClassifyPurposeResponse:
    """
    Classify whether a description implies a single bot or a team/project.

    Returns "single" for personal assistants and individual tasks,
    or "project" for multi-role teams and multi-stage workflows.
    """
    try:
        result = await classify_purpose(
            category=request.category,
            description=request.description,
        )
        return ClassifyPurposeResponse(
            classification=result.classification,
            reason=result.reason,
            confidence=result.confidence,
        )
    except Exception:
        logger.exception("Failed to classify purpose")
        raise HTTPException(status_code=500, detail="Failed to classify purpose")


# =============================================================================
# PROJECT FOLLOW-UP QUESTIONS
# =============================================================================


class ProjectQuestionsRequest(BaseModel):
    """Request for project follow-up questions."""

    category: str = Field(description="The purpose category")
    description: str = Field(description="The user's project description")


@router.post("/creation/project-questions/stream")
async def stream_project_follow_up_questions(
    request: ProjectQuestionsRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream project-focused follow-up questions via SSE.

    Events:
    - question: {id, question, placeholder} -- one per question
    - done: {} -- generation complete
    - error: {error} -- if generation fails
    """

    async def generate() -> AsyncGenerator[str, None]:
        try:
            questions = await generate_project_follow_up_questions(
                category=request.category,
                description=request.description,
            )
            for q in questions:
                yield _sse_event(
                    "question",
                    {
                        "id": q.id,
                        "question": q.question,
                        "placeholder": q.placeholder,
                    },
                )
                await asyncio.sleep(0.05)
            yield _sse_event("done", {})
        except Exception as e:
            logger.exception("SSE project question generation failed")
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# PROJECT PROPOSAL GENERATION
# =============================================================================


class GenerateProjectProposalRequest(BaseModel):
    """Request for project proposal generation."""

    category: str = Field(description="The purpose category")
    description: str = Field(description="The user's project description")
    follow_up_answers: list[FollowUpAnswer] = Field(
        default=[], description="Answered follow-up questions"
    )


class ProposalBotModel(BaseModel):
    """A bot in a project proposal response."""

    name: str
    description: str
    role: str
    system_prompt: str
    tone: str = "friendly"
    expertise_level: str = "expert"
    response_length: str = "moderate"
    personality_traits: list[str] = []


class ProposalRoomModel(BaseModel):
    """A room in a project proposal response."""

    name: str
    description: str
    response_mode: str
    bot_names: list[str]


class GenerateProjectProposalResponse(BaseModel):
    """Response with project proposal."""

    project_name: str
    project_description: str
    bots: list[ProposalBotModel]
    rooms: list[ProposalRoomModel]


@router.post(
    "/creation/generate-project-proposal",
    response_model=GenerateProjectProposalResponse,
)
async def generate_project_proposal_endpoint(
    request: GenerateProjectProposalRequest,
    user: User = Depends(get_current_user),
) -> GenerateProjectProposalResponse:
    """
    Generate a complete project proposal with specialized bots and rooms.

    Analyzes the project description and follow-up answers to design
    a team of AI bots organized into rooms with appropriate response modes.
    """
    try:
        result = await generate_project_proposal(
            category=request.category,
            description=request.description,
            follow_up_answers=[(fa.question, fa.answer) for fa in request.follow_up_answers],
        )
        return GenerateProjectProposalResponse(
            project_name=result.project_name,
            project_description=result.project_description,
            bots=[
                ProposalBotModel(
                    name=b.name,
                    description=b.description,
                    role=b.role,
                    system_prompt=b.system_prompt,
                    tone=b.tone,
                    expertise_level=b.expertise_level,
                    response_length=b.response_length,
                    personality_traits=b.personality_traits,
                )
                for b in result.bots
            ],
            rooms=[
                ProposalRoomModel(
                    name=r.name,
                    description=r.description,
                    response_mode=r.response_mode,
                    bot_names=r.bot_names,
                )
                for r in result.rooms
            ],
        )
    except Exception:
        logger.exception("Failed to generate project proposal")
        raise HTTPException(status_code=500, detail="Failed to generate project proposal")


# =============================================================================
# PROJECT CREATION (BATCH)
# =============================================================================


class CreateProjectBot(BaseModel):
    """A bot to create as part of a project."""

    temp_id: str = Field(description="Temporary client-side ID for mapping")
    name: str = Field(description="Bot name")
    description: str = Field(default="", description="Bot description")
    icon: str = Field(default="bot", description="Bot icon identifier")
    color: str = Field(default="#3b82f6", description="Bot color hex code")
    system_prompt: str = Field(default="", description="System prompt for the bot")
    model: str = Field(default="", description="Model identifier for the bot")
    tone: str = Field(default="friendly", description="Communication tone")
    expertise_level: str = Field(default="expert", description="Expertise level")
    response_length: str = Field(default="moderate", description="Response length preference")
    personality_traits: list[str] = Field(
        default_factory=list, description="Personality traits"
    )


class CreateProjectRoom(BaseModel):
    """A room to create as part of a project."""

    name: str = Field(description="Room name")
    description: str = Field(default="", description="Room description")
    response_mode: str = Field(default="parallel", description="Room response mode")
    bot_temp_ids: list[str] = Field(description="Temporary IDs of bots to add to this room")
    settings: dict[str, Any] = Field(default_factory=dict, description="Additional room settings")


class CreateProjectRequest(BaseModel):
    """Request to batch-create a project with bots and rooms."""

    bots: list[CreateProjectBot] = Field(description="Bots to create")
    rooms: list[CreateProjectRoom] = Field(description="Rooms to create")


class CreatedBotInfo(BaseModel):
    """Info about a created bot."""

    temp_id: str
    bot_id: str
    name: str


class CreatedRoomInfo(BaseModel):
    """Info about a created room."""

    room_id: str
    title: str


class CreateProjectResponse(BaseModel):
    """Response from batch project creation."""

    bots: list[CreatedBotInfo]
    rooms: list[CreatedRoomInfo]


@router.post("/creation/create-project", response_model=CreateProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    user: User = Depends(get_current_user),
) -> CreateProjectResponse:
    """
    Batch-create a project with multiple bots and rooms.

    Creates bots in the backend database with ownership assigned to the current
    user, then creates rooms with the real bot IDs mapped from temporary IDs.
    Returns the mapping of temp_ids to real bot_ids plus created room IDs.
    """
    bot_repo = BotRepository()
    ownership_repo = OwnershipRepository()
    room_repo = RoomRepository()
    member_repo = RoomMemberRepository()
    room_bot_repo = RoomBotRepository()

    now = datetime.now(timezone.utc)

    # Step 1: Create all bots and build temp_id -> real_id mapping
    temp_to_real: dict[str, str] = {}
    created_bots: list[CreatedBotInfo] = []

    try:
        for bot_spec in request.bots:
            bot_id = str(uuid.uuid4())
            temp_to_real[bot_spec.temp_id] = bot_id

            # Compose final system prompt by merging core prompt with personality fields
            final_prompt = compose_system_prompt_with_personality(
                core_prompt=bot_spec.system_prompt,
                tone=bot_spec.tone,
                expertise_level=bot_spec.expertise_level,
                response_length=bot_spec.response_length,
                personality_traits=bot_spec.personality_traits,
            )

            bot = Bot(
                id=bot_id,
                name=bot_spec.name,
                description=bot_spec.description,
                icon=bot_spec.icon,
                color=bot_spec.color,
                model=bot_spec.model,
                systemPrompt=final_prompt,
                capabilities={},
                createdAt=now,
                updatedAt=now,
            )
            await bot_repo.upsert_bot(bot)

            # Assign ownership to the current user
            ownership = BotOwnership(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                user_id=user.id,
                created_at=now,
            )
            await ownership_repo.assign_bot_owner(ownership)

            created_bots.append(
                CreatedBotInfo(
                    temp_id=bot_spec.temp_id,
                    bot_id=bot_id,
                    name=bot_spec.name,
                )
            )
    except Exception:
        logger.exception("Failed to create project bots")
        raise HTTPException(status_code=500, detail="Failed to create project bots")

    # Step 2: Create all rooms with mapped real bot IDs
    created_rooms: list[CreatedRoomInfo] = []

    try:
        for room_spec in request.rooms:
            # Map temp_ids to real bot IDs
            real_bot_ids = []
            for temp_id in room_spec.bot_temp_ids:
                real_id = temp_to_real.get(temp_id)
                if real_id is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unknown bot temp_id: {temp_id}",
                    )
                real_bot_ids.append(real_id)

            # Build room settings from the spec
            room_settings = RoomSettings(
                response_mode=room_spec.response_mode,
                **room_spec.settings,
            )

            room_id = str(uuid.uuid4())
            room = Room(
                id=room_id,
                title=room_spec.name,
                description=room_spec.description,
                creator_id=user.id,
                max_bots=max(len(real_bot_ids), 2),
                settings=room_settings,
                created_at=now,
                updated_at=now,
            )
            await room_repo.create_room(room)

            # Add creator as member
            creator_member = RoomMember(
                room_id=room_id,
                user_id=user.id,
                username=user.username,
                role=RoomMemberRole.CREATOR,
                joined_at=now,
            )
            await member_repo.add_member(creator_member)

            # Add bots to the room
            for real_bot_id in real_bot_ids:
                bot_record = await bot_repo.get_bot(real_bot_id)
                rb = RoomBot(
                    room_id=room_id,
                    bot_id=real_bot_id,
                    bot_name=bot_record.name if bot_record else "",
                    added_at=now,
                )
                await room_bot_repo.add_bot(rb)

            created_rooms.append(CreatedRoomInfo(room_id=room_id, title=room_spec.name))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create project rooms")
        raise HTTPException(status_code=500, detail="Failed to create project rooms")

    return CreateProjectResponse(bots=created_bots, rooms=created_rooms)
