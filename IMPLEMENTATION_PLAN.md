# Implementation Plan - Memory Base Service

## Overview
Step-by-step implementation plan for building the multi-tenant memory base service with SurrealDB, LangChain, and Redis.

## Current Status

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Foundation & Infrastructure | ✅ Complete | 4/4 tasks |
| Phase 2: Data Models & Schema | ✅ Complete | 2/2 tasks |
| Phase 3: Core Services | ✅ Complete | 3/3 tasks |
| Phase 4: Database Operations & Retrievers | 🔄 In Progress | 3/5 tasks |
| Phase 5: Redis Queue & Worker | ⏸️ Pending | 0/2 tasks |
| Phase 6: API Endpoints | 🔄 In Progress | 3/4 tasks |
| Phase 7: Testing & Validation | ⏸️ Pending | 0/2 tasks |
| Phase 8: Documentation & Polish | ⏸️ Pending | 0/2 tasks |

**Overall Progress**: 15/24 tasks completed (62%)

---

## Phase 1: Foundation & Infrastructure

### Task 1.1: Update Dependencies ✅ (Already done)
**Status**: Dependencies are already in `pyproject.toml`

**Files**: `app/pyproject.toml`
- ✅ `langchain>=1.1.0`
- ✅ `langchain-community>=0.4.1`
- ✅ `langchain-openai>=1.1.0`
- ✅ `surrealdb>=1.0.7`
- ✅ `redis>=7.1.0`
- ✅ `pydantic>=2.12.5`
- ✅ `httpx>=0.28.1`

### Task 1.2: Update Configuration ✅
**Status**: Completed

**File**: `app/server/config.py`

**Added to Settings class**:
- ✅ `openrouter_api_key: str` (from env: `OPENROUTER_API_KEY`)
- ✅ `openrouter_base_url: str` (default: `"https://openrouter.ai/api/v1"`)
- ✅ `llm_model: str` (from env: `LLM_MODEL`, default: `"google/gemini-2.5-flash"`)
- ✅ `embedding_model: str` (from env: `EMBEDDING_MODEL`, default: `"openai/text-embedding-3-small"`)
- ✅ `redis_queue_name: str` (from env: `REDIS_QUEUE_NAME`, default: `"memory:ingest:queue"`)
- ✅ `surreal_namespace: str` (from env: `SURREAL_NAMESPACE`, default: `"memory"`)
- ✅ `surreal_database: str` (from env: `SURREAL_DATABASE`, default: `"default"`)

### Task 1.3: Update Docker Compose ✅
**Status**: Completed

**File**: `docker-compose.yml`

**Added services**:
1. ✅ **Redis service** (using Valkey):
   - Image: `valkey/valkey:alpine`
   - Networks: `default`, `surreal-net`
   - Volume: `./redis.data/:/data`

2. ✅ **Worker service**:
   - Build: `app`
   - Command: `python -m worker`
   - Networks: `default`, `surreal-net`
   - Depends on: `redis`

3. ✅ **Networks**:
   - `default` network added for internal communication

### Task 1.4: Integrate Database into Server Lifespan ✅
**Status**: Completed

**File**: `app/server/server.py`

**Updated lifespan function**:
- ✅ Import `db` module
- ✅ Call `await db.get_db()` on startup
- ✅ Call `await db.close_db()` on shutdown
- ✅ Added proper logging for lifecycle events

**File**: `app/server/db.py`

**Updated**:
- ✅ `get_db()` now uses namespace and database from config
- ✅ Proper connection lifecycle management

---

## Phase 2: Data Models & Schema ✅

### Task 2.1: Create SurrealDB Schema Module ✅
**Status**: Completed (using schema generator approach)

**Files**: 
- `app/server/schema_generator.py` - Schema generator utility
- `app/apps/base/schemas.py` - Base `SurrealTenantSchema` with tenant_id, timestamps, soft delete
- `app/apps/memory/schemas.py` - Memory domain schemas

**Schema Definitions** (using Pydantic models with schema generator):
- ✅ `KnowledgeSource` - Extends `SurrealTenantSchema`
  - Fields: `source_type`, `source_id`, `sensor_name`
  - Indexes: `idx_tenant_source`, `idx_tenant_sensor`
  
- ✅ `KnowledgeChunk` - Extends `SurrealTenantSchema`
  - Fields: `source_id`, `chunk_index`, `text`, `embedding` (vector)
  - Indexes: `idx_tenant_source`, `idx_tenant_embedding`
  
- ✅ `Entity` - Extends `SurrealTenantSchema`
  - Fields: `entity_type`, `name`, `attributes`, `source_ids`
  - Indexes: `idx_tenant_type`, `idx_tenant_name`
  
- ✅ `Relation` - Extends `SurrealTenantSchema`
  - Fields: `from_entity_id`, `to_entity_id`, `relation_type`, `attributes`, `source_ids`
  - Indexes: `idx_tenant_from`, `idx_tenant_to`, `idx_tenant_type`
  
- ✅ `IngestJob` - Extends `SurrealTenantSchema`
  - Fields: `status`, `source_type`, `source_id`, `error_message`, `completed_at`
  - Indexes: `idx_tenant_status`, `idx_tenant_source`

**Note**: Schema is generated from Pydantic models using `schema_generator.py`, which automatically creates SurrealDB table definitions with proper indexes.

### Task 2.2: Create Pydantic Models ✅
**Status**: Completed

**File**: `app/apps/memory/models/requests.py`

**Request Models**:
- ✅ `IngestRequest`:
  - `tenant_id: str`
  - `source_type: Literal["document", "meeting", "calendar", "task", "crm", "chat"]`
  - `source_id: str`
  - `sensor_name: str | None`
  - `content: str` (MD text)
  - `metadata: dict[str, object]`

- ✅ `RetrieveRequest`:
  - `tenant_id: str`
  - `question: str`
  - `hints: dict[str, object]`
  - `limits: dict[str, int]` (max_entities, max_chunks)
  - `source_types: list[str] | None`

**File**: `app/apps/memory/models/responses.py`

**Response Models**:
- ✅ `IngestResponse`: `job_id: str`, `status: str`
- ✅ `RetrieveResponse`: `tenant_id: str`, `question: str`, `context: ContextResponse`
- ✅ `ContextResponse`: `entities: list[EntityResponse]`, `chunks: list[ChunkResponse]`
- ✅ `EntityResponse`: `type: str`, `id: str`, `data: dict[str, object]`
- ✅ `ChunkResponse`: `id: str`, `document_id: str`, `source_type: str`, `score: float`, `text: str`, `metadata: dict[str, object]`
- ✅ `JobStatusResponse`: `job_id: str`, `status: str`, `progress: float | None`, `error_message: str | None`, timestamps

**File**: `app/apps/memory/models/__init__.py`

**Exports**:
- ✅ All request/response models exported
- ✅ All entity models exported (`MemorySource`, `MemoryChunk`, `Entity`, `Relation`, `IngestJob`)

---

## Phase 3: Core Services

### Task 3.1: Text Processor Service ✅
**File**: `app/apps/memory/services/text_processor.py`

**Implement**:
- `TextProcessor` class
- `normalize_text(text: str) -> str` - Clean/normalize MD text
- `split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]` - Use `RecursiveCharacterTextSplitter`
- `create_chunks(text: str, source_id: str, metadata: dict) -> list[MemoryChunk]` - Create chunk objects with metadata

### Task 3.2: Embedding Service ✅
**File**: `app/apps/memory/utils/embedding_service.py`

**Implemented (functional + async)**:
- `generate_embedding` / `generate_embeddings_batch` using shared async OpenAI client (`utils/openai_client.py`)
- OpenRouter-configured client with caching

### Task 3.3: LLM Chains ✅
**Files**:
- `app/apps/memory/ingest/chain.py` (functional helpers `extract_entities`, `extract_relations`, `process_text`)
- `app/apps/memory/retrieve/chain.py` (functional helpers `classify_query`, `extract_filters`)

Notes: both use shared async OpenAI client and cached PromptService instances.

---

## Phase 4: Database Operations & Retrievers

### Task 4.1: Knowledge Source Service ✅
Implemented in `apps/memory/ingest/knowledge_source_service.py` (create/get/update).

### Task 4.2: Entity & Relation Ops ✅
Functional helpers in `apps/memory/utils/entity_service.py` and `apps/memory/utils/relation_service.py` (create/upsert/get/link).

### Task 4.3: Vector/Graph/Hybrid Retrievers ✅
Files: `retrieve/retrievers/vector_retriever.py`, `graph_retriever.py`, `hybrid_retriever.py`, `fulltext_retriever.py`, `exact_match_retriever.py`.

### Task 4.4: Vector Service ⏳
Dedicated vector service wrapper not separated yet; retrieval uses direct query helpers. (Pending if still desired.)

### Task 4.5: Job Service ✅
`ingest/job_service.py` handles create/update/get for jobs.

### Task 4.3: Vector Service
**File**: `app/apps/memory/services/vector_service.py`

**Implement**:
- `VectorService` class
- `store_chunks(tenant_id, chunks: list[MemoryChunk], embeddings: list[list[float]]) -> None`
- `vector_search(tenant_id, query_embedding, k: int, filters: dict) -> list[MemoryChunk]`
- Direct SurrealDB vector queries

### Task 4.4: Custom Retrievers
**File**: `app/apps/memory/retrievers/vector_retriever.py`

**Implement**:
- `SurrealDBVectorRetriever(BaseRetriever)` class
- `_get_relevant_documents(query: str, *, run_manager) -> list[Document]`
- Use `VectorService` for search
- Support tenant_id and other filters

**File**: `app/apps/memory/retrievers/graph_retriever.py`

**Implement**:
- `SurrealDBGraphRetriever(BaseRetriever)` class
- `_get_relevant_documents(query: str, *, run_manager) -> list[Document]`
- Use SurrealQL graph queries
- Convert entities/relations to Document objects

**File**: `app/apps/memory/retrievers/hybrid_retriever.py`

**Implement**:
- `HybridRetriever` class
- Combines `SurrealDBVectorRetriever` and `SurrealDBGraphRetriever`
- Weighted scoring and result merging
- Deduplication

### Task 4.5: Job Service
**File**: `app/apps/memory/services/job_service.py`

**Implement**:
- `JobService` class
- `create_job(tenant_id, source_type, source_id) -> str`
- `update_job_status(job_id, status, error_message=None) -> None`
- `get_job(job_id: str) -> IngestJob | None`

---

## Phase 5: Redis Queue & Worker

### Task 5.1: Redis Queue Service
**File**: `app/apps/memory/services/queue_service.py`

**Implement**:
- `QueueService` class
- `enqueue_job(job_id: str, job_data: dict) -> None`
- `dequeue_job() -> dict | None` (for worker)
- Job serialization/deserialization
- Redis connection management

### Task 5.2: Worker Implementation
**File**: `app/worker.py`

**Implement**:
- Main worker script
- Connect to Redis and SurrealDB
- Poll Redis for jobs (BLPOP or similar)
- Process ingestion jobs:
  1. Load job data
  2. Get memory source
  3. Run LangChain ingestion chain
  4. Extract entities & relations
  5. Chunk text
  6. Generate embeddings
  7. Store in SurrealDB
  8. Update job status
- Error handling & retries
- Graceful shutdown (signal handling)

---

## Phase 6: API Endpoints

### Task 6.1–6.4: API Endpoints 🔄
Current implemented routes (FastAPI):
- `POST /api/memory/v1/ingest` (unstructured, async LLM pipeline)
- `POST /api/memory/v1/ingest/entity` (structured)
- `POST /api/memory/v1/ingest/relation` (structured)
- `POST /api/memory/v1/retrieve` (RAG hybrid)
- `POST /api/memory/v1/retrieve/entity` (structured graph/entity fetch)
- `GET /api/memory/v1/metadata` (tenant config)
Pending: job status endpoint and queue integration once Redis/worker land.

---

## Phase 7: Testing & Validation

### Task 7.1: Unit Tests
- Test all services
- Test models validation
- Test database operations

### Task 7.2: Integration Tests
- Test API endpoints
- Test end-to-end ingestion flow
- Test end-to-end retrieval flow
- Test worker job processing

---

## Phase 8: Documentation & Polish

### Task 8.1: API Documentation
- Ensure OpenAPI/Swagger docs are generated
- Add request/response examples
- Document error codes

### Task 8.2: Code Documentation
- Add docstrings to all functions/classes
- Update README with setup instructions

---

## Implementation Order

1. ✅ Phase 1: Foundation (Tasks 1.1-1.4) - **COMPLETED**
2. ✅ Phase 2: Data Models & Schema (Tasks 2.1-2.2) - **COMPLETED**
3. ⏳ Phase 3: Core Services (Tasks 3.1-3.3) - **IN PROGRESS**
4. ⏸️ Phase 4: Database Operations (Tasks 4.1-4.5) - **PENDING**
5. ⏸️ Phase 5: Redis Queue & Worker (Tasks 5.1-5.2) - **PENDING**
6. ⏸️ Phase 6: API Endpoints (Tasks 6.1-6.4) - **PENDING**
7. ⏸️ Phase 7: Testing - **PENDING**
8. ⏸️ Phase 8: Documentation - **PENDING**

---

## Implementation Notes

### Schema Generation Approach
The project uses a **schema generator** (`app/server/schema_generator.py`) that automatically generates SurrealDB table definitions from Pydantic models. This approach:
- Ensures schema stays in sync with models
- Reduces manual schema maintenance
- Supports index definitions via `json_schema_extra` metadata

### Base Schema Pattern
All domain schemas extend `SurrealTenantSchema` from `apps.base.schemas`, which provides:
- `tenant_id` field (required)
- `id` field (SurrealDB record ID)
- `created_at`, `updated_at` timestamps
- `is_deleted` soft delete flag
- `meta_data` for additional metadata

### File Structure
```
app/
├── apps/
│   ├── base/
│   │   └── schemas.py          # Base SurrealTenantSchema
│   └── memory/
│       ├── models/
│       │   ├── __init__.py     # Exports
│       │   ├── requests.py     # API request models
│       │   └── responses.py    # API response models
│       └── schemas.py          # Domain schemas (MemorySource, etc.)
├── server/
│   ├── schema_generator.py     # Auto-generates SurrealDB schemas
│   ├── config.py              # Settings with all configs
│   ├── db.py                   # SurrealDB connection
│   └── server.py               # FastAPI app with lifespan
```

---

## Notes

- Start with Phase 1, complete all tasks before moving to next phase
- Test each component as you build it
- Keep database schema flexible for future sensor types
- Ensure all operations are tenant-scoped
- Use async/await throughout for better performance

