# Data Model: AI Discovery Agent

**Branch**: `051-ai-discovery-agent` | **Date**: 2026-04-04

## Entity Relationship Diagram

```
DiscoveryContact 1──N DiscoveryAuthSession
DiscoveryContact 1──N DiscoveryChatSession
DiscoveryContact 1──1 DiscoveryState
DiscoveryContact N──M DiscoveryWorkflow (via DiscoveryContribution)
DiscoveryChatSession 1──N DiscoveryMessage
DiscoveryChatSession 1──N DiscoveryArtifact
DiscoveryWorkflow 1──N DiscoveryArtifact
DiscoveryWorkflow 1──N DiscoveryExtraction
DiscoveryMessage 1──N DiscoveryExtraction
```

## Entities

### DiscoveryContact

The accountant being interviewed. Lightweight identity, not a Clairo subscriber.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Primary identity anchor |
| name | VARCHAR(255) | | Contact's full name |
| practice_name | VARCHAR(255) | | Accounting practice/firm name |
| practice_size | INTEGER | | Estimated number of clients |
| invited_by_tenant_id | UUID | FK → tenants.id, NOT NULL | Tenant who sent the first invitation |
| invitation_token_hash | VARCHAR(64) | UNIQUE | SHA-256 hash of invitation token |
| invitation_status | ENUM | NOT NULL, DEFAULT 'pending' | pending, sent, accepted, expired |
| invitation_expires_at | TIMESTAMPTZ | | Token expiry |
| first_authenticated_at | TIMESTAMPTZ | | When they first verified email |
| last_active_at | TIMESTAMPTZ | | Last session activity |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_contacts_email` (unique), `idx_discovery_contacts_invited_by`

**Note**: No `tenant_id` on this table — contacts exist outside the tenant boundary. Access is controlled by `invited_by_tenant_id` for admin views.

### DiscoveryAuthSession

Auth sessions for passwordless email login. Parallel to `PortalSession`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| contact_id | UUID | FK → discovery_contacts.id, NOT NULL | |
| refresh_token_hash | VARCHAR(64) | UNIQUE, NOT NULL | SHA-256 of refresh token |
| device_fingerprint | VARCHAR(255) | | Browser/device identifier |
| ip_address | INET | | IP at session creation |
| user_agent | TEXT | | Browser user agent |
| expires_at | TIMESTAMPTZ | NOT NULL | 30-day expiry |
| revoked | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_auth_sessions_contact_id`, `idx_discovery_auth_sessions_refresh_token_hash` (unique)

### DiscoveryChatSession

A single conversation sitting between a contact and the agent.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| contact_id | UUID | FK → discovery_contacts.id, NOT NULL | |
| started_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| ended_at | TIMESTAMPTZ | | Null if active |
| message_count | INTEGER | NOT NULL, DEFAULT 0 | |
| state_snapshot_start | JSONB | | Discovery state at session start (for diff) |
| state_snapshot_end | JSONB | | Discovery state at session end |
| session_summary | TEXT | | AI-generated session summary |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_sessions_contact_id`

### DiscoveryMessage

Individual messages in a session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| session_id | UUID | FK → discovery_chat_sessions.id, NOT NULL | |
| contact_id | UUID | FK → discovery_contacts.id, NOT NULL | Denormalized for querying |
| role | VARCHAR(20) | NOT NULL | 'user' or 'assistant' |
| content | TEXT | NOT NULL | Message text content |
| a2ui_message | JSONB | | A2UI component payload (assistant messages only) |
| metadata_ | JSONB | | Attachment info, skill execution context |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_messages_session_id`, `idx_discovery_messages_contact_id`

### DiscoveryState

Living structured summary per contact. One row per contact, updated after each session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| contact_id | UUID | FK → discovery_contacts.id, UNIQUE, NOT NULL | |
| state_data | JSONB | NOT NULL, DEFAULT '{}' | The structured discovery state |
| version | INTEGER | NOT NULL, DEFAULT 1 | Incremented on each update |
| last_updated_by_session_id | UUID | FK → discovery_chat_sessions.id | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_state_contact_id` (unique)

**`state_data` schema**: See research.md R3 for the JSONB structure.

### DiscoveryWorkflow

A workflow type identified during conversations. Shared across contacts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| name | VARCHAR(255) | NOT NULL | e.g., "Uber Driver BAS Preparation" |
| slug | VARCHAR(255) | UNIQUE, NOT NULL | URL-safe identifier |
| description | TEXT | | AI-generated summary |
| embedding | VECTOR(1024) | | Voyage 3.5 lite embedding for similarity |
| completeness_score | FLOAT | DEFAULT 0.0 | Aggregate completeness 0.0–1.0 |
| contributor_count | INTEGER | DEFAULT 0 | Number of contributing contacts |
| merged_from_ids | UUID[] | | If this workflow was merged from others |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_workflows_slug` (unique), `idx_discovery_workflows_embedding` (ivfflat for pgvector)

### DiscoveryContribution

Join table: which contacts have contributed to which workflows.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| contact_id | UUID | FK → discovery_contacts.id, NOT NULL | |
| workflow_id | UUID | FK → discovery_workflows.id, NOT NULL | |
| first_mentioned_session_id | UUID | FK → discovery_chat_sessions.id | |
| confirmed | BOOLEAN | DEFAULT FALSE | Admin confirmed the link |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_contributions_contact_workflow` (unique composite)

### DiscoveryExtraction

Atomic unit of insight extracted from conversation. Traces back to source message.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| message_id | UUID | FK → discovery_messages.id, NOT NULL | Source message |
| contact_id | UUID | FK → discovery_contacts.id, NOT NULL | |
| workflow_id | UUID | FK → discovery_workflows.id | Null if not yet linked |
| extraction_type | VARCHAR(50) | NOT NULL | workflow_step, pain_point, tool_mention, volume_estimate, edge_case, data_format |
| content | JSONB | NOT NULL | Structured extraction data |
| confidence | FLOAT | | AI confidence 0.0–1.0 |
| feedback | VARCHAR(20) | | accepted, modified, rejected |
| feedback_content | JSONB | | Modified version if feedback='modified' |
| skill_name | VARCHAR(100) | | Which skill produced this extraction |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_extractions_contact_id`, `idx_discovery_extractions_workflow_id`, `idx_discovery_extractions_type`

### DiscoveryArtifact

Files uploaded during sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PK | |
| session_id | UUID | FK → discovery_chat_sessions.id, NOT NULL | |
| contact_id | UUID | FK → discovery_contacts.id, NOT NULL | |
| workflow_id | UUID | FK → discovery_workflows.id | |
| filename | VARCHAR(255) | NOT NULL | Original filename |
| media_type | VARCHAR(100) | NOT NULL | MIME type |
| size_bytes | BIGINT | NOT NULL | |
| storage_key | VARCHAR(500) | NOT NULL | MinIO object key |
| category | VARCHAR(50) | NOT NULL | csv, excel, pdf, image, text |
| analysis_result | JSONB | | AI analysis of file contents (schema, summary) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

**Indexes**: `idx_discovery_artifacts_contact_id`, `idx_discovery_artifacts_workflow_id`

## State Transitions

### Contact Status
```
pending → sent → accepted → (active, tracked by last_active_at)
pending → expired (after invitation_expires_at)
```

### Chat Session Lifecycle
```
created (started_at set) → active (messages flowing) → ended (ended_at set, summary generated, state snapshot saved)
```

### Extraction Feedback
```
created (no feedback) → accepted | modified | rejected (by accountant via A2UI)
```

## Multi-Tenancy Note

Discovery contacts exist **outside** the normal tenant boundary. They are not tenant-scoped entities. Access control is via `invited_by_tenant_id` — a tenant admin can only see contacts they invited and the associated sessions/insights. Platform admins (Suren) can see all contacts.

The `DiscoveryWorkflow` entity is fully global — shared across all contacts regardless of which tenant invited them. This is by design: the value is in cross-practice pattern aggregation.
