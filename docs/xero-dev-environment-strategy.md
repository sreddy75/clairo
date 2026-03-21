# Xero Developer Environment & XPM Integration Strategy

> **Last updated**: 2026-03-10
> **Status**: Research complete, action required
> **Author**: KR8IT / Clairo team

## Executive Summary

Clairo currently tests Xero integration against a personal Xero account. This doc covers how to set up a proper multi-org test environment and what's required for Xero Practice Manager (XPM) API integration. The key blocker: **XPM API access requires Xero Advanced tier at $1,445 AUD/month** plus a security assessment.

---

## Current State of Clairo's Xero Integration

Already built (4,500+ lines of models, 20+ API methods):

| Component | Status |
|-----------|--------|
| OAuth 2.0 PKCE flow | Complete |
| Token encryption (AES-256-GCM) | Complete |
| Accounting API (invoices, contacts, accounts, bank txns) | Complete |
| Payroll API (employees, pay runs) | Complete |
| Reports (P&L, Balance Sheet, Aged AR/AP, Trial Balance, Bank Summary, Budget) | Complete |
| Credit notes, payments, overpayments, prepayments | Complete |
| Journals, manual journals | Complete |
| Assets, purchase orders, quotes, repeating invoices | Complete |
| Webhook handler (HMAC verification, dedup, batched sync) | Complete |
| Rate limiter (per-org daily/minute tracking) | Complete |
| Celery background sync tasks | Complete |
| Multi-tenant support (xero-tenant-id header) | Complete |
| XPM data model (`xpm_clients` table) | Model only — no API client |
| XPM API HTTP client | **Not started** |

**28 database tables**, **20+ transformers**, full sync pipeline with phased sync and SSE progress streaming.

### Current Xero Scopes

```
offline_access openid profile email
accounting.settings accounting.transactions accounting.contacts
accounting.journals.read accounting.reports.read
payroll.employees payroll.payruns payroll.settings
assets assets.read
```

**Missing scope**: `practicemanager` (required for XPM API, must be granted by Xero).

---

## Part 1: Test Environment Setup

### What's Available (Free)

#### Demo Company
- One per Xero account, pre-loaded with AU sample data
- **Auto-resets every 28 days** (all custom data wiped, sample data repopulates)
- Can manually reset anytime from My Xero page
- Can change country (AU, US, UK, NZ, etc.)
- **Excluded** from the connection limit count
- No bank feeds, no multi-user, no banking transaction creation
- Access: Log into Xero → org dropdown → "Try the Demo Company"

#### Free Trial Organisations
- Create **multiple 30-day trial orgs** — no credit card required
- Each is a full Xero organisation with all features
- Use these to simulate multiple client companies
- Can create AU-specific orgs with GST, BAS-relevant chart of accounts

### Recommended Dev Setup

**Step 1**: Create/use existing Xero developer account at [developer.xero.com](https://developer.xero.com) (free)

**Step 2**: Register app in Developer Portal as "Web app" (OAuth 2.0 code flow) — already done for Clairo

**Step 3**: Set up test organisations:

| Org | Purpose | How |
|-----|---------|-----|
| Demo Company (AU) | Primary test org, BAS testing | Built-in, free |
| Trial Org 1 "Cafe PTY LTD" | Small business client simulation | Free 30-day trial |
| Trial Org 2 "Smith Construction" | Trade business with subcontractors | Free 30-day trial |
| Trial Org 3 "Tech Solutions AU" | Service business, GST-free exports | Free 30-day trial |
| Personal Xero account | Real data edge case testing | Already connected |

**Step 4**: Authorise all orgs through Clairo's OAuth flow — each gets a `tenantId` via `GET /connections`

**Step 5**: Populate trial orgs with test data:
- Create contacts with real-looking ABNs
- Create invoices spanning 2-3 BAS periods
- Mix of GST-applicable and GST-free transactions
- Some overdue invoices for aged receivables testing
- Payroll data if testing PAYG withholding

### Connection Limits by Tier

| Tier | Connections | Daily API/Org | Monthly Cost (AUD) |
|------|-------------|---------------|---------------------|
| Starter | 5 | 1,000 | Free |
| Core | 50 | 5,000 | $35 |
| Plus | 1,000 | 5,000 | $245 |
| Advanced | 10,000 | 5,000 | $1,445 |
| Enterprise | Unlimited | 5,000 | Custom |

Demo company is excluded from connection count. **Starter tier (5 connections) is sufficient for dev/test.**

### Rate Limits

| Limit | Value | Scope |
|-------|-------|-------|
| Concurrent | 5 calls in progress | Per org, per app |
| Per-minute | 60 calls | Per org, per app |
| Daily | 1,000 (Starter) / 5,000 (Core+) | Per org, per app |
| App-wide minute | 10,000 calls/min | All orgs combined |

Response headers to track: `X-DayLimit-Remaining`, `X-MinLimit-Remaining`, `X-AppMinLimit-Remaining`

Clairo already implements rate limit tracking in `rate_limiter.py` — reads these headers and applies exponential backoff on 429s.

### Data Egress Billing (New — effective March 2, 2026)

| Tier | Included Egress | Overage |
|------|-----------------|---------|
| Starter | Unlimited | N/A |
| Core | 10 GB | $2.40/GB |
| Plus | 50 GB | $2.40/GB |
| Advanced | 250 GB | $2.40/GB |

Egress = GET response payloads only. Writes (POST/PUT) are free and unlimited. Organisation endpoint is excluded.

---

## Part 2: Xero Practice Manager (XPM) API

### What XPM Is

XPM (formerly WorkflowMax) is Xero's practice management product for accountants. It's where accounting practices manage their clients, jobs, time entries, invoices, and workflow — the "orchestration layer" above Xero's accounting data.

For Clairo, XPM integration would let us pull the **practice-side view**: which clients belong to which accountant, what jobs are in progress, which BAS returns are being worked on, who's assigned to what.

### XPM API Capabilities

**API Versions**: v3.0 (stable) and v3.1 (newer, additional endpoints)

| Resource | Available Operations |
|----------|---------------------|
| **Clients** | List, search, get, add, update, archive, delete, contacts (CRUD), documents, notes, custom fields |
| **Jobs** | List (current, by staff, by client, by number), add, update, state changes, tasks (CRUD + complete/reopen), costs, notes, documents, milestones, assignees, templates, quotes |
| **Invoices** | List (current, draft, by job, by number), payments |
| **Time Entries** | List (by job, by staff, by ID), add, update, delete |
| **Staff** | List, get, add, update, delete, enable/disable, forgotten password |
| **Tasks** | List, get by ID |
| **Categories** | List, get by ID |
| **Custom Fields** | Get definitions, options |
| **Costs** | Get by job, add, update |
| **Quotes** | Via jobs — tasks, costs, options |

**33 entities total** including relationship objects (JobTask, JobCost, InvoiceTask, InvoicePayment, Milestone, etc.)

### XPM API Authentication

- **Same OAuth 2.0 flow** as Xero Accounting API
- Requires the **`practicemanager` scope** — cannot be self-added, must be granted by Xero
- Access tokens expire after **12 minutes** (same as accounting API)
- Refresh tokens use the same rotating refresh pattern
- In XPM, each staff member must enable **"Authorise 3rd Party Full Access"** in their staff profile

### XPM Access Requirements — THE BLOCKER

| Requirement | Detail | Cost |
|-------------|--------|------|
| **Xero Developer tier** | Advanced tier minimum | **$1,445 AUD/month ($17,340/yr)** |
| **Security self-assessment** | Against "Security Standard for Xero API Consumers" | Internal effort (initial + annual renewal) |
| **Use case approval** | Xero reviews your intended use of XPM data | Application process |
| **XPM subscription** | Need an actual XPM account to test against | $149 USD/month (or free at Silver+ partner level) |
| **Scope grant** | Email api@support.xero.com to add `practicemanager` scope | Free but gated |

**There is NO XPM sandbox.** No demo XPM environment exists. You must have a real XPM subscription to test.

### XPM Developer Resources

| Resource | URL |
|----------|-----|
| XPM API Overview | [developer.xero.com/documentation/api/practice-manager/overview-practice-manager](https://developer.xero.com/documentation/api/practice-manager/overview-practice-manager) |
| XPM API v3.1 | [developer.xero.com/documentation/api/practice-manager-3-1/overview-practice-manager](https://developer.xero.com/documentation/api/practice-manager-3-1/overview-practice-manager) |
| Postman Collection (OAuth2) | [github.com/XeroAPI/xeropracticemanager-postman-oauth2](https://github.com/XeroAPI/xeropracticemanager-postman-oauth2) |
| .NET Core Sample | [github.com/XeroAPI/xeropracticemanager-dotnetcore-oauth2-sample](https://github.com/XeroAPI/xeropracticemanager-dotnetcore-oauth2-sample) |
| XPM Scopes Docs | [developer.xero.com/documentation/guides/oauth2/scopes](https://developer.xero.com/documentation/guides/oauth2/scopes/) |

### Contact for XPM Access

| Purpose | Contact |
|---------|---------|
| Request `practicemanager` scope | api@support.xero.com |
| Security assessment queries | api@support.xero.com |
| Partner program (for free XPM) | [xero.com/au/partner-programme](https://www.xero.com/au/partner-programme/) |
| Developer tier upgrade | [developer.xero.com/pricing](https://developer.xero.com/pricing) |

---

## Part 3: Xero Partner Program (for Accounting Practices)

Separate from the developer API tiers. These are for accounting firms using Xero:

| Level | Requirements | Benefits for Clairo |
|-------|-------------|---------------------|
| **Bronze** | Xero subscription | Access to partner portal |
| **Silver** | 10+ Xero clients on ledger | Free XPM subscription, partner badge |
| **Gold** | 50+ clients | Priority support, additional tools |
| **Platinum** | 200+ clients | Dedicated account manager |

**Key insight**: If you reach Silver partner level (10+ clients), XPM is **free**. But this is about the accounting practice's status, not Clairo's developer access. It doesn't bypass the $1,445/mo Advanced developer tier requirement for API access.

---

## Part 4: Critical Policy Change — AI/ML Data Prohibition

**Effective March 2, 2026**, Xero's updated developer terms prohibit:

> "The use of data obtained through Xero's APIs to train or contribute to the creation of any AI or machine learning model."

### Impact on Clairo

**Not a concern.** Clairo does not train or fine-tune any AI/ML models. All AI features use Claude (Anthropic) for per-tenant inference — analyzing a specific client's data and generating insights. The RAG knowledge base in Pinecone contains only public ATO content, not Xero financial data.

| What Clairo Does | Policy Status |
|-----------------|---------------|
| Display Xero data in UI | Allowed |
| AI analysis on a tenant's own data (inference via Claude) | Allowed |
| BAS variance detection on a client's transactions | Allowed |
| AI advisory insights for a specific client | Allowed |
| RAG knowledge base (public ATO content only, no Xero data) | Allowed |

Just don't embed Xero financial data into Pinecone vectors or use it to train/fine-tune models in the future.

---

## Part 5: What Clairo Needs from XPM (and Whether It's Worth It)

### What XPM Would Give Us

| Capability | Value to Clairo |
|-----------|----------------|
| Client list with assigned accountant/partner | Map BAS work to responsible staff |
| Job tracking (BAS prep as a "job") | Track BAS workflow status within practice |
| Time entries against BAS jobs | Profitability analysis per client |
| Practice-wide workload view | Power "Today View" dashboard with practice context |
| Task assignments | Show which accountant is handling which BAS |

### Do We Actually Need It Now?

**Probably not for MVP.** Here's why:

1. Clairo already syncs the **client list from Xero Accounting API** (contacts with `IsCustomer=true`)
2. BAS workflow is managed **within Clairo** (our own status tracking, quality scoring, lodgment flow)
3. The "accountant managing multiple clients" scenario works via **Xero multi-tenant OAuth** — we already support this
4. XPM integration is a "nice to have" for practices that use XPM for job management, but many don't

**When it becomes worth it**: Phase F (Business Owner Portal) or when targeting larger practices (10+ staff) where job/time management is critical.

### Alternatives to Full XPM Integration

| Alternative | What It Gives | Cost |
|-------------|---------------|------|
| **Multi-org Xero OAuth** (already built) | Accountant connects multiple client orgs, switches between them | Free (Starter tier) |
| **Clairo's own job/workflow tracking** | Build lightweight BAS job tracking in Clairo | Engineering time only |
| **Karbon/XPM push integration** (Spec 028) | Push tasks from ATOtrack to external PM tools | Depends on Karbon API |

---

## Recommended Strategy

### Immediate (Now)

1. **Stop using personal Xero account for primary testing**
2. Set up Demo Company (AU) + 3 free trial orgs
3. Populate trial orgs with realistic BAS test data
4. Test multi-org OAuth flow with 4-5 connected orgs
5. Stay on **Starter tier** (free, 5 connections, sufficient for dev)

### Short-term (When First Customers Onboard)

1. Upgrade to **Core tier** ($35/mo) for 50 connections and 5,000 daily API calls per org
2. Implement webhook-based sync to reduce polling and data egress
3. Apply for **App Partner** status once 3+ real customer connections exist (removes 25-org cap)

### Medium-term (When Targeting Larger Practices)

1. Evaluate whether XPM integration is justified by customer demand
2. If yes: upgrade to **Advanced tier** ($1,445/mo), complete security assessment, request `practicemanager` scope
3. Start with XPM read-only: client list, job list, staff assignments
4. Consider XPM free trial (14 days) for initial API exploration before committing

### Long-term

1. Full XPM bidirectional sync (create jobs/tasks in XPM from Clairo)
2. Consider Xero App Store listing at Plus/Advanced tier
3. Monitor Xero API Portal for any XPM access tier changes

---

## Action Items

### Immediate: Test Environment
- [ ] Access Xero Demo Company (AU country) via org dropdown
- [ ] Create 3 free trial Xero organisations (AU, 30-day, no card needed)
- [ ] Populate trial orgs with test data (contacts with ABNs, invoices across BAS periods, mix of GST/GST-free)
- [ ] Connect all orgs through Clairo's OAuth flow
- [ ] Verify multi-tenant sync works across all connected orgs
- [ ] Stop using personal Xero account as primary test org

### Later: XPM Exploration
- [ ] Email api@support.xero.com to understand XPM access process and security assessment requirements
- [ ] Evaluate whether to start XPM trial ($149 USD/mo or 14-day free) for API exploration
- [ ] Review Xero Postman collection for XPM: github.com/XeroAPI/xeropracticemanager-postman-oauth2
- [ ] Assess customer demand for XPM integration before committing to Advanced tier

### Later: Production Readiness
- [ ] Upgrade to Core tier ($35/mo) when first real customers connect
- [ ] Apply for App Partner status at 3+ customer connections
- [x] ~~Review Clairo's AI features against Xero's AI/ML data prohibition~~ — no concern, Clairo only does per-tenant inference via Claude, no model training

---

## References

### Xero Developer Portal
- [Development Accounts](https://developer.xero.com/documentation/development-accounts/)
- [Pricing](https://developer.xero.com/pricing)
- [Pricing & Policy FAQs](https://developer.xero.com/faq/pricing-and-policy-updates)
- [OAuth 2.0 Scopes](https://developer.xero.com/documentation/guides/oauth2/scopes/)
- [OAuth 2.0 Tenants (Connections)](https://developer.xero.com/documentation/guides/oauth2/tenants)
- [API Rate Limits](https://developer.xero.com/documentation/guides/oauth2/limits/)
- [Rate Limit Best Practices](https://developer.xero.com/documentation/best-practices/api-call-efficiencies/rate-limits)
- [Multi-tenancy Guide](https://developer.xero.com/documentation/best-practices/managing-connections/multi-tenancy)

### XPM API
- [XPM API Overview](https://developer.xero.com/documentation/api/practice-manager/overview-practice-manager)
- [XPM API v3.1](https://developer.xero.com/documentation/api/practice-manager-3-1/overview-practice-manager)
- [XPM Postman Collection](https://github.com/XeroAPI/xeropracticemanager-postman-oauth2)
- [XPM .NET Core Sample](https://github.com/XeroAPI/xeropracticemanager-dotnetcore-oauth2-sample)

### Xero Central
- [Demo Company Guide](https://central.xero.com/s/article/Use-the-demo-company)
- [Partner Program Levels](https://central.xero.com/s/article/Partner-program-status-levels-explained-ROW)

### Xero Contact
- **XPM API access**: api@support.xero.com
- **Partner program**: [xero.com/au/partner-programme](https://www.xero.com/au/partner-programme/)
- **Developer terms**: [developer.xero.com/xero-developer-platform-terms-conditions](https://developer.xero.com/xero-developer-platform-terms-conditions)

### Internal Docs
- [Xero API Mapping](docs/xero-api-mapping.md) — endpoint reference with XPM coverage
- [Xero Integration Module](backend/app/modules/integrations/xero/) — 28 tables, 20+ API methods
