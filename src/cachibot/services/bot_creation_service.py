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


# Category-specific question templates as fallbacks (user-centric)
CATEGORY_QUESTIONS = {
    "fitness": [
        FollowUpQuestion(id="q1", question="What's your name and what are your current fitness goals?", placeholder="e.g., I'm Maria, trying to lose 10kg and run a 5K by summer"),
        FollowUpQuestion(id="q2", question="What does your typical week look like — when do you work out?", placeholder="e.g., I work 9-6, gym at 7am on weekdays, long run on Saturdays"),
        FollowUpQuestion(id="q3", question="What tasks or reminders would help you stay on track?", placeholder="e.g., Remind me to stretch daily, track my calories, plan weekly workouts"),
    ],
    "cooking": [
        FollowUpQuestion(id="q1", question="What's your name and who do you usually cook for?", placeholder="e.g., I'm Sam, cooking for myself and my partner, they're vegetarian"),
        FollowUpQuestion(id="q2", question="What does your weekly meal routine look like?", placeholder="e.g., Meal prep on Sundays, quick lunches during work, nice dinner on Fridays"),
        FollowUpQuestion(id="q3", question="What cooking tasks would you want me to help with regularly?", placeholder="e.g., Weekly meal plans, grocery lists, new recipe ideas for date night"),
    ],
    "finance": [
        FollowUpQuestion(id="q1", question="What's your name and what's your current financial situation?", placeholder="e.g., I'm Jordan, just started a new job, trying to build an emergency fund"),
        FollowUpQuestion(id="q2", question="What does your income and spending look like right now?", placeholder="e.g., Salary + freelance, biggest expenses are rent and eating out"),
        FollowUpQuestion(id="q3", question="What financial tasks would you want me to remind you about?", placeholder="e.g., Track daily spending, review budget weekly, save $500/month"),
    ],
    "travel": [
        FollowUpQuestion(id="q1", question="What's your name and what kind of trips do you enjoy?", placeholder="e.g., I'm Chris, love backpacking through Southeast Asia on a budget"),
        FollowUpQuestion(id="q2", question="Any upcoming trips or travel goals you're working towards?", placeholder="e.g., Planning 2-week Japan trip in March, need to save for it"),
        FollowUpQuestion(id="q3", question="What travel tasks would you want help with?", placeholder="e.g., Research destinations, create packing lists, track travel budget"),
    ],
    "coding": [
        FollowUpQuestion(id="q1", question="What's your name and what do you do as a developer?", placeholder="e.g., I'm Alex, fullstack dev at a startup working with React + Python"),
        FollowUpQuestion(id="q2", question="What are you currently working on or learning?", placeholder="e.g., Building a SaaS product, learning Rust on the side"),
        FollowUpQuestion(id="q3", question="What coding tasks would you want help with regularly?", placeholder="e.g., Code review, debugging, learning new patterns, planning features"),
    ],
    "writing": [
        FollowUpQuestion(id="q1", question="What's your name and what kind of writing do you do?", placeholder="e.g., I'm Pat, writing a sci-fi novel and weekly blog posts"),
        FollowUpQuestion(id="q2", question="What does your writing routine look like?", placeholder="e.g., Write 1 hour before work, aim for 1000 words/day"),
        FollowUpQuestion(id="q3", question="What writing tasks would you want me to help with?", placeholder="e.g., Daily writing prompts, editing feedback, outline my next chapter"),
    ],
    "learning": [
        FollowUpQuestion(id="q1", question="What's your name and what are you currently studying?", placeholder="e.g., I'm Taylor, studying for AWS certification while working full-time"),
        FollowUpQuestion(id="q2", question="What's your study schedule and learning goals?", placeholder="e.g., 30 min before bed on weekdays, exam in 3 months"),
        FollowUpQuestion(id="q3", question="What study tasks would you want me to help track?", placeholder="e.g., Quiz me daily, track progress through chapters, remind me to review"),
    ],
    "productivity": [
        FollowUpQuestion(id="q1", question="What's your name and what do you do day-to-day?", placeholder="e.g., I'm Morgan, freelance designer juggling 3 clients + personal projects"),
        FollowUpQuestion(id="q2", question="What does your ideal productive day look like?", placeholder="e.g., Deep work 9-12, meetings after lunch, personal time after 5"),
        FollowUpQuestion(id="q3", question="What tasks or habits would you want me to track for you?", placeholder="e.g., Daily top-3 priorities, weekly review, break reminders"),
    ],
    "creative": [
        FollowUpQuestion(id="q1", question="What's your name and what creative work do you do?", placeholder="e.g., I'm Jamie, digital artist doing commissions + personal art"),
        FollowUpQuestion(id="q2", question="What does your creative routine look like?", placeholder="e.g., Draw after dinner, post on Instagram Tuesdays and Fridays"),
        FollowUpQuestion(id="q3", question="What creative tasks would you want help managing?", placeholder="e.g., Track commissions, brainstorm ideas, schedule posts"),
    ],
    "gaming": [
        FollowUpQuestion(id="q1", question="What's your name and what games are you into right now?", placeholder="e.g., I'm Riley, playing Elden Ring and Baldur's Gate 3 on PC"),
        FollowUpQuestion(id="q2", question="What's your gaming schedule like?", placeholder="e.g., 2-3 hours on weeknights, longer sessions on weekends"),
        FollowUpQuestion(id="q3", question="What gaming-related things would you want help with?", placeholder="e.g., Build guides for my character, track achievements, find new games"),
    ],
    "social": [
        FollowUpQuestion(id="q1", question="What's your name and what's your social life like right now?", placeholder="e.g., I'm Casey, moved to a new city and trying to meet people"),
        FollowUpQuestion(id="q2", question="What social situations come up most for you?", placeholder="e.g., Work networking events, dating apps, making friends at hobbies"),
        FollowUpQuestion(id="q3", question="What would you want me to help you with specifically?", placeholder="e.g., Practice conversations, plan social outings, follow up with contacts"),
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

    prompt_text = f"""Generate 3 follow-up questions to learn about the USER so the bot can truly know them.

## Context
- Category: {category}
- User's description: "{description}"

## Requirements for questions:
1. Questions should learn about the USER's identity, routine, and specific needs — not about bot preferences
2. Ask about their name, schedule, current situation, and concrete tasks they need help with
3. Questions should be warm and personal, making the user feel heard
4. Include helpful placeholder text showing example answers
5. The answers will be used to create custom instructions so the bot always remembers who the user is

## Good question examples:
- "What's your name and how should I address you?"
- "Tell me about your typical day/week — what does your routine look like?"
- "What specific tasks, reminders, or recurring things would you want me to help with?"

## Bad question examples (avoid these):
- "What equipment do you have?" (too generic/impersonal)
- "What's your skill level?" (about preferences, not the user)
- "How do you prefer information?" (about bot style, not user identity)

Generate exactly 3 questions that will help the bot KNOW the user personally."""

    instruction = "Generate 3 follow-up questions with placeholders in JSON format:"

    fallback_questions = CATEGORY_QUESTIONS.get(category, [
        FollowUpQuestion(
            id="q1",
            question="What's your name and how should I address you?",
            placeholder="e.g., I'm Alex, call me Alex or just A",
        ),
        FollowUpQuestion(
            id="q2",
            question="Tell me about your typical day or week — what does your routine look like?",
            placeholder="e.g., I work 9-5 remotely, gym in the morning, study at night",
        ),
        FollowUpQuestion(
            id="q3",
            question="What specific tasks or reminders would you want me to help with?",
            placeholder="e.g., Track my workouts, remind me to meal prep on Sundays, help plan my week",
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


# =============================================================================
# POST-CREATION CONTEXT ANALYSIS
# =============================================================================


class SuggestedTodo(BaseModel):
    """A todo item extracted from the creation context."""

    title: str = Field(description="Short actionable title for the todo")
    notes: str = Field(default="", description="Additional details or context")


class SuggestedSchedule(BaseModel):
    """A recurring task/schedule extracted from the creation context."""

    name: str = Field(description="Name of the recurring task")
    description: str = Field(default="", description="What this schedule does")
    frequency: str = Field(description="How often, e.g. 'daily', 'weekly on Mondays', 'every morning'")


class CreationAnalysis(BaseModel):
    """Analysis result from the creation context."""

    user_context: str = Field(
        description="Markdown text summarizing what the bot should know about the user. "
        "Include name, routine, preferences, goals — everything the bot needs to "
        "address the user personally."
    )
    suggested_todos: list[SuggestedTodo] = Field(
        default_factory=list,
        description="Actionable tasks/todos detected from the user's answers",
    )
    suggested_schedules: list[SuggestedSchedule] = Field(
        default_factory=list,
        description="Recurring tasks or schedules detected from the user's answers",
    )


async def analyze_creation_context(
    purpose_category: str,
    purpose_description: str,
    follow_up_answers: list[tuple[str, str]],
    system_prompt: str,
    bot_name: str,
    model: str | None = None,
) -> CreationAnalysis:
    """
    Analyze all wizard data to extract user context, todos, and schedules.

    This runs after the system prompt is generated and extracts structured
    data that helps the bot truly know its user.

    Args:
        purpose_category: The bot's purpose category
        purpose_description: What the user wants the bot to do
        follow_up_answers: List of (question, answer) pairs
        system_prompt: The generated system prompt
        bot_name: The bot's name
        model: Model to use for analysis

    Returns:
        CreationAnalysis with user_context, suggested_todos, suggested_schedules
    """
    if model is None:
        model = _resolve_utility_model()

    # Format follow-up Q&A
    qa_section = ""
    if follow_up_answers:
        qa_section = "\n## User's Answers\n"
        for question, answer in follow_up_answers:
            if answer.strip():
                qa_section += f"- Q: {question}\n  A: {answer}\n"

    prompt_text = f"""Analyze the following bot creation context to extract structured information about the user.

## Bot Being Created
- Name: {bot_name}
- Category: {purpose_category}
- Purpose: {purpose_description}

## System Prompt
{system_prompt}
{qa_section}
## Your Task

Extract three things from the above context:

### 1. User Context (Custom Instructions)
Write a concise markdown summary of everything the bot should ALWAYS know about its user.
Include: name (if mentioned), routine/schedule, goals, preferences, situation, constraints.
Write it as instructions TO the bot, e.g. "The user's name is Alex. They work 9-5..."
Only include information that was actually mentioned — don't invent details.
If no personal info was shared, write a brief note like "No personal details shared yet."

### 2. Suggested Todos
Extract any specific one-time tasks or action items the user mentioned.
Examples: "Set up a workout plan", "Create a weekly meal prep list", "Research X"
Only include clear, actionable items — not vague wishes.
Return an empty list if none were mentioned.

### 3. Suggested Schedules
Extract any recurring activities or habits the user mentioned wanting help with.
Examples: "Daily workout reminder", "Weekly meal planning on Sundays"
Include the frequency (daily, weekly, etc.) based on what the user said.
Return an empty list if none were mentioned."""

    instruction = (
        "Analyze the context and extract user_context, suggested_todos, "
        "and suggested_schedules in JSON format:"
    )

    try:
        result = await _extract_with_retry(
            CreationAnalysis,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model
    except Exception:
        logger.exception("Creation context analysis failed")
        return CreationAnalysis(
            user_context="No personal details extracted yet.",
            suggested_todos=[],
            suggested_schedules=[],
        )
