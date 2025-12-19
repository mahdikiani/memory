# Korsi Organizational Memory (KOM)
### Memory Service for Korsi Core
**Status:** Internal Draft  
**Audience:** Backend, AI, Product  
**Database:** SurrealDB  
**API Style:** REST-oriented (MVP), MCP-ready (Phase 2)

---

## 1. Overview

Korsi Organizational Memory (KOM) is a centralized **organizational memory service** designed to transform raw organizational data into a **connected, queryable, and evolving knowledge graph**.

KOM is not a data warehouse.
It is not a search engine.
It is not a chatbot memory.

KOM is a **memory system** that:
- Knows *what exists* (entities)
- Knows *what happened* (events)
- Knows *where it was said* (artifacts & chunks)
- Preserves *current truth* (entity snapshots)
- Preserves *history* (events)
- Supports *reasoning* without mutating truth during retrieval

SurrealDB is used as the **single source of truth** for:
- Structured data
- Graph relations
- Full-text search
- Vector embeddings
- Temporal history

---

## 2. Core Design Principles

### 2.1 Single Writer, Read-only Retrieval
- **Ingest** is the only component allowed to mutate memory.
- **Retrieve** is strictly read-only.
- No query, LLM, or assistant is allowed to change truth.

### 2.2 Snapshot + Event History
- `Entity` stores the **latest verified state**.
- `Event` stores **how and when the state changed**.
- Pending changes never modify the snapshot.

### 2.3 Proposal-Based Knowledge Growth
Nothing enters memory as truth by default.

- AI proposes
- User or policy verifies
- Only verified changes update entities

### 2.4 Artifact-First Ingestion
All external inputs enter KOM as **artifacts**:
- Files
- Meetings
- Chats
- API payloads

Artifacts are processed into chunks and linked to entities and events.

---

## 3. Conceptual Data Model

### 3.1 Company (Tenant Root)
Represents a tenant organization.

**Responsibilities:**
- Multi-tenancy boundary
- Allowed entity types
- Allowed source types
- Lookup by national/company ID

---

### 3.2 Artifact
Represents an external knowledge source.

Examples:
- Contract file
- Meeting transcript
- Chat export
- API payload

Artifacts are immutable containers.

---

### 3.3 Chunk
Processed segments of an artifact.

**Purpose:**
- Semantic search
- Citation
- Evidence linking

Each chunk contains:
- Full text
- Vector embedding
- Reference to its artifact

---

### 3.4 Entity
Represents a real-world object.

Examples:
- Person
- Company
- Project
- Department

**Entity is a snapshot.**
It always reflects the **latest verified state**.

Attributes are stored directly on the entity.

---

### 3.5 Event
Represents a change or occurrence in time.

Events are **structured, stateful, and queryable**.

Events serve three roles:
1. History of entity changes
2. Timeline of organizational activity
3. Pending proposals before verification

Events are the **temporal memory** of KOM.

---

### 3.6 Relations
Two kinds of relations exist:

1. **Mention Relations**
   - chunk/artifact → entity
   - Used for citation and retrieval
   - No truth semantics

2. **Truth Relations**
   - entity → entity
   - Always backed by a verified event
   - Edge may be materialized for traversal

---

## 4. Detailed Data Models

### 4.1 Company
```
company
- id (record id)
- national_id (indexed, unique)
- name
- source_types[]
- entity_types[]
- data{}
```

---

### 4.2 Artifact
```
artifact
- id
- tenant_id (company record id)
- artifact_type (contract, meeting, chat, ...)
- source_id (external reference)
- raw_data{}
- created_at
```

---

### 4.3 Chunk
```
chunk
- id
- tenant_id
- artifact_id
- text
- embedding[]
- chunk_index
- language
```

Indexes:
- Full-text on `text`
- Vector index on `embedding`

---

### 4.4 Entity
```
entity
- id
- tenant_id
- entity_type
- name
- aliases[]
- attributes{}
- external_ids{}
- status (active | merged | archived)
- confidence_level (user_confirmed | auto_extracted)
- created_at
```

---

### 4.5 Event
```
event
- id
- tenant_id
- event_type
- subject_id (entity record id)
- occurred_at
- actor_id (user or system)
- state (pending | verified | rejected)

- op (set | unset | append | remove | inc)
- path (e.g. attributes.contract_value)
- old_value
- new_value

- source_ref (artifact/chunk/user)
- metadata{}
```

---

### 4.6 Entity Checkpoint (Optional but Recommended)
```
entity_checkpoint
- id
- tenant_id
- entity_id
- as_of
- snapshot{}
- based_on_event_id
```

Used to speed up historical reconstruction.

---

## 5. Ingestion Flow

1. Artifact is created
2. Artifact is chunked and embedded
3. Extraction produces:
   - proposed entities
   - proposed relations
   - proposed events
4. Proposals are stored as `event(state=pending)`
5. User or policy resolves proposals
6. Verified events update entity snapshots
7. Optional: checkpoint is created

---

## 6. Retrieval Rules

- Retrieval is **read-only**
- Only verified data affects answers
- Pending events are visible but never applied
- Historical queries reconstruct state via:
  - nearest checkpoint
  - verified events up to time T

---

## 7. REST API (MVP)

### Core Resources
```
POST   /companies
GET    /companies/{id}
GET    /companies/resolve?national_id=

POST   /artifacts
POST   /artifacts/{id}/chunks

POST   /entities
GET    /entities/{id}

POST   /events        # proposals & changes
GET    /proposals
POST   /proposals/{id}/decisions

POST   /retrieve
```

---

## 8. Project Structure

```
app/
├── apps/
│   └── memory/
│       ├── ingest/
│       │   ├── processors/
│       │   ├── services/
│       │   └── routes.py
│       ├── retrieve/
│       │   ├── retrievers/
│       │   └── routes.py
│       ├── core/                 # Domain logic (single source of truth)
│       │   ├── entity_service.py
│       │   ├── event_service.py
│       │   ├── relation_service.py
│       │   └── artifact_service.py
│       ├── models.py
│       ├── schemas.py
│       └── exceptions.py
│
├── db/
│   ├── manager.py
│   ├── query_builder.py
│   ├── query_executor.py
│   └── schema_generator.py
│
├── prompts/
├── server/
├── worker.py
└── main.py
```

---

## 9. What KOM Is Not (By Design)

- KOM is not a chatbot memory
- KOM does not hallucinate truth
- KOM does not auto-write facts during retrieval
- KOM does not collapse time into a single state

---

## 10. Future Phases (Explicitly Deferred)

- MCP Tooling
- Aggregations & KPIs
- Memory Health Dashboard
- Conflict Resolution Policies
- Auto-approval heuristics

---

## 11. Final Note

KOM treats organizational knowledge as:
> **A living system, not a static database**

Truth is earned.
History is preserved.
Reasoning is constrained.
Memory evolves.
