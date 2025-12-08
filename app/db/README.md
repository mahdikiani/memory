# SurrealDB Dynamic Query Builder

این ماژول یک ساختار دینامیک و امن برای کار با SurrealDB در پروژه RAG فراهم می‌کند. تمام کوئری‌ها به صورت parameterized و type-safe ساخته می‌شوند تا از SQL injection جلوگیری شود.

## ساختار کلی

```
db/
├── __init__.py              # Export اصلی ماژول
├── models.py                # Base models برای entities
├── manager.py               # Database connection manager
├── query_builder.py         # Query builder پایه
├── query_builder_orm.py     # ORM-like query builder interface
├── query_executor.py        # Query executor با parameterization
├── schema_generator.py       # تولید خودکار schema از Pydantic models
├── specialized_builders.py # Query builders تخصصی (vector, fulltext, graph)
├── metadata.py              # Metadata extraction از models
├── field_validation.py      # اعتبارسنجی و sanitization فیلدها
├── utils.py                 # توابع کمکی
└── surreal_files/           # فایل‌های SQL سفارشی
    └── cossine_function.sql # تابع cosine similarity
```

## ویژگی‌های کلیدی

### 1. **Dynamic Schema Generation**
Schema به صورت خودکار از Pydantic models تولید می‌شود:
- تبدیل خودکار Python types به SurrealDB types
- پشتیبانی از Union types (`str | None` → `option<string>`)
- پشتیبانی از arrays و nested types
- تشخیص خودکار record references از نام فیلدها
- تولید خودکار indexes از Field metadata

### 2. **Type-Safe Query Building**
کوئری‌ها به صورت type-safe و parameterized ساخته می‌شوند:
- جلوگیری از SQL injection
- اعتبارسنجی نام فیلدها و جداول
- Method chaining برای خوانایی بهتر
- پشتیبانی از WHERE, ORDER BY, LIMIT

### 3. **Specialized Query Builders**
Query builders تخصصی برای انواع مختلف جستجو:
- **VectorQueryBuilder**: جستجوی similarity با embeddings
- **FullTextQueryBuilder**: جستجوی fulltext
- **GraphQueryBuilder**: پیمایش graph و روابط

### 4. **Dynamic Model Discovery**
کشف خودکار models از BaseSurrealEntity:
- نیازی به ثبت دستی models نیست
- استخراج خودکار metadata از Field definitions
- پشتیبانی از inheritance

## استفاده

### تعریف Model

```python
from db.models import BaseSurrealTenantEntity
from pydantic import Field
from datetime import datetime

class Entity(BaseSurrealTenantEntity):
    name: str = Field(..., description="Entity name")
    embedding: list[float] | None = Field(
        None,
        description="Vector embedding",
        json_schema_extra={"surreal_vector_field": True}
    )
    content: str = Field(
        ...,
        description="Content for fulltext search",
        json_schema_extra={"surreal_fulltext_field": True}
    )
```

### استفاده از Query Builder

```python
from db import query, execute_query

# کوئری ساده
query_builder = query("entity") \
    .where_eq("tenant_id", "tenant_123") \
    .where_eq("is_deleted", False) \
    .where_in("status", ["active", "pending"]) \
    .order_by("created_at", "DESC") \
    .limit(10)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
```

### Vector Search

```python
from db import VectorQueryBuilder, execute_query

query_builder = VectorQueryBuilder() \
    .with_embedding_similarity(query_embedding) \
    .where_eq("tenant_id", "tenant_123") \
    .where_is_not_none("embedding") \
    .limit(5)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
# results شامل similarity_score است
```

### Fulltext Search

```python
from db import FullTextQueryBuilder, execute_query

query_builder = FullTextQueryBuilder() \
    .search("search text") \
    .where_eq("tenant_id", "tenant_123") \
    .limit(10)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
# results شامل relevance_score است
```

### Graph Traversal

```python
from db import GraphQueryBuilder, execute_query

# Simple traversal with single depth
query_builder = GraphQueryBuilder() \
    .from_entities(["entity:1", "entity:2"]) \
    .max_depth(3) \
    .where_eq("tenant_id", "tenant_123") \
    .limit(20)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)

# Traversal with depth range and distance ordering
query_builder = GraphQueryBuilder() \
    .from_entities(["entity:1", "entity:2", "entity:3"]) \
    .depth_range(min_depth=3, max_depth=7) \
    .where_eq("tenant_id", "tenant_123") \
    .order_by_distance() \
    .limit(20)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
# Results include 'distance' field and are ordered by distance (ascending)
```

### استفاده از Base Model Methods

```python
# ایجاد
entity = Entity(
    tenant_id="tenant_123",
    name="Test Entity",
    content="Some content"
)
await entity.save()

# جستجو
entity = await Entity.find_one(name="Test Entity")
entities = await Entity.find_many(limit=10, status="active")

# به‌روزرسانی
await entity.update(name="Updated Name")

# حذف (soft delete)
await entity.delete(soft=True)
```

## امنیت

### Field Validation
- تمام نام فیلدها از طریق whitelist اعتبارسنجی می‌شوند
- Whitelist به صورت دینامیک از models استخراج می‌شود
- Pattern-based fallback برای فیلدهای معتبر

### Parameterized Queries
- تمام مقادیر به صورت parameterized به query اضافه می‌شوند
- استفاده از `$param_name` placeholders
- جلوگیری کامل از SQL injection

### Table Validation
- نام جداول از طریق whitelist اعتبارسنجی می‌شوند
- Whitelist از BaseSurrealEntity subclasses استخراج می‌شود
- Warning برای جداول غیرثبت‌شده (اما خطا نمی‌دهد برای flexibility)

## Schema Generation

Schema به صورت خودکار از models تولید می‌شود:

```python
# در manager.py
await db_manager.init_schema()
```

این تابع:
1. تمام subclasses از `BaseSurrealEntity` را پیدا می‌کند
2. برای هر model یک `DEFINE TABLE` statement می‌سازد
3. فیلدها را با types مناسب تعریف می‌کند
4. Indexes را از Field metadata استخراج می‌کند
5. توابع سفارشی (مثل `cosine_similarity`) را اضافه می‌کند

### Field Metadata

برای اضافه کردن metadata به فیلدها:

```python
from pydantic import Field

class MyModel(BaseSurrealTenantEntity):
    # Index
    tenant_id: str = Field(
        ...,
        json_schema_extra={"surreal_index": "idx_tenant_id"}
    )
    
    # Vector field
    embedding: list[float] = Field(
        ...,
        json_schema_extra={"surreal_vector_field": True}
    )
    
    # Fulltext field
    content: str = Field(
        ...,
        json_schema_extra={"surreal_fulltext_field": True}
    )
```

## Type Mapping

| Python Type | SurrealDB Type |
|------------|----------------|
| `str` | `string` |
| `int` | `int` |
| `float` | `float` |
| `bool` | `bool` |
| `datetime` | `datetime` |
| `str \| None` | `option<string>` |
| `list[str]` | `array<string>` |
| `list[float]` | `array<float>` |
| `dict` | `object` |
| `field_name_id` (ends with `_id`) | `record<table>` (inferred) |

## Query Builders

### QueryBuilder (Base)
- `where_eq(field, value)`: WHERE field = value
- `where(field, value, operator)`: WHERE با operator دلخواه
- `where_in(field, values)`: WHERE field IN [...]
- `where_not_in(field, values)`: WHERE field NOT IN [...]
- `where_is_none(field)`: WHERE field IS NONE
- `where_is_not_none(field)`: WHERE field IS NOT NONE
- `select(*fields)`: SELECT fields
- `order_by(field, direction)`: ORDER BY
- `limit(count)`: LIMIT
- `build()`: ساخت query string و parameters

### VectorQueryBuilder
- تمام متدهای QueryBuilder
- `with_embedding_similarity(embedding)`: اضافه کردن similarity calculation
- به صورت خودکار `similarity_score` را در SELECT اضافه می‌کند

### FullTextQueryBuilder
- تمام متدهای QueryBuilder
- `search(query_text)`: اضافه کردن fulltext search
- به صورت خودکار `relevance_score` را در SELECT اضافه می‌کند

### GraphQueryBuilder
- `from_entities(entity_ids)`: تعیین starting entities
- `to_entities(entity_ids)`: تعیین target entities (اختیاری)
- `min_depth(depth)`: حداقل عمق traversal (1-10)
- `max_depth(depth)`: حداکثر عمق traversal (1-10)
- `depth_range(min_depth, max_depth)`: تعیین بازه عمق traversal
- `order_by_distance()`: مرتب‌سازی نتایج بر اساس فاصله (کمترین فاصله اول)
- `limit(count)`: محدود کردن نتایج
- `where(...)`: فیلتر روی edges
- نتایج شامل فیلد `distance` هستند که فاصله از starting entities را نشان می‌دهد

## Database Manager

```python
from db.manager import DatabaseManager

# در startup
db_manager = DatabaseManager(settings)
await db_manager.connect()
await db_manager.init_schema()

# استفاده
db = db_manager.get_db()

# در shutdown
await db_manager.disconnect()
```

## نکات مهم

1. **همیشه از Query Builders استفاده کنید**: هرگز query string را به صورت دستی نسازید
2. **Field Validation**: نام فیلدها باید در models تعریف شده باشند
3. **Table Validation**: نام جداول باید از models استخراج شده باشند
4. **Parameterization**: تمام مقادیر باید از طریق parameters پاس داده شوند
5. **Schema Initialization**: همیشه `init_schema()` را قبل از استفاده فراخوانی کنید

## مثال کامل

```python
from db.models import BaseSurrealTenantEntity
from db import query, execute_query, VectorQueryBuilder
from pydantic import Field

# تعریف Model
class Document(BaseSurrealTenantEntity):
    title: str
    content: str = Field(
        ...,
        json_schema_extra={"surreal_fulltext_field": True}
    )
    embedding: list[float] | None = Field(
        None,
        json_schema_extra={"surreal_vector_field": True}
    )

# ایجاد document
doc = Document(
    tenant_id="tenant_123",
    title="Test Document",
    content="This is test content",
    embedding=[0.1, 0.2, 0.3]
)
await doc.save()

# جستجوی fulltext
from db import FullTextQueryBuilder
query_builder = FullTextQueryBuilder() \
    .search("test") \
    .where_eq("tenant_id", "tenant_123") \
    .limit(10)
query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)

# جستجوی vector
query_builder = VectorQueryBuilder() \
    .with_embedding_similarity([0.1, 0.2, 0.3]) \
    .where_eq("tenant_id", "tenant_123") \
    .limit(5)
query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
```

## استفاده در RAG System

این ماژول به طور کامل برای ساخت یک RAG system با قابلیت‌های زیر آماده است:

### 1. Exact Match / Relational Search
```python
from db import execute_exact_match_query

results = await execute_exact_match_query(
    table="knowledge_chunk",
    filters={"source_type": "document", "status": "active"},
    tenant_id="tenant_123",
    limit=10
)
```

### 2. Vector Search (Semantic Search)
```python
from db import VectorQueryBuilder, execute_query

query_builder = VectorQueryBuilder() \
    .with_embedding_similarity(query_embedding) \
    .where_eq("tenant_id", "tenant_123") \
    .limit(5)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
```

### 3. Fulltext Search
```python
from db import FullTextQueryBuilder, execute_query

query_builder = FullTextQueryBuilder() \
    .search("search text") \
    .where_eq("tenant_id", "tenant_123") \
    .limit(10)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
```

### 4. Graph Search
```python
from db import GraphQueryBuilder, execute_query, execute_graph_query

# Using GraphQueryBuilder directly
query_builder = GraphQueryBuilder() \
    .from_entities(["entity:1", "entity:2", "entity:3"]) \
    .depth_range(min_depth=3, max_depth=7) \
    .where_eq("tenant_id", "tenant_123") \
    .order_by_distance() \
    .limit(20)

query_sql, params = query_builder.build()
results = await execute_query(query_sql, params)
# Results include 'distance' field

# Using execute_graph_query helper
results = await execute_graph_query(
    tenant_id="tenant_123",
    entity_ids=["entity:1", "entity:2", "entity:3"],
    relation_type=None,  # Optional
    limit=20,
    min_depth=3,
    max_depth=7,
    order_by_distance=True
)
# Results are ordered by distance (ascending) and include 'distance' field
```

### 5. Combined Search (ترکیب در یک Query)
ترکیب Exact Match + Fulltext + Vector در یک query (Graph جداگانه):

```python
from db import CombinedQueryBuilder, execute_query, execute_combined_query

# Using CombinedQueryBuilder directly
query_builder = CombinedQueryBuilder() \
    .where_eq("tenant_id", "tenant_123") \
    .where_eq("is_deleted", False) \
    .where_eq("source_type", "document") \
    .with_fulltext_search("search text") \
    .with_vector_similarity([0.1, 0.2, 0.3]) \
    .with_graph_search(
        entity_ids=["entity:1", "entity:2"],
        min_depth=3,
        max_depth=7,
        tenant_id="tenant_123"
    ) \
    .limit(20)

# Build all queries
queries = query_builder.build_all()
# queries = {
#     "main": (query_sql, params),  # Combined exact + fulltext + vector
#     "graph": (graph_query, graph_params)  # Graph search (separate)
# }

# Execute main query
main_query, main_params = queries["main"]
main_results = await execute_query(main_query, main_params)

# Execute graph query
if "graph" in queries:
    graph_query, graph_params = queries["graph"]
    graph_results = await execute_query(graph_query, graph_params)

# Using execute_combined_query helper
results = await execute_combined_query(
    tenant_id="tenant_123",
    exact_match_filters={"source_type": "document", "status": "active"},
    fulltext_query="search text",
    vector_embedding=[0.1, 0.2, 0.3],
    graph_entity_ids=["entity:1", "entity:2"],
    graph_min_depth=3,
    graph_max_depth=7,
    limit=20
)
# results = {
#     "main": [...],  # Combined results with similarity_score and relevance_score
#     "graph": [...]  # Graph results with distance field
# }
```

**نکات مهم:**
- Exact Match + Fulltext + Vector در یک query ترکیب می‌شوند (بهینه‌تر)
- Graph Search جداگانه اجرا می‌شود (ساختار query متفاوت است)
- نتایج `main` شامل `similarity_score` و `relevance_score` هستند
- نتایج `graph` شامل `distance` هستند

### 6. Hybrid Search (ترکیبی در Application Layer)
برای استفاده از Hybrid Retriever که تمام روش‌های بالا را در application layer ترکیب می‌کند:

```python
from apps.memory.retrieve.retrievers.hybrid_retriever import HybridRetriever

retriever = HybridRetriever(
    tenant_id="tenant_123",
    use_exact_match=True,
    use_fulltext=True,
    use_vector=True,
    use_graph=True,
    exact_match_filters={"source_type": "document"},
    vector_filters={"status": "active"},
    entity_ids=["entity:1", "entity:2"],
    limit_per_type=5
)

documents = await retriever._aget_relevant_documents("query text")
```

## Troubleshooting

### خطای "Table not found in registered models"
- مطمئن شوید model از `BaseSurrealTenantEntity` ارث‌بری می‌کند
- مطمئن شوید model import شده است (تا در subclass discovery پیدا شود)

### خطای "Unsafe field name"
- نام فیلد باید در model تعریف شده باشد
- یا باید pattern معتبر داشته باشد (`^[a-zA-Z_][a-zA-Z0-9_]*$`)

### خطای "No model with surreal_vector_field found"
- برای `VectorQueryBuilder` و `FullTextQueryBuilder` باید table را به صورت explicit مشخص کنید
- یا در model فیلد را با metadata مناسب علامت‌گذاری کنید

### Import Errors
- مطمئن شوید از `from db import ...` استفاده می‌کنید نه `from ...utils.query_executor import ...`
- تمام query executors و builders از ماژول `db` export می‌شوند

