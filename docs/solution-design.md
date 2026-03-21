# Solution Design Document: Clairo

**Version:** 1.0
**Date:** December 2025
**Status:** Draft

---

## Executive Summary

Clairo is an intelligent practice operating system designed for Australian accounting firms managing BAS compliance for multiple clients. This document outlines the technical architecture, component design, and implementation approach for delivering a secure, scalable, multi-tenant SaaS platform that integrates with accounting ledgers (Xero, MYOB) and leverages AI agents for data quality assessment, compliance checking, and workflow automation.

**Core Design Principles:**
- **Ledger-agnostic:** Abstract data layer supporting multiple accounting platforms
- **Human-in-the-loop:** AI assists, accountants approve with full audit trails
- **Deterministic compliance:** Tax rules in modular, updatable engine
- **Multi-tenant security:** Cryptographic isolation with per-tenant key management
- **API-first:** Enable integrations with practice management tools

---

## 1. Architecture Overview

### 1.1 System Context Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         External Systems                                  │
├──────────────┬──────────────┬──────────────┬────────────────────────────┤
│              │              │              │                            │
│   ┌──────────▼──────┐  ┌───▼────────┐ ┌───▼──────┐  ┌──────────────┐  │
│   │  Xero API       │  │  MYOB API  │ │  ATO     │  │ Practice Mgmt│  │
│   │  (OAuth 2.0)    │  │  (OAuth)   │ │ Services │  │ Tools (APIs) │  │
│   └──────────┬──────┘  └───┬────────┘ └───┬──────┘  └──────┬───────┘  │
│              │              │              │                │           │
└──────────────┼──────────────┼──────────────┼────────────────┼───────────┘
               │              │              │                │
     ┌─────────▼──────────────▼──────────────▼────────────────▼─────────┐
     │                    API Gateway Layer                              │
     │  ┌────────────────┐  ┌──────────────┐  ┌────────────────────┐   │
     │  │ Auth Service   │  │ Rate Limiter │  │ Request Router     │   │
     │  │ (JWT/OAuth)    │  │              │  │                    │   │
     │  └────────────────┘  └──────────────┘  └────────────────────┘   │
     └─────────┬──────────────────────────────────────────────────────┬─┘
               │                                                      │
     ┌─────────▼──────────────────────────────────────────────────────▼─┐
     │                   Application Layer                              │
     │  ┌──────────────────────────────────────────────────────────┐   │
     │  │           Multi-Agent Orchestration Engine                │   │
     │  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐  │   │
     │  │  │  Data   │ │ Quality │ │   BAS    │ │  Advisory    │  │   │
     │  │  │  Agent  │ │  Agent  │ │   Agent  │ │  Agent       │  │   │
     │  │  └─────────┘ └─────────┘ └──────────┘ └──────────────┘  │   │
     │  └──────────────────────────────────────────────────────────┘   │
     │  ┌──────────────────────────────────────────────────────────┐   │
     │  │            Core Services Layer                            │   │
     │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │   │
     │  │  │Compliance│ │ Workflow │ │   Sync   │ │ Reporting │  │   │
     │  │  │  Engine  │ │  Engine  │ │  Service │ │  Service  │  │   │
     │  │  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │   │
     │  └──────────────────────────────────────────────────────────┘   │
     └─────────┬──────────────────────────────────────────────────────┬─┘
               │                                                      │
     ┌─────────▼──────────────────────────────────────────────────────▼─┐
     │              Unified Accounting Data Layer                       │
     │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
     │  │   Xero   │ │   MYOB   │ │   QBO    │ │  Manual Import   │   │
     │  │ Adapter  │ │ Adapter  │ │ Adapter  │ │  (CSV/Excel)     │   │
     │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
     └─────────┬──────────────────────────────────────────────────────┬─┘
               │                                                      │
     ┌─────────▼──────────────────────────────────────────────────────▼─┐
     │                    Data & Storage Layer                          │
     │  ┌────────────────┐  ┌────────────┐  ┌──────────────────────┐  │
     │  │  PostgreSQL    │  │   Redis    │  │  S3 / Object Store   │  │
     │  │  (Multi-tenant)│  │   Cache    │  │  (Documents, Logs)   │  │
     │  └────────────────┘  └────────────┘  └──────────────────────┘  │
     └──────────────────────────────────────────────────────────────────┘
               │                                                      │
     ┌─────────▼──────────────────────────────────────────────────────▼─┐
     │                    Client Applications                           │
     │  ┌────────────────┐  ┌────────────┐  ┌──────────────────────┐  │
     │  │  Web App       │  │   Client   │  │  Mobile App          │  │
     │  │  (Accountants) │  │   Portal   │  │  (iOS/Android)       │  │
     │  └────────────────┘  └────────────┘  └──────────────────────┘  │
     └──────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

| Principle | Implementation Approach |
|-----------|------------------------|
| **Ledger Agnostic** | Abstract accounting data layer with adapter pattern; standardized internal data model |
| **Human-in-the-Loop** | AI provides recommendations; accountants review and approve all compliance-critical actions |
| **Audit Trail First** | Immutable event log for all data changes, AI decisions, and user actions |
| **Zero-Trust Security** | Per-tenant cryptographic isolation; assume breach scenarios in design |
| **Offline Capability** | Progressive Web App with service workers; sync when connectivity restored |
| **API-First Design** | All features accessible via REST/GraphQL APIs; UI consumes same APIs |
| **Fail-Safe Compliance** | Conservative automation; block processing when confidence < threshold |
| **Observable by Default** | Comprehensive logging, metrics, and tracing built into all components |

---

## 2. Core Components

### 2.1 Accounting Data Layer

#### Purpose
Abstract integration with multiple accounting platforms (Xero, MYOB, QBO) into a unified internal data model, handling OAuth flows, rate limiting, data synchronization, and transformation.

#### Architecture Pattern: Adapter Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│              Accounting Data Abstraction Layer                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         Unified Data Model (Internal Schema)           │    │
│  │                                                         │    │
│  │  Account, Transaction, Contact, Invoice, BankFeed,     │    │
│  │  TaxRate, JournalEntry, BASWorksheet, PayrollRun       │    │
│  └────────────────────────────────────────────────────────┘    │
│                           │                                     │
│           ┌───────────────┼───────────────┬──────────────┐     │
│           │               │               │              │     │
│  ┌────────▼──────┐ ┌──────▼──────┐ ┌──────▼─────┐ ┌────▼────┐ │
│  │ Xero Adapter  │ │MYOB Adapter │ │QBO Adapter │ │  Manual │ │
│  ├───────────────┤ ├─────────────┤ ├────────────┤ │ Importer│ │
│  │ OAuth Manager │ │OAuth Manager│ │OAuth Mgr   │ │ CSV/XLS │ │
│  │ Rate Limiter  │ │Rate Limiter │ │Rate Limiter│ │ Parser  │ │
│  │ Sync Engine   │ │Sync Engine  │ │Sync Engine │ │ Mapper  │ │
│  │ Error Handler │ │Error Handler│ │Error Hdlr  │ │Validator│ │
│  └───────┬───────┘ └──────┬──────┘ └─────┬──────┘ └────┬────┘ │
│          │                │               │             │      │
└──────────┼────────────────┼───────────────┼─────────────┼──────┘
           │                │               │             │
   ┌───────▼──────┐  ┌──────▼─────┐  ┌─────▼────┐  ┌────▼─────┐
   │  Xero API    │  │  MYOB API  │  │  QBO API │  │  User    │
   │  (REST)      │  │  (REST)    │  │  (REST)  │  │  Upload  │
   └──────────────┘  └────────────┘  └──────────┘  └──────────┘
```

#### Xero Integration Specifics

**OAuth 2.0 Flow Implementation:**

```
1. Authorization Request
   GET https://login.xero.com/identity/connect/authorize
   ?response_type=code
   &client_id={CLIENT_ID}
   &redirect_uri={REDIRECT_URI}
   &scope=offline_access accounting.transactions accounting.reports.read
   &state={CSRF_TOKEN}

2. Token Exchange
   POST https://identity.xero.com/connect/token
   Content-Type: application/x-www-form-urlencoded

   grant_type=authorization_code
   &code={AUTH_CODE}
   &redirect_uri={REDIRECT_URI}

3. Tenant Discovery
   GET https://api.xero.com/connections
   Authorization: Bearer {ACCESS_TOKEN}

   Response: [{ tenantId, tenantType, tenantName }]

4. API Calls
   GET https://api.xero.com/api.xro/2.0/Invoices
   Authorization: Bearer {ACCESS_TOKEN}
   Xero-tenant-id: {TENANT_ID}
```

**Rate Limiting Strategy:**

```javascript
// Token bucket algorithm with tenant-level tracking
class XeroRateLimiter {
  constructor() {
    this.buckets = new Map(); // tenantId -> bucket
    this.CALLS_PER_MINUTE = 60;
    this.CALLS_PER_DAY = 5000;
  }

  async acquirePermit(tenantId) {
    const bucket = this.getBucket(tenantId);

    // Check minute limit
    if (bucket.minuteTokens <= 0) {
      await this.backoffWithJitter(bucket);
    }

    // Check daily limit (warn at 80%, block at 95%)
    if (bucket.dailyTokens < bucket.DAILY_LIMIT * 0.05) {
      throw new Error('Daily API limit approaching');
    }

    bucket.minuteTokens--;
    bucket.dailyTokens--;
    this.scheduleRefill(bucket);
  }

  async backoffWithJitter(bucket) {
    const baseDelay = 1000; // 1 second
    const jitter = Math.random() * 500;
    await sleep(baseDelay + jitter);
  }
}
```

**Incremental Sync Pattern:**

```python
class XeroSyncService:
    def sync_transactions(self, tenant_id: str, entity_type: str):
        """Incremental sync to avoid 100k document threshold"""
        last_sync = self.get_last_sync_timestamp(tenant_id, entity_type)

        # Use ModifiedAfter filter for incremental sync
        params = {
            'where': f'UpdatedDateUTC >= DateTime({last_sync.isoformat()})',
            'page': 1
        }

        while True:
            response = self.xero_client.get(
                endpoint=f'/{entity_type}',
                tenant_id=tenant_id,
                params=params
            )

            # Transform to internal model
            records = self.transform_to_internal_model(response.data)
            self.upsert_records(tenant_id, records)

            # Check pagination
            if not response.has_next_page:
                break
            params['page'] += 1

        self.update_last_sync_timestamp(tenant_id, entity_type)
```

**Data Transformation Layer:**

```typescript
interface InternalTransaction {
  id: string;
  tenantId: string;
  sourceSystem: 'xero' | 'myob' | 'qbo' | 'manual';
  sourceId: string;
  type: 'invoice' | 'bill' | 'payment' | 'journal';
  date: Date;
  amount: Decimal;
  taxAmount: Decimal;
  taxType: string;
  account: { code: string; name: string };
  contact: { id: string; name: string };
  description: string;
  reconciled: boolean;
  metadata: Record<string, any>;
}

class XeroTransactionAdapter {
  toInternal(xeroInvoice: XeroInvoice): InternalTransaction {
    return {
      id: uuid(),
      tenantId: xeroInvoice.tenantId,
      sourceSystem: 'xero',
      sourceId: xeroInvoice.InvoiceID,
      type: 'invoice',
      date: new Date(xeroInvoice.Date),
      amount: new Decimal(xeroInvoice.Total),
      taxAmount: new Decimal(xeroInvoice.TotalTax),
      taxType: xeroInvoice.LineItems[0]?.TaxType || 'NONE',
      account: {
        code: xeroInvoice.LineItems[0]?.AccountCode,
        name: xeroInvoice.LineItems[0]?.AccountName
      },
      contact: {
        id: xeroInvoice.Contact.ContactID,
        name: xeroInvoice.Contact.Name
      },
      description: xeroInvoice.Reference || '',
      reconciled: xeroInvoice.Status === 'PAID',
      metadata: { xeroStatus: xeroInvoice.Status }
    };
  }
}
```

#### MYOB Integration Approach

- **OAuth 2.0** similar to Xero but with different scopes
- **Rate Limits:** 1000 calls/day (more restrictive than Xero)
- **API Version:** AccountRight API (cloud-based)
- **Sync Strategy:** Webhook-based when available, polling fallback

---

### 2.2 Data Quality Engine

#### Purpose
Proactively assess BAS readiness by scoring data quality across multiple dimensions, detecting issues before BAS preparation begins, and providing actionable remediation guidance.

#### Quality Scoring Framework

Based on ISO 8000 and TDQM (Total Data Quality Management) frameworks, adapted for Australian BAS compliance:

```
┌─────────────────────────────────────────────────────────────────┐
│              Data Quality Assessment Engine                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         Quality Dimensions (ISO 8000 Based)            │    │
│  ├────────────────────────────────────────────────────────┤    │
│  │                                                         │    │
│  │  1. Accuracy      - Correct GST classification         │    │
│  │  2. Completeness  - No missing transactions/fields     │    │
│  │  3. Consistency   - Matching bank feeds/ledger         │    │
│  │  4. Timeliness    - Transaction dates vs periods       │    │
│  │  5. Validity      - Complies with ATO rules            │    │
│  │  6. Uniqueness    - No duplicate entries               │    │
│  │                                                         │    │
│  └─────────────────────────┬──────────────────────────────┘    │
│                            │                                    │
│  ┌─────────────────────────▼──────────────────────────────┐    │
│  │           Scoring Algorithm Engine                      │    │
│  │                                                         │    │
│  │  Overall Score = Σ(dimension_score × weight)           │    │
│  │                                                         │    │
│  │  Weights (configurable per client):                    │    │
│  │  - Accuracy: 25%                                        │    │
│  │  - Completeness: 20%                                    │    │
│  │  - Consistency: 20%                                     │    │
│  │  - Validity: 20%                                        │    │
│  │  - Timeliness: 10%                                      │    │
│  │  - Uniqueness: 5%                                       │    │
│  │                                                         │    │
│  └─────────────────────────┬──────────────────────────────┘    │
│                            │                                    │
│  ┌─────────────────────────▼──────────────────────────────┐    │
│  │         Issue Detection & Classification               │    │
│  │                                                         │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │    │
│  │  │ BLOCKING │  │ WARNING  │  │  INFORMATIONAL   │     │    │
│  │  ├──────────┤  ├──────────┤  ├──────────────────┤     │    │
│  │  │Unreconcil│  │Unusual   │  │ Minor category   │     │    │
│  │  │ed bank   │  │variance  │  │ inconsistencies  │     │    │
│  │  │feeds     │  │>30% vs   │  │                  │     │    │
│  │  │          │  │prior     │  │                  │     │    │
│  │  │Missing   │  │period    │  │ Optimization     │     │    │
│  │  │PAYG/Super│  │          │  │ opportunities    │     │    │
│  │  │payments  │  │Pending   │  │                  │     │    │
│  │  │          │  │approvals │  │                  │     │    │
│  │  └──────────┘  └──────────┘  └──────────────────┘     │    │
│  │                                                         │    │
│  │  Score Impact: -30 points   Score Impact: -10 points   │    │
│  │  Blocks BAS                  Flags for review          │    │
│  │                                                         │    │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation Example

```python
from decimal import Decimal
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum

class IssueSeverity(Enum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"

@dataclass
class QualityIssue:
    dimension: str
    severity: IssueSeverity
    description: str
    affected_count: int
    remediation: str
    score_impact: int

class DataQualityScorer:
    """
    BAS-specific data quality scoring engine
    """

    DIMENSION_WEIGHTS = {
        'accuracy': 0.25,
        'completeness': 0.20,
        'consistency': 0.20,
        'validity': 0.20,
        'timeliness': 0.10,
        'uniqueness': 0.05
    }

    def score_client(self, client_id: str, period: str) -> Dict:
        """
        Calculate comprehensive quality score for client BAS period
        """
        transactions = self.get_transactions(client_id, period)
        bank_feeds = self.get_bank_feeds(client_id, period)
        payroll = self.get_payroll(client_id, period)

        scores = {
            'accuracy': self.score_accuracy(transactions),
            'completeness': self.score_completeness(transactions, payroll),
            'consistency': self.score_consistency(transactions, bank_feeds),
            'validity': self.score_validity(transactions),
            'timeliness': self.score_timeliness(transactions, period),
            'uniqueness': self.score_uniqueness(transactions)
        }

        issues = self.detect_issues(transactions, bank_feeds, payroll, period)

        # Apply issue penalties
        total_score = sum(
            scores[dim] * weight
            for dim, weight in self.DIMENSION_WEIGHTS.items()
        )

        penalty = sum(issue.score_impact for issue in issues)
        final_score = max(0, total_score - penalty)

        return {
            'overall_score': final_score,
            'dimension_scores': scores,
            'issues': issues,
            'status': self.get_readiness_status(final_score, issues),
            'blocking_issues': [i for i in issues if i.severity == IssueSeverity.BLOCKING]
        }

    def score_accuracy(self, transactions: List) -> int:
        """
        Accuracy: Correct GST/tax classification
        """
        total = len(transactions)
        if total == 0:
            return 100

        # Check for common GST misclassifications
        suspicious = 0
        for txn in transactions:
            # GST-free items with tax amount
            if txn.tax_type == 'GST_FREE' and txn.tax_amount > 0:
                suspicious += 1
            # Input taxed with wrong rate
            if txn.tax_type == 'INPUT' and abs(txn.tax_amount / txn.amount - 0.1) > 0.01:
                suspicious += 1

        accuracy_rate = (total - suspicious) / total
        return int(accuracy_rate * 100)

    def score_completeness(self, transactions: List, payroll: List) -> int:
        """
        Completeness: Required fields populated, no gaps in periods
        """
        issues = 0
        total_checks = 0

        # Check transaction completeness
        for txn in transactions:
            total_checks += 5  # 5 required fields
            if not txn.description:
                issues += 1
            if not txn.account_code:
                issues += 1
            if not txn.contact:
                issues += 1
            if txn.tax_type is None:
                issues += 1
            if not txn.date:
                issues += 1

        # Check payroll completeness (PAYG, Super)
        for pay_run in payroll:
            total_checks += 2
            if pay_run.payg_withheld is None:
                issues += 1
            if pay_run.super_contribution is None:
                issues += 1

        if total_checks == 0:
            return 100

        completeness_rate = (total_checks - issues) / total_checks
        return int(completeness_rate * 100)

    def score_consistency(self, transactions: List, bank_feeds: List) -> int:
        """
        Consistency: Bank feeds reconciled with ledger
        """
        if not bank_feeds:
            return 100  # No bank feeds to reconcile

        unreconciled = [bf for bf in bank_feeds if not bf.reconciled]
        reconciliation_rate = (len(bank_feeds) - len(unreconciled)) / len(bank_feeds)

        return int(reconciliation_rate * 100)

    def detect_issues(self, transactions, bank_feeds, payroll, period) -> List[QualityIssue]:
        """
        Detect specific BAS-blocking and warning issues
        """
        issues = []

        # BLOCKING: Unreconciled bank feeds
        unreconciled = [bf for bf in bank_feeds if not bf.reconciled]
        if unreconciled:
            issues.append(QualityIssue(
                dimension='consistency',
                severity=IssueSeverity.BLOCKING,
                description=f'{len(unreconciled)} unreconciled bank transactions',
                affected_count=len(unreconciled),
                remediation='Reconcile all bank feeds before BAS preparation',
                score_impact=30
            ))

        # BLOCKING: Missing PAYG/Super payments
        if not payroll:
            issues.append(QualityIssue(
                dimension='completeness',
                severity=IssueSeverity.BLOCKING,
                description='No payroll data found for period',
                affected_count=0,
                remediation='Enter PAYG withholding and superannuation payments',
                score_impact=30
            ))

        # WARNING: Unusual variance from prior period
        prior_period_total = self.get_prior_period_total(period)
        current_total = sum(txn.amount for txn in transactions)

        if prior_period_total and abs(current_total - prior_period_total) / prior_period_total > 0.30:
            issues.append(QualityIssue(
                dimension='validity',
                severity=IssueSeverity.WARNING,
                description=f'Revenue variance >30% from prior period',
                affected_count=1,
                remediation='Review for unusual transactions or business changes',
                score_impact=10
            ))

        return issues
```

#### Quality Dashboard Metrics

```
┌────────────────────────────────────────────────────────────┐
│  Client: ABC Pty Ltd                    Period: Q2 2025    │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Overall Quality Score: 72/100  ⚠️  NOT READY              │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Accuracy      ████████████████░░░░   85/100          │  │
│  │ Completeness  ██████████████░░░░░░   70/100          │  │
│  │ Consistency   ████████░░░░░░░░░░░░   45/100  ⚠️      │  │
│  │ Validity      ██████████████████░░   90/100          │  │
│  │ Timeliness    ████████████████████   95/100          │  │
│  │ Uniqueness    ████████████████████  100/100          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  BLOCKING ISSUES (2):                                       │
│  🚫 47 unreconciled bank transactions                       │
│  🚫 Missing superannuation payment records                  │
│                                                             │
│  WARNINGS (1):                                              │
│  ⚠️  GST revenue 35% higher than Q1 2025                    │
│                                                             │
│  [View Details] [Start Remediation Workflow]               │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

### 2.3 AI Agent System

#### Multi-Agent Architecture Pattern

Based on LangGraph's supervisor/hierarchical pattern and AutoGen's conversational agent approach, adapted for financial compliance workflows.

```
┌─────────────────────────────────────────────────────────────────┐
│                 Agent Orchestration Layer                        │
│                    (LangGraph-based)                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Supervisor Agent                          │    │
│  │  (Task routing, state management, human escalation)    │    │
│  └───────┬────────────┬────────────┬────────────┬─────────┘    │
│          │            │            │            │               │
│  ┌───────▼──────┐ ┌──▼────────┐ ┌─▼──────────┐ ┌▼───────────┐ │
│  │ Data Sync    │ │ Quality   │ │    BAS     │ │  Advisory  │ │
│  │ Agent        │ │ Agent     │ │   Agent    │ │   Agent    │ │
│  ├──────────────┤ ├───────────┤ ├────────────┤ ├────────────┤ │
│  │ Pulls data   │ │ Scores    │ │ Calculates │ │ Analyzes   │ │
│  │ from Xero/   │ │ quality   │ │ GST, PAYG  │ │ trends,    │ │
│  │ MYOB         │ │ dimensions│ │ Super      │ │ forecasts  │ │
│  │              │ │           │ │            │ │ cash flow  │ │
│  │ Detects      │ │ Flags     │ │ Detects    │ │            │ │
│  │ schema       │ │ issues    │ │ variances  │ │ Suggests   │ │
│  │ changes      │ │           │ │            │ │ scenarios  │ │
│  │              │ │ Suggests  │ │ Generates  │ │            │ │
│  │ Transforms   │ │ remedies  │ │ worksheets │ │            │ │
│  └──────────────┘ └───────────┘ └────────────┘ └────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         Shared Agent Memory & State                    │    │
│  │                                                         │    │
│  │  - Conversation history (per client)                   │    │
│  │  - Prior period data for context                       │    │
│  │  - User preferences & overrides                        │    │
│  │  - Pending human approvals                             │    │
│  │                                                         │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │         Deterministic Workflow Engine                  │    │
│  │                                                         │    │
│  │  Agents recommend → Workflows enforce → Humans approve │    │
│  │                                                         │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Agent Specifications

**1. Data Sync Agent**

```python
class DataSyncAgent:
    """
    Responsible for pulling accounting data from external systems
    """

    capabilities = [
        'detect_new_transactions',
        'handle_schema_changes',
        'resolve_sync_conflicts',
        'optimize_sync_schedule'
    ]

    def execute(self, context: AgentContext) -> AgentResponse:
        """
        Determine which data to sync and when
        """
        # Check last sync timestamp
        last_sync = self.get_last_sync(context.client_id)

        # Analyze transaction volume patterns
        pattern = self.llm.invoke(
            prompt=f"Based on historical data, when should we next sync "
                   f"for client {context.client_name}? Last sync: {last_sync}. "
                   f"Typical daily transactions: {context.avg_daily_txns}",
            tools=['calculate_optimal_sync_time']
        )

        # Recommend sync strategy
        return AgentResponse(
            action='schedule_sync',
            parameters={'next_sync': pattern.recommended_time},
            confidence=0.92,
            requires_approval=False
        )
```

**2. Quality Agent**

```python
class QualityAgent:
    """
    Analyzes data quality and suggests remediation
    """

    capabilities = [
        'score_quality_dimensions',
        'detect_anomalies',
        'suggest_fixes',
        'prioritize_issues'
    ]

    def execute(self, context: AgentContext) -> AgentResponse:
        """
        Assess quality and recommend remediation
        """
        # Get quality scores from engine
        scores = self.quality_engine.score_client(
            client_id=context.client_id,
            period=context.period
        )

        # Use LLM to prioritize issues and suggest fixes
        remediation_plan = self.llm.invoke(
            prompt=f"Client has these quality issues: {scores['issues']}. "
                   f"BAS lodgement due in {context.days_until_due} days. "
                   f"Prioritize issues and suggest remediation steps.",
            tools=['prioritize_by_impact', 'estimate_fix_time']
        )

        return AgentResponse(
            action='present_remediation_plan',
            parameters={
                'priority_issues': remediation_plan.priority_list,
                'estimated_hours': remediation_plan.total_hours
            },
            confidence=0.88,
            requires_approval=True  # Human reviews plan
        )
```

**3. BAS Agent**

```python
class BASAgent:
    """
    Calculates BAS amounts and detects variances
    """

    capabilities = [
        'calculate_gst',
        'calculate_payg',
        'detect_variances',
        'generate_worksheets'
    ]

    def execute(self, context: AgentContext) -> AgentResponse:
        """
        Calculate BAS and flag unusual patterns
        """
        # Deterministic calculation (no LLM)
        bas_calc = self.compliance_engine.calculate_bas(
            client_id=context.client_id,
            period=context.period
        )

        # Use LLM for variance analysis
        analysis = self.llm.invoke(
            prompt=f"BAS results: G1 (sales) ${bas_calc.g1}, "
                   f"G11 (purchases) ${bas_calc.g11}. "
                   f"Prior period: G1 ${context.prior_g1}, G11 ${context.prior_g11}. "
                   f"Explain variance and suggest whether review is needed.",
            tools=['calculate_variance_percentage', 'check_seasonal_patterns']
        )

        return AgentResponse(
            action='present_bas_draft',
            parameters={
                'bas_amounts': bas_calc.to_dict(),
                'variance_explanation': analysis.explanation,
                'review_required': analysis.needs_review
            },
            confidence=0.95 if not analysis.needs_review else 0.70,
            requires_approval=True  # Always require human approval
        )
```

**4. Advisory Agent**

```python
class AdvisoryAgent:
    """
    Provides strategic insights and scenario modeling
    """

    capabilities = [
        'forecast_cash_flow',
        'identify_gst_opportunities',
        'model_scenarios',
        'benchmark_performance'
    ]

    def execute(self, context: AgentContext) -> AgentResponse:
        """
        Generate strategic recommendations
        """
        # Analyze trends
        trends = self.analytics_engine.analyze_trends(
            client_id=context.client_id,
            periods=4  # Last 4 quarters
        )

        # Use LLM for insights
        insights = self.llm.invoke(
            prompt=f"Client trends: Revenue {trends.revenue_trend}, "
                   f"GST paid {trends.gst_trend}, Cash flow {trends.cashflow_trend}. "
                   f"Industry: {context.industry}. Suggest 3 advisory opportunities.",
            tools=['benchmark_against_industry', 'calculate_gst_impact']
        )

        return AgentResponse(
            action='present_advisory_insights',
            parameters={'recommendations': insights.opportunities},
            confidence=0.75,
            requires_approval=False  # Informational only
        )
```

#### Supervisor Agent Orchestration

```python
class SupervisorAgent:
    """
    Routes tasks to specialist agents and manages workflow
    """

    def orchestrate_bas_preparation(self, client_id: str, period: str):
        """
        Coordinate multi-agent BAS preparation workflow
        """
        state = WorkflowState(
            client_id=client_id,
            period=period,
            stage='initiated'
        )

        # Step 1: Sync data
        sync_result = self.data_sync_agent.execute(state.context)
        if sync_result.requires_approval:
            state = self.await_human_approval(sync_result)
        state.update(sync_result)

        # Step 2: Check quality
        quality_result = self.quality_agent.execute(state.context)
        if quality_result.parameters['blocking_issues']:
            # Don't proceed if blocking issues
            return self.escalate_to_human(
                reason='blocking_quality_issues',
                details=quality_result
            )
        state.update(quality_result)

        # Step 3: Calculate BAS
        bas_result = self.bas_agent.execute(state.context)
        state.update(bas_result)

        # Step 4: Advisory insights (parallel, non-blocking)
        advisory_result = self.advisory_agent.execute(state.context)
        state.update(advisory_result)

        # Step 5: Present to human for approval
        return self.present_for_approval(state)
```

#### Human-in-the-Loop Pattern

```
┌──────────────────────────────────────────────────────────┐
│                  AI Decision Flow                         │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Agent generates recommendation                           │
│           │                                               │
│           ▼                                               │
│  ┌─────────────────┐                                     │
│  │ Confidence > 95%│                                     │
│  │ AND             │                                     │
│  │ Non-compliance  │                                     │
│  │ impact?         │                                     │
│  └────┬────────┬───┘                                     │
│       │        │                                         │
│      YES       NO                                        │
│       │        │                                         │
│       ▼        ▼                                         │
│   Execute    Human Review Required                       │
│   with audit ┌───────────────────────┐                  │
│   log        │ Present:              │                  │
│              │ - AI recommendation   │                  │
│              │ - Confidence score    │                  │
│              │ - Supporting data     │                  │
│              │ - Audit trail         │                  │
│              │                       │                  │
│              │ Human Actions:        │                  │
│              │ [Approve] [Reject]    │                  │
│              │ [Modify] [Defer]      │                  │
│              └───────────────────────┘                  │
│                        │                                 │
│                        ▼                                 │
│              Record human decision                       │
│              Update agent training data                  │
│              (without exposing client data)              │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

### 2.4 Compliance Engine

#### Purpose
Deterministic calculation of BAS amounts based on ATO tax rules, ensuring accuracy and auditability without AI/LLM involvement in compliance-critical calculations.

#### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Compliance Engine                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │          Tax Rule Repository                       │    │
│  │                                                     │    │
│  │  - GST calculation rules (GSTR 2025)               │    │
│  │  - PAYG withholding tables (ATO schedules)         │    │
│  │  - Superannuation guarantee rates (11.5% 2025)     │    │
│  │  - Wine Equalisation Tax, Luxury Car Tax, etc.     │    │
│  │                                                     │    │
│  │  Versioned rules with effective dates              │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                 │
│  ┌────────────────────────▼───────────────────────────┐    │
│  │          BAS Calculation Modules                   │    │
│  │                                                     │    │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │    │
│  │  │   GST    │  │  PAYG-W  │  │  Superannuation │  │    │
│  │  │ Module   │  │  Module  │  │     Module      │  │    │
│  │  ├──────────┤  ├──────────┤  ├─────────────────┤  │    │
│  │  │ G1: Sales│  │ W1: Total│  │ Amount due      │  │    │
│  │  │ G2: Expt │  │ W2: Amt  │  │ SGC rate check  │  │    │
│  │  │ G3: Other│  │ W3: W4   │  │                 │  │    │
│  │  │ ...G21   │  │ W5       │  │                 │  │    │
│  │  └──────────┘  └──────────┘  └─────────────────┘  │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌────────────────────────▼───────────────────────────┐    │
│  │          Validation & Audit Trail                  │    │
│  │                                                     │    │
│  │  - Cross-check calculations                        │    │
│  │  - Record all inputs/outputs                       │    │
│  │  - Generate audit logs                             │    │
│  │  - Support ATO audit requirements                  │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### BAS Calculation Logic

```python
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Dict, List

class BASCalculator:
    """
    Deterministic BAS calculation following ATO specifications
    """

    def calculate_gst(self, transactions: List[Transaction], period: str) -> Dict[str, Decimal]:
        """
        Calculate GST amounts for BAS labels G1-G21
        """
        # G1: Total sales (including GST)
        g1 = sum(
            txn.amount for txn in transactions
            if txn.type == 'SALE' and txn.tax_type in ['OUTPUT', 'CAPPUR']
        )

        # G2: Export sales
        g2 = sum(
            txn.amount for txn in transactions
            if txn.type == 'SALE' and txn.tax_type == 'EXPORT'
        )

        # G3: Other GST-free sales
        g3 = sum(
            txn.amount for txn in transactions
            if txn.type == 'SALE' and txn.tax_type == 'GST_FREE'
        )

        # G10: Capital purchases
        g10 = sum(
            txn.amount for txn in transactions
            if txn.type == 'PURCHASE' and txn.is_capital_acquisition
        )

        # G11: Non-capital purchases
        g11 = sum(
            txn.amount for txn in transactions
            if txn.type == 'PURCHASE' and not txn.is_capital_acquisition
        )

        # G18: Total purchases
        g18 = g10 + g11

        # 1A: GST on sales (G1 ÷ 11, rounded to nearest dollar)
        label_1a = (g1 / Decimal('11')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        # 1B: GST on purchases (G18 ÷ 11, rounded to nearest dollar)
        label_1b = (g18 / Decimal('11')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        # 7: GST payable/refundable (1A - 1B)
        label_7 = label_1a - label_1b

        return {
            'G1': g1,
            'G2': g2,
            'G3': g3,
            'G10': g10,
            'G11': g11,
            'G18': g18,
            '1A': label_1a,
            '1B': label_1b,
            '7': label_7
        }

    def calculate_payg_withholding(self, payroll: List[PayrollRun]) -> Dict[str, Decimal]:
        """
        Calculate PAYG withholding amounts for W1-W5
        """
        # W1: Total salary/wages paid
        w1 = sum(run.gross_wages for run in payroll)

        # W2: Amount withheld
        w2 = sum(run.payg_withheld for run in payroll)

        # W3 & W4: Credits (typically zero for most businesses)
        w3 = Decimal('0')
        w4 = Decimal('0')

        # W5: Total payable (W2 - W3 - W4)
        w5 = w2 - w3 - w4

        return {
            'W1': w1,
            'W2': w2,
            'W5': w5
        }

    def validate_bas(self, bas_data: Dict) -> List[ValidationError]:
        """
        Run validation rules against calculated BAS
        """
        errors = []

        # Rule: G1 should include G2 and G3 (total sales = taxable + GST-free)
        # Actually, G1 is only taxable sales. Let me correct:
        # Total sales = G1 + G2 + G3

        # Rule: 1A should equal G1 ÷ 11 (within rounding)
        expected_1a = (bas_data['G1'] / Decimal('11')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        if abs(bas_data['1A'] - expected_1a) > 1:
            errors.append(ValidationError(
                field='1A',
                message=f'GST on sales calculation incorrect. Expected {expected_1a}, got {bas_data["1A"]}'
            ))

        # Rule: Negative GST refund > $10,000 requires manual review
        if bas_data['7'] < Decimal('-10000'):
            errors.append(ValidationError(
                field='7',
                message=f'Large GST refund ${abs(bas_data["7"])} requires review',
                severity='WARNING'
            ))

        return errors
```

#### Rule Versioning System

```python
@dataclass
class TaxRule:
    rule_id: str
    description: str
    effective_from: date
    effective_to: date | None
    calculation_logic: callable

class TaxRuleRepository:
    """
    Versioned tax rules with temporal validity
    """

    def get_gst_rate(self, as_of_date: date) -> Decimal:
        """
        Get applicable GST rate for date (10% in Australia, but versioned)
        """
        rules = [
            TaxRule(
                rule_id='GST_RATE_2000',
                description='GST rate 10%',
                effective_from=date(2000, 7, 1),
                effective_to=None,
                calculation_logic=lambda: Decimal('0.10')
            )
        ]

        applicable_rule = next(
            r for r in rules
            if r.effective_from <= as_of_date and (r.effective_to is None or r.effective_to >= as_of_date)
        )

        return applicable_rule.calculation_logic()

    def get_sgc_rate(self, period: str) -> Decimal:
        """
        Get Superannuation Guarantee Contribution rate for period
        """
        rates = {
            '2024-Q3': Decimal('0.115'),  # 11.5%
            '2024-Q4': Decimal('0.115'),
            '2025-Q1': Decimal('0.115'),
            # Future increases legislated
            '2025-Q3': Decimal('0.120'),  # 12.0%
        }

        return rates.get(period, Decimal('0.115'))  # Default current rate
```

---

### 2.5 Workflow Engine

#### Purpose
Orchestrate multi-step approval workflows, track status transitions, enforce business rules, and maintain immutable audit trails.

#### State Machine Design

```
┌─────────────────────────────────────────────────────────────┐
│              BAS Workflow State Machine                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│                    ┌──────────┐                             │
│                    │  DRAFT   │                             │
│                    └─────┬────┘                             │
│                          │                                  │
│                          │ submit_for_review                │
│                          ▼                                  │
│                    ┌──────────┐                             │
│              ┌─────│  REVIEW  │─────┐                       │
│              │     └──────────┘     │                       │
│         reject                   approve                    │
│              │                       │                      │
│              ▼                       ▼                      │
│        ┌──────────┐            ┌──────────┐                │
│        │ REJECTED │            │ APPROVED │                │
│        └─────┬────┘            └─────┬────┘                │
│              │                       │                      │
│          revise                   lodge                     │
│              │                       │                      │
│              │                       ▼                      │
│              │                 ┌──────────┐                │
│              │                 │  LODGED  │                │
│              │                 └─────┬────┘                │
│              │                       │                      │
│              │                  ato_confirm                 │
│              │                       │                      │
│              │                       ▼                      │
│              │                 ┌──────────┐                │
│              └────────────────►│COMPLETED │                │
│                                └──────────┘                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Implementation

```python
from enum import Enum
from datetime import datetime
from typing import Optional, List

class WorkflowState(Enum):
    DRAFT = "draft"
    REVIEW = "review"
    REJECTED = "rejected"
    APPROVED = "approved"
    LODGED = "lodged"
    COMPLETED = "completed"

class WorkflowTransition:
    """
    Allowed state transitions with business rules
    """

    TRANSITIONS = {
        WorkflowState.DRAFT: [WorkflowState.REVIEW],
        WorkflowState.REVIEW: [WorkflowState.APPROVED, WorkflowState.REJECTED],
        WorkflowState.REJECTED: [WorkflowState.DRAFT],
        WorkflowState.APPROVED: [WorkflowState.LODGED],
        WorkflowState.LODGED: [WorkflowState.COMPLETED],
    }

    @classmethod
    def can_transition(cls, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        return to_state in cls.TRANSITIONS.get(from_state, [])

class BASWorkflow:
    """
    Manages BAS preparation and approval workflow
    """

    def __init__(self, client_id: str, period: str):
        self.workflow_id = uuid4()
        self.client_id = client_id
        self.period = period
        self.state = WorkflowState.DRAFT
        self.events: List[WorkflowEvent] = []
        self.assigned_to: Optional[str] = None
        self.due_date: Optional[datetime] = None

    def transition(self, to_state: WorkflowState, actor: str, comment: Optional[str] = None):
        """
        Transition workflow to new state with audit trail
        """
        if not WorkflowTransition.can_transition(self.state, to_state):
            raise InvalidTransitionError(
                f"Cannot transition from {self.state} to {to_state}"
            )

        # Record event
        event = WorkflowEvent(
            workflow_id=self.workflow_id,
            from_state=self.state,
            to_state=to_state,
            actor=actor,
            timestamp=datetime.utcnow(),
            comment=comment
        )
        self.events.append(event)

        # Update state
        old_state = self.state
        self.state = to_state

        # Trigger side effects
        self._on_state_change(old_state, to_state, actor)

        # Persist to database
        self.save()

    def _on_state_change(self, old_state: WorkflowState, new_state: WorkflowState, actor: str):
        """
        Execute side effects based on state transitions
        """
        if new_state == WorkflowState.REVIEW:
            # Notify accountant
            self.notification_service.send(
                to=self.assigned_to,
                subject=f'BAS ready for review: {self.client_id}',
                body=f'BAS for period {self.period} is ready for your review.'
            )

        elif new_state == WorkflowState.REJECTED:
            # Log rejection reason
            self.audit_logger.log(
                event='BAS_REJECTED',
                workflow_id=self.workflow_id,
                actor=actor,
                details={'reason': self.events[-1].comment}
            )

        elif new_state == WorkflowState.LODGED:
            # Record lodgement timestamp for ATO deadline compliance
            self.compliance_logger.log(
                event='BAS_LODGED',
                workflow_id=self.workflow_id,
                lodged_at=datetime.utcnow(),
                lodged_by=actor
            )

@dataclass
class WorkflowEvent:
    """
    Immutable audit event
    """
    workflow_id: str
    from_state: WorkflowState
    to_state: WorkflowState
    actor: str  # User ID who triggered transition
    timestamp: datetime
    comment: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

## 3. Data Architecture

### 3.1 Entity Relationship Diagram

```
┌──────────────┐         ┌──────────────────┐         ┌──────────────┐
│   Tenant     │         │   Client         │         │   User       │
├──────────────┤         ├──────────────────┤         ├──────────────┤
│ id           │────────<│ tenant_id        │>────────│ id           │
│ name         │         │ id               │         │ tenant_id    │
│ plan         │         │ name             │         │ email        │
│ encryption_  │         │ abn              │         │ role         │
│   key_id     │         │ ledger_type      │         │ permissions  │
│ created_at   │         │ ledger_tenant_id │         └──────────────┘
└──────────────┘         │ quality_score    │
                         │ status           │
                         └────────┬─────────┘
                                  │
                        ┌─────────┴──────────────────────┐
                        │                                │
                ┌───────▼──────────┐          ┌──────────▼────────┐
                │  BAS_Period      │          │  Transaction      │
                ├──────────────────┤          ├───────────────────┤
                │ id               │          │ id                │
                │ client_id        │<─────────│ client_id         │
                │ period           │          │ source_system     │
                │ start_date       │          │ source_id         │
                │ end_date         │          │ type              │
                │ lodgement_due    │          │ date              │
                │ workflow_state   │          │ amount            │
                │ quality_score    │          │ tax_amount        │
                │ bas_data (JSON)  │          │ tax_type          │
                └──────────────────┘          │ account_code      │
                        │                     │ reconciled        │
                        │                     └───────────────────┘
                ┌───────▼──────────┐
                │  Workflow_Event  │
                ├──────────────────┤
                │ id               │
                │ workflow_id      │
                │ from_state       │
                │ to_state         │
                │ actor_id         │
                │ timestamp        │
                │ comment          │
                └──────────────────┘

┌─────────────────┐         ┌──────────────────┐
│  Quality_Issue  │         │  Audit_Log       │
├─────────────────┤         ├──────────────────┤
│ id              │         │ id               │
│ client_id       │         │ tenant_id        │
│ period          │         │ event_type       │
│ dimension       │         │ actor_id         │
│ severity        │         │ resource_type    │
│ description     │         │ resource_id      │
│ affected_count  │         │ action           │
│ status          │         │ timestamp        │
│ resolved_at     │         │ ip_address       │
└─────────────────┘         │ metadata (JSON)  │
                            └──────────────────┘
```

### 3.2 Multi-Tenant Isolation Strategy

Based on AWS SaaS best practices, Clairo uses a **pooled database with row-level isolation** enhanced by **cryptographic tenant separation**.

#### Row-Level Security (PostgreSQL)

```sql
-- Enable Row-Level Security on all tenant tables
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE bas_periods ENABLE ROW LEVEL SECURITY;

-- Create policy to enforce tenant isolation
CREATE POLICY tenant_isolation ON clients
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY tenant_isolation ON transactions
  USING (
    client_id IN (
      SELECT id FROM clients
      WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

-- Application sets tenant context per request
SET SESSION app.current_tenant_id = '550e8400-e29b-41d4-a716-446655440000';
```

#### Cryptographic Isolation with Per-Tenant Keys

```python
from cryptography.fernet import Fernet
import boto3

class TenantEncryptionService:
    """
    Per-tenant encryption using AWS KMS
    """

    def __init__(self):
        self.kms_client = boto3.client('kms')
        self.key_cache = {}  # Tenant ID -> Data Encryption Key

    def get_tenant_key(self, tenant_id: str) -> bytes:
        """
        Get or create tenant-specific data encryption key
        """
        if tenant_id in self.key_cache:
            return self.key_cache[tenant_id]

        # Generate unique KMS key alias for tenant
        alias_name = f'alias/clairo-tenant-{tenant_id}'

        try:
            # Check if key exists
            response = self.kms_client.describe_key(KeyId=alias_name)
            key_id = response['KeyMetadata']['KeyId']
        except:
            # Create new KMS key for tenant
            response = self.kms_client.create_key(
                Description=f'Encryption key for tenant {tenant_id}',
                KeyUsage='ENCRYPT_DECRYPT',
                Origin='AWS_KMS'
            )
            key_id = response['KeyMetadata']['KeyId']

            # Create alias
            self.kms_client.create_alias(
                AliasName=alias_name,
                TargetKeyId=key_id
            )

        # Generate data encryption key
        dek_response = self.kms_client.generate_data_key(
            KeyId=key_id,
            KeySpec='AES_256'
        )

        self.key_cache[tenant_id] = dek_response['Plaintext']
        return dek_response['Plaintext']

    def encrypt_field(self, tenant_id: str, plaintext: str) -> str:
        """
        Encrypt sensitive field using tenant-specific key
        """
        key = self.get_tenant_key(tenant_id)
        cipher = Fernet(key)
        ciphertext = cipher.encrypt(plaintext.encode())
        return ciphertext.decode()

    def decrypt_field(self, tenant_id: str, ciphertext: str) -> str:
        """
        Decrypt sensitive field
        """
        key = self.get_tenant_key(tenant_id)
        cipher = Fernet(key)
        plaintext = cipher.decrypt(ciphertext.encode())
        return plaintext.decode()
```

#### Database Schema with Encryption

```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    abn_encrypted TEXT NOT NULL,  -- Encrypted with tenant key
    ledger_type VARCHAR(50),
    ledger_tenant_id_encrypted TEXT,  -- Encrypted OAuth tokens
    quality_score INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);

CREATE INDEX idx_clients_tenant ON clients(tenant_id);
```

### 3.3 Data Synchronization Strategy

#### Incremental Sync Pattern

```
┌─────────────────────────────────────────────────────────────┐
│              Sync Orchestration Service                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Schedule Determination                                   │
│     ┌────────────────────────────────────────┐             │
│     │ - High volume clients: Every 2 hours   │             │
│     │ - Medium volume: Daily at 8am          │             │
│     │ - Low volume: Every 3 days             │             │
│     │ - Pre-BAS: Hourly (7 days before due)  │             │
│     └────────────────────────────────────────┘             │
│                                                              │
│  2. Incremental Fetch                                        │
│     ┌────────────────────────────────────────┐             │
│     │ GET /Invoices?ModifiedAfter=2025-12-01 │             │
│     │ GET /BankTransactions?ModifiedAfter=.. │             │
│     └────────────────────────────────────────┘             │
│                                                              │
│  3. Change Detection                                         │
│     ┌────────────────────────────────────────┐             │
│     │ Compare source_updated_at with local   │             │
│     │ Hash content to detect true changes    │             │
│     └────────────────────────────────────────┘             │
│                                                              │
│  4. Conflict Resolution                                      │
│     ┌────────────────────────────────────────┐             │
│     │ Source system wins (Xero/MYOB)         │             │
│     │ Flag if local changes exist            │             │
│     │ Log conflict for human review          │             │
│     └────────────────────────────────────────┘             │
│                                                              │
│  5. Quality Re-scoring                                       │
│     ┌────────────────────────────────────────┐             │
│     │ Trigger quality agent after sync       │             │
│     │ Update dashboard status                │             │
│     └────────────────────────────────────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Integration Design

### 4.1 Xero OAuth 2.0 Flow

```
┌──────────┐                                           ┌──────────┐
│          │                                           │          │
│ Clairo  │                                           │   Xero   │
│   App    │                                           │   API    │
│          │                                           │          │
└────┬─────┘                                           └────┬─────┘
     │                                                      │
     │ 1. User clicks "Connect Xero"                       │
     │ ──────────────────────────────────────────────────> │
     │                                                      │
     │ 2. Redirect to Xero authorization                   │
     │    GET /identity/connect/authorize                  │
     │    ?client_id={ID}&scope=accounting.transactions... │
     │ <────────────────────────────────────────────────── │
     │                                                      │
     │ 3. User approves in Xero (selects organization)     │
     │                                                      │
     │ 4. Redirect back with authorization code            │
     │    GET /callback?code={CODE}&state={STATE}          │
     │ <────────────────────────────────────────────────── │
     │                                                      │
     │ 5. Exchange code for tokens                         │
     │    POST /connect/token                              │
     │    grant_type=authorization_code&code={CODE}        │
     │ ──────────────────────────────────────────────────> │
     │                                                      │
     │ 6. Receive access & refresh tokens                  │
     │    { access_token, refresh_token, expires_in }      │
     │ <────────────────────────────────────────────────── │
     │                                                      │
     │ 7. Discover tenant IDs                              │
     │    GET /connections                                 │
     │    Authorization: Bearer {ACCESS_TOKEN}             │
     │ ──────────────────────────────────────────────────> │
     │                                                      │
     │ 8. Receive tenant list                              │
     │    [{ tenantId, tenantType, tenantName }]           │
     │ <────────────────────────────────────────────────── │
     │                                                      │
     │ 9. Store encrypted tokens + tenant mapping          │
     │    (in database with tenant-specific encryption)    │
     │                                                      │
     │ 10. Make API calls with tenant context              │
     │     GET /api.xro/2.0/Invoices                       │
     │     Authorization: Bearer {TOKEN}                   │
     │     Xero-tenant-id: {TENANT_ID}                     │
     │ ──────────────────────────────────────────────────> │
     │                                                      │
     │ 11. Token expires (30 min), auto-refresh            │
     │     POST /connect/token                             │
     │     grant_type=refresh_token&refresh_token={RT}     │
     │ ──────────────────────────────────────────────────> │
     │                                                      │
```

### 4.2 MYOB Integration Approach

- **OAuth 2.0** flow similar to Xero
- **Company File selection** required post-authorization
- **API Base:** `https://api.myob.com/accountright/`
- **Rate Limits:** 1000 calls/day (more restrictive)
- **Webhook support:** Limited; rely on polling

### 4.3 ATO Integration Considerations

For Phase 3 (Direct Lodgement):

1. **Digital Service Provider (DSP) Registration**
   - Apply to ATO's Software Developers Program
   - Meet security, privacy, operational requirements
   - Obtain DSP credentials

2. **Practitioner Lodgment Service (PLS)**
   - Implement SBR (Standard Business Reporting) protocols
   - Support XBRL format for BAS
   - Handle ATO authentication via Access Manager

3. **Compliance Requirements**
   - Maintain audit logs for 7 years
   - Support ATO data requests
   - Implement lodgement receipt storage

**MVP Approach:** Export BAS worksheets (PDF/Excel) for manual lodgement via existing tools (Xero Tax, LodgeiT) to avoid DSP certification overhead.

---

## 5. AI/ML Architecture

### 5.1 LLM Usage Patterns

**Prohibited Uses (Per Xero API Terms):**
- Training ML models on client accounting data retrieved via API
- Creating derivative datasets for model training

**Permitted Uses:**
- Pre-trained LLMs for analysis and recommendations
- Zero-shot and few-shot prompting with client data in context
- Reasoning over data without persistent storage for training

### 5.2 Agent Framework: LangGraph

```python
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from typing import TypedDict, Annotated, Sequence
import operator

class AgentState(TypedDict):
    """Shared state across agents"""
    client_id: str
    period: str
    transactions: List[dict]
    quality_score: int
    issues: List[dict]
    bas_draft: dict
    messages: Annotated[Sequence[str], operator.add]
    next_agent: str

def create_bas_workflow():
    """
    Build multi-agent workflow using LangGraph
    """
    workflow = StateGraph(AgentState)

    # Add agent nodes
    workflow.add_node("sync", data_sync_agent)
    workflow.add_node("quality", quality_assessment_agent)
    workflow.add_node("calculate", bas_calculation_agent)
    workflow.add_node("advisory", advisory_agent)
    workflow.add_node("supervisor", supervisor_agent)

    # Define edges (workflow transitions)
    workflow.add_edge("sync", "quality")
    workflow.add_conditional_edges(
        "quality",
        should_continue_quality,
        {
            "continue": "calculate",
            "block": END  # Stop if blocking issues
        }
    )
    workflow.add_edge("calculate", "advisory")
    workflow.add_edge("advisory", "supervisor")
    workflow.add_edge("supervisor", END)

    # Set entry point
    workflow.set_entry_point("sync")

    return workflow.compile()

def quality_assessment_agent(state: AgentState) -> AgentState:
    """
    Quality agent with LLM reasoning
    """
    llm = ChatOpenAI(model="gpt-4", temperature=0)

    prompt = f"""
    Analyze data quality for client BAS preparation.

    Client ID: {state['client_id']}
    Period: {state['period']}
    Transaction count: {len(state['transactions'])}

    Recent issues from prior periods:
    {get_historical_issues(state['client_id'])}

    Identify:
    1. Missing or incomplete data
    2. Unusual patterns requiring review
    3. Compliance risks

    Respond in JSON format: {{
      "quality_score": 0-100,
      "blocking_issues": [],
      "warnings": []
    }}
    """

    response = llm.invoke(prompt)
    quality_result = parse_json(response.content)

    return {
        **state,
        "quality_score": quality_result["quality_score"],
        "issues": quality_result["blocking_issues"] + quality_result["warnings"],
        "messages": [f"Quality assessment complete: {quality_result['quality_score']}/100"]
    }

def should_continue_quality(state: AgentState) -> str:
    """
    Conditional logic: block workflow if quality too low
    """
    blocking_issues = [i for i in state["issues"] if i["severity"] == "blocking"]
    if blocking_issues or state["quality_score"] < 50:
        return "block"
    return "continue"
```

### 5.3 Human-in-the-Loop Implementation

```python
class HumanApprovalStep:
    """
    Pause workflow for human review and approval
    """

    def __init__(self, workflow_id: str, approval_type: str):
        self.workflow_id = workflow_id
        self.approval_type = approval_type
        self.status = 'pending'
        self.approved_by = None
        self.approved_at = None

    async def request_approval(self, data: dict) -> dict:
        """
        Pause execution and wait for human decision
        """
        # Create approval request in database
        approval = ApprovalRequest.create(
            workflow_id=self.workflow_id,
            type=self.approval_type,
            data=data,
            status='pending'
        )

        # Notify assigned accountant
        await self.notify_accountant(approval)

        # Wait for approval (async, non-blocking)
        # Workflow resumes when approval record updated
        return await self.wait_for_decision(approval.id)

    async def wait_for_decision(self, approval_id: str) -> dict:
        """
        Poll database for approval decision
        """
        while True:
            approval = ApprovalRequest.get(approval_id)

            if approval.status == 'approved':
                return {
                    'approved': True,
                    'modifications': approval.modifications,
                    'approved_by': approval.approved_by
                }

            elif approval.status == 'rejected':
                return {
                    'approved': False,
                    'reason': approval.rejection_reason
                }

            await asyncio.sleep(5)  # Poll every 5 seconds
```

### 5.4 Model Selection Strategy

| Use Case | Model | Reasoning |
|----------|-------|-----------|
| **Quality Analysis** | GPT-4 Turbo | Complex reasoning over financial data |
| **Variance Explanation** | GPT-4 Turbo | Nuanced understanding of business context |
| **Advisory Insights** | GPT-4 Turbo | Strategic recommendations require depth |
| **Data Classification** | GPT-3.5 Turbo | Simple categorization tasks, faster/cheaper |
| **Document Parsing** | GPT-4 Vision | Extract data from PDF/image documents |
| **Embeddings** | text-embedding-3-large | Semantic search across historical data |

**Cost Management:**
- Use GPT-3.5 Turbo for routine tasks (50x cheaper than GPT-4)
- Cache frequently used prompts and responses
- Implement request deduplication

---

## 6. Security Architecture

### 6.1 Authentication & Authorization

#### Authentication Flow

```
┌──────────────────────────────────────────────────────────┐
│           Multi-Provider Authentication                   │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Supported Auth Providers (OAuth 2.0 / OIDC)    │    │
│  │                                                  │    │
│  │  - Google Workspace                             │    │
│  │  - Microsoft Entra ID (Azure AD)                │    │
│  │  - Xero (for seamless onboarding)               │    │
│  │  - Email/Password (with MFA)                    │    │
│  │                                                  │    │
│  └─────────────────┬───────────────────────────────┘    │
│                    │                                     │
│                    ▼                                     │
│  ┌─────────────────────────────────────────────────┐    │
│  │         JWT Token Issuance                      │    │
│  │                                                  │    │
│  │  {                                               │    │
│  │    "sub": "user-uuid",                          │    │
│  │    "tenant_id": "tenant-uuid",                  │    │
│  │    "role": "accountant",                        │    │
│  │    "permissions": ["read:clients",              │    │
│  │                    "write:bas"],                │    │
│  │    "exp": 1735689600                            │    │
│  │  }                                               │    │
│  │                                                  │    │
│  │  Signing: RS256 with rotated keys               │    │
│  │  Expiry: 1 hour (refresh token: 30 days)        │    │
│  │                                                  │    │
│  └─────────────────────────────────────────────────┘    │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

#### Role-Based Access Control (RBAC)

```python
from enum import Enum

class Role(Enum):
    OWNER = "owner"            # Tenant owner, full access
    ADMIN = "admin"            # Manage users, settings
    ACCOUNTANT = "accountant"  # Full BAS workflow access
    REVIEWER = "reviewer"      # Review-only access
    CLIENT = "client"          # Limited client portal access

PERMISSIONS = {
    Role.OWNER: [
        "tenant:manage",
        "users:manage",
        "clients:*",
        "bas:*",
        "billing:manage"
    ],
    Role.ADMIN: [
        "users:manage",
        "clients:*",
        "bas:*"
    ],
    Role.ACCOUNTANT: [
        "clients:read",
        "clients:write",
        "bas:read",
        "bas:write",
        "bas:approve"
    ],
    Role.REVIEWER: [
        "clients:read",
        "bas:read"
    ],
    Role.CLIENT: [
        "clients:read_own",
        "bas:read_own"
    ]
}

def check_permission(user: User, permission: str, resource_id: str) -> bool:
    """
    Check if user has permission to access resource
    """
    # Check role-based permissions
    user_permissions = PERMISSIONS.get(user.role, [])

    # Wildcard match
    if permission in user_permissions or f"{permission.split(':')[0]}:*" in user_permissions:
        # Additional check: ensure user's tenant matches resource tenant
        resource = get_resource(resource_id)
        if resource.tenant_id != user.tenant_id:
            return False
        return True

    return False
```

### 6.2 Encryption Strategy

#### Data at Rest

```python
# Field-level encryption for sensitive data
ENCRYPTED_FIELDS = [
    'clients.abn',
    'clients.ledger_tenant_id',
    'oauth_tokens.access_token',
    'oauth_tokens.refresh_token',
    'transactions.description'  # May contain sensitive info
]

# Database-level encryption
# PostgreSQL: Enable Transparent Data Encryption (TDE)
# Or use AWS RDS encryption with KMS
```

#### Data in Transit

- **TLS 1.3** for all API connections
- **Certificate pinning** for mobile apps
- **HSTS** (HTTP Strict Transport Security) headers

### 6.3 Audit Logging

Every sensitive action generates an immutable audit log entry:

```python
@dataclass
class AuditLog:
    id: UUID
    tenant_id: UUID
    timestamp: datetime
    event_type: str  # 'BAS_APPROVED', 'CLIENT_CREATED', etc.
    actor_id: UUID
    actor_ip: str
    resource_type: str
    resource_id: UUID
    action: str  # 'CREATE', 'READ', 'UPDATE', 'DELETE'
    before_state: dict | None
    after_state: dict | None
    metadata: dict

# Example: Log BAS approval
audit_logger.log(
    event_type='BAS_APPROVED',
    actor_id=current_user.id,
    actor_ip=request.remote_addr,
    resource_type='bas_period',
    resource_id=bas_period.id,
    action='APPROVE',
    before_state={'status': 'review'},
    after_state={'status': 'approved'},
    metadata={'client_id': client.id, 'period': 'Q2-2025'}
)
```

### 6.4 Compliance Certifications Roadmap

| Certification | Timeline | Requirements |
|--------------|----------|--------------|
| **SOC 2 Type I** | Month 6-9 | Security controls documented and tested |
| **SOC 2 Type II** | Month 12-18 | Operating effectiveness over 6+ months |
| **ISO 27001** | Month 18-24 | Information security management system (ISMS) |
| **ATO DSP** | Month 12+ | Digital Service Provider certification for lodgement |

---

## 7. Infrastructure

### 7.1 Cloud Platform: AWS

**Rationale:**
- Mature multi-tenant SaaS support (AWS SaaS Factory)
- Comprehensive security services (KMS, Secrets Manager, CloudTrail)
- Australian data residency (Sydney ap-southeast-2 region)
- PostgreSQL RDS with automated backups
- Strong compliance certifications (SOC 2, ISO 27001, IRAP)

### 7.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          AWS Cloud                               │
│                     Region: ap-southeast-2                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              CloudFront CDN                             │    │
│  │  (Static assets, edge caching)                         │    │
│  └─────────────────────┬──────────────────────────────────┘    │
│                        │                                        │
│  ┌─────────────────────▼──────────────────────────────────┐    │
│  │         Application Load Balancer (ALB)                │    │
│  │  - SSL/TLS termination                                 │    │
│  │  - WAF (Web Application Firewall)                      │    │
│  └─────────┬───────────────────────┬──────────────────────┘    │
│            │                       │                            │
│  ┌─────────▼────────┐    ┌─────────▼────────┐                 │
│  │  ECS Fargate     │    │  ECS Fargate     │                 │
│  │  (Web/API)       │    │  (Workers)       │                 │
│  │                  │    │                  │                 │
│  │  - Auto-scaling  │    │  - Sync jobs     │                 │
│  │  - Multi-AZ      │    │  - Agent tasks   │                 │
│  └────────┬─────────┘    └────────┬─────────┘                 │
│           │                       │                            │
│           ├───────────────────────┴──────────┐                │
│           │                                   │                │
│  ┌────────▼──────────┐          ┌────────────▼──────────┐    │
│  │  RDS PostgreSQL   │          │  ElastiCache Redis    │    │
│  │  - Multi-AZ       │          │  - Session storage    │    │
│  │  - Encrypted      │          │  - Rate limit cache   │    │
│  │  - Auto backup    │          │  - Agent state        │    │
│  └───────────────────┘          └───────────────────────┘    │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │               S3 Buckets                             │    │
│  │  - clairo-documents (encrypted)                     │    │
│  │  - clairo-audit-logs (WORM, 7yr retention)          │    │
│  │  - clairo-backups                                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │          Security Services                           │    │
│  │                                                       │    │
│  │  - AWS KMS (per-tenant encryption keys)              │    │
│  │  - Secrets Manager (API keys, DB credentials)        │    │
│  │  - CloudTrail (audit logging)                        │    │
│  │  - GuardDuty (threat detection)                      │    │
│  │                                                       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │          Monitoring & Observability                  │    │
│  │                                                       │    │
│  │  - CloudWatch (metrics, logs)                        │    │
│  │  - X-Ray (distributed tracing)                       │    │
│  │  - SNS (alerts)                                      │    │
│  │                                                       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 Deployment Strategy

**Containerized Microservices (Docker + ECS Fargate):**

```yaml
# docker-compose.yml (development)
version: '3.8'

services:
  api:
    build: ./services/api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/clairo
      - REDIS_URL=redis://cache:6379
      - XERO_CLIENT_ID=${XERO_CLIENT_ID}
      - XERO_CLIENT_SECRET=${XERO_CLIENT_SECRET}
    depends_on:
      - db
      - cache

  worker:
    build: ./services/worker
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/clairo
      - REDIS_URL=redis://cache:6379
    depends_on:
      - db
      - cache

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=clairo
      - POSTGRES_PASSWORD=password

  cache:
    image: redis:7-alpine
```

**CI/CD Pipeline (GitHub Actions):**

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          docker-compose -f docker-compose.test.yml up --abort-on-container-exit

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-region: ap-southeast-2

      - name: Login to Amazon ECR
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build and push API image
        run: |
          docker build -t clairo-api:${{ github.sha }} ./services/api
          docker tag clairo-api:${{ github.sha }} $ECR_REGISTRY/clairo-api:latest
          docker push $ECR_REGISTRY/clairo-api:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster clairo-production \
            --service clairo-api \
            --force-new-deployment
```

### 7.4 Scaling Strategy

| Component | Scaling Approach | Trigger |
|-----------|-----------------|---------|
| **API Servers** | Horizontal (ECS Auto Scaling) | CPU > 70% or request latency > 500ms |
| **Worker Processes** | Horizontal (ECS Auto Scaling) | Queue depth > 100 jobs |
| **Database** | Vertical (RDS instance resize) + Read Replicas | CPU > 80% sustained |
| **Cache** | Horizontal (Redis Cluster) | Memory utilization > 75% |

**Capacity Planning:**
- **MVP (50 firms, ~2,500 clients):** Single RDS instance (db.t3.large), 2-4 API containers
- **Growth (200 firms, ~10,000 clients):** RDS Multi-AZ (db.r5.xlarge), read replicas, 10+ API containers
- **Scale (1000+ firms):** RDS Aurora PostgreSQL cluster, Redis Cluster, 50+ containers

---

## 8. Technology Stack

### 8.1 Backend

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **API Framework** | FastAPI (Python) | Async support, auto-generated OpenAPI docs, type safety |
| **Worker Queue** | Celery + Redis | Distributed task execution for sync jobs |
| **ORM** | SQLAlchemy 2.0 | Mature PostgreSQL support, async queries |
| **Validation** | Pydantic v2 | Type-safe data validation, JSON schema generation |
| **LLM Framework** | LangChain + LangGraph | Multi-agent orchestration, pre-built integrations |
| **Testing** | pytest + pytest-asyncio | Comprehensive async testing support |

**Alternative Considered:** Node.js (TypeScript) - Rejected due to weaker data science ecosystem for quality scoring algorithms.

### 8.2 Frontend

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Framework** | Next.js 14 (React) | Server-side rendering, API routes, TypeScript support |
| **UI Components** | shadcn/ui + Tailwind CSS | Accessible, customizable, modern design system |
| **State Management** | TanStack Query + Zustand | Server state (TanStack), client state (Zustand) |
| **Forms** | React Hook Form + Zod | Type-safe form validation |
| **Charts** | Recharts | Financial data visualization |
| **Mobile** | React Native (Phase 2) | Code sharing with web app |

### 8.3 Database

**Primary:** PostgreSQL 15
- JSON columns for flexible metadata storage
- Row-level security for multi-tenancy
- Full-text search capabilities

**Schema Example:**

```sql
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id),
    source_system VARCHAR(20) NOT NULL,  -- 'xero', 'myob', 'qbo'
    source_id VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- 'invoice', 'bill', 'payment'
    date DATE NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    tax_amount NUMERIC(15, 2),
    tax_type VARCHAR(50),
    account_code VARCHAR(50),
    contact_id UUID,
    description TEXT,
    reconciled BOOLEAN DEFAULT FALSE,
    metadata JSONB,  -- Flexible storage for platform-specific fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_source_txn UNIQUE(client_id, source_system, source_id)
);

CREATE INDEX idx_transactions_client_date ON transactions(client_id, date);
CREATE INDEX idx_transactions_metadata ON transactions USING GIN(metadata);
```

### 8.4 Infrastructure as Code

**Terraform** for AWS resource provisioning:

```hcl
# terraform/main.tf
resource "aws_ecs_cluster" "clairo" {
  name = "clairo-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_db_instance" "postgres" {
  identifier           = "clairo-${var.environment}"
  engine              = "postgres"
  engine_version      = "15.3"
  instance_class      = var.db_instance_class
  allocated_storage   = 100
  storage_encrypted   = true
  kms_key_id          = aws_kms_key.database.arn

  db_name  = "clairo"
  username = var.db_username
  password = var.db_password

  multi_az               = var.environment == "production"
  backup_retention_period = 30
  backup_window          = "03:00-04:00"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
```

---

## 9. API Design

### 9.1 REST vs GraphQL

**Decision:** Hybrid Approach
- **REST** for core CRUD operations (simple, cacheable)
- **GraphQL** for complex dashboard queries (reduce over-fetching)

### 9.2 Key REST Endpoints

```
Authentication
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

OAuth Integrations
GET    /api/v1/integrations/xero/authorize
GET    /api/v1/integrations/xero/callback
POST   /api/v1/integrations/xero/disconnect
GET    /api/v1/integrations/myob/authorize

Clients
GET    /api/v1/clients
POST   /api/v1/clients
GET    /api/v1/clients/{id}
PUT    /api/v1/clients/{id}
DELETE /api/v1/clients/{id}
POST   /api/v1/clients/{id}/sync        # Trigger manual sync

BAS Periods
GET    /api/v1/clients/{id}/bas-periods
POST   /api/v1/clients/{id}/bas-periods
GET    /api/v1/bas-periods/{id}
PUT    /api/v1/bas-periods/{id}
POST   /api/v1/bas-periods/{id}/submit   # Submit for review
POST   /api/v1/bas-periods/{id}/approve
POST   /api/v1/bas-periods/{id}/reject
GET    /api/v1/bas-periods/{id}/worksheet.pdf

Data Quality
GET    /api/v1/clients/{id}/quality-score
GET    /api/v1/clients/{id}/quality-issues
POST   /api/v1/quality-issues/{id}/resolve

Workflows
GET    /api/v1/workflows
GET    /api/v1/workflows/{id}
GET    /api/v1/workflows/{id}/events     # Audit trail

Dashboard
GET    /api/v1/dashboard/pipeline        # All clients' BAS status
GET    /api/v1/dashboard/alerts          # Upcoming deadlines, blockers
```

### 9.3 GraphQL Schema (Dashboard Queries)

```graphql
type Query {
  dashboard: Dashboard!
  client(id: ID!): Client!
  basWorkflow(id: ID!): BASWorkflow!
}

type Dashboard {
  clients(status: ClientStatus, search: String): [ClientSummary!]!
  upcomingDeadlines(daysAhead: Int = 30): [Deadline!]!
  qualityAlerts(severity: Severity): [QualityAlert!]!
  portfolioMetrics: PortfolioMetrics!
}

type ClientSummary {
  id: ID!
  name: String!
  abn: String!
  currentPeriod: BASPeriod
  qualityScore: Int!
  status: ClientStatus!
  daysUntilDue: Int
}

type BASPeriod {
  id: ID!
  period: String!
  status: WorkflowStatus!
  qualityScore: Int!
  issues: [QualityIssue!]!
  basData: BASData
}

type BASData {
  g1: Decimal!
  g2: Decimal!
  g3: Decimal!
  g10: Decimal!
  g11: Decimal!
  label1A: Decimal!
  label1B: Decimal!
  label7: Decimal!
  w1: Decimal
  w2: Decimal
  w5: Decimal
}

enum WorkflowStatus {
  DRAFT
  REVIEW
  APPROVED
  REJECTED
  LODGED
  COMPLETED
}
```

### 9.4 API Versioning Strategy

- **URL-based versioning:** `/api/v1/...`, `/api/v2/...`
- **Deprecation policy:** 12 months notice before removal
- **Backward compatibility:** Additive changes only within major version

### 9.5 Rate Limiting

```python
from fastapi import Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/v1/clients")
@limiter.limit("100/minute")  # Per IP address
async def list_clients(request: Request):
    # Endpoint logic
    pass

# Tenant-level rate limiting
@app.get("/api/v1/clients/{id}/sync")
@limiter.limit("10/hour", key_func=get_tenant_id)
async def sync_client(client_id: str, request: Request):
    # Prevent excessive sync requests
    pass
```

---

## 10. Non-Functional Requirements

### 10.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Response Time (p95)** | < 500ms | CloudWatch metrics |
| **Dashboard Load Time** | < 2 seconds | Real User Monitoring (RUM) |
| **Sync Job Completion** | < 5 minutes for 1000 transactions | Worker queue metrics |
| **BAS Calculation** | < 10 seconds for quarterly period | Application instrumentation |
| **Concurrent Users** | 500+ simultaneous users | Load testing |

### 10.2 Availability Targets

| Tier | Uptime SLA | Allowed Downtime/Month |
|------|-----------|------------------------|
| **Starter** | 99.5% | ~3.6 hours |
| **Professional** | 99.9% | ~43 minutes |
| **Enterprise** | 99.95% | ~21 minutes |

**Strategies:**
- Multi-AZ database deployment
- Auto-scaling compute instances
- Health checks and automated recovery
- Scheduled maintenance windows (Sunday 2-4am AEST)

### 10.3 Data Retention & Backup

| Data Type | Retention Period | Backup Frequency |
|-----------|------------------|------------------|
| **Transactions** | 7 years (ATO requirement) | Daily incremental, weekly full |
| **Audit Logs** | 7 years (permanent) | Real-time to S3 (WORM) |
| **BAS Worksheets** | 7 years | Immutable S3 storage |
| **User Sessions** | 30 days | Redis persistence |

**Disaster Recovery:**
- **RTO (Recovery Time Objective):** 4 hours
- **RPO (Recovery Point Objective):** 1 hour (max data loss)
- **Backup Testing:** Quarterly restore drills

### 10.4 Scalability Projections

| Metric | MVP (6 months) | Growth (12 months) | Scale (24 months) |
|--------|----------------|--------------------|--------------------|
| **Firms** | 50 | 200 | 1,000 |
| **Clients** | 2,500 | 10,000 | 50,000 |
| **Monthly API Calls** | 500K | 2M | 10M |
| **Database Size** | 50 GB | 200 GB | 1 TB |
| **Infrastructure Cost** | $2K/month | $8K/month | $40K/month |

---

## Appendix: ASCII Diagrams

### Multi-Agent Interaction Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                   BAS Preparation Workflow                        │
└──────────────────────────────────────────────────────────────────┘

User: "Prepare BAS for ABC Pty Ltd Q2 2025"
  │
  ▼
┌─────────────────────┐
│ Supervisor Agent    │
│                     │
│ 1. Parse request    │
│ 2. Route to agents  │
│ 3. Manage state     │
└──────┬──────────────┘
       │
       ├──────────────────────────────────────┐
       │                                      │
       ▼                                      ▼
┌──────────────┐                      ┌──────────────┐
│ Sync Agent   │                      │Quality Agent │
│              │                      │              │
│ Pull latest  │─────── Data ───────►│ Score: 72/100│
│ transactions │                      │ Issues: 2    │
│ from Xero    │                      │              │
└──────┬───────┘                      └──────┬───────┘
       │                                     │
       │                                     │ Blocking issues?
       │                                     │    NO
       │                                     ▼
       │                              ┌──────────────┐
       │                              │  BAS Agent   │
       │                              │              │
       └──────── Context ────────────►│ Calculate:   │
                                      │ G1: $110,000 │
                                      │ 1A: $10,000  │
                                      │ 7: $2,500    │
                                      └──────┬───────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │Human Approval│
                                      │              │
                                      │ Present draft│
                                      │ [Approve]    │
                                      └──────┬───────┘
                                             │
                                             ▼ Approved
                                      ┌──────────────┐
                                      │   Workflow   │
                                      │ State=APPROVED│
                                      │              │
                                      │ Generate PDF │
                                      └──────────────┘
```

---

## Implementation Roadmap

### Phase 1: MVP (Months 1-6)

**Month 1-2: Foundation**
- [ ] AWS infrastructure setup (Terraform)
- [ ] PostgreSQL schema design and migration scripts
- [ ] Authentication system (OAuth providers)
- [ ] Xero OAuth integration (read-only)

**Month 3-4: Core Features**
- [ ] Data sync engine (Xero → internal model)
- [ ] Data quality scoring engine
- [ ] Multi-client dashboard (React/Next.js)
- [ ] Basic BAS calculation module

**Month 5-6: AI & Workflow**
- [ ] LangGraph multi-agent orchestration
- [ ] Quality assessment agent
- [ ] BAS approval workflow
- [ ] Audit trail system

### Phase 2: Intelligence (Months 7-12)

- [ ] MYOB integration
- [ ] Advisory agent (cash flow, benchmarking)
- [ ] Client communication automation
- [ ] Mobile app (React Native)

### Phase 3: Platform (Months 13-18)

- [ ] White-label client portal
- [ ] ATO DSP certification
- [ ] Direct lodgement capability
- [ ] Advanced scenario modeling

---

## Sources

### Xero API & OAuth
- [OAuth 2.0 — Xero Developer](https://developer.xero.com/documentation/guides/oauth2/overview/)
- [The standard authorization code flow — Xero Developer](https://developer.xero.com/documentation/guides/oauth2/auth-flow/)
- [Xero API Examples: Python, JavaScript & Best Practices Guide](https://datasights.co/xero-api-examples/)
- [Mastering Xero API - Essential Design Principles Every Developer Should Know](https://moldstud.com/articles/p-mastering-xero-api-essential-design-principles-every-developer-should-know)
- [Xero Integration Made Easy: Authentication and Accounts Receivable Best Practices](https://www.apideck.com/blog/xero-integration-authentication-and-accounts-receivable-best-practices)

### Multi-Agent AI Architecture
- [The ultimate guide to AI agent architectures in 2025 - DEV Community](https://dev.to/sohail-akbar/the-ultimate-guide-to-ai-agent-architectures-in-2025-2j1c)
- [Building Multi-Agent Architectures → Orchestrating Intelligent Agent Systems | by Akanksha Sinha | Medium](https://medium.com/@akankshasinha247/building-multi-agent-architectures-orchestrating-intelligent-agent-systems-46700e50250b)
- [LangGraph Multi-Agent Orchestration: Complete Framework Guide + Architecture Analysis 2025](https://latenode.com/blog/langgraph-multi-agent-orchestration-complete-framework-guide-architecture-analysis-2025)
- [Microsoft AutoGen: Orchestrating Multi-Agent LLM Systems | Tribe AI](https://www.tribe.ai/applied-ai/microsoft-autogen-orchestrating-multi-agent-llm-systems)
- [LangGraph vs AutoGen: How are These LLM Workflow Orchestration Platforms Different? - ZenML Blog](https://www.zenml.io/blog/langgraph-vs-autogen)

### Multi-Tenant SaaS Security
- [Tenant isolation - SaaS Architecture Fundamentals](https://docs.aws.amazon.com/whitepapers/latest/saas-architecture-fundamentals/tenant-isolation.html)
- [Architecting Secure Multi-Tenant Data Isolation | by Justin Hamade | Medium](https://medium.com/@justhamade/architecting-secure-multi-tenant-data-isolation-d8f36cb0d25e)
- [Designing Multi-tenant SaaS Architecture on AWS: The Complete Guide for 2026](https://www.clickittech.com/software-development/multi-tenant-architecture/)
- [Isolating AWS Resources for a Secure Multi-Tenant SaaS](https://pcg.io/insights/isolating-aws-resources-for-a-secure-multi-tenant-saas/)

### Data Quality Frameworks
- [Data Quality Framework Guide: Components To Implementation](https://www.montecarlodata.com/blog-data-quality-framework/)
- [Data Quality Framework: Best Practices & Tools [2025]](https://lakefs.io/data-quality/data-quality-framework/)
- [Data Quality Framework: The Only Ultimate Guide You'll Need](https://atlan.com/data-quality-framework/)
- [5 Essential Data Quality Steps for Secure Banking & Finance](https://www.numberanalytics.com/blog/essential-data-quality-steps-banking-finance)
- [Financial Data Quality Management: How to Improve It](https://www.dqlabs.ai/blog/how-to-improve-your-financial-data-quality-management/)

---

**Document Status:** Ready for technical review
**Next Steps:**
1. Review with technical stakeholders
2. Validate AWS cost projections
3. Create detailed sprint plans for Phase 1
4. Set up development environment
