# Data Model

<!-- sdlc:auto:start entities -->
### documents

| Field | Type | PK | FK | Nullable |
|---|---|---|---|---|
| id | uuid | True | — | False |
| file_name | text | False | — | False |
| mime_type | text | False | — | False |
| size_bytes | bigint | False | — | False |
| storage_key | text | False | — | False |
| status | text | False | — | False |
| failure_reason | text | False | — | True |
| chunk_count | integer | False | — | True |
| uploaded_at | timestamptz | False | — | False |

### chunks

| Field | Type | PK | FK | Nullable |
|---|---|---|---|---|
| id | uuid | True | — | False |
| document_id | uuid | False | documents.id | False |
| content | text | False | — | False |
| source_location | text | False | — | False |
| chunk_index | integer | False | — | False |
| embedding | vector | False | — | False |

### threads

| Field | Type | PK | FK | Nullable |
|---|---|---|---|---|
| id | uuid | True | — | False |
| title | text | False | — | True |
| created_at | timestamptz | False | — | False |
| last_active_at | timestamptz | False | — | False |

### messages

| Field | Type | PK | FK | Nullable |
|---|---|---|---|---|
| id | uuid | True | — | False |
| thread_id | uuid | False | threads.id | False |
| role | text | False | — | False |
| content | text | False | — | False |
| status | text | False | — | False |
| created_at | timestamptz | False | — | False |

### citations

| Field | Type | PK | FK | Nullable |
|---|---|---|---|---|
| id | uuid | True | — | False |
| message_id | uuid | False | messages.id | False |
| chunk_id | uuid | False | chunks.id | True |
| document_name | text | False | — | False |
| source_location | text | False | — | False |
| excerpt | text | False | — | False |
<!-- sdlc:auto:end entities -->

<!-- sdlc:auto:start relationships -->
| Source | Target | Type |
|---|---|---|
| documents | chunks | one-to-many |
| threads | messages | one-to-many |
| messages | citations | one-to-many |
| chunks | citations | one-to-many |
<!-- sdlc:auto:end relationships -->

<!-- sdlc:auto:start er-diagram -->
```mermaid
erDiagram
  documents {
    uuid id PK
    text file_name
    text mime_type
    bigint size_bytes
    text storage_key
    text status
    text failure_reason
    integer chunk_count
    timestamptz uploaded_at
  }
  chunks {
    uuid id PK
    uuid document_id FK
    text content
    text source_location
    integer chunk_index
    vector embedding
  }
  threads {
    uuid id PK
    text title
    timestamptz created_at
    timestamptz last_active_at
  }
  messages {
    uuid id PK
    uuid thread_id FK
    text role
    text content
    text status
    timestamptz created_at
  }
  citations {
    uuid id PK
    uuid message_id FK
    uuid chunk_id FK
    text document_name
    text source_location
    text excerpt
  }
  documents ||--o{ chunks : "one-to-many"
  threads ||--o{ messages : "one-to-many"
  messages ||--o{ citations : "one-to-many"
  chunks ||--o{ citations : "one-to-many"
```
<!-- sdlc:auto:end er-diagram -->
