"""Bot creation service with AI-assisted prompt generation."""

import logging
from typing import Any, Literal

from prompture.aio import extract_with_model
from pydantic import BaseModel, Field

from cachibot.config import Config

logger = logging.getLogger(__name__)


async def _extract_with_retry(
    model_cls: type[BaseModel],
    text: str,
    model_name: str,
    instruction_template: str,
    max_retries: int = 2,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call extract_with_model with manual retries."""
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await extract_with_model(
                model_cls,
                text,
                model_name,
                instruction_template=instruction_template,
                **kwargs,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "Extraction attempt %d/%d failed: %s",
                attempt + 1, max_retries, e,
            )
    raise last_error  # type: ignore[misc]


class FollowUpQuestion(BaseModel):
    """A follow-up question to gather more context."""

    id: str = Field(description="Unique identifier for this question")
    question: str = Field(description="The question to ask the user")
    placeholder: str = Field(description="Placeholder text showing an example answer")


class FollowUpQuestions(BaseModel):
    """Generated follow-up questions based on category and description."""

    questions: list[FollowUpQuestion] = Field(
        description="List of 3 follow-up questions to gather more context"
    )


class PersonalityConfig(BaseModel):
    """Bot personality configuration from user inputs."""

    purpose_category: str = Field(
        description="Category of bot purpose (e.g., coding, writing, analysis, support)"
    )
    purpose_description: str = Field(
        description="Detailed description of what the bot should do"
    )
    communication_style: str = Field(
        description="How the bot should communicate (e.g., professional, casual, friendly)"
    )
    use_emojis: Literal["yes", "no", "sometimes"] = Field(
        default="sometimes",
        description="Whether the bot should use emojis in responses"
    )


class FullBotContext(BaseModel):
    """Complete context for generating a system prompt."""

    name: str = Field(description="The bot's chosen name")
    name_meaning: str = Field(description="Why this name was chosen")
    purpose_category: str = Field(description="Category like fitness, cooking, coding")
    purpose_description: str = Field(description="What the user wants the bot to do")
    follow_up_answers: list[tuple[str, str]] = Field(
        description="List of (question, answer) pairs from follow-up questions"
    )
    communication_style: str = Field(description="How to communicate")
    use_emojis: Literal["yes", "no", "sometimes"] = Field(default="sometimes")


class GeneratedPrompt(BaseModel):
    """AI-generated system prompt result."""

    system_prompt: str = Field(
        description="The generated system prompt for the bot"
    )
    suggested_name: str = Field(
        description="A suggested name for the bot based on its personality"
    )
    suggested_description: str = Field(
        description="A one-line description of the bot"
    )


class RefinedPrompt(BaseModel):
    """Refined system prompt based on feedback."""

    system_prompt: str = Field(
        description="The refined system prompt incorporating the feedback"
    )
    changes_made: str = Field(
        description="Brief summary of what was changed"
    )


class PreviewResponse(BaseModel):
    """Response from the preview chat."""

    response: str = Field(
        description="The bot's response to the test message"
    )


def _resolve_utility_model() -> str:
    """Resolve the model to use for utility tasks."""
    try:
        config = Config.load()
        return config.agent.utility_model or config.agent.model
    except Exception:
        return "moonshot/kimi-k2.5"


def _resolve_main_model() -> str:
    """Resolve the main model for generation tasks."""
    try:
        config = Config.load()
        return config.agent.model
    except Exception:
        return "moonshot/kimi-k2.5"


# Category-specific question templates as fallbacks
CATEGORY_QUESTIONS = {
    "fitness": [
        FollowUpQuestion(id="q1", question="What are your main fitness goals?", placeholder="e.g., Lose weight, build muscle, improve endurance"),
        FollowUpQuestion(id="q2", question="What equipment do you have access to?", placeholder="e.g., Full gym, dumbbells at home, no equipment"),
        FollowUpQuestion(id="q3", question="Any injuries or limitations I should know about?", placeholder="e.g., Bad knees, lower back issues, none"),
    ],
    "cooking": [
        FollowUpQuestion(id="q1", question="Any dietary restrictions or preferences?", placeholder="e.g., Vegetarian, gluten-free, keto, no restrictions"),
        FollowUpQuestion(id="q2", question="What's your cooking skill level?", placeholder="e.g., Beginner, can follow recipes, experienced home cook"),
        FollowUpQuestion(id="q3", question="How much time do you usually have to cook?", placeholder="e.g., 15 min quick meals, 30-45 min, I enjoy long cooking sessions"),
    ],
    "finance": [
        FollowUpQuestion(id="q1", question="What's your main financial goal right now?", placeholder="e.g., Save for a house, pay off debt, build emergency fund"),
        FollowUpQuestion(id="q2", question="How would you describe your spending habits?", placeholder="e.g., Impulsive buyer, careful planner, somewhere in between"),
        FollowUpQuestion(id="q3", question="What areas of finance do you struggle with most?", placeholder="e.g., Budgeting, investing, tracking expenses"),
    ],
    "travel": [
        FollowUpQuestion(id="q1", question="What type of traveler are you?", placeholder="e.g., Adventure seeker, relaxation, cultural explorer, budget backpacker"),
        FollowUpQuestion(id="q2", question="Do you prefer solo travel, couples, or family trips?", placeholder="e.g., Solo, with partner, family with kids"),
        FollowUpQuestion(id="q3", question="Any destinations or experiences on your bucket list?", placeholder="e.g., Japan, Northern Lights, road trip across Europe"),
    ],
    "coding": [
        FollowUpQuestion(id="q1", question="What languages/technologies do you mainly work with?", placeholder="e.g., Python, React, full-stack web development"),
        FollowUpQuestion(id="q2", question="What's your experience level?", placeholder="e.g., Beginner learning, mid-level professional, senior developer"),
        FollowUpQuestion(id="q3", question="What kind of projects do you work on?", placeholder="e.g., Web apps, data science, mobile apps, DevOps"),
    ],
    "writing": [
        FollowUpQuestion(id="q1", question="What type of writing do you do most?", placeholder="e.g., Blog posts, fiction, technical docs, marketing copy"),
        FollowUpQuestion(id="q2", question="Who is your target audience?", placeholder="e.g., Tech professionals, general public, B2B clients"),
        FollowUpQuestion(id="q3", question="What do you struggle with most in writing?", placeholder="e.g., Starting, editing, finding my voice, meeting deadlines"),
    ],
    "learning": [
        FollowUpQuestion(id="q1", question="What subjects are you studying or want to learn?", placeholder="e.g., Math, languages, programming, history"),
        FollowUpQuestion(id="q2", question="How do you learn best?", placeholder="e.g., Visual examples, practice problems, explanations, flashcards"),
        FollowUpQuestion(id="q3", question="What's your goal with learning?", placeholder="e.g., Pass exams, career change, personal interest"),
    ],
    "productivity": [
        FollowUpQuestion(id="q1", question="What's your biggest productivity challenge?", placeholder="e.g., Procrastination, too many tasks, losing focus"),
        FollowUpQuestion(id="q2", question="What tools or methods have you tried?", placeholder="e.g., Pomodoro, to-do apps, calendar blocking"),
        FollowUpQuestion(id="q3", question="What does a productive day look like for you?", placeholder="e.g., Finishing top 3 tasks, no distractions, balanced work-life"),
    ],
    "creative": [
        FollowUpQuestion(id="q1", question="What type of creative work do you do?", placeholder="e.g., Digital art, music production, writing, photography"),
        FollowUpQuestion(id="q2", question="What part of the creative process do you need help with?", placeholder="e.g., Brainstorming ideas, feedback, learning techniques"),
        FollowUpQuestion(id="q3", question="Any specific style or aesthetic you're drawn to?", placeholder="e.g., Minimalist, retro, dark/moody, colorful"),
    ],
    "gaming": [
        FollowUpQuestion(id="q1", question="What games or genres do you play most?", placeholder="e.g., RPGs, FPS, strategy, indie games"),
        FollowUpQuestion(id="q2", question="What platform do you play on?", placeholder="e.g., PC, PlayStation, Switch, mobile"),
        FollowUpQuestion(id="q3", question="What kind of help do you usually need?", placeholder="e.g., Strategy guides, build optimization, finding new games"),
    ],
    "social": [
        FollowUpQuestion(id="q1", question="What's your main goal in social situations?", placeholder="e.g., Better conversations, dating advice, networking"),
        FollowUpQuestion(id="q2", question="What do you find most challenging socially?", placeholder="e.g., Starting conversations, keeping them going, confidence"),
        FollowUpQuestion(id="q3", question="Any specific situations you want help with?", placeholder="e.g., First dates, work events, making friends"),
    ],
}


async def generate_follow_up_questions(
    category: str,
    description: str,
    model: str | None = None,
) -> list[FollowUpQuestion]:
    """
    Generate follow-up questions based on category and description.

    Args:
        category: The purpose category (e.g., fitness, cooking)
        description: The user's initial description
        model: Model to use for generation

    Returns:
        List of 3 follow-up questions
    """
    if model is None:
        model = _resolve_utility_model()

    prompt_text = f"""Generate 3 follow-up questions to better understand what the user wants from their AI assistant.

## Context
- Category: {category}
- User's description: "{description}"

## Requirements for questions:
1. Questions should dig deeper into their specific needs
2. Each question should reveal something unique about their use case
3. Questions should be personal and conversational, not generic
4. Include helpful placeholder text showing example answers
5. Questions should help create a more personalized bot

Generate exactly 3 questions that will help customize this bot perfectly for the user."""

    instruction = "Generate 3 follow-up questions with placeholders in JSON format:"

    fallback_questions = CATEGORY_QUESTIONS.get(category, [
        FollowUpQuestion(
            id="q1",
            question="What specific tasks should I help you with?",
            placeholder="e.g., Daily tasks, specific projects, ongoing support",
        ),
        FollowUpQuestion(
            id="q2",
            question="How do you prefer to receive information?",
            placeholder="e.g., Step-by-step, quick summaries, detailed explanations",
        ),
        FollowUpQuestion(
            id="q3",
            question="Anything specific about your situation I should know?",
            placeholder="e.g., Time constraints, preferences, past experiences",
        ),
    ])

    try:
        result = await _extract_with_retry(
            FollowUpQuestions,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model.questions[:3]
    except Exception:
        logger.exception("Follow-up question generation failed, using fallbacks")
        return fallback_questions


async def generate_system_prompt_full(
    context: FullBotContext,
    model: str | None = None,
) -> GeneratedPrompt:
    """
    Generate a comprehensive system prompt with full context.

    Args:
        context: Complete bot context including name, purpose, and follow-up answers
        model: Model to use for generation

    Returns:
        Generated system prompt
    """
    if model is None:
        model = _resolve_main_model()

    emoji_instruction = {
        "yes": "Use emojis liberally to express emotions and emphasize points.",
        "no": "Never use emojis in responses.",
        "sometimes": "Use emojis sparingly and only when appropriate for emphasis.",
    }[context.use_emojis]

    # Format follow-up Q&A
    qa_section = ""
    if context.follow_up_answers:
        qa_section = "\n## User's Specific Needs\n"
        for question, answer in context.follow_up_answers:
            if answer.strip():
                qa_section += f"- {question}\n  -> {answer}\n"

    prompt_text = f"""Create a highly personalized system prompt for an AI assistant named "{context.name}".

## Identity
- Name: {context.name}
- Name meaning: {context.name_meaning}

## Purpose
- Category: {context.purpose_category}
- User's description: {context.purpose_description}
{qa_section}
## Communication Style
- Style: {context.communication_style}
- Emoji usage: {emoji_instruction}

## System Prompt Requirements:
1. **Start with a strong identity**: "{context.name}" should embrace their name's meaning
2. **Be specific to the user's needs**: Reference the actual tasks and preferences mentioned
3. **Include personality**: Based on the communication style, make the bot feel real
4. **Add expertise**: Define specific knowledge areas based on the category
5. **Set boundaries**: What the bot should and shouldn't do
6. **Include interaction patterns**: How to greet, how to handle requests

## Format:
Write a comprehensive system prompt (300-500 words) that makes this bot feel unique and personal.
The prompt should read naturally, not like a template."""

    instruction = "Generate the complete system prompt and a one-line description in JSON format:"

    fallback_prompt = f"""You are {context.name}, a personal {context.purpose_category} assistant.

Your name comes from: {context.name_meaning}

## Your Purpose
{context.purpose_description}

## How You Communicate
- Style: {context.communication_style}
- {emoji_instruction}

## Your Expertise
You specialize in {context.purpose_category} and are here to help with specific tasks and questions in this area.

## Guidelines
- Always be helpful and supportive
- Give practical, actionable advice
- Remember the user's preferences and adapt accordingly
- Be honest about limitations"""

    try:
        result = await _extract_with_retry(
            GeneratedPrompt,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model
    except Exception:
        logger.warning("System prompt generation failed, using fallback")
        return GeneratedPrompt(
            system_prompt=fallback_prompt,
            suggested_name=context.name,
            suggested_description=f"Your personal {context.purpose_category} assistant",
        )


async def generate_system_prompt(
    personality: PersonalityConfig,
    model: str | None = None,
) -> GeneratedPrompt:
    """
    Generate a system prompt based on bot personality configuration.

    Args:
        personality: User-defined personality settings
        model: Model to use for generation

    Returns:
        Generated system prompt with suggestions
    """
    if model is None:
        model = _resolve_main_model()

    emoji_instruction = {
        "yes": "Use emojis liberally to express emotions and emphasize points.",
        "no": "Never use emojis in responses.",
        "sometimes": "Use emojis sparingly and only when appropriate for emphasis.",
    }[personality.use_emojis]

    prompt_text = f"""Create a system prompt for an AI assistant bot with these characteristics:

## Purpose
- Category: {personality.purpose_category}
- Description: {personality.purpose_description}

## Communication Style
- Style: {personality.communication_style}
- Emoji usage: {emoji_instruction}

## Requirements for the system prompt:
1. Start with a clear identity statement (who the bot is)
2. Define the bot's expertise and capabilities
3. Set the communication tone and style
4. Include any relevant guidelines for behavior
5. Keep it concise but comprehensive (200-400 words)
6. Make it feel natural, not robotic

Also suggest a creative name (1-2 words) and a one-line description for this bot."""

    instruction = (
        "Generate a complete system prompt, suggested name, and description in JSON format:"
    )

    basic_prompt = (
        f"You are a helpful {personality.purpose_category} assistant. "
        f"{personality.purpose_description}. "
        f"Communicate in a {personality.communication_style} manner."
    )

    try:
        result = await _extract_with_retry(
            GeneratedPrompt,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model
    except Exception:
        logger.warning("System prompt generation failed, using fallback")
        return GeneratedPrompt(
            system_prompt=basic_prompt,
            suggested_name="Assistant",
            suggested_description=personality.purpose_description[:100],
        )


async def refine_system_prompt(
    current_prompt: str,
    feedback: str,
    model: str | None = None,
) -> RefinedPrompt:
    """
    Refine an existing system prompt based on user feedback.

    Args:
        current_prompt: The current system prompt to refine
        feedback: User's feedback on what to change
        model: Model to use for generation

    Returns:
        Refined system prompt with change summary
    """
    if model is None:
        model = _resolve_main_model()

    prompt_text = f"""You are helping refine a bot's system prompt based on user feedback.

## Current System Prompt:
{current_prompt}

## User Feedback:
{feedback}

## Instructions:
- Incorporate the user's feedback while keeping the overall structure
- Maintain the bot's core identity and purpose
- Make targeted changes based on the feedback
- Keep the prompt professional and well-organized"""

    instruction = "Generate the refined system prompt and summarize the changes in JSON format:"

    try:
        result = await _extract_with_retry(
            RefinedPrompt,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model
    except Exception:
        logger.warning("Prompt refinement failed, returning original")
        return RefinedPrompt(
            system_prompt=current_prompt,
            changes_made="Refinement failed - original prompt unchanged",
        )


async def preview_bot_response(
    system_prompt: str,
    test_message: str,
    model: str | None = None,
) -> PreviewResponse:
    """
    Generate a preview response from the bot with the given system prompt.

    Args:
        system_prompt: The system prompt to test
        test_message: A test user message to respond to
        model: Model to use for generation

    Returns:
        The bot's response to the test message
    """
    if model is None:
        model = _resolve_main_model()

    prompt_text = f"""You are an AI assistant with the following system prompt:

{system_prompt}

---

Now respond to this user message as that assistant would:

User: {test_message}"""

    instruction = "Generate a response as the assistant would, in JSON format with a 'response' field:"

    try:
        result = await _extract_with_retry(
            PreviewResponse,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model
    except Exception:
        logger.warning("Preview generation failed, using fallback")
        return PreviewResponse(
            response="I'm ready to help! How can I assist you today?",
        )
