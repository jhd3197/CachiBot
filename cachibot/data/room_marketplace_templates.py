"""Bundled room marketplace templates for room creation.

Local fallback copy — used when remote marketplace is unavailable.
"""

from typing import Any, Literal, TypedDict

RoomTemplateCategory = Literal[
    "coding",
    "creative",
    "productivity",
    "data",
    "learning",
    "marketing",
    "health",
    "finance",
]


class RoomBotSpecDefinition(TypedDict):
    template_id: str
    role: str
    position: str | None
    keywords: list[str]
    waterfall_condition: str | None


class RoomTemplateDefinition(TypedDict):
    id: str
    name: str
    description: str
    icon: str
    color: str
    category: RoomTemplateCategory
    tags: list[str]
    response_mode: str
    bots: list[RoomBotSpecDefinition]
    settings: dict[str, Any]
    rating: float
    downloads: int


ROOM_MARKETPLACE_TEMPLATES: list[RoomTemplateDefinition] = [
    {
        "id": "code-review-panel",
        "name": "Code Review Panel",
        "description": (
            "Paste code and get layered review: correctness, security, then documentation"
        ),
        "icon": "code",
        "color": "#ef4444",
        "category": "coding",
        "tags": ["code review", "security", "documentation", "quality"],
        "response_mode": "chain",
        "bots": [
            {
                "template_id": "code-reviewer",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "bug-hunter",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "doc-writer",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 3,
            "auto_relevance": True,
        },
        "rating": 4.9,
        "downloads": 14200,
    },
    {
        "id": "debate-club",
        "name": "Debate Club",
        "description": "Structured arguments on any topic with a judge rendering the final verdict",
        "icon": "brain",
        "color": "#a855f7",
        "category": "creative",
        "tags": ["debate", "arguments", "critical thinking", "analysis"],
        "response_mode": "debate",
        "bots": [
            {
                "template_id": "brainstorm-buddy",
                "role": "default",
                "position": "FOR",
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "concept-explainer",
                "role": "default",
                "position": "AGAINST",
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "research-assistant",
                "role": "default",
                "position": "NEUTRAL",
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
            "debate_rounds": 2,
        },
        "rating": 4.8,
        "downloads": 11500,
    },
    {
        "id": "research-team",
        "name": "Research Team",
        "description": (
            "Research question to data patterns to polished summary — a full research pipeline"
        ),
        "icon": "microscope",
        "color": "#f59e0b",
        "category": "productivity",
        "tags": ["research", "analysis", "data", "summary"],
        "response_mode": "sequential",
        "bots": [
            {
                "template_id": "research-assistant",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "csv-analyst",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "doc-writer",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.7,
        "downloads": 9800,
    },
    {
        "id": "smart-help-desk",
        "name": "Smart Help Desk",
        "description": "AI automatically routes your questions to the right specialist bot",
        "icon": "laptop",
        "color": "#3b82f6",
        "category": "coding",
        "tags": ["help desk", "routing", "support", "specialist"],
        "response_mode": "router",
        "bots": [
            {
                "template_id": "code-reviewer",
                "role": "specialist",
                "position": None,
                "keywords": ["code", "review", "refactor", "function", "class"],
                "waterfall_condition": None,
            },
            {
                "template_id": "sql-expert",
                "role": "specialist",
                "position": None,
                "keywords": ["sql", "query", "database", "table", "join"],
                "waterfall_condition": None,
            },
            {
                "template_id": "tech-support",
                "role": "specialist",
                "position": None,
                "keywords": ["install", "error", "crash", "setup", "config"],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 3,
            "auto_relevance": True,
            "routing_strategy": "llm",
        },
        "rating": 4.7,
        "downloads": 10300,
    },
    {
        "id": "content-pipeline",
        "name": "Content Pipeline",
        "description": "Ideas to draft to polished content — stops when the piece is ready",
        "icon": "pen-tool",
        "color": "#f97316",
        "category": "creative",
        "tags": ["content", "writing", "pipeline", "creative"],
        "response_mode": "waterfall",
        "bots": [
            {
                "template_id": "brainstorm-buddy",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": "always_continue",
            },
            {
                "template_id": "copywriter",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": "resolved",
            },
            {
                "template_id": "story-writer",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": "resolved",
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.6,
        "downloads": 8700,
    },
    {
        "id": "learning-lab",
        "name": "Learning Lab",
        "description": "Get simultaneous explanations from three different perspectives at once",
        "icon": "brain",
        "color": "#ec4899",
        "category": "learning",
        "tags": ["learning", "education", "tutoring", "quiz"],
        "response_mode": "parallel",
        "bots": [
            {
                "template_id": "language-tutor",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "quiz-master",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "concept-explainer",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.6,
        "downloads": 7900,
    },
    {
        "id": "data-analysis-pipeline",
        "name": "Data Analysis Pipeline",
        "description": "Full data analysis: profiling, charts, and query optimization in a chain",
        "icon": "bar-chart",
        "color": "#22c55e",
        "category": "data",
        "tags": ["data", "analysis", "visualization", "sql"],
        "response_mode": "chain",
        "bots": [
            {
                "template_id": "csv-analyst",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "data-visualizer",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "sql-expert",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.8,
        "downloads": 12100,
    },
    {
        "id": "writing-workshop",
        "name": "Writing Workshop",
        "description": (
            "Get contrasting creative feedback on your drafts"
            " from narrative and commercial perspectives"
        ),
        "icon": "sparkles",
        "color": "#ec4899",
        "category": "creative",
        "tags": ["writing", "feedback", "creative", "debate"],
        "response_mode": "debate",
        "bots": [
            {
                "template_id": "story-writer",
                "role": "default",
                "position": "FOR",
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "copywriter",
                "role": "default",
                "position": "AGAINST",
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "brainstorm-buddy",
                "role": "default",
                "position": "NEUTRAL",
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
            "debate_rounds": 2,
        },
        "rating": 4.5,
        "downloads": 6800,
    },
    {
        "id": "bug-triage",
        "name": "Bug Triage",
        "description": "Investigate, fix, and document bugs — stops when the issue is resolved",
        "icon": "ghost",
        "color": "#f59e0b",
        "category": "coding",
        "tags": ["debugging", "triage", "documentation", "fix"],
        "response_mode": "waterfall",
        "bots": [
            {
                "template_id": "bug-hunter",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": "always_continue",
            },
            {
                "template_id": "code-reviewer",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": "resolved",
            },
            {
                "template_id": "doc-writer",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": "resolved",
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.7,
        "downloads": 9400,
    },
    {
        "id": "meeting-prep",
        "name": "Meeting Prep",
        "description": (
            "Background research, agenda creation, and follow-up draft emails — all in sequence"
        ),
        "icon": "pen-tool",
        "color": "#8b5cf6",
        "category": "productivity",
        "tags": ["meetings", "preparation", "agenda", "follow-up"],
        "response_mode": "sequential",
        "bots": [
            {
                "template_id": "research-assistant",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "task-manager",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "email-writer",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.5,
        "downloads": 7200,
    },
    {
        "id": "marketing-war-room",
        "name": "Marketing War Room",
        "description": (
            "Debate marketing strategy from three angles: growth, creative, and data-driven"
        ),
        "icon": "megaphone",
        "color": "#8b5cf6",
        "category": "marketing",
        "tags": ["marketing", "strategy", "debate", "growth"],
        "response_mode": "debate",
        "bots": [
            {
                "template_id": "marketing-strategist",
                "role": "default",
                "position": "FOR",
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "ad-copywriter",
                "role": "default",
                "position": "AGAINST",
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "seo-optimizer",
                "role": "default",
                "position": "NEUTRAL",
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
            "debate_rounds": 2,
        },
        "rating": 4.8,
        "downloads": 8900,
    },
    {
        "id": "seo-content-pipeline",
        "name": "SEO Content Pipeline",
        "description": "Full SEO workflow: research keywords, write optimized copy, then schedule posts",
        "icon": "search",
        "color": "#22c55e",
        "category": "marketing",
        "tags": ["seo", "content", "pipeline", "social media"],
        "response_mode": "chain",
        "bots": [
            {
                "template_id": "seo-optimizer",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "copywriter",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "social-media-manager",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.7,
        "downloads": 9600,
    },
    {
        "id": "wellness-dashboard",
        "name": "Wellness Dashboard",
        "description": "Get fitness, nutrition, and mindfulness advice simultaneously from specialists",
        "icon": "heart",
        "color": "#ef4444",
        "category": "health",
        "tags": ["fitness", "nutrition", "mindfulness", "wellness"],
        "response_mode": "parallel",
        "bots": [
            {
                "template_id": "fitness-coach",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "nutrition-advisor",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "mindfulness-guide",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.7,
        "downloads": 7400,
    },
    {
        "id": "financial-review",
        "name": "Financial Review",
        "description": (
            "Full financial checkup: budget analysis, investment review, then tax optimization"
        ),
        "icon": "bar-chart",
        "color": "#22c55e",
        "category": "finance",
        "tags": ["budget", "investment", "tax", "financial planning"],
        "response_mode": "sequential",
        "bots": [
            {
                "template_id": "budget-planner",
                "role": "lead",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "investment-analyst",
                "role": "specialist",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
            {
                "template_id": "tax-helper",
                "role": "reviewer",
                "position": None,
                "keywords": [],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 5,
            "auto_relevance": True,
        },
        "rating": 4.6,
        "downloads": 6800,
    },
    {
        "id": "full-stack-review",
        "name": "Full Stack Review",
        "description": "Route your questions to the right coding specialist automatically",
        "icon": "code",
        "color": "#3b82f6",
        "category": "coding",
        "tags": ["code review", "api", "debugging", "routing"],
        "response_mode": "router",
        "bots": [
            {
                "template_id": "code-reviewer",
                "role": "specialist",
                "position": None,
                "keywords": ["code", "review", "refactor", "quality", "pattern"],
                "waterfall_condition": None,
            },
            {
                "template_id": "api-designer",
                "role": "specialist",
                "position": None,
                "keywords": ["api", "endpoint", "rest", "graphql", "schema"],
                "waterfall_condition": None,
            },
            {
                "template_id": "bug-hunter",
                "role": "specialist",
                "position": None,
                "keywords": ["bug", "error", "debug", "crash", "fix"],
                "waterfall_condition": None,
            },
        ],
        "settings": {
            "cooldown_seconds": 3,
            "auto_relevance": True,
            "routing_strategy": "llm",
        },
        "rating": 4.8,
        "downloads": 10500,
    },
]

ROOM_CATEGORY_INFO: dict[str, dict[str, str]] = {
    "coding": {
        "id": "coding",
        "name": "Coding & Development",
        "description": "Multi-bot coding workflows",
    },
    "creative": {
        "id": "creative",
        "name": "Creative & Writing",
        "description": "Collaborative creative workflows",
    },
    "productivity": {
        "id": "productivity",
        "name": "Productivity",
        "description": "Productive multi-bot workflows",
    },
    "data": {
        "id": "data",
        "name": "Data & Analysis",
        "description": "Data analysis pipelines",
    },
    "learning": {
        "id": "learning",
        "name": "Learning & Education",
        "description": "Multi-perspective learning rooms",
    },
    "marketing": {
        "id": "marketing",
        "name": "Marketing & Growth",
        "description": "Marketing strategy and content workflows",
    },
    "health": {
        "id": "health",
        "name": "Health & Wellness",
        "description": "Fitness, nutrition, and wellness rooms",
    },
    "finance": {
        "id": "finance",
        "name": "Finance & Business",
        "description": "Financial planning and analysis workflows",
    },
}


def get_all_room_templates() -> list[RoomTemplateDefinition]:
    return list(ROOM_MARKETPLACE_TEMPLATES)


def get_room_templates_by_category(category: RoomTemplateCategory) -> list[RoomTemplateDefinition]:
    return [t for t in ROOM_MARKETPLACE_TEMPLATES if t["category"] == category]


def get_room_template_by_id(template_id: str) -> RoomTemplateDefinition | None:
    for t in ROOM_MARKETPLACE_TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def search_room_templates(query: str) -> list[RoomTemplateDefinition]:
    query_lower = query.lower()
    return [
        t
        for t in ROOM_MARKETPLACE_TEMPLATES
        if query_lower in t["name"].lower()
        or query_lower in t["description"].lower()
        or any(query_lower in tag.lower() for tag in t["tags"])
    ]
