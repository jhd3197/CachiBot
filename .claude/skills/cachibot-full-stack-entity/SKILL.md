---
name: cachibot-full-stack-entity
description: Add a complete full-stack entity to CachiBot spanning database table, repository, Pydantic models, API routes, TypeScript types, API client, and Zustand store. Use this skill when adding a new data entity or resource that needs persistence and CRUD across the entire stack — e.g., "add bookmarks", "add a reminders system", "create a templates feature".
metadata:
  author: cachibot
  version: "1.0"
---

# CachiBot Full-Stack Entity

Add a new persistent data entity across all layers: database, repository, models, API, frontend types, API client, and Zustand store.

## Layer Overview

```
Database (SQLite)
  └── Repository (async CRUD)
      └── Pydantic Models (request/response schemas)
          └── API Routes (FastAPI endpoints)
              └── Frontend Types (TypeScript interfaces)
                  └── API Client (fetch functions)
                      └── Zustand Store (state management)
```

## Step 1: Database Table

Edit `cachibot/storage/database.py` — add to the `init_db()` `CREATE TABLE` block:

```sql
-- Your entities
CREATE TABLE IF NOT EXISTS your_entities (
    id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_your_entities_bot ON your_entities(bot_id);
CREATE INDEX IF NOT EXISTS idx_your_entities_status ON your_entities(status);
```

**Conventions:**
- Table name: `snake_case`, plural
- Always include `id TEXT PRIMARY KEY`
- Bot-scoped entities always have `bot_id TEXT NOT NULL` with an index
- Timestamps as ISO 8601 TEXT: `created_at`, `updated_at`
- JSON fields stored as TEXT with `DEFAULT '{}'` or `DEFAULT '[]'`
- Foreign keys with `ON DELETE CASCADE` or `ON DELETE SET NULL`

**If adding columns to an existing table**, add a migration at the end of `init_db()`:

```python
migrations = [
    # ... existing migrations ...
    "ALTER TABLE your_entities ADD COLUMN new_column TEXT",
]
```

## Step 2: Repository

Add to `cachibot/storage/repository.py` (or create a new repo file):

```python
class YourEntityRepository:
    """CRUD operations for your_entities table."""

    async def get_by_bot(self, bot_id: str) -> list[dict]:
        db = await get_db()
        async with db.execute(
            "SELECT * FROM your_entities WHERE bot_id = ? ORDER BY created_at DESC",
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_by_id(self, entity_id: str) -> dict | None:
        db = await get_db()
        async with db.execute(
            "SELECT * FROM your_entities WHERE id = ?",
            (entity_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def save(self, entity: dict) -> None:
        db = await get_db()
        await db.execute(
            """INSERT OR REPLACE INTO your_entities
               (id, bot_id, title, description, status, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity["id"],
                entity["bot_id"],
                entity["title"],
                entity.get("description", ""),
                entity.get("status", "active"),
                entity.get("metadata", "{}"),
                entity["created_at"],
                entity["updated_at"],
            ),
        )
        await db.commit()

    async def update(self, entity_id: str, updates: dict) -> None:
        db = await get_db()
        set_clauses = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [entity_id]
        await db.execute(
            f"UPDATE your_entities SET {set_clauses} WHERE id = ?",
            values,
        )
        await db.commit()

    async def delete(self, entity_id: str) -> None:
        db = await get_db()
        await db.execute("DELETE FROM your_entities WHERE id = ?", (entity_id,))
        await db.commit()
```

## Step 3: Pydantic Models

Create `cachibot/models/your_entity.py`:

```python
"""Your Entity Models — Pydantic schemas for the API."""

from pydantic import BaseModel


class YourEntityCreate(BaseModel):
    title: str
    description: str = ""


class YourEntityUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class YourEntityResponse(BaseModel):
    id: str
    botId: str
    title: str
    description: str
    status: str
    createdAt: str
    updatedAt: str

    @classmethod
    def from_db(cls, row: dict) -> "YourEntityResponse":
        return cls(
            id=row["id"],
            botId=row["bot_id"],
            title=row["title"],
            description=row["description"] or "",
            status=row["status"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )
```

## Step 4: API Routes

Create `cachibot/api/routes/your_entities.py`:

```python
"""Your Entity API Routes"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from cachibot.api.auth import require_bot_access
from cachibot.models.auth import User
from cachibot.models.your_entity import (
    YourEntityCreate,
    YourEntityResponse,
    YourEntityUpdate,
)
from cachibot.storage.repository import YourEntityRepository

router = APIRouter(prefix="/api/bots/{bot_id}/your-entities", tags=["your-entities"])
repo = YourEntityRepository()


@router.get("")
async def list_entities(
    bot_id: str, user: User = Depends(require_bot_access)
) -> list[YourEntityResponse]:
    items = await repo.get_by_bot(bot_id)
    return [YourEntityResponse.from_db(i) for i in items]


@router.post("", status_code=201)
async def create_entity(
    bot_id: str, req: YourEntityCreate, user: User = Depends(require_bot_access)
) -> YourEntityResponse:
    now = datetime.now(timezone.utc).isoformat()
    entity = {
        "id": str(uuid.uuid4()),
        "bot_id": bot_id,
        "title": req.title,
        "description": req.description,
        "status": "active",
        "metadata": "{}",
        "created_at": now,
        "updated_at": now,
    }
    await repo.save(entity)
    return YourEntityResponse.from_db(entity)


@router.get("/{entity_id}")
async def get_entity(
    bot_id: str, entity_id: str, user: User = Depends(require_bot_access)
) -> YourEntityResponse:
    item = await repo.get_by_id(entity_id)
    if not item or item["bot_id"] != bot_id:
        raise HTTPException(404, "Entity not found")
    return YourEntityResponse.from_db(item)


@router.put("/{entity_id}")
async def update_entity(
    bot_id: str,
    entity_id: str,
    req: YourEntityUpdate,
    user: User = Depends(require_bot_access),
) -> YourEntityResponse:
    item = await repo.get_by_id(entity_id)
    if not item or item["bot_id"] != bot_id:
        raise HTTPException(404, "Entity not found")
    updates = req.model_dump(exclude_unset=True)
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await repo.update(entity_id, updates)
    updated = await repo.get_by_id(entity_id)
    return YourEntityResponse.from_db(updated)


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(
    bot_id: str, entity_id: str, user: User = Depends(require_bot_access)
) -> None:
    item = await repo.get_by_id(entity_id)
    if not item or item["bot_id"] != bot_id:
        raise HTTPException(404, "Entity not found")
    await repo.delete(entity_id)
```

Register in `cachibot/api/server.py`:

```python
from cachibot.api.routes import your_entities
app.include_router(your_entities.router, tags=["your-entities"])
```

## Step 5: Frontend Types

Add to `frontend/src/types/index.ts`:

```typescript
// =============================================================================
// YOUR ENTITY TYPES
// =============================================================================

export interface YourEntity {
  id: string
  botId: string
  title: string
  description: string
  status: string
  createdAt: string
  updatedAt: string
}

export interface YourEntityCreate {
  title: string
  description?: string
}

export interface YourEntityUpdate {
  title?: string
  description?: string
  status?: string
}
```

## Step 6: API Client

Add to `frontend/src/api/client.ts` (or create a new file in `frontend/src/api/`):

```typescript
import type { YourEntity, YourEntityCreate, YourEntityUpdate } from '../types'

export async function getYourEntities(botId: string): Promise<YourEntity[]> {
  const res = await fetchWithAuth(`/api/bots/${botId}/your-entities`)
  if (!res.ok) throw new Error('Failed to fetch entities')
  return res.json()
}

export async function createYourEntity(botId: string, data: YourEntityCreate): Promise<YourEntity> {
  const res = await fetchWithAuth(`/api/bots/${botId}/your-entities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to create entity')
  return res.json()
}

export async function updateYourEntity(
  botId: string, entityId: string, data: YourEntityUpdate
): Promise<YourEntity> {
  const res = await fetchWithAuth(`/api/bots/${botId}/your-entities/${entityId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error('Failed to update entity')
  return res.json()
}

export async function deleteYourEntity(botId: string, entityId: string): Promise<void> {
  const res = await fetchWithAuth(`/api/bots/${botId}/your-entities/${entityId}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('Failed to delete entity')
}
```

## Step 7: Zustand Store

Create `frontend/src/stores/your-entities.ts`:

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { YourEntity } from '../types'

interface YourEntityState {
  entities: YourEntity[]
  loading: boolean
  error: string | null

  setEntities: (entities: YourEntity[]) => void
  addEntity: (entity: YourEntity) => void
  updateEntity: (id: string, updates: Partial<YourEntity>) => void
  removeEntity: (id: string) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useYourEntityStore = create<YourEntityState>()(
  persist(
    (set) => ({
      entities: [],
      loading: false,
      error: null,

      setEntities: (entities) => set({ entities, error: null }),
      addEntity: (entity) => set((s) => ({
        entities: [entity, ...s.entities],
      })),
      updateEntity: (id, updates) => set((s) => ({
        entities: s.entities.map((e) =>
          e.id === id ? { ...e, ...updates } : e
        ),
      })),
      removeEntity: (id) => set((s) => ({
        entities: s.entities.filter((e) => e.id !== id),
      })),
      setLoading: (loading) => set({ loading }),
      setError: (error) => set({ error }),
    }),
    { name: 'cachibot-your-entities' }
  )
)
```

## Full Checklist

### Backend
- [ ] Table created in `cachibot/storage/database.py`
- [ ] Repository class in `cachibot/storage/repository.py`
- [ ] Pydantic models in `cachibot/models/`
- [ ] API routes in `cachibot/api/routes/`
- [ ] Router registered in `cachibot/api/server.py`

### Frontend
- [ ] TypeScript types in `frontend/src/types/index.ts`
- [ ] API client functions in `frontend/src/api/`
- [ ] Zustand store in `frontend/src/stores/`
- [ ] `npm run build` passes
