---
name: clairo-domain-knowledge
description: >
  Domain knowledge for Clairo: entity taxonomy, Australian tax compliance concepts, subscription tiers, and recurring edge cases.
  Enriches specifications and implementation plans with correct domain terminology and business rules.
  Use during /speckit.specify, /speckit.plan, or when writing specs, designing features, or reviewing domain logic.
  Do NOT use for pure infrastructure, CI/CD, or frontend styling tasks.
---

# Clairo Domain Knowledge

## When This Applies

Use this skill when:
- Writing or reviewing feature specifications (specs/)
- Designing data models or entity relationships
- Implementing business logic involving Australian tax compliance (GST, BAS, PAYG, FBT)
- Working on subscription/billing/feature-gating logic
- Debugging tenant isolation, Xero sync, or background task issues
- Planning features that touch multiple modules

Do NOT use for:
- Pure CSS/styling changes
- CI/CD pipeline configuration
- Infrastructure-only changes (Terraform, Docker)
- Generic library upgrades with no domain impact

---

## Entity Taxonomy (Summary)

### Auth & Multi-Tenancy Layer
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **Tenant** | `tenants` | Has many PracticeUsers, XeroConnections, BillingEvents. Owns `tier`, `subscription_status`, `client_count` |
| **User** | `users` | Global identity (NOT tenant-scoped). Has one PracticeUser profile or ClientUser profile |
| **PracticeUser** | `practice_users` | Tenant-scoped profile for accountants. FK to User + Tenant. Has `role` (admin/accountant/staff) |
| **Invitation** | `invitations` | Tenant-scoped. Tracks pending team invitations |

### Data Layer (Xero Integration)
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **XeroConnection** | `xero_connections` | Central "client" entity. FK to Tenant. Has OAuth tokens, sync timestamps, rate limits. One per Xero org |
| **XeroClient** | `xero_clients` | Xero contacts (customers/suppliers). FK to XeroConnection |
| **XeroInvoice** | `xero_invoices` | Sales (ACCREC) and purchase (ACCPAY) invoices. FK to XeroConnection |
| **XeroBankTransaction** | `xero_bank_transactions` | Bank feed transactions. FK to XeroConnection |
| **XeroAccount** | `xero_accounts` | Chart of accounts. FK to XeroConnection |
| **XeroEmployee** | `xero_employees` | Payroll employees. FK to XeroConnection |
| **XeroPayRun** | `xero_pay_runs` | Payroll runs with PAYG/super. FK to XeroConnection |
| **XeroCreditNote** | `xero_credit_notes` | Credit notes affecting GST. FK to XeroConnection |
| **XeroPayment** | `xero_payments` | Payments for cash flow analysis. FK to XeroConnection |
| **XeroJournal** | `xero_journals` | System-generated journals. FK to XeroConnection |
| **XeroManualJournal** | `xero_manual_journals` | User-created journals. FK to XeroConnection |
| **XeroReport** | `xero_reports` | Cached Xero reports (P&L, Balance Sheet, etc). FK to XeroConnection |
| **XeroAsset** | `xero_assets` | Fixed assets with depreciation. FK to XeroConnection |

### Compliance Layer (BAS Workflow)
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **BASPeriod** | `bas_periods` | A quarter/month for a client. FK to XeroConnection |
| **BASSession** | `bas_sessions` | Preparation workflow. 1:1 with BASPeriod. Status: draft > in_progress > ready_for_review > approved > lodged |
| **BASCalculation** | `bas_calculations` | GST G-fields + PAYG W-fields. 1:1 with BASSession |
| **BASAdjustment** | `bas_adjustments` | Manual adjustments with mandatory reason. FK to BASSession |
| **BASAuditLog** | `bas_audit_log` | Immutable compliance audit trail |

### AI & Intelligence Layer
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **Insight** | `insights` | AI-generated proactive insights. FK to Tenant + XeroConnection |
| **ActionItem** | `action_items` | Curated tasks from insights. FK to Insight (optional) + XeroConnection |
| **Trigger** | `triggers` | Automated insight generation rules. FK to Tenant |
| **TriggerExecution** | `trigger_executions` | Execution audit log. FK to Trigger |
| **AgentQuery** | `agent_queries` | Multi-agent audit log (no query text for privacy). FK to Tenant |
| **AgentEscalation** | `agent_escalations` | Human escalation records. FK to AgentQuery |

### Knowledge Base Layer
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **KnowledgeSource** | `knowledge_sources` | Content source configs (ATO, AustLII, etc). NOT tenant-scoped |
| **ContentChunk** | `content_chunks` | Individual chunks in Pinecone. FK to KnowledgeSource |
| **IngestionJob** | `ingestion_jobs` | Pipeline run tracking. FK to KnowledgeSource |
| **LegislationSection** | `legislation_sections` | Structured legislation references |
| **ContentCrossReference** | `content_cross_references` | Graph links between chunks |
| **TaxDomain** | `tax_domains` | Specialist domain configs for scoped retrieval |
| **BM25IndexEntry** | `bm25_index_entries` | Hybrid search keyword index. FK to ContentChunk |
| **ChatConversation** | `chat_conversations` | User chat sessions. FK to XeroConnection (optional) |
| **ChatMessage** | `chat_messages` | Individual messages with citations. FK to ChatConversation |

### Quality & Scoring Layer
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **QualityScore** | `quality_scores` | Per-client per-quarter scores. FK to XeroConnection |
| **QualityIssue** | `quality_issues` | Detected data quality problems. FK to XeroConnection |

### Billing & Subscription Layer
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **BillingEvent** | `billing_events` | Stripe webhook events. FK to Tenant |
| **UsageSnapshot** | `usage_snapshots` | Historical usage metrics. FK to Tenant |
| **UsageAlert** | `usage_alerts` | Threshold alerts (80%, 90%, 100%). FK to Tenant |
| **FeatureFlagOverride** | `feature_flag_overrides` | Per-tenant overrides. FK to Tenant |

### Portal Layer (Business Owner)
| Entity | Table | Key Relationships |
|--------|-------|-------------------|
| **PortalInvitation** | `portal_invitations` | Client portal invitations. FK to XeroConnection |
| **DocumentRequest** | `document_requests` | ClientChase document requests. FK to XeroConnection |

Full entity details: `references/entity-taxonomy.md`

---

## Australian Compliance Quick Reference

| Term | Definition |
|------|------------|
| **GST** | Goods and Services Tax (10%). Collected on sales, claimed on purchases. Reported on BAS |
| **BAS** | Business Activity Statement. Periodic ATO report covering GST, PAYG-W, PAYG-I, FBT-I |
| **IAS** | Instalment Activity Statement. Monthly PAYG-W report for non-GST-registered entities |
| **PAYG-W** | Pay As You Go Withholding. Tax withheld from employee wages. BAS fields W1/W2 |
| **PAYG-I** | Pay As You Go Instalments. Prepaid income tax for businesses. BAS field T1 |
| **FBT** | Fringe Benefits Tax. Tax on non-cash employee benefits. Annual return + quarterly BAS instalment |
| **STP** | Single Touch Payroll. Real-time payroll reporting to ATO (each pay run) |
| **ABN** | Australian Business Number. 11-digit identifier for all businesses |
| **TFN** | Tax File Number. 9-digit individual/entity tax identifier. SENSITIVE - never log or display |
| **ATO** | Australian Taxation Office. The federal tax authority |
| **FY** | Financial Year. July 1 - June 30 in Australia (e.g., FY2025 = 1 Jul 2024 - 30 Jun 2025) |

Full glossary: `references/compliance-glossary.md`

---

## Subscription Tiers

| Tier | Price | Client Limit | AI Insights | Client Portal | Custom Triggers | API Access | Knowledge Base |
|------|-------|--------------|-------------|---------------|-----------------|------------|----------------|
| **Starter** | $99/mo | 25 | Basic (limited analyzers) | No | No | No | No |
| **Professional** | $299/mo | 100 | Full (all analyzers) | Yes | Yes | No | Yes |
| **Growth** | $599/mo | 250 | Full | Yes | Yes | Yes | Yes |
| **Enterprise** | Custom | Unlimited | Full | Yes (white-label) | Yes | Yes | Yes |

- All existing tenants default to Professional tier
- 14-day free trial available
- `SubscriptionStatus`: trial, active, past_due, suspended, cancelled, grandfathered
- Feature gating via `@require_feature()` decorator + `useTier()` frontend hook
- Client limit enforced on new client creation (existing clients continue)

---

## Recurring Edge Case Categories

| Category | Description | Affected Modules |
|----------|-------------|------------------|
| **Tenant Isolation** | RLS bypass, cross-tenant data leaks, tenant_id missing from queries | All modules |
| **Xero OAuth Token Races** | Concurrent token refresh, token expiry mid-sync, multi-org shared tokens | integrations/xero |
| **Xero Rate Limiting** | 60 calls/min, 5000/day per org; multi-client parallel sync; missing rate headers | integrations/xero, onboarding |
| **Background Task Failures** | Celery task crashes, partial progress, retry storms, idempotency | tasks, knowledge, integrations |
| **Subscription Limit Enforcement** | Client count during bulk import, mid-operation limit reached, tier downgrades | billing, clients, onboarding |
| **Stale Data** | Xero data not synced, cached reports expired, quality scores outdated | quality, insights, bas |
| **Concurrent Operations** | Duplicate syncs, simultaneous BAS edits, parallel bulk imports | integrations, bas, onboarding |
| **External Service Unavailability** | Xero 503, ATO site down, Pinecone outage, Stripe webhook delays | All integration points |
| **Knowledge Ingestion Reliability** | Dedup failures, orphaned vectors, circuit breaker states, checkpoint/resume | knowledge |
| **AI Output Trust** | Hardcoded confidence scores, missing evidence, no data freshness indicator | insights, agents |

Full edge case library: `references/edge-case-library.md`

---

## Key Domain Terminology

| Term | Clairo Meaning |
|------|---------------|
| **Tenant** | An accounting practice/firm. The PAYING SUBSCRIBER. Has tier, subscription, client_count |
| **Client** | A business whose BAS the accountant manages. Represented by XeroConnection (not XeroClient) |
| **Business Owner** | The owner of a client business. Portal user with magic-link auth. NOT a paying subscriber |
| **Accountant** | A PracticeUser with role=accountant or role=admin. Can prepare/approve BAS |
| **XeroConnection** | The central "client" entity. One per Xero organization. Stores OAuth tokens and sync state |
| **XeroClient** | A Xero contact (customer/supplier within a Xero org). NOT the same as "client" in Clairo |
| **Quality Score** | 0-100 data readiness score across 5 dimensions. Per-client per-quarter |
| **Insight** | Proactive AI-generated finding. Categories: compliance, quality, cash_flow, tax, strategic |
| **Magic Zone** | Multi-agent collaborative analysis producing strategic OPTIONS for accountants |
| **Action Item** | A curated task created from an insight (or standalone). Has assignee, due date, priority |
| **Trigger** | Automated rule that generates insights when conditions are met (threshold, schedule, event) |
| **Data Snapshot** | Point-in-time financial context stored with insights for audit trail |
| **G-fields** | BAS GST fields: G1 (total sales), G2 (exports), G3 (GST-free), G10/G11 (purchases) |
| **W-fields** | BAS PAYG fields: W1 (total wages), W2 (amount withheld) |
| **ATOtrack** | Planned feature for ATO correspondence parsing and deadline management |
| **ClientChase** | Document request and response tracking system within the client portal |

---

## Reference Files

- `references/entity-taxonomy.md` - Full entity details with fields and FK relationships
- `references/edge-case-library.md` - Edge cases organized by category with mitigations
- `references/compliance-glossary.md` - Australian tax compliance terminology and BAS mapping
- `specs/ROADMAP.md` - Implementation phases and feature list (SOURCE OF TRUTH)
- `backend/app/modules/` - Module source code
- `docs/solution-design.md` - Technical architecture
