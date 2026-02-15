---
name: cachibot-api-route
description: Add new REST API endpoints to CachiBot's FastAPI backend following the project's conventions. Use this skill when adding API routes, endpoints, or REST resources — e.g., "add an API for reminders", "create a CRUD endpoint for bookmarks".
metadata:
  author: cachibot
  version: "1.0"
---

# CachiBot API Route Creation

Add new REST API endpoints following CachiBot's FastAPI patterns with Pydantic models, auth, and bot-scoping.

## Architecture Overview

- **Framework**: FastAPI with APIRouter per domain
- **Auth**: JWT-based via `require_bot_access` dependency
- **Models**: Pydantic BaseModel for request/response schemas
- **Storage**: Repository pattern with PostgreSQL (SQLAlchemy 2.0 + asyncpg)
- **Registration**: Routers included in `server.py`

## Step-by-Step Process

### 1. Define Pydantic Models

Create or extend models in `src/cachibot/models/<domain>.py`:

```python
"""
<Domain> Models

Pydantic schemas for <domain> API.
"""

from pydantic import BaseModel


class YourItemCreate(BaseModel):
    """Request body for creating an item."""

    name: str
    description: str = ""
    # Add fields as needed


class YourItemUpdate(BaseModel):
    """Request body for updating an item (all fields optional)."""

    name: str | None = None
    description: str | None = None


class YourItemResponse(BaseModel):
    """Response model for an item."""

    id: str
    botId: str  # camelCase for frontend
    name: str
    description: str
    createdAt: str
    updatedAt: str

    @classmethod
    def from_db(cls, row: dict) -> "YourItemResponse":
        """Convert a database row to a response model."""
        return cls(
            id=row["id"],
            botId=row["bot_id"],
            name=row["name"],
            description=row["description"] or "",
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )
```

### 2. Create the Route File

Create `src/cachibot/api/routes/<domain>.py`:

```python
"""
<Domain> API Routes

Endpoints for managing <domain resources>.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access
from cachibot.models.auth import User
from cachibot.storage.repository import YourRepository

router = APIRouter(prefix="/api/bots/{bot_id}/<domain>", tags=["<domain>"])

# Repository instance
repo = YourRepository()


@router.get("")
async def list_items(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[YourItemResponse]:
    """List all items for a bot."""
    items = await repo.get_items_by_bot(bot_id)
    return [YourItemResponse.from_db(item) for item in items]


@router.post("", status_code=201)
async def create_item(
    bot_id: str,
    req: YourItemCreate,
    user: User = Depends(require_bot_access),
) -> YourItemResponse:
    """Create a new item."""
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    item_id = str(uuid.uuid4())

    item = {
        "id": item_id,
        "bot_id": bot_id,
        "name": req.name,
        "description": req.description,
        "created_at": now,
        "updated_at": now,
    }
    await repo.save_item(item)
    return YourItemResponse.from_db(item)


@router.get("/{item_id}")
async def get_item(
    bot_id: str,
    item_id: str,
    user: User = Depends(require_bot_access),
) -> YourItemResponse:
    """Get a specific item."""
    item = await repo.get_item(item_id)
    if item is None or item["bot_id"] != bot_id:
        raise HTTPException(status_code=404, detail="Item not found")
    return YourItemResponse.from_db(item)


@router.put("/{item_id}")
async def update_item(
    bot_id: str,
    item_id: str,
    req: YourItemUpdate,
    user: User = Depends(require_bot_access),
) -> YourItemResponse:
    """Update an item."""
    item = await repo.get_item(item_id)
    if item is None or item["bot_id"] != bot_id:
        raise HTTPException(status_code=404, detail="Item not found")

    updates = req.model_dump(exclude_unset=True)
    if updates:
        from datetime import datetime, timezone
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await repo.update_item(item_id, updates)

    updated = await repo.get_item(item_id)
    return YourItemResponse.from_db(updated)


@router.delete("/{item_id}", status_code=204)
async def delete_item(
    bot_id: str,
    item_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete an item."""
    item = await repo.get_item(item_id)
    if item is None or item["bot_id"] != bot_id:
        raise HTTPException(status_code=404, detail="Item not found")
    await repo.delete_item(item_id)
```

### 3. Register the Router

Edit `src/cachibot/api/server.py`:

```python
# Add import
from cachibot.api.routes import your_domain

# Add in create_app(), after existing routers:
app.include_router(your_domain.router, tags=["your_domain"])
```

Note: If the router already has a full prefix (e.g., `/api/bots/{bot_id}/items`), don't add `prefix="/api"` — that would double the prefix. Use `prefix="/api"` only for routers that don't have `/api` in their own prefix.

### 4. Add the route module to `__init__.py`

Make sure `src/cachibot/api/routes/__init__.py` exports the new module (or at minimum that it's importable from the routes package).

## Conventions

### URL Patterns

```
GET    /api/bots/{bot_id}/<domain>              → list
POST   /api/bots/{bot_id}/<domain>              → create (201)
GET    /api/bots/{bot_id}/<domain>/{item_id}    → get
PUT    /api/bots/{bot_id}/<domain>/{item_id}    → update
DELETE /api/bots/{bot_id}/<domain>/{item_id}    → delete (204)

# Batch/action endpoints use underscore prefix:
POST   /api/bots/{bot_id}/<domain>/_clear       → bulk action
POST   /api/bots/{bot_id}/<domain>/{id}/_archive → action on item
```

### Auth Pattern

All bot-scoped endpoints use:

```python
user: User = Depends(require_bot_access)
```

This validates the JWT and checks the user owns the bot.

For non-bot-scoped endpoints (global resources), use:

```python
from cachibot.api.auth import require_user
user: User = Depends(require_user)
```

### Response Field Naming

- **Python/DB**: `snake_case` (e.g., `bot_id`, `created_at`)
- **API responses**: `camelCase` (e.g., `botId`, `createdAt`)
- Use `from_db()` classmethod on response models to convert

### Error Handling

```python
# 404 for missing resources
raise HTTPException(status_code=404, detail="Item not found")

# 400 for invalid input
raise HTTPException(status_code=400, detail="Invalid name: must be non-empty")

# 409 for conflicts
raise HTTPException(status_code=409, detail="Item with this name already exists")
```

## Checklist

- [ ] Pydantic models created for request/response in `src/cachibot/models/`
- [ ] Route file created in `src/cachibot/api/routes/`
- [ ] Router uses `APIRouter(prefix="/api/bots/{bot_id}/<domain>", tags=[...])`
- [ ] All endpoints have `user: User = Depends(require_bot_access)`
- [ ] Response models use camelCase field names
- [ ] Router registered in `src/cachibot/api/server.py`
- [ ] Route module importable from `cachibot.api.routes`
