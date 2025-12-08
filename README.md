# Memory Service

Multi-tenant **memory base** service for RAG (Retrieval-Augmented Generation).

The service ingests structured and unstructured data (documents, events, entities), builds a **graph + vector** memory store on **SurrealDB**, and exposes APIs to retrieve relevant context for downstream LLMs.

It is **not** an answer-bot; it is the **memory layer** behind one.

---

## High-Level Overview

- **Multi-tenant**: multiple organizations share the service; data is logically isolated per tenant.
- **Unified store**: SurrealDB used for:
  - entities & relations (graph)
  - text chunks & embeddings (vector)
  - metadata / events
- **LangChain-based pipelines** for:
  - ingestion (understanding and structuring new data)
  - retrieval (fetching relevant context for a question)

The service currently exposes two main RPC-style APIs (to be evolved to REST Maturity Level 2):

1. `POST /memory/ingest` – new data arrives, is queued, understood, and stored.
2. `POST /memory/retrieve` – a question arrives, relevant memory is fetched and returned for RAG.

---

## Project Structure

Repository layout (top-level):

```text
.
├── app
│   ├── apps
│   │   └── __init__.py
│   ├── Dockerfile
│   ├── main.py
│   ├── pyproject.toml
│   ├── README.md
│   └── server
│       ├── config.py
│       ├── __init__.py
│       └── server.py
├── docker-compose.yml
├── LICENSE
└── README.md
```

* `app/` – application source code.
  * `main.py` – application entrypoint (server bootstrap).
  * `server/` – HTTP / API server configuration and startup code.
    * `config.py` – environment, SurrealDB connection, queue config, etc.
    * `server.py` – FastAPI / Flask / other web framework setup.

  * `apps/` – logical modules (e.g. `memory`, ...).
  * `pyproject.toml` – Python package & dependency configuration.
  * `Dockerfile` – container image for the app.

* `docker-compose.yml` – local stack (app + SurrealDB + queue, etc.).
* `LICENSE` – project license.
* `README.md` – this file.

---

## Multi-Tenancy

Each request is associated with a **tenant** (organization):

- `tenant_id` is required in every API call.
- All records in SurrealDB are scoped by `tenant_id` (or separate namespaces/DBs per tenant, depending on deployment).
- Retrieval and ingestion never cross tenant boundaries.

---

## Conceptual Architecture

**Components:**

- **HTTP API Layer**
  - `ingest` and `retrieve` endpoints.
- **Job Queue**
  - Each ingest request becomes a job.
  - Workers consume jobs and run ingestion pipelines.
- **SurrealDB**
  - Entities and graph relations.
  - Document chunks and vector embeddings.
- **LangChain**
  - Orchestrates:
    - LLM-based extraction pipelines.
    - Hybrid retrieval (graph + vector + structured).

**LLM is pluggable** (OpenAI, local models, etc.), configured via environment.

---

## Data Model (Conceptual)

All stored in SurrealDB. Exact schema is implementation-specific; below is the conceptual shape.

### Core Entities

Each record includes `tenant_id`, an `id`, and audit fields (`created_at`, `updated_at`, `source`, etc.).

Examples:

- `organization` (optional, to manage metadata per tenant)
- `entity_generic` (optional abstraction)
- `person`
- `company`
- `product`
- `project`
- `contract`
- `document`
- `meeting`
- `event` (generic activity/interaction)

### Relations (Graph)

Represented as SurrealDB relations/links.

Examples:

- `(company)-[:PARTY {role}]->(contract)`
- `(project)-[:FOR_COMPANY]->(company)`
- `(project)-[:DELIVERS_PRODUCT]->(product)`
- `(person)-[:WORKS_ON {role}]->(project)`
- `(meeting)-[:WITH_COMPANY]->(company)`
- `(document)-[:ATTACHED_TO {type}]->(contract|project|meeting|company|product)`
- `(event)-[:RELATED_TO]->(entity)`

### Text & Vectors

**Document chunks** are the unit for semantic retrieval:

- `document_chunk`:
  - `tenant_id`
  - `id`
  - `document_id`
  - `source_type` (contract, minutes, policy, email, note, ...)
  - `text`
  - `embedding` (vector field)
  - Metadata:
    - `linked_entities`: list of entity IDs (company, project, contract, ...)
    - timestamps, tags, etc.

Vector search is always **filterable** by `tenant_id` and optionally by related entities.

---

## API Design

> Initial version is RPC-style over HTTP.  
> Later it can be refactored to REST Level 2 (resources + verbs).

### 1. Ingest API

**Goal:**  
Accept new memory (documents or structured payloads), enqueue it, and process it asynchronously into the memory base.

**Endpoint:**

```http
POST /memory/ingest
Content-Type: application/json
````

**Request Body (generic shape):**

```json
{
  "tenant_id": "org-123",
  "type": "document",
  "subtype": "contract",
  "source": {
    "storage_url": "s3://bucket/path/to/file.pdf",
    "content_type": "application/pdf"
  },
  "metadata": {
    "external_id": "contract-001",
    "tags": ["legal", "customer-x"],
    "hints": {
      "company_name": "Example Bank",
      "product_name": "Example Product"
    }
  }
}
```

Another example for structured/event-like ingest:

```json
{
  "tenant_id": "org-123",
  "type": "event",
  "subtype": "meeting",
  "payload": {
    "subject": "Quarterly status review",
    "datetime": "2025-12-01T10:00:00Z",
    "company_name": "Example Bank",
    "participants": ["Alice Doe", "Bob Smith"],
    "notes": "Raw notes or summary text here..."
  }
}
```

**Response:**

```json
{
  "job_id": "ingest-2025-12-04-000123",
  "status": "queued"
}
```

#### Ingest Processing Flow

Worker flow for a `document` ingest (simplified):

1. Fetch the document (from `storage_url` or direct content).
2. Extract raw text (PDF/DOCX parsing, OCR if needed).
3. Pass text + metadata to a **LangChain ingestion chain**:

   * Normalize/clean text.
   * Use LLM to extract structured fields (entities, relations, key attributes).
   * Generate optional summaries.
4. Map extracted entities/relations to the **tenant-scoped schema** in SurrealDB:

   * Upsert entities (company, project, contract, etc.).
   * Create/attach relations (edges).
5. Chunk text (e.g. by semantic/size rules).
6. Compute embeddings for each chunk and upsert `document_chunk` records with:

   * `tenant_id`
   * `document_id`
   * `text`
   * `embedding`
   * enriched metadata (linked entity IDs, tags, etc.).
7. Update job status (success/failure, error details).

For structured/event ingest, steps 2–3 may be lighter (direct mapping + optional LLM enrichment).

---

### 2. Retrieve API

**Goal:**
Given a natural language question (optionally with hints/filters), return the most relevant memory for that tenant:

* structured entities / relations
* text chunks (for semantic RAG)

This service does **not** generate the final natural-language answer; it supplies the **context**.

**Endpoint:**

```http
POST /memory/retrieve
Content-Type: application/json
```

**Request Body:**

```json
{
  "tenant_id": "org-123",
  "question": "What is the current status of our collaboration with Example Bank?",
  "hints": {
    "language": "en",
    "company_name": "Example Bank"
  },
  "limits": {
    "max_entities": 20,
    "max_chunks": 20
  }
}
```

#### Retrieval Flow

1. **Question interpretation** (LangChain):

   * Classify query as:

     * `structured` (directly answerable via graph/fields),
     * `semantic` (requires semantic search over text),
     * or `hybrid` (both).
   * Extract candidate filters (e.g. company name, product, time ranges).

2. **Structured / graph retrieval** (for `structured` or `hybrid`):

   * Build a SurrealQL query to fetch relevant entities/relations for the tenant:

     * e.g. contracts, projects, meetings, last events, etc.
   * Result: list of entity records + their relationships.

3. **Vector retrieval** (for `semantic` or `hybrid`):

   * Generate an embedding for the question.
   * Run vector search over `document_chunk` filtered by:

     * `tenant_id`,
     * any additional filters (e.g. linked to a specific company or project).
   * Result: top-k text chunks ranked by similarity.

4. **Merge & rank**:

   * Combine structured and semantic results into a unified `context` object.

**Response (example):**

```json
{
  "tenant_id": "org-123",
  "question": "What is the current status of our collaboration with Example Bank?",
  "context": {
    "entities": [
      {
        "type": "company",
        "id": "company:example-bank",
        "data": {
          "name": "Example Bank",
          "last_interaction_at": "2025-11-20T09:00:00Z"
        }
      },
      {
        "type": "contract",
        "id": "contract:example-product-example-bank-001",
        "data": {
          "title": "Example Product Implementation",
          "status": "active",
          "sign_date": "2025-06-10",
          "amount": 1200000000
        }
      }
    ],
    "chunks": [
      {
        "id": "chunk-abc",
        "document_id": "doc-123",
        "source_type": "meeting_minutes",
        "score": 0.88,
        "text": "In the last review meeting with Example Bank, the main concern was the delay in phase 2 delivery..."
      }
    ]
  }
}
```

The caller is expected to feed `(question, context)` to an LLM to generate a final answer.

---

## LangChain Usage

**Ingestion side:**

* A LangChain Runnable/chain that:

  * Receives raw text + metadata.
  * Calls LLM to:

    * extract entities (companies, contracts, projects, people, etc.),
    * infer relations (which entity is related to which),
    * optionally produce summaries.
  * Outputs:

    * structured records for SurrealDB
    * text chunks for embedding.

**Retrieval side:**

* Custom **Retriever** that:

  * Combines:

    * SurrealDB graph/structured queries,
    * SurrealDB vector search.
  * Supports:

    * query classification (structured vs semantic vs hybrid),
    * filter-aware vector search (e.g. by entity IDs).

This service stops at **context retrieval**; answer generation is a responsibility of the caller.

---

## Tech Stack

* **Database:** SurrealDB (graph + vector + document)
* **Orchestration:** LangChain
* **LLM:** pluggable (e.g. OpenAI / local model)
* **API Layer:** HTTP JSON (Node.js / Python / Go; implementation detail)
* **Queue:** pluggable (e.g. Redis, RabbitMQ, Kafka) behind a job abstraction

---

## Roadmap (High-Level)

1. Define minimal SurrealDB schema for:
   * `tenant`, `person`, `company`, `project`, `contract`, `document`, `document_chunk`, `meeting`, `event`.
2. Implement `POST /memory/ingest`:
   * Basic validation.
   * Queue job creation.
   * Worker skeleton with a simple LangChain ingestion chain.
3. Implement `POST /memory/retrieve`:
   * Basic vector retrieval for a tenant.
   * Add structured/graph queries.
   * Add hybrid retrieval logic.
4. Add more entity types and relation templates as new use cases appear.
5. Evolve API toward REST Level 2 (resource-oriented URIs and HTTP verbs).
