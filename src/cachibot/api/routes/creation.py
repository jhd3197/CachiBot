"""Bot creation endpoints with AI assistance."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.services.bot_creation_service import (
    FullBotContext,
    PersonalityConfig,
    generate_follow_up_questions,
    generate_system_prompt,
    generate_system_prompt_full,
    preview_bot_response,
    refine_system_prompt,
)
from cachibot.services.name_generator import (
    generate_bot_names,
    generate_bot_names_with_meanings,
)

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate names: {str(e)}")


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate names: {str(e)}")


class FollowUpQuestionModel(BaseModel):
    """A follow-up question."""

    id: str
    question: str
    placeholder: str


class GenerateQuestionsRequest(BaseModel):
    """Request for follow-up questions."""

    category: str = Field(description="The purpose category")
    description: str = Field(description="The user's initial description")


class GenerateQuestionsResponse(BaseModel):
    """Response with follow-up questions."""

    questions: list[FollowUpQuestionModel]


# =============================================================================
# SSE STREAMING ENDPOINTS
# =============================================================================


def _sse_event(event: str, data: dict) -> str:
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
            )
            for q in questions:
                yield _sse_event("question", {
                    "id": q.id,
                    "question": q.question,
                    "placeholder": q.placeholder,
                })
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
        )
        return GenerateQuestionsResponse(
            questions=[
                FollowUpQuestionModel(id=q.id, question=q.question, placeholder=q.placeholder)
                for q in questions
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate questions: {str(e)}")


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
    follow_up_answers: list[FollowUpAnswer] = Field(default=[], description="Answered follow-up questions")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prompt: {str(e)}")


class SuggestPromptRequest(BaseModel):
    """Request for AI-generated system prompt."""

    purpose_category: str = Field(
        description="Category of bot purpose (e.g., coding, writing, analysis)"
    )
    purpose_description: str = Field(
        description="Detailed description of what the bot should do"
    )
    communication_style: str = Field(
        default="professional",
        description="How the bot should communicate"
    )
    use_emojis: Literal["yes", "no", "sometimes"] = Field(
        default="sometimes",
        description="Whether the bot should use emojis"
    )
    model: str | None = Field(
        default=None,
        description="Model to use for generation (uses default if not specified)"
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prompt: {str(e)}")


class RefinePromptRequest(BaseModel):
    """Request to refine an existing system prompt."""

    current_prompt: str = Field(
        description="The current system prompt to refine"
    )
    feedback: str = Field(
        description="User feedback on what to change"
    )
    model: str | None = Field(
        default=None,
        description="Model to use for generation"
    )


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refine prompt: {str(e)}")


class PreviewBotRequest(BaseModel):
    """Request to preview bot response."""

    system_prompt: str = Field(
        description="The system prompt to test"
    )
    test_message: str = Field(
        description="A test user message to respond to"
    )
    model: str | None = Field(
        default=None,
        description="Model to use for generation"
    )


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")
