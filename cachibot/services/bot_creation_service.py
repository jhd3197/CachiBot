"""Bot creation service with AI-assisted prompt generation."""

import logging
from typing import Any, Literal

from prompture.aio import extract_with_model
from pydantic import BaseModel, Field

from cachibot.services.model_resolver import resolve_main_model, resolve_utility_model

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
                attempt + 1,
                max_retries,
                e,
            )
    logger.error("Bot creation failed after all retries", exc_info=True)
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
    purpose_description: str = Field(description="Detailed description of what the bot should do")
    communication_style: str = Field(
        description="How the bot should communicate (e.g., professional, casual, friendly)"
    )
    use_emojis: Literal["yes", "no", "sometimes"] = Field(
        default="sometimes", description="Whether the bot should use emojis in responses"
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

    system_prompt: str = Field(description="The generated system prompt for the bot")
    suggested_name: str = Field(description="A suggested name for the bot based on its personality")
    suggested_description: str = Field(description="A one-line description of the bot")


class RefinedPrompt(BaseModel):
    """Refined system prompt based on feedback."""

    system_prompt: str = Field(description="The refined system prompt incorporating the feedback")
    changes_made: str = Field(description="Brief summary of what was changed")


class PreviewResponse(BaseModel):
    """Response from the preview chat."""

    response: str = Field(description="The bot's response to the test message")


# Category-specific question templates as fallbacks (user-centric)
CATEGORY_QUESTIONS = {
    "fitness": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what are your current fitness goals?",
            placeholder="e.g., I'm Maria, trying to lose 10kg and run a 5K by summer",
        ),
        FollowUpQuestion(
            id="q2",
            question="What does your typical week look like — when do you work out?",
            placeholder="e.g., I work 9-6, gym at 7am on weekdays, long run on Saturdays",
        ),
        FollowUpQuestion(
            id="q3",
            question="What tasks or reminders would help you stay on track?",
            placeholder="e.g., Remind me to stretch daily, track my calories, plan weekly workouts",
        ),
    ],
    "cooking": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and who do you usually cook for?",
            placeholder="e.g., I'm Sam, cooking for myself and my partner, they're vegetarian",
        ),
        FollowUpQuestion(
            id="q2",
            question="What does your weekly meal routine look like?",
            placeholder=(
                "e.g., Meal prep on Sundays, quick lunches during work, nice dinner on Fridays"
            ),
        ),
        FollowUpQuestion(
            id="q3",
            question="What cooking tasks would you want me to help with regularly?",
            placeholder="e.g., Weekly meal plans, grocery lists, new recipe ideas for date night",
        ),
    ],
    "finance": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what's your current financial situation?",
            placeholder=(
                "e.g., I'm Jordan, just started a new job, trying to build an emergency fund"
            ),
        ),
        FollowUpQuestion(
            id="q2",
            question="What does your income and spending look like right now?",
            placeholder="e.g., Salary + freelance, biggest expenses are rent and eating out",
        ),
        FollowUpQuestion(
            id="q3",
            question="What financial tasks would you want me to remind you about?",
            placeholder="e.g., Track daily spending, review budget weekly, save $500/month",
        ),
    ],
    "travel": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what kind of trips do you enjoy?",
            placeholder="e.g., I'm Chris, love backpacking through Southeast Asia on a budget",
        ),
        FollowUpQuestion(
            id="q2",
            question="Any upcoming trips or travel goals you're working towards?",
            placeholder="e.g., Planning 2-week Japan trip in March, need to save for it",
        ),
        FollowUpQuestion(
            id="q3",
            question="What travel tasks would you want help with?",
            placeholder="e.g., Research destinations, create packing lists, track travel budget",
        ),
    ],
    "coding": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what do you do as a developer?",
            placeholder="e.g., I'm Alex, fullstack dev at a startup working with React + Python",
        ),
        FollowUpQuestion(
            id="q2",
            question="What are you currently working on or learning?",
            placeholder="e.g., Building a SaaS product, learning Rust on the side",
        ),
        FollowUpQuestion(
            id="q3",
            question="What coding tasks would you want help with regularly?",
            placeholder="e.g., Code review, debugging, learning new patterns, planning features",
        ),
    ],
    "writing": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what kind of writing do you do?",
            placeholder="e.g., I'm Pat, writing a sci-fi novel and weekly blog posts",
        ),
        FollowUpQuestion(
            id="q2",
            question="What does your writing routine look like?",
            placeholder="e.g., Write 1 hour before work, aim for 1000 words/day",
        ),
        FollowUpQuestion(
            id="q3",
            question="What writing tasks would you want me to help with?",
            placeholder="e.g., Daily writing prompts, editing feedback, outline my next chapter",
        ),
    ],
    "learning": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what are you currently studying?",
            placeholder="e.g., I'm Taylor, studying for AWS certification while working full-time",
        ),
        FollowUpQuestion(
            id="q2",
            question="What's your study schedule and learning goals?",
            placeholder="e.g., 30 min before bed on weekdays, exam in 3 months",
        ),
        FollowUpQuestion(
            id="q3",
            question="What study tasks would you want me to help track?",
            placeholder="e.g., Quiz me daily, track progress through chapters, remind me to review",
        ),
    ],
    "productivity": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what do you do day-to-day?",
            placeholder=(
                "e.g., I'm Morgan, freelance designer juggling 3 clients + personal projects"
            ),
        ),
        FollowUpQuestion(
            id="q2",
            question="What does your ideal productive day look like?",
            placeholder="e.g., Deep work 9-12, meetings after lunch, personal time after 5",
        ),
        FollowUpQuestion(
            id="q3",
            question="What tasks or habits would you want me to track for you?",
            placeholder="e.g., Daily top-3 priorities, weekly review, break reminders",
        ),
    ],
    "creative": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what creative work do you do?",
            placeholder="e.g., I'm Jamie, digital artist doing commissions + personal art",
        ),
        FollowUpQuestion(
            id="q2",
            question="What does your creative routine look like?",
            placeholder="e.g., Draw after dinner, post on Instagram Tuesdays and Fridays",
        ),
        FollowUpQuestion(
            id="q3",
            question="What creative tasks would you want help managing?",
            placeholder="e.g., Track commissions, brainstorm ideas, schedule posts",
        ),
    ],
    "gaming": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what games are you into right now?",
            placeholder="e.g., I'm Riley, playing Elden Ring and Baldur's Gate 3 on PC",
        ),
        FollowUpQuestion(
            id="q2",
            question="What's your gaming schedule like?",
            placeholder="e.g., 2-3 hours on weeknights, longer sessions on weekends",
        ),
        FollowUpQuestion(
            id="q3",
            question="What gaming-related things would you want help with?",
            placeholder="e.g., Build guides for my character, track achievements, find new games",
        ),
    ],
    "social": [
        FollowUpQuestion(
            id="q1",
            question="What's your name and what's your social life like right now?",
            placeholder="e.g., I'm Casey, moved to a new city and trying to meet people",
        ),
        FollowUpQuestion(
            id="q2",
            question="What social situations come up most for you?",
            placeholder="e.g., Work networking events, dating apps, making friends at hobbies",
        ),
        FollowUpQuestion(
            id="q3",
            question="What would you want me to help you with specifically?",
            placeholder=(
                "e.g., Practice conversations, plan social outings, follow up with contacts"
            ),
        ),
    ],
}


async def generate_follow_up_questions(
    category: str,
    description: str,
    mode: Literal["user-focused", "task-focused"] = "user-focused",
    model: str | None = None,
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> list[FollowUpQuestion]:
    """
    Generate follow-up questions based on category and description.

    Args:
        category: The purpose category (e.g., fitness, cooking)
        description: The user's initial description
        mode: Question generation mode. "user-focused" asks about the user's identity
            and routine. "task-focused" asks about the bot's capabilities and tasks.
        model: Model to use for generation
        bot_models: Per-bot model slots (checked first for "utility")
        resolved_env: Per-bot resolved environment override

    Returns:
        List of 3 follow-up questions
    """
    if model is None:
        model = resolve_utility_model(bot_models=bot_models, resolved_env=resolved_env)

    if mode == "task-focused":
        prompt_text = (
            "Generate 3 follow-up questions: 2 about the bot's task/capabilities "
            "and 1 light personal question."
        )
        prompt_text += f"""

## Context
- Category: {category}
- User's description: "{description}"

## Requirements for questions:
1. The first 2 questions should focus on what the bot should DO — \
its tasks, capabilities, scope, and specific behaviors
2. The 3rd question should be a light personal question (e.g., name, \
how they want to be addressed)
3. Include helpful placeholder text showing example answers
4. Questions should help define the bot's role and responsibilities

## Good question examples:
- "What specific tasks should this bot handle on a daily basis?"
- "Are there any boundaries or topics the bot should avoid?"
- "What's your name so the bot can address you personally?"

## Bad question examples (avoid these):
- "What communication style do you prefer?" (too generic)
- "What's your budget?" (irrelevant to bot capabilities)

Generate exactly 3 questions — 2 task-focused, 1 personal."""

        fallback_questions = [
            FollowUpQuestion(
                id="q1",
                question="What specific tasks should this bot handle regularly?",
                placeholder="e.g., Review pull requests, summarize daily standups, draft emails",
            ),
            FollowUpQuestion(
                id="q2",
                question=("Are there any boundaries or topics the bot should stay away from?"),
                placeholder="e.g., Don't make financial decisions, avoid personal advice",
            ),
            FollowUpQuestion(
                id="q3",
                question="What's your name so the bot knows how to address you?",
                placeholder="e.g., I'm Alex, just call me Alex",
            ),
        ]
    else:
        prompt_text = (
            "Generate 3 follow-up questions to learn about the USER so the bot can truly know them."
        )
        prompt_text += f"""

## Context
- Category: {category}
- User's description: "{description}"

## Requirements for questions:
1. Questions should learn about the USER's identity, routine, and \
specific needs — not about bot preferences
2. Ask about their name, schedule, current situation, and concrete tasks they need help with
3. Questions should be warm and personal, making the user feel heard
4. Include helpful placeholder text showing example answers
5. The answers will be used to create custom instructions so the \
bot always remembers who the user is

## Good question examples:
- "What's your name and how should I address you?"
- "Tell me about your typical day/week — what does your routine look like?"
- "What specific tasks, reminders, or recurring things would you want me to help with?"

## Bad question examples (avoid these):
- "What equipment do you have?" (too generic/impersonal)
- "What's your skill level?" (about preferences, not the user)
- "How do you prefer information?" (about bot style, not user identity)

Generate exactly 3 questions that will help the bot KNOW the user personally."""

        fallback_questions = CATEGORY_QUESTIONS.get(
            category,
            [
                FollowUpQuestion(
                    id="q1",
                    question="What's your name and how should I address you?",
                    placeholder="e.g., I'm Alex, call me Alex or just A",
                ),
                FollowUpQuestion(
                    id="q2",
                    question=(
                        "Tell me about your typical day or week — what does your routine look like?"
                    ),
                    placeholder=("e.g., I work 9-5 remotely, gym in the morning, study at night"),
                ),
                FollowUpQuestion(
                    id="q3",
                    question="What specific tasks or reminders would you want me to help with?",
                    placeholder=(
                        "e.g., Track my workouts, remind me to meal prep on Sundays, "
                        "help plan my week"
                    ),
                ),
            ],
        )

    instruction = "Generate 3 follow-up questions with placeholders in JSON format:"

    try:
        result = await _extract_with_retry(
            FollowUpQuestions,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model.questions[:3]  # type: ignore[attr-defined, no-any-return]
    except Exception:
        logger.exception("Follow-up question generation failed, using fallbacks")
        return fallback_questions


async def generate_system_prompt_full(
    context: FullBotContext,
    model: str | None = None,
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> GeneratedPrompt:
    """
    Generate a comprehensive system prompt with full context.

    Args:
        context: Complete bot context including name, purpose, and follow-up answers
        model: Model to use for generation
        bot_models: Per-bot model slots (checked first for "default")
        resolved_env: Per-bot resolved environment override

    Returns:
        Generated system prompt
    """
    if model is None:
        model = resolve_main_model(bot_models=bot_models, resolved_env=resolved_env)

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

    prompt_text = (
        f'Create a highly personalized system prompt for an AI assistant named "{context.name}".'
    )
    prompt_text += f"""

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
You specialize in {context.purpose_category} and are here to help \
with specific tasks and questions in this area.

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
        return result.model  # type: ignore[attr-defined, no-any-return]
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
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> GeneratedPrompt:
    """
    Generate a system prompt based on bot personality configuration.

    Args:
        personality: User-defined personality settings
        model: Model to use for generation
        bot_models: Per-bot model slots (checked first for "default")
        resolved_env: Per-bot resolved environment override

    Returns:
        Generated system prompt with suggestions
    """
    if model is None:
        model = resolve_main_model(bot_models=bot_models, resolved_env=resolved_env)

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
        return result.model  # type: ignore[attr-defined, no-any-return]
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
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> RefinedPrompt:
    """
    Refine an existing system prompt based on user feedback.

    Args:
        current_prompt: The current system prompt to refine
        feedback: User's feedback on what to change
        model: Model to use for generation
        bot_models: Per-bot model slots (checked first for "default")
        resolved_env: Per-bot resolved environment override

    Returns:
        Refined system prompt with change summary
    """
    if model is None:
        model = resolve_main_model(bot_models=bot_models, resolved_env=resolved_env)

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
        return result.model  # type: ignore[attr-defined, no-any-return]
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
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> PreviewResponse:
    """
    Generate a preview response from the bot with the given system prompt.

    Args:
        system_prompt: The system prompt to test
        test_message: A test user message to respond to
        model: Model to use for generation
        bot_models: Per-bot model slots (checked first for "default")
        resolved_env: Per-bot resolved environment override

    Returns:
        The bot's response to the test message
    """
    if model is None:
        model = resolve_main_model(bot_models=bot_models, resolved_env=resolved_env)

    prompt_text = f"""You are an AI assistant with the following system prompt:

{system_prompt}

---

Now respond to this user message as that assistant would:

User: {test_message}"""

    instruction = (
        "Generate a response as the assistant would, in JSON format with a 'response' field:"
    )

    try:
        result = await _extract_with_retry(
            PreviewResponse,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model  # type: ignore[attr-defined, no-any-return]
    except Exception:
        logger.warning("Preview generation failed, using fallback")
        return PreviewResponse(
            response="I'm ready to help! How can I assist you today?",
        )


# =============================================================================
# PURPOSE CLASSIFICATION
# =============================================================================


class PurposeClassification(BaseModel):
    """Whether a description implies a single bot or a team of bots."""

    classification: Literal["single", "project"] = Field(
        description="Whether this needs a single bot or a team of bots"
    )
    reason: str = Field(description="Brief explanation of why this classification was chosen")
    confidence: float = Field(description="Confidence score between 0 and 1")


async def classify_purpose(
    category: str,
    description: str,
    model: str | None = None,
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> PurposeClassification:
    """
    Classify whether a description implies a single bot or a project with multiple bots.

    Args:
        category: The purpose category (e.g., fitness, coding)
        description: The user's initial description
        model: Model to use for classification
        bot_models: Per-bot model slots (checked first for "utility")
        resolved_env: Per-bot resolved environment override

    Returns:
        PurposeClassification with classification, reason, and confidence
    """
    if model is None:
        model = resolve_utility_model(bot_models=bot_models, resolved_env=resolved_env)

    prompt_text = "Classify whether this description implies a single bot or a project/team."
    prompt_text += f"""

## Context
- Category: {category}
- Description: "{description}"

## Classification Rules

### Single Bot ("single"):
- Personal assistant for one person
- One specific task or domain
- Individual use case
- Simple Q&A or helper bot
- Examples: "a fitness coach", "help me cook", "a coding buddy"

### Project / Team ("project"):
- Multiple distinct roles or specialists needed
- Team workflow or pipeline
- Multi-stage process requiring different expertise
- Collaboration between specialized agents
- Examples: "a content team with writer, editor, and SEO specialist", \
"a dev team with architect, coder, and reviewer", \
"a customer support pipeline with triage, response, and escalation"

Analyze the description carefully and classify it."""

    instruction = "Classify the purpose and provide reasoning in JSON format:"

    try:
        result = await _extract_with_retry(
            PurposeClassification,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model  # type: ignore[attr-defined, no-any-return]
    except Exception:
        logger.exception("Purpose classification failed, defaulting to single")
        return PurposeClassification(
            classification="single",
            reason="Classification failed — defaulting to single bot.",
            confidence=0.5,
        )


# =============================================================================
# PROJECT FOLLOW-UP QUESTIONS
# =============================================================================


async def generate_project_follow_up_questions(
    category: str,
    description: str,
    model: str | None = None,
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> list[FollowUpQuestion]:
    """
    Generate follow-up questions for a project/team workflow.

    These questions help gather context about the project's workflow stages,
    goals, and the specializations needed.

    Args:
        category: The purpose category
        description: The user's initial description
        model: Model to use for generation
        bot_models: Per-bot model slots (checked first for "utility")
        resolved_env: Per-bot resolved environment override

    Returns:
        List of 2-3 project-focused follow-up questions
    """
    if model is None:
        model = resolve_utility_model(bot_models=bot_models, resolved_env=resolved_env)

    prompt_text = "Generate 2-3 follow-up questions about this project/team workflow."
    prompt_text += f"""

## Context
- Category: {category}
- Description: "{description}"

## Requirements for questions:
1. Ask about the workflow stages, pipeline steps, or team structure
2. Ask about the project's primary goals and success criteria
3. Ask about specific specializations or roles needed
4. Questions should help design a team of AI bots that work together
5. Include helpful placeholder text showing example answers

## Good question examples:
- "What are the main stages or steps in your workflow?"
- "What specific roles or specializations do you need in this team?"
- "What's the primary goal — what does success look like for this project?"

Generate 2-3 questions that will help design the right team of bots."""

    instruction = (
        "Generate 2-3 project-focused follow-up questions with placeholders in JSON format:"
    )

    fallback_questions = [
        FollowUpQuestion(
            id="pq1",
            question="What are the main stages or steps in your workflow?",
            placeholder=("e.g., First we plan, then we draft, then review, then publish"),
        ),
        FollowUpQuestion(
            id="pq2",
            question="What specific roles or specializations do you need in this team?",
            placeholder=("e.g., A project lead, a writer, a reviewer, and a QA specialist"),
        ),
    ]

    try:
        result = await _extract_with_retry(
            FollowUpQuestions,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model.questions[:3]  # type: ignore[attr-defined, no-any-return]
    except Exception:
        logger.exception("Project follow-up question generation failed, using fallbacks")
        return fallback_questions


# =============================================================================
# PROJECT PROPOSAL GENERATION
# =============================================================================


class ProposalBotSpec(BaseModel):
    """Specification for a bot in a project proposal."""

    name: str = Field(description="Bot name")
    description: str = Field(description="One-line description of the bot's role")
    role: str = Field(description="Bot role: default, lead, reviewer, observer, or specialist")
    system_prompt: str = Field(description="Complete system prompt for this bot")
    tone: str = Field(
        default="friendly",
        description="Tone: professional, friendly, casual, concise, playful, or witty",
    )
    expertise_level: str = Field(
        default="expert",
        description="Expertise level: beginner, intermediate, expert, or authority",
    )
    response_length: str = Field(
        default="moderate",
        description="Response length: brief, moderate, detailed, or comprehensive",
    )
    personality_traits: list[str] = Field(
        default_factory=list,
        description=(
            "2-4 personality traits from: patient, assertive, creative, analytical, "
            "empathetic, humorous, encouraging, direct, methodical, innovative"
        ),
    )


class ProposalRoomSpec(BaseModel):
    """Specification for a room in a project proposal."""

    name: str = Field(description="Room name")
    description: str = Field(description="One-line description of the room's purpose")
    response_mode: str = Field(
        description=(
            "Response mode: parallel, sequential, chain, router, debate, "
            "waterfall, relay, consensus, or interview"
        )
    )
    bot_names: list[str] = Field(description="Names of bots assigned to this room")


class ProjectProposalResult(BaseModel):
    """Complete project proposal with bots and rooms."""

    project_name: str = Field(description="Short project name")
    project_description: str = Field(description="One-line project description")
    bots: list[ProposalBotSpec] = Field(description="Proposed bots")
    rooms: list[ProposalRoomSpec] = Field(description="Proposed rooms")


_TONE_DIRECTIVES: dict[str, str] = {
    "professional": "Maintain a professional, business-appropriate tone at all times.",
    "friendly": "Communicate in a warm, approachable, and conversational manner.",
    "casual": "Keep things relaxed, informal, and easy-going.",
    "concise": "Be brief and to-the-point — minimize filler and unnecessary elaboration.",
    "playful": "Bring a fun, lighthearted energy to your responses.",
    "witty": "Use clever, sharp humor and smart observations in your communication.",
}

_EXPERTISE_DIRECTIVES: dict[str, str] = {
    "beginner": "Explain concepts from the ground up, assuming no prior knowledge.",
    "intermediate": "Assume a working knowledge of the basics and focus on practical application.",
    "expert": "Speak at an advanced level, using precise terminology and skipping basics.",
    "authority": "Communicate as a leading authority — cite nuance, trade-offs, and edge cases.",
}

_LENGTH_DIRECTIVES: dict[str, str] = {
    "brief": "Keep responses short — aim for 1-3 sentences when possible.",
    "moderate": "Provide balanced responses — enough detail without being verbose.",
    "detailed": "Give thorough, well-structured responses with examples when helpful.",
    "comprehensive": "Provide exhaustive, in-depth responses covering all angles.",
}

_TRAIT_DIRECTIVES: dict[str, str] = {
    "patient": "Be patient and never rush the user — repeat or rephrase willingly.",
    "assertive": "State your position confidently and don't hedge unnecessarily.",
    "creative": "Think outside the box and offer inventive, unexpected solutions.",
    "analytical": "Break down problems methodically with data-driven reasoning.",
    "empathetic": "Show genuine understanding of the user's feelings and situation.",
    "humorous": "Use appropriate humor to keep interactions engaging.",
    "encouraging": "Motivate and uplift — celebrate progress and effort.",
    "direct": "Get straight to the answer without preamble or fluff.",
    "methodical": "Follow structured, step-by-step approaches to every task.",
    "innovative": "Push boundaries and suggest cutting-edge approaches.",
}


def compose_system_prompt_with_personality(
    core_prompt: str,
    tone: str,
    expertise_level: str,
    response_length: str,
    personality_traits: list[str],
) -> str:
    """Compose a full system prompt by appending a Communication Profile section.

    The structured personality fields are translated into natural-language directives
    and appended to the core system prompt. This keeps the core prompt focused on
    domain knowledge and responsibilities while the profile handles communication style.
    """
    lines: list[str] = []

    if tone in _TONE_DIRECTIVES:
        lines.append(f"- **Tone:** {_TONE_DIRECTIVES[tone]}")
    if expertise_level in _EXPERTISE_DIRECTIVES:
        lines.append(f"- **Expertise Level:** {_EXPERTISE_DIRECTIVES[expertise_level]}")
    if response_length in _LENGTH_DIRECTIVES:
        lines.append(f"- **Response Length:** {_LENGTH_DIRECTIVES[response_length]}")

    valid_traits = [t for t in personality_traits if t in _TRAIT_DIRECTIVES]
    if valid_traits:
        trait_lines = "; ".join(_TRAIT_DIRECTIVES[t] for t in valid_traits)
        lines.append(f"- **Personality:** {trait_lines}")

    if not lines:
        return core_prompt

    profile_section = "\n\n## Communication Profile\n" + "\n".join(lines)
    return core_prompt.rstrip() + profile_section


async def generate_project_proposal(
    category: str,
    description: str,
    follow_up_answers: list[tuple[str, str]],
    model: str | None = None,
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> ProjectProposalResult:
    """
    Generate a complete project proposal with specialized bots and rooms.

    Analyzes the project description and follow-up answers to design a team
    of specialized AI bots organized into rooms with appropriate response modes.

    Args:
        category: The purpose category
        description: The user's project description
        follow_up_answers: List of (question, answer) pairs from follow-up questions
        model: Model to use for generation
        bot_models: Per-bot model slots (checked first for "default")
        resolved_env: Per-bot resolved environment override

    Returns:
        ProjectProposalResult with project name, description, bots, and rooms
    """
    if model is None:
        model = resolve_main_model(bot_models=bot_models, resolved_env=resolved_env)

    # Format follow-up Q&A
    qa_section = ""
    if follow_up_answers:
        qa_section = "\n## User's Answers\n"
        for question, answer in follow_up_answers:
            if answer.strip():
                qa_section += f"- Q: {question}\n  A: {answer}\n"

    prompt_text = "Design a team of specialized AI bots for this project."
    prompt_text += f"""

## Project Context
- Category: {category}
- Description: "{description}"
{qa_section}
## Your Task

Design a team of AI bots that work together to accomplish this project.

### Bot Naming Rules (CRITICAL)
**FORBIDDEN names** — NEVER use any of these generic words as bot names:
Lead, Leader, Specialist, Expert, Manager, Coordinator, Assistant, Helper, Advisor, Analyst, Bot

**REQUIRED** — Each bot MUST have a creative, evocative, 1-2 word name that reflects its
personality or domain. Think of names like characters or code-names:
- Good examples: "Cipher" (security), "Quill" (writing), "Forge" (engineering),
  "Prism" (analysis), "Echo" (communication), "Atlas" (research), "Spark" (ideas),
  "Nexus" (coordination), "Sable" (design), "Meridian" (planning)
- The name should hint at what the bot does without being a literal job title

### For Each Bot, Provide:
1. **name**: A creative, evocative name (see rules above)
2. **description**: One-line description of its role
3. **role**: default, lead, reviewer, observer, or specialist
4. **system_prompt**: Comprehensive system prompt (300+ words) focused ONLY on:
   - The bot's identity, expertise, and domain knowledge
   - Its specific responsibilities within the team
   - How it interacts with other bots
   - DO NOT include communication style or tone in the system prompt — that goes in
     the structured personality fields below
5. **tone**: One of: professional, friendly, casual, concise, playful, witty
6. **expertise_level**: One of: beginner, intermediate, expert, authority
7. **response_length**: One of: brief, moderate, detailed, comprehensive
8. **personality_traits**: Pick 2-4 from: patient, assertive, creative, analytical,
   empathetic, humorous, encouraging, direct, methodical, innovative

### Personality Diversity
Each bot MUST have a distinct personality profile. Vary the tone, expertise level, and
traits across the team so that bots feel like different characters, not clones.

### Room Organization
Organize the bots into rooms:
1. Each room represents a workflow stage, discussion topic, or collaboration space
2. Choose the appropriate response mode:
   - parallel: All bots respond independently
   - sequential: Bots respond one after another
   - chain: Each bot builds on the previous bot's response
   - router: One bot routes to the appropriate specialist
   - debate: Bots argue different positions
   - waterfall: Pipeline with conditional handoffs
   - relay: Bots take turns in a rotating fashion
   - consensus: Bots discuss and converge on a shared answer
   - interview: One bot interviews the user, then hands off
3. Assign the relevant bots to each room

## Guidelines
- Design the right number of bots for the project (typically 2-6)
- Design the right number of rooms (typically 1-3)
- Each bot should have a distinct specialty — avoid overlap
- System prompts should be detailed and specific, not generic
- Room assignments should make logical sense for the workflow
- bot_names in rooms must exactly match the bot names you define"""

    instruction = "Generate the complete project proposal with bots and rooms in JSON format:"

    try:
        result = await _extract_with_retry(
            ProjectProposalResult,
            prompt_text,
            model,
            instruction_template=instruction,
        )
        return result.model  # type: ignore[attr-defined, no-any-return]
    except Exception:
        logger.exception("Project proposal generation failed, using fallback")
        return ProjectProposalResult(
            project_name=f"{category.title()} Project",
            project_description=description[:100] if description else "AI-assisted project",
            bots=[
                ProposalBotSpec(
                    name="Nexus",
                    description="Project coordinator who keeps the team aligned and on track",
                    role="lead",
                    system_prompt=(
                        f"You are Nexus, the coordinator for a {category} project. "
                        f"You synthesize input from all team members, identify blockers, "
                        f"set priorities, and ensure the team moves toward its goals. "
                        f"You track progress, mediate disagreements, and maintain a "
                        f"holistic view of the project. When team members provide "
                        f"conflicting advice, you weigh trade-offs and make clear "
                        f"recommendations. Project context: {description}"
                    ),
                    tone="professional",
                    expertise_level="expert",
                    response_length="moderate",
                    personality_traits=["assertive", "methodical", "direct"],
                ),
                ProposalBotSpec(
                    name="Forge",
                    description=f"Deep domain expert in {category} who handles the core work",
                    role="specialist",
                    system_prompt=(
                        f"You are Forge, the domain expert for a {category} project. "
                        f"You bring deep, hands-on expertise to every task. You don't "
                        f"just advise — you build, analyze, and produce concrete output. "
                        f"You explain your reasoning and flag edge cases that others "
                        f"might miss. You take pride in precision and craftsmanship. "
                        f"Project context: {description}"
                    ),
                    tone="friendly",
                    expertise_level="authority",
                    response_length="detailed",
                    personality_traits=["creative", "analytical", "patient"],
                ),
            ],
            rooms=[
                ProposalRoomSpec(
                    name="Main",
                    description="Primary collaboration room",
                    response_mode="parallel",
                    bot_names=["Nexus", "Forge"],
                ),
            ],
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
    frequency: str = Field(
        description="How often, e.g. 'daily', 'weekly on Mondays', 'every morning'"
    )


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
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
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
        bot_models: Per-bot model slots (checked first for "utility")
        resolved_env: Per-bot resolved environment override

    Returns:
        CreationAnalysis with user_context, suggested_todos, suggested_schedules
    """
    if model is None:
        model = resolve_utility_model(bot_models=bot_models, resolved_env=resolved_env)

    # Format follow-up Q&A
    qa_section = ""
    if follow_up_answers:
        qa_section = "\n## User's Answers\n"
        for question, answer in follow_up_answers:
            if answer.strip():
                qa_section += f"- Q: {question}\n  A: {answer}\n"

    prompt_text = (
        "Analyze the following bot creation context"
        " to extract structured information"
        " about the user."
    )
    prompt_text += f"""

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
        return result.model  # type: ignore[attr-defined, no-any-return]
    except Exception:
        logger.exception("Creation context analysis failed")
        return CreationAnalysis(
            user_context="No personal details extracted yet.",
            suggested_todos=[],
            suggested_schedules=[],
        )
