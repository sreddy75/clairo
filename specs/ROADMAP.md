# Clairo Implementation Roadmap

**Source of Truth for Implementation Order**
**Version**: 5.9.0 | **Updated**: 2026-01-04

> This document guides AI agents and developers through the implementation sequence.
> Read this FIRST in any new session to understand context and current focus.

---

## Quick Context

**What**: Clairo - AI-Powered BAS Management Platform for Australian Accounting Practices
**Vision**: Three Pillars (Data + Compliance + Strategy) via Multi-Agent AI
**Architecture**: Python/FastAPI Modular Monolith + Multi-Agent AI System
**Go-to-Market**: B2B2C (Accountant-first, then client portal distribution)

```
┌─────────────────────────────────────────────────────────────────┐
│  🎉 PHASE E COMPLETE - Data Intelligence ✅                      │
│                                                                 │
│  CURRENT FOCUS: PHASE E.5 → Spec 026 (Email Integration)        │
│  Status: NOT_STARTED                                            │
│  Previous: Spec 025 (Fixed Assets & Analysis) - COMPLETE ✅      │
│                                                                 │
│  STRATEGY: ATOtrack next for post-lodgement intelligence        │
│                                                                 │
│  ROADMAP UPDATE v5.6:                                           │
│  ├── Phase E: Data Intelligence (Specs 023-025) ✅ COMPLETE      │
│  │   └── Xero Reports, Credit Notes, Payments, Journals, Assets │
│  ├── Phase E.5: ATOtrack (Specs 026-028) ← NEXT                 │
│  │   └── Email OAuth, ATO parsing, workflow integration         │
│  ├── Phase E.6: AI Intelligence Flywheel (Spec 029)             │
│  │   └── Capture interactions, learn patterns, fine-tune models │
│  ├── Phase F: Business Owner + ClientChase (Specs 030-033)      │
│  ├── Phase G: Growth & Scale (Specs 034-041)                    │
│  │   └── A2UI Agent-Driven Interfaces                           │
│  └── Phase H: Polish & Operations (Specs 010, 040)              │
│                                                                 │
│  MILESTONE: Phase E Complete = Enhanced AI Insights ✅           │
│  MILESTONE: Phase D Complete = Ready for Pilot Launch ✅         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Strategic Alignment

### Go-to-Market Strategy

**Reference**: `/docs/strategy/MARKETING_STRATEGY.md`

| Phase | Timeline | Target | Revenue Goal |
|-------|----------|--------|--------------|
| Phase 1 | Months 1-6 | 50 practices, 5K clients | $15K MRR |
| Phase 2 | Months 6-12 | 150 practices, 10K portal users | $50K MRR |
| Phase 3 | Months 12-18 | 400 practices, B2C test | $150K MRR |

### Pricing Strategy

**Reference**: `/docs/strategy/PRICING_STRATEGY.md`

| Tier | Price | Client Limit | Key Features |
|------|-------|--------------|--------------|
| Starter | $99/mo | 25 clients | Core BAS, basic AI |
| Professional | $299/mo | 100 clients | Full AI, client portal, triggers |
| Growth | $599/mo | 250 clients | API access, priority support |
| Enterprise | Custom | Unlimited | White-label, dedicated CSM |

### Implementation → Strategy Mapping

```
IMPLEMENTATION PHASES                    GO-TO-MARKET PHASES
═══════════════════════════════════════════════════════════════════

Phase A-C: Platform Built ✅

Phase D: Monetization Foundation ──────► Ready for GTM Phase 1
  └── Subscriptions, tiers, gating       (Accountant acquisition)

Phase E: Data Intelligence ────────────► Enhanced AI Insights
  └── Xero Reports, Credit Notes,        (Deeper financial analysis)
      Payments, Journals, Assets

Phase E.5: ATOtrack ───────────────────► Post-Lodgement Intelligence
  └── Email OAuth, ATO parsing,          (Never miss ATO deadlines)
      workflow integration

Phase E.6: AI Intelligence Flywheel ──► AI Learning Active
  └── Capture interactions, patterns,     (Every query makes AI smarter)
      fine-tuning pipeline

Phase F: Business Owner + ClientChase ─► Ready for GTM Phase 2
  └── Client portal, document requests    (Portal + doc collection)

Phase G: Growth & Scale ───────────────► Ready for GTM Phase 3
  └── B2C, white-label, API, A2UI        (B2C conversion + dynamic UX)
```

---

## Phase Summary

### Completed Phases

| Phase | Focus | Status | Key Deliverables |
|-------|-------|--------|------------------|
| **A** | Foundation | ✅ COMPLETE | Auth, Xero sync, BAS prep, data quality |
| **B** | AI Core (Moat) | ✅ COMPLETE | Knowledge base, RAG, multi-agent system |
| **C** | Proactive Intelligence | ✅ COMPLETE | Insights, triggers, action items, Magic Zone |

### Completed Phases (continued)

| Phase | Focus | Status | Key Deliverables |
|-------|-------|--------|------------------|
| **D** | Monetization Foundation | ✅ COMPLETE | Subscriptions, tiers, usage tracking, onboarding |
| **E** | Data Intelligence | ✅ COMPLETE | Xero Reports, Credit Notes, Payments, Journals, Fixed Assets |

### Remaining Phases

| Phase | Focus | Specs | Go-Live Milestone |
|-------|-------|-------|-------------------|
| **E.5** | ATOtrack | 026-028 | Post-Lodgement Intelligence (ATO correspondence) |
| **E.6** | AI Intelligence Flywheel | 029 | AI Learning Active (data moat) |
| **F** | Business Owner + ClientChase | 030-033 | Portal Launch + Doc Collection |
| **G** | Growth & Scale | 034-041 | Enterprise, B2C, Observability, A2UI |
| **H** | Polish & Operations | 010, 040 | Production hardening |

---

## Phase D: Monetization Foundation

**Goal**: Enable paid subscriptions with tier-based feature access

**Why This Phase First**:
- Current features are "always on" - no tier differentiation
- Can't validate pricing strategy without payment system
- Every new feature after this inherits the gating pattern
- Lower disruption to add gating now vs retrofitting later

### Spec 019: Subscription & Feature Gating

**Disruption Level**: Medium (30% modification, 70% additive)

```
FEATURE GATING ARCHITECTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                     TENANT (Accounting Practice)                 │
│                                                                 │
│  tier: "professional"                                           │
│  stripe_customer_id: "cus_xxx"                                  │
│  subscription_status: "active"                                  │
│  client_count: 47                                               │
│  client_limit: 100                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE FLAG CONFIG                          │
│                                                                 │
│  TIER_FEATURES = {                                              │
│    "starter": {                                                 │
│      "max_clients": 25,                                         │
│      "ai_insights": "basic",     # Limited analyzers            │
│      "client_portal": False,                                    │
│      "custom_triggers": False,                                  │
│      "api_access": False,                                       │
│      "knowledge_base": False,                                   │
│    },                                                           │
│    "professional": {                                            │
│      "max_clients": 100,                                        │
│      "ai_insights": "full",      # All analyzers               │
│      "client_portal": True,                                     │
│      "custom_triggers": True,                                   │
│      "api_access": False,                                       │
│      "knowledge_base": True,                                    │
│    },                                                           │
│    ...                                                          │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GATING ENFORCEMENT                           │
│                                                                 │
│  Backend:                                                       │
│  @require_feature("custom_triggers")                            │
│  async def create_trigger(...):                                 │
│      ...                                                        │
│                                                                 │
│  @require_tier("professional")                                  │
│  async def access_knowledge_base(...):                          │
│      ...                                                        │
│                                                                 │
│  Frontend:                                                      │
│  const { canAccess, tier } = useTier();                         │
│  {canAccess("custom_triggers") ? <TriggerUI /> : <Upgrade />}   │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Tenant tier model | Add `tier`, `stripe_customer_id`, `subscription_status` to Tenant |
| Feature flag config | Python dict defining features per tier |
| Backend gating | `@require_feature()` decorator, middleware |
| Frontend gating | `useTier()` hook, `<UpgradePrompt>` component |
| Stripe integration | Checkout, webhooks, customer portal |
| Billing tables | `stripe_customers`, `subscriptions`, `billing_events` |
| Subscription API | Create checkout, manage subscription, usage |

**Migration Path**:
1. All existing tenants start as "professional" (no disruption)
2. New tenants choose tier at signup
3. Existing features wrapped with gating checks

### Spec 020: Usage Tracking & Limits

**Disruption Level**: Low (additive)

```
USAGE ENFORCEMENT
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT COUNT TRACKING                        │
│                                                                 │
│  On Xero Sync:                                                  │
│    client_count = count(xero_connections WHERE tenant_id = X)   │
│    IF client_count > tenant.client_limit:                       │
│      - Block new client creation                                │
│      - Show upgrade prompt                                      │
│      - Allow existing clients to continue                       │
│                                                                 │
│  Overage Billing (optional):                                    │
│    overage_clients = client_count - client_limit                │
│    overage_charge = overage_clients * OVERAGE_RATE              │
│                                                                 │
│  Usage Dashboard:                                               │
│    - Clients used: 47 / 100                                     │
│    - AI queries this month: 1,234                               │
│    - Documents processed: 89                                    │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Client count tracking | Real-time count per tenant |
| Limit enforcement | Block new clients at limit |
| Usage dashboard | Visual usage vs limits |
| Overage alerts | Email when approaching limit |
| Usage analytics | Track feature usage per tier |

### Spec 021: Onboarding Flow

**Disruption Level**: Low (additive)

```
NEW ACCOUNTANT ONBOARDING
═══════════════════════════════════════════════════════════════════

Step 1: Signup (Clerk)
    │
    ▼
Step 2: Choose Tier
    ├── Starter ($99/mo) - "I'm just starting out"
    ├── Professional ($299/mo) - "Most popular" ⭐
    └── Growth ($599/mo) - "I have a larger practice"
    │
    ▼
Step 3: Payment (Stripe Checkout)
    │
    ▼
Step 4: Connect Xero
    │
    ▼
Step 5: Import First Client
    │
    ▼
Step 6: Quick Tour (product walkthrough)
    │
    ▼
Dashboard (ready to use)
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Signup flow | Clerk → Tier selection → Stripe checkout |
| Trial mode | 14-day free trial option |
| Onboarding checklist | Track setup completion |
| Product tour | Interactive walkthrough for new users |
| Welcome emails | Drip sequence for activation |

### Spec 022: Admin Dashboard (Internal)

**Disruption Level**: Low (additive)

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Customer list | All tenants with tier, status, usage |
| Revenue dashboard | MRR, churn, expansion |
| Subscription management | Manual tier changes, credits |
| Feature flag overrides | Enable/disable features per tenant |
| Usage analytics | Aggregate usage patterns |

### Phase D Summary

| Spec | Name | Priority | Effort | Dependencies | Status |
|------|------|----------|--------|--------------|--------|
| 019 | Subscription & Feature Gating | P0 | 1 week | Specs 001-018 ✓ | ✅ COMPLETE |
| 020 | Usage Tracking & Limits | P0 | 3 days | 019 | ✅ COMPLETE |
| 021 | Onboarding Flow | P1 | 3 days | 019, 020 | ✅ COMPLETE |
| 022 | Admin Dashboard (Internal) | P2 | 2 days | 019, 020 | ✅ COMPLETE |

**Phase D Exit Criteria**:
- [x] New tenant can sign up and pay via Stripe ✅
- [x] Tier-based feature access working (Professional tier tested) ✅
- [x] Client limits enforced ✅
- [x] Usage dashboard shows real-time counts ✅
- [x] Admin can view all customers and subscriptions (Spec 022) ✅

**Milestone**: Ready for Pilot Launch (paying customers) - PHASE D COMPLETE ✅

---

## Phase E: Data Intelligence

**Goal**: Expand Xero data coverage to enhance AI insights and financial analysis

**Why This Phase**:
- Gap analysis revealed we fetch only ~20% of available Xero data
- Reports API provides pre-calculated financials (P&L, Balance Sheet, Aged Reports)
- Credit Notes are missing from GST calculations
- Payments data enables actual cash flow analysis (vs invoiced amounts)
- Journals provide complete audit trail for anomaly detection
- Better data = significantly smarter AI agents

**Reference**: `/planning/analysis/xero-api-gap-analysis.md`

### Spec 023: Xero Reports API

**Disruption Level**: Low (additive)

```
XERO REPORTS INTEGRATION
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    XERO REPORTS API                             │
│                    (Pre-calculated by Xero)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GET /Reports/ProfitAndLoss                                     │
│  └── Revenue, expenses, net profit by period                   │
│                                                                 │
│  GET /Reports/BalanceSheet                                      │
│  └── Assets, liabilities, equity snapshot                      │
│                                                                 │
│  GET /Reports/AgedReceivablesByContact                         │
│  └── Who owes money, how overdue (debtor days)                 │
│                                                                 │
│  GET /Reports/AgedPayablesByContact                            │
│  └── Who we owe, payment patterns                              │
│                                                                 │
│  GET /Reports/TrialBalance                                      │
│  └── Account balances for reconciliation                       │
│                                                                 │
│  GET /Reports/BankSummary                                       │
│  └── Cash position across all accounts                         │
│                                                                 │
│  GET /Reports/BudgetSummary                                     │
│  └── Budget vs actual variance                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI AGENT ENHANCEMENT                         │
│                                                                 │
│  Financial Health Agent:                                        │
│  └── "Current ratio dropped from 2.1 to 1.4 - liquidity risk"  │
│                                                                 │
│  Trend Analysis Agent:                                          │
│  └── "Revenue up 15% but COGS up 22% - margin compression"     │
│                                                                 │
│  Collection Risk Agent:                                         │
│  └── "$45K over 90 days with Customer X - recommend follow-up" │
│                                                                 │
│  Budget Variance Agent:                                         │
│  └── "Marketing spend 40% over budget this quarter"            │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Report sync service | Fetch and cache Xero reports |
| Report data models | `XeroReport`, `XeroReportRow`, `XeroReportCell` |
| P&L analysis | Period comparison, trend detection |
| Balance sheet analysis | Ratio calculations, health scoring |
| Aged receivables/payables | Debtor days, collection risk |
| Report caching strategy | Daily refresh, on-demand for current period |
| AI agent integration | Reports as context for all financial agents |

**AI Impact**:
- Financial Health agent can assess ratios without recalculating
- Trend agent can compare periods accurately
- Collection agent has precise aging data

### Spec 024: Credit Notes, Payments & Journals

**Disruption Level**: Medium (modifies GST calculations)

```
COMPLETE FINANCIAL PICTURE
═══════════════════════════════════════════════════════════════════

CURRENT STATE (Incomplete):
┌──────────────┐     ┌──────────────┐
│   Invoices   │  +  │    Bank      │  =  GST Calculation
│  (Sales/Purch)│     │ Transactions │     (INCOMPLETE!)
└──────────────┘     └──────────────┘

MISSING PIECES:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Credit Notes │     │   Payments   │     │   Journals   │
│              │     │              │     │              │
│ GST adjust-  │     │ When cash    │     │ Complete     │
│ ments,refunds│     │ actually     │     │ audit trail  │
│              │     │ moved        │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
              ┌──────────────────────────┐
              │  COMPLETE GST PICTURE    │
              │  + Cash Flow Accuracy    │
              │  + Anomaly Detection     │
              └──────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Credit Notes sync | `XeroCreditNote` model, allocations |
| Payments sync | `XeroPayment` model with invoice links |
| Journals sync | `XeroJournal` model (system-generated) |
| Manual Journals sync | `XeroManualJournal` model (user-created) |
| GST calculation update | Include credit notes in GST totals |
| Cash flow enhancement | Actual payment dates vs invoice dates |
| Audit trail | Journal-based transaction history |
| Anomaly detection | Flag unusual manual journal patterns |

**GST Impact**:
```
BEFORE: GST Collected = Sum(Invoice GST)
AFTER:  GST Collected = Sum(Invoice GST) - Sum(Credit Note GST)
```

**Cash Flow Impact**:
```
BEFORE: Revenue = Invoice amounts (when invoiced)
AFTER:  Cash In = Payment amounts (when received)
        Debtor Days = (Payment Date - Invoice Date)
```

### Spec 025: Fixed Assets & Enhanced Analysis

**Disruption Level**: Low (additive)

```
ASSETS API INTEGRATION
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    XERO ASSETS API                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GET /Assets                                                    │
│  └── Fixed asset register                                       │
│      ├── Purchase date, cost                                    │
│      ├── Depreciation method                                    │
│      ├── Book value, tax value                                  │
│      └── Disposal details                                       │
│                                                                 │
│  GET /AssetTypes                                                │
│  └── Depreciation configurations                                │
│                                                                 │
│  GET /Settings                                                  │
│  └── Asset register settings                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI INSIGHTS                                   │
│                                                                 │
│  Instant Asset Write-Off Agent:                                 │
│  └── "3 assets qualify for instant write-off ($12,400 total)"  │
│                                                                 │
│  Depreciation Planning Agent:                                   │
│  └── "Current year depreciation: $8,200 (tax deduction)"       │
│                                                                 │
│  Capital Planning Agent:                                        │
│  └── "Asset X fully depreciated - consider replacement"        │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Assets API integration | New OAuth scope, API client |
| Asset sync service | `XeroAsset`, `XeroAssetType` models |
| Depreciation tracking | Book vs tax depreciation |
| Instant write-off detection | Flag qualifying assets |
| Enhanced financial summary | Include depreciation in analysis |
| Capital expenditure insights | Asset purchase patterns |

**Additional Enhancements** (in this spec):

| Enhancement | Description |
|-------------|-------------|
| Purchase Orders sync | Future cash outflow visibility |
| Quotes sync | Revenue pipeline analysis |
| Repeating Invoices sync | Recurring revenue/expense prediction |
| Tracking Categories sync | Project/department profitability |

### Phase E Summary

| Spec | Name | Priority | Effort | Dependencies | Status |
|------|------|----------|--------|--------------|--------|
| 023 | Xero Reports API | P0 | 3 days | Phase D ✓ | ✅ COMPLETE |
| 024 | Credit Notes, Payments & Journals | P0 | 4 days | 023 ✓ | ✅ COMPLETE |
| 025 | Fixed Assets & Enhanced Analysis | P1 | 3 days | 023 ✓, 024 ✓ | ✅ COMPLETE |

**Phase E Exit Criteria**:
- [x] P&L, Balance Sheet, Aged Reports syncing daily ✅
- [x] Credit Notes included in GST calculations ✅
- [x] Payments providing actual cash flow data ✅
- [x] Journals enabling complete audit trail ✅
- [x] Fixed Assets API integrated (if scope enabled) ✅
- [x] AI agents using new data sources ✅
- [x] Financial insights accuracy improved by >40% ✅

**Milestone**: Enhanced AI Insights (significantly smarter analysis) - PHASE E COMPLETE ✅

---

## Phase E.5: ATOtrack (Post-Lodgement Intelligence)

**Goal**: Capture and process ATO correspondence automatically, never miss deadlines

**Why This Phase**:
- Xero stops at lodgement - post-lodgement workflow is completely manual
- ATO notices buried in email cause penalties ($222+ per missed deadline)
- Practice-level view of ATO correspondence doesn't exist elsewhere
- Complements Portfolio Intelligence with proactive deadline management
- Key differentiator: "Never miss an ATO deadline again"

**Reference**: `/planning/analysis/agentic-actions-research.md`

### Spec 026: Email Integration & OAuth

**Disruption Level**: Medium (new integration pattern)

```
EMAIL INTEGRATION ARCHITECTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    EMAIL CONNECTION OPTIONS                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PRIMARY: OAuth Integration                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Gmail (Google Workspace)                                │   │
│  │  └── Scopes: gmail.readonly, gmail.labels               │   │
│  │  └── Query: from:@ato.gov.au newer_than:30d             │   │
│  │                                                          │   │
│  │  Microsoft 365 / Outlook                                 │   │
│  │  └── Scopes: Mail.Read, Mail.ReadBasic                  │   │
│  │  └── Filter: from/emailAddress contains 'ato.gov.au'    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  FALLBACK: Email Forwarding                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Unique ingest address: practice-abc@ingest.clairo.au  │   │
│  │  User sets up mail rule: From @ato.gov.au → Forward     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SYNC STRATEGY                                 │
│                                                                 │
│  Initial Sync: Backfill last 12 months of ATO emails           │
│  Incremental: Webhook/polling for new emails                    │
│  Filter: Only @ato.gov.au, @notifications.ato.gov.au           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Email connection model | `EmailConnection` with OAuth tokens (encrypted) |
| Gmail OAuth flow | Google Workspace integration |
| Microsoft OAuth flow | Microsoft 365 / Outlook integration |
| Email sync service | Initial backfill + incremental sync |
| Forwarding fallback | Ingest email address per tenant |
| Token refresh | Background token refresh before expiry |
| Connection management | Connect/disconnect UI, status display |

**Data Model**:
```python
class EmailConnection(Base):
    id: UUID
    tenant_id: UUID
    provider: EmailProvider  # GMAIL, OUTLOOK, FORWARDING
    access_token_encrypted: str
    refresh_token_encrypted: str
    token_expires_at: datetime
    last_sync_at: datetime
    sync_cursor: str
    status: ConnectionStatus  # ACTIVE, EXPIRED, REVOKED
```

### Spec 027: ATO Correspondence Parsing

**Disruption Level**: Low (additive)

```
ATO PARSING PIPELINE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    EMAIL ARRIVES                                 │
│                    (from @ato.gov.au)                           │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI PARSING (Claude)                          │
│                                                                 │
│  Extract:                                                       │
│  ├── Notice type (Activity Statement, Audit, Penalty, etc.)   │
│  ├── Client identifier (ABN, TFN, Entity name)                 │
│  ├── Due date / Response deadline                              │
│  ├── Amount (if penalty/debt related)                          │
│  ├── Reference number                                           │
│  └── Required action summary                                    │
│                                                                 │
│  Confidence score for each field                                │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT MATCHING                              │
│                                                                 │
│  1. ABN in email → Direct match                                │
│  2. Entity name → Fuzzy match against clients                  │
│  3. If confidence < 80% → Surface for manual triage            │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STORAGE                                       │
│                                                                 │
│  Vector Store (Qdrant):                                         │
│  └── Full email text + embeddings for semantic search          │
│                                                                 │
│  Relational DB (PostgreSQL):                                    │
│  └── Structured metadata, client link, due dates               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| ATO Correspondence model | `ATOCorrespondence` with parsed fields |
| Claude parsing service | Structured extraction with confidence scores |
| Notice type taxonomy | Activity Statement, Audit, Penalty, Debt, etc. |
| Client matching service | ABN lookup, fuzzy name matching |
| Triage queue | Unmatched/low-confidence items for manual review |
| Vector storage | Email content in Qdrant per tenant |
| Attachment handling | Extract and store PDF notices |

**Data Model**:
```python
class ATOCorrespondence(Base):
    id: UUID
    tenant_id: UUID
    client_id: UUID | None  # Matched client
    email_connection_id: UUID

    # Email metadata
    received_at: datetime
    subject: str
    from_address: str
    raw_email_s3_key: str

    # Parsed fields
    notice_type: ATONoticeType
    reference_number: str | None
    due_date: date | None
    amount: Decimal | None
    required_action: str

    # Processing
    parsed_at: datetime
    confidence_score: float
    match_confidence: float
    vector_id: str  # Qdrant reference

    # Workflow
    status: CorrespondenceStatus  # NEW, REVIEWED, ACTIONED, RESOLVED
    task_id: UUID | None
    insight_id: UUID | None
```

### Spec 028: ATOtrack Workflow Integration

**Disruption Level**: Low (extends existing systems)

```
ATOTRACK WORKFLOW
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    PARSED ATO CORRESPONDENCE                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│    INSIGHT      │ │      TASK       │ │   NOTIFICATION  │
│                 │ │                 │ │                 │
│ "ATO audit      │ │ "Respond to     │ │ Email + Push    │
│  notice for     │ │  ATO audit by   │ │ alert to        │
│  Smith Plumbing"│ │  Jan 15"        │ │ accountant      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PRACTICE MANAGEMENT PUSH                     │
│                    (Optional Integration)                       │
│                                                                 │
│  Karbon: Create task in appropriate workflow                   │
│  XPM: Create job with deadline                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

ATOTRACK DASHBOARD
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│  ATO CORRESPONDENCE                              [Connect Email] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ 🔴 3    │  │ 🟡 5    │  │ 🟢 12   │  │ 📥 2    │           │
│  │ Overdue │  │ Due Soon│  │ Handled │  │ Triage  │           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
│                                                                 │
│  REQUIRES ATTENTION                                             │
│  ──────────────────────────────────────────────────────────────│
│  🔴 Smith Plumbing - Audit response due in 2 DAYS              │
│     [View Notice] [Open Task] [Mark Resolved]                  │
│                                                                 │
│  🔴 ABC Retail - Penalty notice $1,100 - due Jan 10           │
│     [View Notice] [Draft Remission Request]                    │
│                                                                 │
│  🟡 Jones Consulting - Activity Statement reminder             │
│     Due Jan 21 (14 days)                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| ATOtrack dashboard | Dedicated view for ATO correspondence |
| Insight integration | Auto-create insights from correspondence |
| Task integration | Auto-create tasks with due dates |
| Notification triggers | Email/push for new correspondence, approaching deadlines |
| Karbon integration | Push tasks to Karbon (optional) |
| XPM integration | Push jobs to XPM (optional) |
| AI response drafting | Use RAG to draft audit responses, remission requests |
| Correspondence search | Semantic search across all ATO emails |
| Status tracking | NEW → REVIEWED → ACTIONED → RESOLVED workflow |

### Phase E.5 Summary

| Spec | Name | Priority | Effort | Dependencies |
|------|------|----------|--------|--------------|
| 026 | Email Integration & OAuth | P0 | 1 week | Phase E ✓ |
| 027 | ATO Correspondence Parsing | P0 | 1 week | 026 |
| 028 | ATOtrack Workflow Integration | P0 | 1 week | 027, existing tasks/insights |

**Phase E.5 Exit Criteria**:
- [ ] Gmail and/or Outlook OAuth working
- [ ] ATO emails being captured and parsed
- [ ] Client matching working (>80% auto-match rate)
- [ ] Tasks auto-created with correct due dates
- [ ] ATOtrack dashboard showing correspondence status
- [ ] Notifications firing for new/overdue items

**Milestone**: Post-Lodgement Intelligence (never miss an ATO deadline)

---

## Phase E.6: AI Intelligence Flywheel

**Goal**: Capture, analyze, and learn from every AI interaction to continuously improve

**Why This Phase**:
- Every AI interaction is a learning opportunity we're currently wasting
- Accountant queries reveal what they actually need (vs what we assume)
- Low-satisfaction responses identify knowledge gaps to fix
- Repeated requests reveal features we should build
- Fine-tuned models become an unreplicable competitive moat
- The earlier we start capturing, the bigger the moat grows

**Reference**: `/planning/analysis/ai-intelligence-flywheel.md`

### Spec 029: AI Interaction Capture & Learning

**Disruption Level**: Low (additive instrumentation)

```
THE INTELLIGENCE FLYWHEEL
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│     ┌──────────────┐                                                    │
│     │  Accountants │                                                    │
│     │  Ask Questions│                                                   │
│     └──────┬───────┘                                                    │
│            │                                                            │
│            ▼                                                            │
│     ┌──────────────┐      ┌──────────────┐                             │
│     │  AI Responds │      │  We Capture  │                             │
│     │              │─────▶│  Query + Context                           │
│     └──────┬───────┘      │  + Outcome   │                             │
│            │              └──────┬───────┘                             │
│            ▼                     │                                      │
│     ┌──────────────┐             │                                      │
│     │  Accountant  │             ▼                                      │
│     │  Acts (or not)│     ┌──────────────┐                             │
│     └──────┬───────┘      │  Pattern     │                             │
│            │              │  Analysis    │                             │
│            │              └──────┬───────┘                             │
│            ▼                     │                                      │
│     ┌──────────────┐             ▼                                      │
│     │  Better      │◀─────┌──────────────┐                             │
│     │  Outcomes    │      │  Model       │                             │
│     └──────────────┘      │  Improvement │                             │
│                           └──────────────┘                             │
│                                                                         │
│  MORE USAGE → BETTER DATA → SMARTER AI → MORE VALUE → MORE USAGE       │
└─────────────────────────────────────────────────────────────────────────┘

DATA CAPTURE PIPELINE
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  EVERY AI INTERACTION CAPTURES:                                         │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                         │
│  Query:                              Response:                          │
│  ├── Text + embedding               ├── Text + sources used            │
│  ├── Auto-classified category       ├── Confidence score               │
│  ├── Session context                ├── Model version                  │
│  └── Client context                 └── Latency                        │
│                                                                         │
│  Outcome:                            Feedback:                          │
│  ├── Follow-up query? (clarity)     ├── Thumbs up/down                 │
│  ├── Action taken?                  ├── Optional comment               │
│  └── Time to action                 └── Implicit signals               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

WEEKLY INTELLIGENCE REPORT
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│  AI LEARNING DASHBOARD                                   Admin Only     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  This Week: 12,847 interactions (+18%)                                  │
│  Satisfaction: 4.2/5.0 (↑0.1)                                          │
│                                                                         │
│  TOP QUERY CATEGORIES              KNOWLEDGE GAPS (Low Satisfaction)   │
│  ─────────────────────────────────────────────────────────────────────  │
│  1. GST compliance (42%)           🔴 FBT electric vehicles (2.8/5)    │
│  2. Data quality (22%)             🔴 Division 7A calcs (3.1/5)        │
│  3. Cash flow (18%)                🟡 Multi-currency GST (3.4/5)       │
│                                                                         │
│  FEATURE OPPORTUNITIES             FINE-TUNING CANDIDATES              │
│  ─────────────────────────────────────────────────────────────────────  │
│  "Compare to last year" (289x)     847 high-quality examples ready     │
│  "All clients with X" (156x)       Next training: Jan 15               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| **Data Capture** | |
| `AIInteraction` model | Enhanced capture: query/response/outcome with 40+ metadata fields |
| Chat instrumentation | Log all client-context chat interactions |
| Insight instrumentation | Log insight generation and actions |
| Feedback UI | Thumbs up/down on AI responses |
| Query auto-classification | COMPLIANCE, STRATEGY, DATA_QUALITY, WORKFLOW auto-tagging |
| **Storage & Infrastructure** | |
| PostgreSQL tables | `ai_interactions`, `query_patterns`, `knowledge_gaps`, `fine_tuning_*` |
| Qdrant collection | `ai_queries` for semantic clustering and similarity search |
| S3 buckets | `/raw-interactions/`, `/training-datasets/`, `/analytics-exports/` |
| Redis metrics | Real-time counters with TTL (prefix: `ai:metrics:`) |
| **Analysis Pipeline** | |
| `QueryPattern` model | Aggregated patterns with occurrence counts, satisfaction |
| `KnowledgeGap` model | Low-satisfaction topics with priority scoring |
| Pattern clustering job | Daily job to identify query patterns |
| Satisfaction analysis | Weekly report on response quality |
| Feature discovery | Identify repeated manual requests |
| **Fine-Tuning Pipeline** | |
| `FineTuningCandidate` model | Auto-identified high-quality interactions (daily job) |
| `FineTuningExample` model | Human-curated, approved examples |
| `FineTuningDataset` model | Versioned JSONL exports for training |
| Candidate auto-scoring | Quality score from feedback, actions, follow-ups |
| Curation admin UI | Review candidates, edit responses, approve examples |
| JSONL export service | Generate train.jsonl + eval.jsonl with category balancing |
| **Admin & Privacy** | |
| Admin intelligence dashboard | View patterns, gaps, opportunities, fine-tuning status |
| Anonymization pipeline | Remove PII before analysis/training |
| `TenantAISettings` model | Consent preferences, retention settings |
| Tenant opt-out | Allow tenants to exclude from training data

**Storage Architecture**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATA STORAGE LOCATIONS                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  PostgreSQL (modules/ai_learning/)                                      │
│  ├── ai_interactions      → Structured metadata, outcomes, feedback     │
│  ├── query_patterns       → Aggregated patterns, occurrence counts      │
│  ├── knowledge_gaps       → Low-satisfaction topics, resolution status  │
│  ├── fine_tuning_*        → Candidates, examples, dataset versions      │
│  └── tenant_ai_settings   → Consent, retention preferences              │
│                                                                         │
│  Qdrant (collection: ai_queries)                                        │
│  └── Query embeddings for semantic clustering & similarity search       │
│                                                                         │
│  S3/MinIO (bucket: ai-learning-archive)                                 │
│  ├── /raw-interactions/   → Full request/response JSON logs             │
│  ├── /training-datasets/  → JSONL files for fine-tuning                 │
│  └── /analytics-exports/  → Aggregated analytics (parquet)              │
│                                                                         │
│  Redis (prefix: ai:metrics:)                                            │
│  └── Real-time counters, rolling averages (TTL auto-expire)             │
│                                                                         │
│  KEY INSIGHT: JSONL is an EXPORT format. Store flexibly in              │
│  PostgreSQL/S3, generate JSONL when ready to fine-tune.                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Fine-Tuning Pipeline**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│            4-STAGE FINE-TUNING PIPELINE: Raw → JSONL Export             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  STAGE 1: RAW CAPTURE (AIInteraction)                                   │
│  └── Every AI interaction → PostgreSQL + S3 (full context)              │
│                                                                         │
│  STAGE 2: AUTO-FILTER (FineTuningCandidate) - Daily job                 │
│  └── Quality signals: positive feedback, action taken, no follow-up    │
│  └── Auto-score interactions → Mark as candidates                       │
│                                                                         │
│  STAGE 3: HUMAN CURATION (FineTuningExample)                            │
│  └── Admin reviews candidates, edits if needed                          │
│  └── Sets quality score, marks ready for export                         │
│                                                                         │
│  STAGE 4: JSONL EXPORT (FineTuningDataset)                              │
│  └── Generate train.jsonl + eval.jsonl (90/10 split)                    │
│  └── Category-balanced sampling                                         │
│  └── Upload to S3: /training-datasets/{version}/                        │
│  └── Track: version, example count, category distribution               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Data Models**:

```python
class AIInteraction(Base):
    """Enhanced interaction capture with full metadata for learning."""
    id: UUID
    tenant_id: UUID
    user_id: UUID
    client_id: UUID | None
    conversation_id: UUID | None

    # === QUERY CONTEXT ===
    query_text: str
    query_hash: str  # SHA-256 for deduplication
    query_tokens: int
    query_embedding_id: str | None  # Qdrant reference

    # Auto-classification
    category: str  # COMPLIANCE, STRATEGY, DATA_QUALITY, WORKFLOW
    subcategory: str | None  # GST, PAYG, SUPER, etc.
    intent: str | None  # QUESTION, COMMAND, CLARIFICATION
    complexity_score: float | None

    # Session context
    session_type: str  # CHAT, BAS_PREP, INSIGHT_REVIEW, MAGIC_ZONE
    session_id: UUID | None
    queries_in_session: int
    previous_interaction_id: UUID | None

    # Client context (denormalized for analysis)
    client_revenue_band: str | None
    client_industry: str | None
    client_complexity_score: float | None

    # Timing context
    days_to_bas_deadline: int | None
    is_eofy_period: bool
    hour_of_day: int | None
    day_of_week: int | None

    # === RESPONSE CONTEXT ===
    response_text: str | None
    response_tokens: int | None
    response_latency_ms: int
    model_version: str

    # RAG quality
    sources_count: int | None
    sources_avg_score: float | None
    source_types: list[str] | None  # ["kb", "ato", "custom"]

    # Agent details
    perspectives_used: list[str] | None
    agents_invoked: list[str] | None
    tool_calls: list[dict] | None

    # Confidence
    confidence_score: float | None
    escalation_required: bool
    escalation_reason: str | None

    # === OUTCOME TRACKING ===
    # Explicit feedback
    feedback_rating: int | None  # 1 (down) or 5 (up)
    feedback_comment: str | None
    feedback_at: datetime | None

    # Implicit signals
    had_follow_up: bool | None
    follow_up_interaction_id: UUID | None
    time_reading_ms: int | None
    copied_response: bool | None

    # Action correlation
    action_type: str | None  # created_insight, created_task, etc.
    action_entity_id: UUID | None
    time_to_action_seconds: int | None
    action_modified: bool | None

    # === PRIVACY ===
    consent_training: bool  # Tenant opted in
    anonymized: bool
    raw_log_s3_key: str | None

    created_at: datetime


class FineTuningCandidate(Base):
    """Auto-identified high-quality interactions (daily job)."""
    id: UUID
    interaction_id: UUID  # FK → AIInteraction

    # Quality signals (auto-calculated)
    quality_score: float  # 0-1 composite
    has_positive_feedback: bool
    had_action_taken: bool
    no_follow_up_needed: bool
    confidence_was_high: bool

    # Category for balanced sampling
    category: str
    subcategory: str | None

    # Curation status
    status: str  # PENDING, APPROVED, REJECTED, EXPORTED
    created_at: datetime


class FineTuningExample(Base):
    """Human-curated, approved examples ready for training."""
    id: UUID
    interaction_id: UUID
    candidate_id: UUID

    # Training data (may be edited from original)
    system_prompt: str
    user_message: str  # Anonymized query
    ideal_response: str  # Original or improved response

    # Was it modified?
    response_was_edited: bool
    original_response: str | None

    # Quality assessment
    quality_score: int  # 1-5 human rating
    quality_notes: str | None

    # Curation tracking
    curated_by: UUID
    curated_at: datetime

    # Export tracking
    exported_in_version: str | None
    exported_at: datetime | None

    category: str
    subcategory: str | None


class FineTuningDataset(Base):
    """Tracks exported JSONL dataset versions."""
    id: UUID
    version: str  # v1.0.0

    # S3 locations (JSONL files)
    train_s3_key: str  # /training-datasets/v1.0.0/train.jsonl
    eval_s3_key: str   # /training-datasets/v1.0.0/eval.jsonl

    # Stats
    total_examples: int
    train_examples: int
    eval_examples: int
    category_distribution: dict  # {"COMPLIANCE": 450, ...}

    # Date range
    source_date_start: date
    source_date_end: date

    # Training status
    training_started_at: datetime | None
    training_completed_at: datetime | None
    model_id: str | None  # Resulting fine-tuned model

    created_at: datetime
    created_by: UUID


class QueryPattern(Base):
    """Aggregated patterns from interactions."""
    id: UUID
    canonical_query: str
    pattern_embedding_id: str
    category: str
    occurrence_count: int
    avg_satisfaction_score: float
    follow_up_rate: float
    suggested_kb_article: str | None
    suggested_feature: str | None
    auto_response_candidate: bool


class KnowledgeGap(Base):
    """Identified gaps needing attention."""
    id: UUID
    topic: str
    sample_queries: list[str]
    interaction_count: int
    avg_satisfaction: float
    status: str  # IDENTIFIED, IN_PROGRESS, RESOLVED
    resolution_type: str | None  # KB_ARTICLE, FEATURE, MODEL_UPDATE
    priority_score: float


class TenantAISettings(Base):
    """Tenant-level AI learning preferences."""
    id: UUID
    tenant_id: UUID

    # Consent
    contribute_to_training: bool  # Default True
    allow_pattern_analysis: bool
    allow_anonymized_benchmarking: bool

    # Retention
    raw_log_retention_days: int  # Default 730 (2 years)
```

### Phase E.6 Summary

| Spec | Name | Priority | Effort | Dependencies |
|------|------|----------|--------|--------------|
| 029 | AI Interaction Capture & Learning | P1 | 1.5 weeks | Phase E.5 ✓ |

**Phase E.6 Exit Criteria**:
- [ ] 100% of AI interactions captured with full context
- [ ] Query auto-classification working (>90% accuracy)
- [ ] Feedback UI (thumbs up/down) on all AI responses
- [ ] Weekly pattern analysis job running
- [ ] Admin dashboard showing intelligence reports
- [ ] Knowledge gaps being identified and actioned
- [ ] First fine-tuning dataset curated (1000+ examples)
- [ ] Privacy controls (anonymization, opt-out) working

**Milestone**: AI Learning Active (every interaction makes the product smarter)

**Competitive Moat Timeline**:
- Year 1: 100K interactions → Basic patterns, first fine-tuned model
- Year 2: 500K interactions → Reliable predictions, 15% better satisfaction
- Year 3: 1M+ interactions → Industry-leading AI, unreplicable advantage

---

## Phase F: Business Owner Engagement + ClientChase

**Goal**: Client portal for B2B2C distribution + automated document collection

**Why After Phase E**:
- Client portal is a "Professional" tier feature
- Need gating in place before building gated features
- Portal benefits from enhanced data (Reports, Cash flow)
- Better data = better client-facing insights
- Portal is the distribution channel for future B2C
- **ClientChase integration**: Portal becomes the vehicle for document requests

**Reference**: `/planning/roadmap/business-owner-app-strategy.md`

**NEW - ClientChase Integration**:
The client portal's "job to be done" is answering accountant requests. Instead of building a passive viewing tool, we build an active engagement system where:
1. Accountants REQUEST documents/info through Clairo
2. Clients RECEIVE requests via portal (push notifications, email)
3. Clients RESPOND directly in portal (camera capture, upload, text)
4. Accountants TRACK response rates and chase slow responders

```
CLIENTCHASE VIRTUOUS LOOP
═══════════════════════════════════════════════════════════════════

ACCOUNTANT SIDE                         CLIENT SIDE
(Request & Track)                       (Receive & Respond)
─────────────────                       ───────────────────

┌─────────────────────────┐            ┌─────────────────────────┐
│  📋 REQUEST DOCUMENTS    │            │  📱 RECEIVE REQUEST      │
│                         │            │                         │
│  "Need Q2 bank state-   │──────────▶ │  Push notification:     │
│   ments for 12 clients" │            │  "Your accountant needs │
│                         │            │   bank statements"      │
│  [Select Clients]       │            │                         │
│  [Choose Template]      │            │  [View Request]         │
│  [Set Due Date]         │            │                         │
└─────────────────────────┘            └─────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────┐            ┌─────────────────────────┐
│  📊 TRACK RESPONSES      │            │  📸 RESPOND IN PORTAL    │
│                         │            │                         │
│  ┌───────────────────┐  │            │  [Take Photo 📷]        │
│  │ ✅ 8 Responded    │  │◀────────── │  [Upload File 📎]       │
│  │ ⏳ 3 Pending      │  │            │  [Add Note 💬]          │
│  │ 🔴 1 Overdue      │  │            │                         │
│  └───────────────────┘  │            │  "Here's my ANZ state-  │
│                         │            │   ment for Oct-Dec"     │
│  [Auto-Chase Overdue]   │            │                         │
└─────────────────────────┘            └─────────────────────────┘
                                                  │
┌─────────────────────────┐                       │
│  📥 RECEIVE & PROCESS    │◀──────────────────────┘
│                         │
│  Documents auto-filed   │
│  to client folder       │
│                         │
│  AI extracts metadata   │
│  (date range, account)  │
└─────────────────────────┘
```

### Spec 030: Client Portal Foundation + Document Requests

```
CLIENT PORTAL ARCHITECTURE (ENHANCED WITH CLIENTCHASE)
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    ACCOUNTANT PORTAL                            │
│                    (Paying Customer)                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Client Management                                       │   │
│  │  └── Invite Client → Email with magic link              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  📋 DOCUMENT REQUEST WORKFLOW (ClientChase)              │   │
│  │                                                          │   │
│  │  Templates:           Request to:        Track:          │   │
│  │  • Bank statements    • Single client    • Response rate │   │
│  │  • BAS workpapers     • Multiple clients • Time to respond│   │
│  │  • Source docs        • All clients      • Auto-reminders│   │
│  │  • Custom request                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Magic Link + Request Notification
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENT PORTAL                                │
│                    (Business Owner - FREE)                      │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Dashboard  │  │  🔴 Requests│  │  Documents  │            │
│  │             │  │   (3 new)   │  │             │            │
│  │  BAS status │  │  Respond to │  │  Upload     │            │
│  │  Key metrics│  │  requests   │  │  receipts   │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  Messages   │  │  BAS Review │  │   Learn     │            │
│  │             │  │             │  │             │            │
│  │  Chat with  │  │  Review &   │  │  Knowledge  │            │
│  │  accountant │  │  approve    │  │  base       │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Client invitation | Accountant invites client via email |
| Magic link auth | Frictionless authentication |
| Client dashboard | BAS status, action items, key metrics |
| Action item responses | Respond to document requests, queries |
| Document upload | Drag-drop, mobile camera capture |
| **Document request templates** | Pre-built templates (bank statements, BAS docs, custom) |
| **Bulk request workflow** | Send same request to multiple clients |
| **Request tracking UI** | Status dashboard for pending requests |
| **Auto-filing** | Uploaded docs auto-organized by client/period |

**Data Model Addition**:
```python
class DocumentRequest(Base):
    id: UUID
    tenant_id: UUID
    client_id: UUID
    template_id: UUID | None

    # Request details
    title: str
    description: str
    due_date: date | None
    priority: RequestPriority  # LOW, NORMAL, HIGH, URGENT

    # Tracking
    status: RequestStatus  # PENDING, VIEWED, RESPONDED, COMPLETE
    sent_at: datetime
    viewed_at: datetime | None
    responded_at: datetime | None

    # Response
    response_note: str | None
    documents: list[Document]  # FK to documents table

    # Reminders
    reminder_count: int
    last_reminder_at: datetime | None
    auto_remind: bool
```

### Spec 031: Messaging & Approvals + Request Conversations

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Contextual messaging | Chat attached to action items, BAS periods |
| BAS review | Client reviews summary before approval |
| Approval workflow | Digital approval with audit trail |
| Notifications | Email/push for new messages, items |
| **Request-context chat** | Messages attached to specific document requests |
| **Clarification flow** | Client can ask "What exactly do you need?" |
| **Request amendments** | Accountant can modify request after client questions |
| **Completion confirmation** | Accountant confirms receipt, closes request |

### Spec 032: PWA & Mobile + Document Capture

**Deliverables**:

| Component | Description |
|-----------|-------------|
| PWA manifest | Installable web app |
| Push notifications | Real-time alerts |
| Offline support | Queue uploads when offline |
| Camera integration | Receipt capture |
| **Push for new requests** | Immediate notification when accountant sends request |
| **Camera-first upload** | Open camera directly from request for quick capture |
| **Multi-page scanning** | Capture multi-page documents as single PDF |
| **Offline request queue** | View requests and queue responses when offline |

### Spec 033: Client Analytics + Response Tracking

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Portal engagement | Track client logins, actions |
| Response rates | Action item completion metrics |
| Adoption dashboard | For accountants to see client engagement |
| **Response time analytics** | Average time to respond per client |
| **Slow responder alerts** | Flag clients who consistently delay |
| **Chase effectiveness** | Track which reminder strategies work |
| **Client responsiveness score** | Scoring based on response patterns |

**Analytics Dashboard Addition**:
```
CLIENT RESPONSIVENESS REPORT
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│  DOCUMENT REQUEST PERFORMANCE                    Last 90 days   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Response Metrics:                                              │
│  ├── Avg response time: 2.3 days                               │
│  ├── Response rate: 87%                                        │
│  └── Requests requiring chase: 24%                             │
│                                                                 │
│  SLOW RESPONDERS (avg > 5 days)           ACTION NEEDED        │
│  ──────────────────────────────────────────────────────────────│
│  🔴 Smith Plumbing - 8.2 days avg         [Send Reminder]      │
│  🔴 ABC Retail - 6.4 days avg             [Send Reminder]      │
│  🟡 Jones Consulting - 5.1 days avg       [Monitor]            │
│                                                                 │
│  STAR RESPONDERS (avg < 1 day)                                 │
│  ──────────────────────────────────────────────────────────────│
│  🌟 Tech Startup Co - 0.5 days avg                             │
│  🌟 Cafe Bloom - 0.8 days avg                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Phase F Summary

| Spec | Name | Priority | Effort | Dependencies | Status |
|------|------|----------|--------|--------------|--------|
| 030 | Client Portal + Document Requests | P0 | 2 weeks | Phase E.6 ✓ | NOT_STARTED |
| 031 | Messaging & Request Conversations | P1 | 1 week | 030 | NOT_STARTED |
| 032 | PWA & Document Capture | P1 | 1 week | 030 | ✅ COMPLETE |
| 033 | Analytics & Response Tracking | P2 | 3 days | 030 | NOT_STARTED |

**Phase F Exit Criteria**:
- [ ] Accountants can invite clients to portal
- [ ] Clients can view BAS status and respond to items
- [ ] Document upload working from mobile
- [ ] BAS approval workflow complete
- [ ] >40% client activation rate
- [ ] **ClientChase**: Document request templates working
- [ ] **ClientChase**: Bulk requests to multiple clients
- [ ] **ClientChase**: Response tracking dashboard live
- [ ] **ClientChase**: Auto-reminders sending to slow responders
- [ ] **ClientChase**: >70% response rate on document requests

**Milestone**: Portal Launch + ClientChase (B2B2C distribution + document automation)

---

## Phase G: Growth & Scale

**Goal**: Enterprise features and B2C self-serve

**Timing**: Only after Phase F validation

### Spec 034: B2C Self-Serve

**Only build if**:
- Client portal has 10,000+ active users
- NPS > 50 from portal users
- >10% express interest in self-serve

```
B2C CONVERSION PATH
═══════════════════════════════════════════════════════════════════

Portal User (Free)                    Self-Serve Customer ($29/mo)
────────────────────────────────────  ─────────────────────────────
• View-only BAS status                • AI-guided BAS prep
• Respond to accountant requests      • Direct question answering
• Document upload                     • Self-service insights
• No direct lodgement                 • No lodgement (or partner)
```

### Spec 035: White-Labeling (Enterprise)

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Custom branding | Logo, colors, domain |
| Client portal theming | Per-accountant branding |
| Email customization | From address, templates |

### Spec 036: API Access (Growth Tier)

**Deliverables**:

| Component | Description |
|-----------|-------------|
| REST API | Programmatic access to BAS data |
| Webhooks | Event notifications |
| API keys | Per-tenant authentication |
| Rate limiting | Tier-based quotas |

### Spec 037: Advanced Integrations

**Deliverables**:

| Component | Description |
|-----------|-------------|
| MYOB integration | Second accounting platform |
| Practice management | Karbon, XPM integration |
| Document management | FYI Docs, SuiteFiles |

### Spec 038: System Observability & APM

**Goal**: Proactive visibility into system health, performance, and AI costs

**Reference**: `/planning/analysis/observability-analytics-architecture.md`

```
OBSERVABILITY STACK
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                      DATA COLLECTION                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Backend (FastAPI)              Frontend (Next.js)              │
│  ├── OpenTelemetry SDK          ├── Sentry SDK                  │
│  ├── Sentry integration         ├── Error boundary              │
│  ├── AI cost logging            └── Performance metrics         │
│  └── Health endpoints                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PLATFORMS                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Sentry              Grafana Cloud         Custom Dashboards    │
│  ├── Error tracking  ├── API latency       ├── AI cost/tenant   │
│  ├── Alerting        ├── DB performance    ├── Token usage      │
│  └── Profiling       ├── Celery jobs       └── Margin analysis  │
│                      └── Alerting                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| OpenTelemetry setup | Traces, metrics, logs instrumentation |
| Sentry integration | Error tracking with alerting |
| API performance dashboard | Latency p50/p95/p99 by endpoint |
| Database query monitoring | Slow query identification |
| AI cost dashboard | Per-tenant, per-feature cost tracking |
| Celery job monitoring | Queue depth, failure rates |
| Health check endpoints | `/health`, `/ready` for k8s |
| Alerting rules | Slack/email alerts for anomalies |
| SLA dashboard | Uptime, response times, error rates |

### Spec 039: Product Analytics & Engagement

**Goal**: Understand user behavior, identify friction, enable data-driven decisions

**Reference**: `/planning/analysis/observability-analytics-architecture.md`

```
PRODUCT ANALYTICS STACK
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│  EVENT TRACKING (PostHog)                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Onboarding:            BAS Prep:             AI Usage:         │
│  ├── Started            ├── Started           ├── Chat opened   │
│  ├── Step completed     ├── Checklist done    ├── Query sent    │
│  ├── Completed          ├── Completed         ├── Feedback      │
│  └── Abandoned          └── Lodged            └── Action taken  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  KEY FUNNELS                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ONBOARDING FUNNEL            BAS PREP FUNNEL                   │
│  100% → Signup                100% → Started                    │
│   85% → Connect Xero           95% → Quality check              │
│   76% → First sync             92% → Issues resolved            │
│   70% → View insight           90% → Completed                  │
│   65% → Take action                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STARTUP KPI DASHBOARD                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DAU: 67  │  WAU: 89  │  Retention W4: 72%  │  NPS: 48         │
│                                                                 │
│  MRR: $12,450  │  ARPU: $142  │  AI Cost/User: $9.52            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Deliverables**:

| Component | Description |
|-----------|-------------|
| PostHog integration | Frontend + backend event tracking |
| Event taxonomy | Standardized naming (`feature.action.detail`) |
| Core funnels | Onboarding, BAS prep, insight→action |
| Feature adoption tracking | Which features are used? By whom? |
| Session recordings | Opt-in, key flows only |
| Feature flags | A/B testing infrastructure |
| Startup KPI dashboard | DAU, WAU, retention, activation |
| Cohort analysis | By tier, client count, tenure |
| Churn indicators | Early warning signals |

### Spec 041: A2UI Agent-Driven Interfaces

**Goal**: Enable AI agents to generate dynamic, context-aware native UIs

**Reference**: `/planning/analysis/a2ui-agent-driven-interfaces.md`

```
A2UI ARCHITECTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT: Static UI                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AI Agent ──► Text/Data ──► Pre-built React Components          │
│                                                                 │
│  Problem: Must build every possible screen ahead of time        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WITH A2UI: Dynamic UI                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AI Agent ──► A2UI JSON ──► Component Catalog ──► Native UI     │
│                                                                 │
│  ┌─────────────────────┐   ┌─────────────────────────────────┐ │
│  │ Agent decides:      │   │ Renderer maps to:               │ │
│  │ - What to show      │   │ - alertCard → Alert             │ │
│  │ - How to show it    │   │ - dataTable → DataTable         │ │
│  │ - Based on context  │   │ - lineChart → LineChart         │ │
│  └─────────────────────┘   └─────────────────────────────────┘ │
│                                                                 │
│  Benefit: Agent generates UI tailored to each situation         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Use Cases**:

| Feature | Current | With A2UI |
|---------|---------|-----------|
| AI Insights | Fixed card layout | Dynamic charts, tables, actions based on findings |
| Document Requests | Static form | Camera-first on mobile, file picker on desktop |
| Dashboard | Same layout for all | Personalized by time, workload, priorities |
| BAS Review | All fields shown | Highlights only anomalies needing attention |

**Deliverables**:

| Component | Description |
|-----------|-------------|
| A2UI renderer | Map abstract components to shadcn/ui |
| Component catalog | 30-40 reusable UI components |
| Agent UI generation | Agents output A2UI alongside text |
| Insight UI | Dynamic insight presentation |
| Document request UI | Context-aware capture forms |
| Dashboard personalization | Time/workload-based layouts |

**Technical Approach**:

- **No schema changes**: A2UI is presentation-only
- **Minimal API changes**: Add `/ui` endpoints alongside existing
- **Additive integration**: Existing UIs continue working

### Phase G Summary

| Spec | Name | Priority | Effort | Dependencies |
|------|------|----------|--------|--------------|
| 034 | B2C Self-Serve | P1 | 2 weeks | Phase F validation |
| 035 | White-Labeling | P2 | 1 week | Phase F ✓ |
| 036 | API Access | P2 | 1 week | Phase D ✓ |
| 037 | Advanced Integrations | P3 | 2+ weeks | Phase F ✓ |
| 038 | System Observability & APM | P1 | 1 week | Phase D ✓ |
| 039 | Product Analytics & Engagement | P1 | 1 week | 038 |
| 041 | A2UI Agent-Driven Interfaces | P2 | 5 weeks | Phase C ✓, 038 |

**Phase G Exit Criteria**:
- [ ] B2C tier converting portal users (if validated)
- [ ] Enterprise customers on white-label
- [ ] API being used by Growth tier customers
- [ ] Full observability stack deployed
- [ ] Product analytics tracking all key funnels
- [ ] AI cost per tenant visible in admin dashboard
- [x] A2UI renderer integrated for AI insights ✅ (moved to Spec 033, complete)

**Milestone**: Enterprise & B2C Ready + Full Observability

---

## Phase H: Polish & Operations

**Goal**: Production hardening, deferred features

### Spec 010: Review & Approval (Rebuild)

**Previously deferred**: Important but not differentiating

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Submit for review | Preparer → Reviewer workflow |
| Review queue | Pending BAS sessions |
| Approval workflow | Approve with audit trail |
| Request changes | Send back with comments |
| Multi-level approval | Junior → Senior → Partner |

### Spec 040: Production Hardening

**Deliverables**:

| Component | Description |
|-----------|-------------|
| Security audit | Penetration testing |
| Compliance | SOC 2 preparation |
| Disaster recovery | Backup, restore procedures |
| Load testing | Performance under scale |
| Documentation | Runbooks, incident response |

**Note**: Basic error monitoring and APM moved to Spec 038 (Phase G).

---

## Spec Registry

### Status Legend
- `COMPLETE` - Done and validated
- `NOT_STARTED` - Not yet begun
- `IMPLEMENTING` - In progress

### Phase A: Foundation ✅ COMPLETE

| Spec | Name | Status |
|------|------|--------|
| 001 | Project Scaffolding | `COMPLETE` |
| 002 | Auth & Multi-tenancy | `COMPLETE` |
| 003 | Xero OAuth | `COMPLETE` |
| 004 | Xero Data Sync | `COMPLETE` |
| 005 | Single Client View | `COMPLETE` |
| 006 | Multi-Client Dashboard | `COMPLETE` |
| 007 | Xero Payroll Sync | `COMPLETE` |
| 008 | Data Quality Scoring | `COMPLETE` |
| 009 | BAS Prep Workflow | `COMPLETE` |
| 011 | Interim Lodgement | `COMPLETE` |

### Phase B: AI Core ✅ COMPLETE

| Spec | Name | Status |
|------|------|--------|
| 012 | Knowledge Base + RAG | `COMPLETE` |
| 013 | Client-Context Chat | `COMPLETE` |
| 014 | Multi-Agent Framework | `COMPLETE` |

### Phase C: Proactive Intelligence ✅ COMPLETE

| Spec | Name | Status |
|------|------|--------|
| 016 | Insight Engine | `COMPLETE` |
| 016b | Action Items | `COMPLETE` |
| 017 | Trigger System | `COMPLETE` |
| 018 | Magic Zone Insights | `COMPLETE` |

### Phase D: Monetization Foundation ✅ COMPLETE

| Spec | Name | Status | Dependencies |
|------|------|--------|--------------|
| 019 | Subscription & Feature Gating | `COMPLETE` | Phase C ✓ |
| 020 | Usage Tracking & Limits | `COMPLETE` | 019 ✓ |
| 021 | Onboarding Flow | `COMPLETE` | 019 ✓, 020 ✓ |
| 022 | Admin Dashboard (Internal) | `COMPLETE` | 019 ✓, 020 ✓ |

### Phase E: Data Intelligence ✅ COMPLETE

| Spec | Name | Status | Dependencies |
|------|------|--------|--------------|
| 023 | Xero Reports API | `COMPLETE` ✅ | Phase D ✓ |
| 024 | Credit Notes, Payments & Journals | `COMPLETE` ✅ | 023 ✓ |
| 025 | Fixed Assets & Enhanced Analysis | `COMPLETE` ✅ | 023 ✓, 024 ✓ |

### Phase E.5: ATOtrack

| Spec | Name | Status | Dependencies |
|------|------|--------|--------------|
| 026 | Email Integration & OAuth | `NOT_STARTED` | Phase E ✓ |
| 027 | ATO Correspondence Parsing | `NOT_STARTED` | 026 |
| 028 | ATOtrack Workflow Integration | `NOT_STARTED` | 027 |

### Phase E.6: AI Intelligence Flywheel ← NEW

| Spec | Name | Status | Dependencies |
|------|------|--------|--------------|
| 029 | AI Interaction Capture & Learning | `NOT_STARTED` | Phase E.5 ✓ |

### Phase F: Business Owner Engagement + ClientChase

| Spec | Name | Status | Dependencies |
|------|------|--------|--------------|
| 030 | Client Portal + Document Requests | `NOT_STARTED` | Phase E.6 ✓ |
| 031 | Messaging & Request Conversations | `NOT_STARTED` | 030 |
| 032 | PWA & Document Capture | `COMPLETE` ✅ | 030 |
| 033 | A2UI Agent-Driven Interfaces | `COMPLETE` ✅ | Phase C ✓ |

### Phase G: Growth & Scale

| Spec | Name | Status | Dependencies |
|------|------|--------|--------------|
| 034 | B2C Self-Serve | `NOT_STARTED` | Phase F validation |
| 035 | White-Labeling | `NOT_STARTED` | Phase F ✓ |
| 036 | API Access | `NOT_STARTED` | Phase D ✓ |
| 037 | Advanced Integrations | `NOT_STARTED` | Phase F ✓ |
| 038 | System Observability & APM | `NOT_STARTED` | Phase D ✓ |
| 039 | Product Analytics & Engagement | `NOT_STARTED` | 038 |
| 041 | (Merged into Spec 033) | - | - |

### Phase H: Polish & Operations

| Spec | Name | Status | Dependencies |
|------|------|--------|--------------|
| 042 | CI/CD Pipeline & Production Deployment | `NOT_STARTED` | Phase D ✓ |
| 010 | Review & Approval (Rebuild) | `NOT_STARTED` | Phase G ✓ |
| 040 | Production Hardening | `NOT_STARTED` | 038, 039, 042 ✓ |

---

## Architecture Impact Assessment

### Feature Gating Pattern

**Backend Pattern**:
```python
# Decorator-based gating
@require_feature("custom_triggers")
async def create_trigger(request: Request, ...):
    # Only runs if tenant has feature access
    ...

# Manual check where needed
if not tenant_has_feature(tenant, "ai_insights_full"):
    raise HTTPException(403, "Upgrade to Professional for full AI insights")
```

**Frontend Pattern**:
```tsx
// Hook-based gating
const { tier, canAccess, limits, usage } = useTier();

// Conditional rendering
{canAccess("custom_triggers") ? (
  <TriggerManager />
) : (
  <UpgradePrompt
    feature="Custom Triggers"
    requiredTier="professional"
  />
)}
```

### Retrofitting Existing Features

| Feature | Current | After Gating |
|---------|---------|--------------|
| AI Insights | Always on | Starter: basic, Pro+: full |
| Triggers | Always on | Starter: disabled, Pro+: enabled |
| Knowledge Base | Always on | Starter: disabled, Pro+: enabled |
| Client Portal | Not built | Pro+: enabled |
| API Access | Not built | Growth+: enabled |

**Retrofitting Effort**: ~2-3 days to wrap existing features with gating checks

---

## Success Metrics by Phase

### Phase D Metrics

| Metric | Target |
|--------|--------|
| Signup → Paid conversion | >20% |
| Stripe integration uptime | 99.9% |
| Feature gating accuracy | 100% (no leaks) |
| Checkout completion | >60% |

### Phase E Metrics

| Metric | Target |
|--------|--------|
| Client invitation rate | >50% of clients invited |
| Client activation rate | >40% of invited |
| Document upload success | >95% |
| BAS approval rate | >90% |

### Phase F Metrics

| Metric | Target |
|--------|--------|
| B2C conversion (if built) | >5% of portal users |
| API adoption (Growth tier) | >30% of Growth customers |
| White-label retention | >95% annual |

---

## Current Focus

```
╔═══════════════════════════════════════════════════════════════════╗
║  NEXT SPEC: 026-email-integration-oauth                           ║
╠═══════════════════════════════════════════════════════════════════╣
║  Phase: E.5 (ATOtrack)                                            ║
║  Status: NOT_STARTED → Needs spec document                        ║
║  Previous: 025 (Fixed Assets & Analysis) - COMPLETE               ║
║                                                                   ║
║  EXPECTED DELIVERABLES:                                           ║
║  • Gmail OAuth integration (Google Workspace)                     ║
║  • Microsoft 365 / Outlook OAuth integration                      ║
║  • Email sync service (initial + incremental)                     ║
║  • Email forwarding fallback option                               ║
║  • Token refresh and connection management                        ║
║                                                                   ║
║  DISRUPTION: Medium (new integration pattern)                     ║
║  EFFORT: ~1 week                                                  ║
║                                                                   ║
║  MILESTONE: Phase E Complete ✅ → Phase E.5 begins                ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-04 | **v5.9.0**: Added Spec 042 (CI/CD Pipeline & Production Deployment) |
| 2026-01-04 | New spec for automated testing, deployment pipelines, and production readiness |
| 2026-01-04 | Targets: Railway (backend), Vercel (frontend), GitHub Actions (CI/CD) |
| 2026-01-03 | **v5.8.0**: Spec 032 (PWA & Mobile Document Capture) COMPLETE |
| 2026-01-03 | PWA: Service worker, manifest, install prompt for client portal |
| 2026-01-03 | Push Notifications: VAPID keys, web push, notification permissions |
| 2026-01-03 | Offline Support: IndexedDB caching, stale-while-revalidate strategy |
| 2026-01-03 | Camera Capture: Image compression, EXIF handling, quality checks |
| 2026-01-03 | Multi-Page Scanning: Page capture, drag-drop reordering, PDF generation |
| 2026-01-03 | Offline Queue: Background sync, exponential backoff retry |
| 2026-01-03 | Biometric Auth: WebAuthn, Face ID/Touch ID support |
| 2026-01-03 | Settings & Analytics: Notification settings, storage management, PWA events |
| 2026-01-02 | **v5.7.0**: Spec 033 (A2UI Agent-Driven Interfaces) COMPLETE |
| 2026-01-02 | LLM-driven A2UI: AI dynamically decides what UI components to show |
| 2026-01-02 | Component catalog: 31 components (stat_card, alert, charts, tables, actions) |
| 2026-01-02 | Structured output: LLM outputs ```a2ui JSON blocks alongside text responses |
| 2026-01-02 | Integrated with multi-perspective agent system for rich insight rendering |
| 2026-01-02 | **v5.6.0**: Phase E Complete - Spec 025 (Fixed Assets & Enhanced Analysis) done |
| 2026-01-02 | Fixed Assets: 8 user stories, 72 tasks - assets, purchase orders, repeating invoices, tracking categories, quotes |
| 2026-01-02 | AI tools: Instant write-off detection, depreciation analysis, CapEx analysis |
| 2026-01-02 | 27 new API endpoints, 6 new database models, client navigation layout |
| 2026-01-02 | Phase E milestone achieved: Enhanced AI Insights |
| 2026-01-02 | Next: Phase E.5 (ATOtrack) - Spec 026 (Email Integration & OAuth) |
| 2026-01-01 | **v5.4.0**: Phase D Complete - Spec 022 (Admin Dashboard) done |
| 2026-01-01 | Admin dashboard: customer list, revenue metrics, tier changes, credits |
| 2026-01-01 | Usage analytics: platform usage, top users by metric |
| 2026-01-01 | Feature flag overrides per tenant |
| 2026-01-02 | **Spec 024 COMPLETE**: Credit Notes, Payments & Journals - 7 user stories, full GST calculation integration |
| 2026-01-02 | Next: Spec 025 (Fixed Assets & Enhanced Analysis) |
| 2026-01-01 | Phase D milestone achieved: Ready for Pilot Launch |
| 2026-01-01 | **Spec 023 COMPLETE**: Xero Reports API - all 6 report types with background sync |
| 2026-01-01 | Next: Spec 024 (Credit Notes, Payments & Journals) |
| 2026-01-01 | **v5.3.0**: Added Observability & Analytics specs to Phase G |
| 2026-01-01 | New Spec 038: System Observability & APM (Sentry, Grafana, OTel) |
| 2026-01-01 | New Spec 039: Product Analytics & Engagement (PostHog, funnels) |
| 2026-01-01 | Renumbered: Phase H (038 → 040) |
| 2026-01-01 | Added lightweight instrumentation (Sentry, PostHog, AI cost logging) |
| 2026-01-01 | Reference: `/planning/analysis/observability-analytics-architecture.md` |
| 2026-01-01 | **v5.2.1**: Enhanced Spec 029 with fine-tuning pipeline architecture |
| 2026-01-01 | Added: 4-stage pipeline (Raw → Candidates → Examples → JSONL Export) |
| 2026-01-01 | Added: Storage architecture (PostgreSQL, Qdrant, S3, Redis) |
| 2026-01-01 | Added: FineTuningCandidate, FineTuningExample, FineTuningDataset models |
| 2026-01-01 | Enhanced: AIInteraction model with 40+ metadata fields |
| 2026-01-01 | **v5.2**: Added Phase E.6 - AI Intelligence Flywheel |
| 2026-01-01 | New Spec 029: AI Interaction Capture & Learning |
| 2026-01-01 | Renumbered: Phase F (030-033), Phase G (034-037), Phase H (038) |
| 2026-01-01 | Reference: `/planning/analysis/ai-intelligence-flywheel.md` |
| 2025-12-31 | **v5.1**: ClientChase integration into Phase F |
| 2025-12-31 | Enhanced specs 029-032 with document request workflow |
| 2025-12-31 | Added: Document request templates, bulk requests, response tracking |
| 2025-12-31 | Added: Client responsiveness analytics, slow responder alerts |
| 2025-12-31 | New data model: `DocumentRequest` for tracking requests/responses |
| 2025-12-31 | **v5.0**: Added Phase E.5: ATOtrack (Specs 026-028) |
| 2025-12-31 | **v4.0**: Major roadmap restructure - Added Phase E: Data Intelligence |
| 2025-12-31 | Gap analysis revealed 80% of Xero data untapped |
| 2025-12-31 | New specs 023-025: Reports API, Credit Notes/Payments/Journals, Assets |
| 2025-12-31 | Renumbered: Phase E→F (026-029), Phase F→G (030-033), Phase G→H (034) |
| 2025-12-31 | Reference: `/planning/analysis/xero-api-gap-analysis.md` |
| 2025-12-31 | **v3.2**: Spec 020 complete (Usage Tracking & Limits) |
| 2025-12-31 | Usage dashboard, alerts, admin analytics, history page |
| 2025-12-31 | Next: Spec 021 (Onboarding Flow) |
| 2025-12-31 | **v3.1**: Renumbered specs to be sequential (019-030) |
| 2025-12-31 | Fixed gap in numbering: 020→019, 021→020, etc. |
| 2025-12-31 | **v3.0**: Major roadmap restructure aligned with GTM strategy |
| 2025-12-31 | New Phase D: Monetization Foundation (Specs 019-022) |
| 2025-12-31 | Moved Client Portal to Phase E (Spec 023) |
| 2025-12-31 | New Phase F: Growth & Scale (B2C, white-label, API) |
| 2025-12-31 | New Phase G: Polish & Operations |
| 2025-12-31 | Added architecture impact assessment |
| 2025-12-31 | Linked to /docs/strategy/ documents |
| 2025-12-31 | **v2.9**: Spec 018 complete (Magic Zone Insights) |
| 2025-12-31 | Phase C (Proactive Intelligence) complete |
