# Solution Design Document: ATOtrack

**Version:** 1.0
**Date:** December 2024
**Status:** Draft

---

## Executive Summary

ATOtrack is an AI-powered platform that automatically captures, parses, and manages ATO correspondence for Australian accounting firms. This document outlines the technical architecture, component design, and implementation approach for delivering a secure, scalable, multi-tenant SaaS platform that integrates with practice management tools and leverages AI for document intelligence.

**Core Design Principles:**
- **Integration-native:** Invisible infrastructure that delivers value through existing tools
- **AI-first:** Document intelligence trained specifically on ATO formats and requirements
- **Multi-channel capture:** Meet users where correspondence arrives
- **Human-in-the-loop:** AI processes, accountants validate with full audit trails
- **Zero-disruption:** Additive to existing workflow, not replacement

---

## 1. Architecture Overview

### 1.1 System Context Diagram

```
+------------------------------------------------------------------------------+
|                          External Systems                                     |
+-------------+-------------+-------------+-------------+----------------------+
|             |             |             |             |                      |
|  +----------v------+  +---v--------+  +v-----------+ |  +-----------------+ |
|  |  Email (ATO)    |  |  Gmail/    |  |  Client    | |  |  Practice Mgmt  | |
|  |  @ato.gov.au    |  |  Outlook   |  |  myGov     | |  |  (Karbon, XPM)  | |
|  +----------+------+  +---+--------+  ++-----------+ |  +--------+--------+ |
|             |             |            |             |           |          |
+-------------+-------------+------------+-------------+-----------+----------+
              |             |            |                         |
    +---------v-------------v------------v-------------------------v----------+
    |                          CAPTURE LAYER                                   |
    |  +---------------+  +--------------+  +-------------+  +--------------+ |
    |  | Email Ingest  |  | Browser      |  | Mobile App  |  | Client       | |
    |  | (Mailgun)     |  | Extensions   |  | (React      |  | Portal       | |
    |  | firm@capture  |  | Gmail/       |  |  Native)    |  | (React)      | |
    |  | .atotrack.com |  | Outlook      |  |             |  |              | |
    |  +-------+-------+  +------+-------+  +------+------+  +------+-------+ |
    |          |                 |                 |                |         |
    +----------+-----------------+-----------------+----------------+---------+
               |                 |                 |                |
               +--------+--------+--------+--------+
                        |
    +-------------------v-------------------------------------------------+
    |                       PROCESSING LAYER                               |
    |                                                                      |
    |  +----------------------------------------------------------------+ |
    |  |                    DOCUMENT QUEUE (Redis/SQS)                   | |
    |  +-----------------------------+----------------------------------+ |
    |                                |                                    |
    |  +-----------------------------v----------------------------------+ |
    |  |                    AI PROCESSING ENGINE                        | |
    |  |                                                                | |
    |  |  +----------+  +----------+  +----------+  +---------------+  | |
    |  |  |   OCR    |  | Document |  | Entity   |  | Deadline      |  | |
    |  |  | (Google  |  | Classify |  | Extract  |  | Calculator    |  | |
    |  |  |  Vision) |  | (GPT-4)  |  | (NER)    |  |               |  | |
    |  |  +----------+  +----------+  +----------+  +---------------+  | |
    |  |                                                                | |
    |  |  +----------+  +----------+  +----------+                     | |
    |  |  | Client   |  | Risk     |  | Action   |                     | |
    |  |  | Matcher  |  | Scorer   |  | Extractor|                     | |
    |  |  | (Fuzzy)  |  |          |  |          |                     | |
    |  |  +----------+  +----------+  +----------+                     | |
    |  +----------------------------------------------------------------+ |
    |                                                                      |
    +----------------------------+----------------------------------------+
                                 |
    +----------------------------v----------------------------------------+
    |                       APPLICATION LAYER                              |
    |                                                                      |
    |  +----------------------------------------------------------------+ |
    |  |                    API (FastAPI / Python)                       | |
    |  |                                                                 | |
    |  |  +------------------+  +------------------+  +----------------+ | |
    |  |  | Correspondence   |  | Client           |  | User           | | |
    |  |  | Service          |  | Service          |  | Service        | | |
    |  |  +------------------+  +------------------+  +----------------+ | |
    |  |                                                                 | |
    |  |  +------------------+  +------------------+  +----------------+ | |
    |  |  | Integration      |  | Reporting        |  | Template       | | |
    |  |  | Orchestrator     |  | Service          |  | Service        | | |
    |  |  +------------------+  +------------------+  +----------------+ | |
    |  +----------------------------------------------------------------+ |
    |                                                                      |
    +----------------------------+----------------------------------------+
                                 |
    +----------------------------v----------------------------------------+
    |                       INTEGRATION LAYER                              |
    |                                                                      |
    |  +----------+  +----------+  +----------+  +----------+             |
    |  | Karbon   |  | XPM      |  | FYI Docs |  | Calendar |             |
    |  | API      |  | API      |  | API      |  | API      |             |
    |  +----------+  +----------+  +----------+  +----------+             |
    |                                                                      |
    |  +----------+  +----------+  +----------+  +----------+             |
    |  | Slack    |  | Teams    |  | Email    |  | Zapier/  |             |
    |  | API      |  | API      |  | (Send)   |  | Make     |             |
    |  +----------+  +----------+  +----------+  +----------+             |
    |                                                                      |
    +----------------------------+----------------------------------------+
                                 |
    +----------------------------v----------------------------------------+
    |                         DATA LAYER                                   |
    |                                                                      |
    |  +----------------+  +-------------+  +---------------------------+ |
    |  | PostgreSQL     |  | Redis       |  | S3 / Cloud Storage        | |
    |  | (Multi-tenant) |  | (Cache/     |  | (Original documents,      | |
    |  |                |  |  Queue)     |  |  OCR output, audit logs)  | |
    |  +----------------+  +-------------+  +---------------------------+ |
    |                                                                      |
    +---------------------------------------------------------------------+
                                 |
    +----------------------------v----------------------------------------+
    |                      CLIENT APPLICATIONS                             |
    |                                                                      |
    |  +----------------+  +----------------+  +-------------------------+ |
    |  | Web Dashboard  |  | Mobile App     |  | Browser Extensions      | |
    |  | (React)        |  | (React Native) |  | (Gmail/Outlook)         | |
    |  +----------------+  +----------------+  +-------------------------+ |
    |                                                                      |
    +---------------------------------------------------------------------+
```

### 1.2 Design Principles

| Principle | Implementation Approach |
|-----------|------------------------|
| **Integration-Native** | Deliver value through existing tools (Karbon, XPM); dashboard is optional |
| **AI Moat** | Custom training on ATO document formats; continuous learning from corrections |
| **Multi-Channel Capture** | Email forwarding, browser add-ins, mobile app, client portal |
| **Human-in-the-Loop** | AI processes automatically; accountants validate flagged items |
| **Audit Trail First** | Immutable log of all captures, processing decisions, and actions |
| **Zero-Trust Security** | Per-tenant isolation; encryption at rest and in transit |
| **Data Sovereignty** | All data stored in Australia (AWS Sydney) |
| **Fail-Safe Processing** | Conservative automation; flag low-confidence items for review |

---

## 2. Core Components

### 2.1 Capture Layer

#### Purpose
Capture ATO correspondence from multiple channels with minimal friction for accountants. The goal is "zero-click capture" where possible.

#### 2.1.1 Email Forwarding Service

**Architecture:**
```
+--------------------+     +------------------+     +------------------+
| ATO sends email    | --> | Firm's email     | --> | Forward rule     |
| to accountant      |     | inbox            |     | to ATOtrack      |
+--------------------+     +------------------+     +------------------+
                                                            |
                                                            v
+--------------------+     +------------------+     +------------------+
| Document Queue     | <-- | Email Parser     | <-- | Mailgun Inbound  |
| (Redis/SQS)        |     | (attachments,    |     | Webhook          |
|                    |     |  body, metadata) |     | firm@capture...  |
+--------------------+     +------------------+     +------------------+
```

**Email Parser Implementation:**
```python
class EmailParser:
    """Parse inbound emails from Mailgun webhook"""

    def parse(self, webhook_data: dict) -> ParsedEmail:
        return ParsedEmail(
            firm_id=self._extract_firm_id(webhook_data['recipient']),
            sender=webhook_data['from'],
            subject=webhook_data['subject'],
            body_plain=webhook_data.get('body-plain'),
            body_html=webhook_data.get('body-html'),
            attachments=self._process_attachments(webhook_data),
            received_at=datetime.utcnow(),
            message_id=webhook_data['Message-Id'],
            is_ato_source=self._verify_ato_source(webhook_data)
        )

    def _verify_ato_source(self, data: dict) -> bool:
        """Verify email originates from ATO"""
        sender = data.get('from', '').lower()
        ato_domains = ['@ato.gov.au', '@ato.com.au', '@online.ato.gov.au']
        return any(domain in sender for domain in ato_domains)

    def _process_attachments(self, data: dict) -> List[Attachment]:
        """Extract and store attachments"""
        attachments = []
        for att in data.get('attachments', []):
            stored_path = self._store_to_s3(att['content'], att['name'])
            attachments.append(Attachment(
                filename=att['name'],
                content_type=att['content-type'],
                size=att['size'],
                storage_path=stored_path
            ))
        return attachments
```

**Configuration:**
```yaml
email_capture:
  provider: mailgun
  domain: capture.atotrack.com.au
  webhook_path: /api/v1/email/inbound
  webhook_auth: hmac_signature

  firm_inbox_format: "{firm_slug}@capture.atotrack.com.au"

  filtering:
    verify_ato_source: true
    allowed_senders:
      - "*@ato.gov.au"
      - "*@online.ato.gov.au"

  storage:
    bucket: atotrack-documents
    path_format: "{firm_id}/{year}/{month}/{document_id}"
```

#### 2.1.2 Gmail Add-in

**Architecture:**
```
+--------------------+     +------------------+     +------------------+
| User clicks        | --> | Gmail Add-in     | --> | ATOtrack API     |
| "Send to ATOtrack" |     | extracts email   |     | /capture/email   |
+--------------------+     +------------------+     +------------------+
```

**Google Workspace Add-on Manifest:**
```json
{
  "oauthScopes": [
    "https://www.googleapis.com/auth/gmail.addons.current.message.readonly",
    "https://www.googleapis.com/auth/gmail.addons.current.action.compose"
  ],
  "gmail": {
    "contextualTriggers": [{
      "unconditional": {},
      "onTriggerFunction": "buildAddOn"
    }],
    "composeTrigger": {
      "selectActions": [{
        "text": "Send to ATOtrack",
        "runFunction": "captureEmail"
      }]
    }
  }
}
```

**Add-in Action Handler:**
```javascript
function captureEmail(e) {
  const message = GmailApp.getMessageById(e.gmail.messageId);
  const accessToken = getATOtrackToken(); // OAuth flow

  const payload = {
    messageId: message.getId(),
    subject: message.getSubject(),
    from: message.getFrom(),
    body: message.getPlainBody(),
    attachments: message.getAttachments().map(att => ({
      name: att.getName(),
      contentType: att.getContentType(),
      content: Utilities.base64Encode(att.getBytes())
    })),
    capturedAt: new Date().toISOString()
  };

  const response = UrlFetchApp.fetch('https://api.atotrack.com.au/v1/capture/email', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    payload: JSON.stringify(payload)
  });

  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification()
      .setText('Sent to ATOtrack for processing'))
    .build();
}
```

#### 2.1.3 Mobile Capture App

**Purpose:** Capture physical ATO letters by photographing them with smartphone.

**Tech Stack:**
- React Native (iOS and Android)
- Camera integration with document detection
- Offline-first with background sync

**Core Features:**
```typescript
interface MobileCaptureFeatures {
  // Document scanning
  cameraCapture: {
    autoEdgeDetection: boolean;      // Detect document boundaries
    autoCapture: boolean;            // Snap when steady
    multiPageMode: boolean;          // Capture multiple pages
    flashControl: boolean;
  };

  // Image processing
  imageProcessing: {
    perspectiveCorrection: boolean;  // Fix skewed captures
    contrastEnhancement: boolean;    // Improve readability
    compressionQuality: number;      // Balance quality/size (0.7-0.9)
  };

  // Offline support
  offlineMode: {
    localStorage: boolean;           // Store captures locally
    backgroundSync: boolean;         // Sync when online
    queuedCaptures: number;          // Max offline queue
  };

  // Quick actions
  quickCapture: {
    clientSearch: boolean;           // Quick client selection
    noteTaking: boolean;             // Add context notes
    urgencyFlag: boolean;            // Mark as urgent
  };
}
```

**Mobile Capture Flow:**
```
+------------------+     +------------------+     +------------------+
| Open App         | --> | Point camera at  | --> | Auto-detect      |
|                  |     | document         |     | edges            |
+------------------+     +------------------+     +------------------+
                                                          |
+------------------+     +------------------+     +--------v---------+
| Queue for        | <-- | Select client    | <-- | Capture &        |
| processing       |     | (optional)       |     | enhance image    |
+------------------+     +------------------+     +------------------+
```

#### 2.1.4 Client Portal

**Purpose:** Allow clients to forward ATO correspondence they receive directly (myGov notifications, physical mail they've scanned).

**Architecture:**
```
+--------------------+     +------------------+     +------------------+
| Client receives    | --> | Logs into firm's | --> | Uploads document |
| ATO notice         |     | branded portal   |     | or enters details|
+--------------------+     +------------------+     +------------------+
                                                            |
                                                            v
+--------------------+     +------------------+     +------------------+
| Queued for         | <-- | Client auto-     | <-- | Document stored  |
| AI processing      |     | matched          |     | in S3            |
+--------------------+     +------------------+     +------------------+
```

**Client Portal Routes:**
```typescript
// Client-facing routes (white-label branded)
const clientPortalRoutes = {
  // Public routes
  '/portal/:firmSlug': 'PortalLanding',
  '/portal/:firmSlug/login': 'ClientLogin',

  // Authenticated routes
  '/portal/:firmSlug/upload': 'DocumentUpload',
  '/portal/:firmSlug/history': 'SubmissionHistory',
  '/portal/:firmSlug/settings': 'ClientSettings'
};

// Upload component
interface DocumentUploadProps {
  acceptedFormats: ['.pdf', '.png', '.jpg', '.heic'];
  maxFileSize: '10MB';
  multipleFiles: true;
  requiredFields: ['documentType'];  // Optional client selection
  optionalFields: ['notes', 'urgency'];
}
```

---

### 2.2 AI Processing Engine

#### Purpose
Transform raw captured documents into structured, actionable data using AI/ML pipelines.

#### 2.2.1 Processing Pipeline

```
+------------------+     +------------------+     +------------------+
| Raw Document     | --> | OCR (if needed)  | --> | Text Extraction  |
| (PDF/Image)      |     | Google Vision    |     |                  |
+------------------+     +------------------+     +------------------+
                                                          |
+------------------+     +------------------+     +--------v---------+
| Structured       | <-- | GPT-4 Extraction | <-- | Document         |
| Data             |     | (entities, dates)|     | Classification   |
+------------------+     +------------------+     +------------------+
         |
         v
+------------------+     +------------------+     +------------------+
| Client Matching  | --> | Deadline Calc    | --> | Risk Scoring     |
| (ABN fuzzy match)|     | (notice rules)   |     |                  |
+------------------+     +------------------+     +------------------+
         |
         v
+------------------+
| Ready for        |
| Integration      |
| Delivery         |
+------------------+
```

#### 2.2.2 Document Classification

**Notice Type Taxonomy (50+ types):**

```python
class ATONoticeType(Enum):
    # Assessment Notices
    NOTICE_OF_ASSESSMENT_INDIVIDUAL = "noa_individual"
    NOTICE_OF_ASSESSMENT_COMPANY = "noa_company"
    NOTICE_OF_ASSESSMENT_TRUST = "noa_trust"
    NOTICE_OF_ASSESSMENT_PARTNERSHIP = "noa_partnership"
    NOTICE_OF_AMENDED_ASSESSMENT = "amended_assessment"

    # Activity Statements
    ACTIVITY_STATEMENT_BAS = "activity_statement_bas"
    ACTIVITY_STATEMENT_IAS = "activity_statement_ias"
    ACTIVITY_STATEMENT_PAYG = "activity_statement_payg"

    # Debt & Payment
    DEBT_NOTIFICATION = "debt_notification"
    PAYMENT_REMINDER = "payment_reminder"
    PAYMENT_PLAN_PROPOSAL = "payment_plan_proposal"
    PAYMENT_PLAN_CONFIRMATION = "payment_plan_confirmation"
    GARNISHEE_NOTICE = "garnishee_notice"
    DIRECTOR_PENALTY_NOTICE = "director_penalty_notice"

    # Audit & Review
    AUDIT_NOTIFICATION = "audit_notification"
    AUDIT_COMPLETION = "audit_completion"
    POSITION_PAPER = "position_paper"
    INFORMATION_REQUEST = "information_request"
    RECORD_KEEPING_REVIEW = "record_keeping_review"

    # Penalties & Interest
    PENALTY_NOTICE = "penalty_notice"
    PENALTY_REMISSION_DECISION = "penalty_remission_decision"
    INTEREST_CALCULATION = "interest_calculation"

    # Registration
    ABN_REGISTRATION_CONFIRMATION = "abn_registration"
    GST_REGISTRATION_CONFIRMATION = "gst_registration"
    PAYG_REGISTRATION = "payg_registration"
    REGISTRATION_CANCELLATION = "registration_cancellation"

    # Superannuation
    SG_CHARGE_STATEMENT = "sg_charge_statement"
    SUPERSTREAM_NOTICE = "superstream_notice"

    # Refunds
    REFUND_NOTIFICATION = "refund_notification"
    REFUND_OFFSET = "refund_offset"

    # General
    GENERAL_CORRESPONDENCE = "general_correspondence"
    ACKNOWLEDGEMENT = "acknowledgement"
    UNKNOWN = "unknown"
```

**Classification Model:**

```python
from openai import OpenAI

class NoticeClassifier:
    """Classify ATO notice types using GPT-4"""

    SYSTEM_PROMPT = """You are an expert Australian tax document classifier.
    Given the text of an ATO notice, classify it into the most specific notice type.

    Return JSON with:
    - notice_type: one of the predefined types
    - confidence: 0.0-1.0
    - reasoning: brief explanation

    Be conservative - if unsure, use 'general_correspondence' or 'unknown'."""

    def __init__(self):
        self.client = OpenAI()
        self.notice_types = [e.value for e in ATONoticeType]

    async def classify(self, document_text: str) -> ClassificationResult:
        response = await self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Classify this ATO notice:\n\n{document_text[:4000]}"}
            ],
            temperature=0.1  # Low temperature for consistency
        )

        result = json.loads(response.choices[0].message.content)

        return ClassificationResult(
            notice_type=ATONoticeType(result['notice_type']),
            confidence=result['confidence'],
            reasoning=result['reasoning'],
            model_version="gpt-4-turbo-preview",
            classified_at=datetime.utcnow()
        )
```

#### 2.2.3 Entity Extraction

**Extracted Entities:**

```python
@dataclass
class ExtractedEntities:
    # Client identification
    abn: Optional[str]                    # Australian Business Number
    tfn: Optional[str]                    # Tax File Number (masked)
    entity_name: Optional[str]            # Business/individual name
    trading_name: Optional[str]

    # Document reference
    document_id: Optional[str]            # ATO reference number
    lodgement_reference: Optional[str]
    assessment_year: Optional[str]        # e.g., "2023-24"
    period: Optional[str]                 # e.g., "July 2024 quarterly"

    # Financial amounts
    amount_owing: Optional[Decimal]
    amount_payable: Optional[Decimal]
    amount_refundable: Optional[Decimal]
    penalty_amount: Optional[Decimal]
    interest_amount: Optional[Decimal]

    # Dates
    issue_date: Optional[date]
    due_date: Optional[date]
    period_start: Optional[date]
    period_end: Optional[date]
    response_required_by: Optional[date]

    # Contact
    contact_officer: Optional[str]
    contact_phone: Optional[str]
    contact_reference: Optional[str]

    # Actions
    action_required: bool
    action_description: Optional[str]
    response_method: Optional[str]        # e.g., "Online", "Phone", "Written"
```

**Entity Extraction Implementation:**

```python
class EntityExtractor:
    """Extract structured entities from ATO documents using GPT-4"""

    EXTRACTION_PROMPT = """Extract the following entities from this ATO document.
    Return JSON with these fields (null if not found):

    - abn: Australian Business Number (11 digits, format: XX XXX XXX XXX)
    - tfn: Tax File Number (mask middle digits as ***)
    - entity_name: Full legal name of the taxpayer
    - document_id: ATO reference/document number
    - issue_date: Date the notice was issued (YYYY-MM-DD)
    - due_date: Payment or response due date (YYYY-MM-DD)
    - amount_owing: Total amount owing (decimal)
    - action_required: boolean - does this require accountant action?
    - action_description: Brief description of required action

    Be precise. Only extract values explicitly stated in the document."""

    async def extract(self, document_text: str) -> ExtractedEntities:
        response = await self.client.chat.completions.create(
            model="gpt-4-turbo-preview",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.EXTRACTION_PROMPT},
                {"role": "user", "content": document_text[:8000]}
            ],
            temperature=0.0  # Zero temperature for deterministic extraction
        )

        data = json.loads(response.choices[0].message.content)
        return ExtractedEntities(**data)
```

#### 2.2.4 Deadline Calculator

**Deadline Rules Engine:**

```python
class DeadlineCalculator:
    """Calculate response/payment deadlines based on notice type and issue date"""

    # Default deadlines by notice type (in days from issue date)
    DEADLINE_RULES = {
        ATONoticeType.NOTICE_OF_ASSESSMENT_INDIVIDUAL: {
            "default_days": 21,
            "description": "Payment due within 21 days of issue"
        },
        ATONoticeType.AUDIT_NOTIFICATION: {
            "default_days": 28,
            "description": "Initial response required within 28 days"
        },
        ATONoticeType.INFORMATION_REQUEST: {
            "default_days": 28,
            "description": "Information must be provided within 28 days"
        },
        ATONoticeType.DIRECTOR_PENALTY_NOTICE: {
            "default_days": 21,
            "description": "CRITICAL: Directors become personally liable after 21 days"
        },
        ATONoticeType.DEBT_NOTIFICATION: {
            "default_days": 14,
            "description": "Payment arrangement should be made within 14 days"
        },
        ATONoticeType.PENALTY_NOTICE: {
            "default_days": 28,
            "description": "Objection/remission request within 28 days"
        },
        ATONoticeType.ACTIVITY_STATEMENT_BAS: {
            "default_days": 21,
            "description": "Amendment or payment within 21 days"
        }
    }

    def calculate(
        self,
        notice_type: ATONoticeType,
        issue_date: date,
        explicit_due_date: Optional[date] = None
    ) -> DeadlineInfo:
        """Calculate deadline, preferring explicit date if provided"""

        # Use explicit due date from document if available
        if explicit_due_date:
            return DeadlineInfo(
                due_date=explicit_due_date,
                source="document",
                business_days_remaining=self._business_days_until(explicit_due_date),
                urgency=self._calculate_urgency(explicit_due_date)
            )

        # Fall back to rule-based calculation
        rule = self.DEADLINE_RULES.get(notice_type, {
            "default_days": 28,
            "description": "Standard 28-day response period"
        })

        calculated_date = issue_date + timedelta(days=rule["default_days"])

        # Skip weekends/public holidays
        calculated_date = self._adjust_for_business_days(calculated_date)

        return DeadlineInfo(
            due_date=calculated_date,
            source="calculated",
            rule_applied=rule["description"],
            business_days_remaining=self._business_days_until(calculated_date),
            urgency=self._calculate_urgency(calculated_date)
        )

    def _calculate_urgency(self, due_date: date) -> UrgencyLevel:
        days_remaining = (due_date - date.today()).days

        if days_remaining < 0:
            return UrgencyLevel.OVERDUE
        elif days_remaining <= 3:
            return UrgencyLevel.CRITICAL
        elif days_remaining <= 7:
            return UrgencyLevel.HIGH
        elif days_remaining <= 14:
            return UrgencyLevel.MEDIUM
        else:
            return UrgencyLevel.LOW
```

#### 2.2.5 Client Matching

**ABN-Based Fuzzy Matching:**

```python
class ClientMatcher:
    """Match captured documents to firm's client database"""

    def __init__(self, db: Database):
        self.db = db

    async def match(
        self,
        firm_id: str,
        extracted: ExtractedEntities
    ) -> MatchResult:
        """Match document to client using ABN, TFN, or name"""

        # Strategy 1: Exact ABN match (highest confidence)
        if extracted.abn:
            client = await self._match_by_abn(firm_id, extracted.abn)
            if client:
                return MatchResult(
                    client=client,
                    confidence=1.0,
                    match_method="abn_exact"
                )

        # Strategy 2: Exact TFN match (if available and permitted)
        if extracted.tfn:
            client = await self._match_by_tfn(firm_id, extracted.tfn)
            if client:
                return MatchResult(
                    client=client,
                    confidence=0.95,
                    match_method="tfn_exact"
                )

        # Strategy 3: Fuzzy name match
        if extracted.entity_name:
            matches = await self._fuzzy_name_match(
                firm_id,
                extracted.entity_name
            )
            if matches and matches[0].score > 0.85:
                return MatchResult(
                    client=matches[0].client,
                    confidence=matches[0].score,
                    match_method="name_fuzzy",
                    alternatives=matches[1:3]  # Top alternatives
                )

        # No confident match
        return MatchResult(
            client=None,
            confidence=0.0,
            match_method="none",
            requires_manual_assignment=True
        )

    async def _fuzzy_name_match(
        self,
        firm_id: str,
        name: str
    ) -> List[FuzzyMatch]:
        """Use trigram similarity for fuzzy name matching"""

        query = """
            SELECT
                id, entity_name, abn,
                similarity(entity_name, $2) as score
            FROM clients
            WHERE firm_id = $1
            AND similarity(entity_name, $2) > 0.3
            ORDER BY score DESC
            LIMIT 5
        """

        results = await self.db.fetch(query, firm_id, name)
        return [FuzzyMatch(client=r, score=r['score']) for r in results]
```

#### 2.2.6 Risk Scoring

**Risk Assessment Model:**

```python
class RiskScorer:
    """Assess risk level of ATO correspondence"""

    # Base risk scores by notice type
    BASE_RISK_SCORES = {
        ATONoticeType.DIRECTOR_PENALTY_NOTICE: 100,
        ATONoticeType.AUDIT_NOTIFICATION: 90,
        ATONoticeType.GARNISHEE_NOTICE: 95,
        ATONoticeType.PENALTY_NOTICE: 70,
        ATONoticeType.DEBT_NOTIFICATION: 60,
        ATONoticeType.INFORMATION_REQUEST: 50,
        ATONoticeType.NOTICE_OF_ASSESSMENT_INDIVIDUAL: 30,
        ATONoticeType.REFUND_NOTIFICATION: 10,
        ATONoticeType.ACKNOWLEDGEMENT: 5,
    }

    def calculate_risk_score(
        self,
        notice_type: ATONoticeType,
        deadline_info: DeadlineInfo,
        amount: Optional[Decimal],
        client_history: ClientHistory
    ) -> RiskAssessment:
        """Calculate composite risk score (0-100)"""

        base_score = self.BASE_RISK_SCORES.get(notice_type, 40)

        # Urgency multiplier (based on days to deadline)
        urgency_multiplier = {
            UrgencyLevel.OVERDUE: 1.5,
            UrgencyLevel.CRITICAL: 1.3,
            UrgencyLevel.HIGH: 1.1,
            UrgencyLevel.MEDIUM: 1.0,
            UrgencyLevel.LOW: 0.9
        }.get(deadline_info.urgency, 1.0)

        # Amount factor (higher amounts = higher risk)
        amount_factor = 1.0
        if amount and amount > 50000:
            amount_factor = 1.3
        elif amount and amount > 10000:
            amount_factor = 1.1

        # Client history factor (previous issues increase risk)
        history_factor = 1.0
        if client_history.previous_audits > 0:
            history_factor += 0.1
        if client_history.missed_deadlines > 0:
            history_factor += 0.15

        final_score = min(100, base_score * urgency_multiplier * amount_factor * history_factor)

        return RiskAssessment(
            score=round(final_score),
            level=self._score_to_level(final_score),
            factors=[
                f"Notice type: {notice_type.value}",
                f"Urgency: {deadline_info.urgency.value}",
                f"Amount: ${amount}" if amount else "No amount specified"
            ]
        )

    def _score_to_level(self, score: float) -> str:
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"
```

---

### 2.3 Integration Layer

#### Purpose
Deliver processed correspondence data into accountants' existing workflow tools, creating tasks, filing documents, and sending notifications.

#### 2.3.1 Integration Architecture

```
+------------------+     +------------------+     +------------------+
| Processed        | --> | Integration      | --> | Output Handlers  |
| Correspondence   |     | Orchestrator     |     |                  |
+------------------+     +------------------+     +------------------+
                                |
        +-----------------------+------------------------+
        |           |           |           |            |
        v           v           v           v            v
+----------+ +----------+ +----------+ +----------+ +----------+
| Karbon   | | XPM      | | FYI      | | Calendar | | Slack/   |
| Handler  | | Handler  | | Handler  | | Handler  | | Teams    |
+----------+ +----------+ +----------+ +----------+ +----------+
```

#### 2.3.2 Karbon Integration

**API Integration:**

```python
class KarbonIntegration:
    """Integrate with Karbon Practice Management"""

    BASE_URL = "https://api.karbonhq.com/v3"

    def __init__(self, firm_config: FirmIntegrationConfig):
        self.api_key = firm_config.karbon_api_key
        self.firm_id = firm_config.firm_id

    async def create_work_item(
        self,
        correspondence: ProcessedCorrespondence
    ) -> KarbonWorkItem:
        """Create a work item in Karbon for this correspondence"""

        # Map ATOtrack notice type to Karbon work type
        work_type = self._map_work_type(correspondence.notice_type)

        # Find or create contact in Karbon
        contact = await self._ensure_contact(correspondence.client)

        payload = {
            "Title": self._generate_title(correspondence),
            "Description": self._generate_description(correspondence),
            "ClientKey": contact.key,
            "WorkTypeKey": work_type.key,
            "DueDate": correspondence.deadline.due_date.isoformat(),
            "AssigneeEmailAddress": correspondence.assigned_to_email,
            "WorkStatus": "NotStarted",
            "Priority": self._map_priority(correspondence.risk_level),
            "CustomFields": {
                "ATOtrack_ID": correspondence.id,
                "Notice_Type": correspondence.notice_type.value,
                "Amount": str(correspondence.amount_owing or "N/A"),
                "Risk_Score": correspondence.risk_score
            }
        }

        response = await self._post("/Work", payload)

        # Attach document to work item
        if correspondence.document_url:
            await self._attach_document(
                response["WorkKey"],
                correspondence.document_url,
                correspondence.original_filename
            )

        return KarbonWorkItem(
            work_key=response["WorkKey"],
            work_url=f"https://app.karbonhq.com/work/{response['WorkKey']}"
        )

    def _generate_title(self, corr: ProcessedCorrespondence) -> str:
        """Generate descriptive work item title"""
        client_name = corr.client.entity_name[:30] if corr.client else "Unknown Client"
        notice_name = corr.notice_type.value.replace("_", " ").title()
        return f"ATO: {notice_name} - {client_name}"

    def _generate_description(self, corr: ProcessedCorrespondence) -> str:
        """Generate detailed work item description"""
        return f"""
ATO Correspondence captured by ATOtrack

Notice Type: {corr.notice_type.value}
Issue Date: {corr.issue_date}
Due Date: {corr.deadline.due_date}
Risk Level: {corr.risk_level}

{corr.action_description or "Review document for required action."}

Amount: ${corr.amount_owing or "N/A"}
ABN: {corr.abn or "N/A"}
ATO Reference: {corr.document_id or "N/A"}

---
Automatically captured and processed by ATOtrack
Document ID: {corr.id}
        """.strip()
```

#### 2.3.3 Xero Practice Manager Integration

```python
class XPMIntegration:
    """Integrate with Xero Practice Manager"""

    BASE_URL = "https://api.xero.com/practicemanager/3.0"

    async def create_job(
        self,
        correspondence: ProcessedCorrespondence,
        access_token: str
    ) -> XPMJob:
        """Create a job in XPM for this correspondence"""

        client = await self._find_client(correspondence.client.abn)

        payload = {
            "Name": self._generate_job_name(correspondence),
            "ClientUUID": client.uuid,
            "TemplateUUID": self._get_template_uuid(correspondence.notice_type),
            "DueDate": correspondence.deadline.due_date.isoformat(),
            "Description": self._generate_description(correspondence),
            "State": "Planned"
        }

        response = await self._post("/Jobs", payload, access_token)

        # Create task within job
        await self._create_task(
            response["UUID"],
            correspondence,
            access_token
        )

        return XPMJob(
            uuid=response["UUID"],
            job_number=response["JobNumber"]
        )
```

#### 2.3.4 Calendar Integration

```python
class CalendarIntegration:
    """Add deadlines to Google Calendar or Outlook"""

    async def create_deadline_event(
        self,
        correspondence: ProcessedCorrespondence,
        calendar_type: str,  # "google" or "outlook"
        credentials: dict
    ) -> CalendarEvent:
        """Create calendar event for deadline"""

        event_data = {
            "summary": f"ATO Deadline: {correspondence.client.entity_name}",
            "description": self._build_description(correspondence),
            "start": {
                "date": correspondence.deadline.due_date.isoformat()
            },
            "end": {
                "date": correspondence.deadline.due_date.isoformat()
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 1440},   # 1 day before
                    {"method": "popup", "minutes": 60}      # 1 hour before
                ]
            }
        }

        # Add color coding based on risk
        if correspondence.risk_level == "critical":
            event_data["colorId"] = "11"  # Red
        elif correspondence.risk_level == "high":
            event_data["colorId"] = "6"   # Orange

        if calendar_type == "google":
            return await self._create_google_event(event_data, credentials)
        else:
            return await self._create_outlook_event(event_data, credentials)
```

#### 2.3.5 Document Storage Integration (FYI Docs)

```python
class FYIDocsIntegration:
    """File documents in FYI Docs"""

    async def file_document(
        self,
        correspondence: ProcessedCorrespondence,
        credentials: dict
    ) -> FYIDocument:
        """Upload and file document in FYI"""

        # Get document from S3
        document_bytes = await self._get_document_bytes(
            correspondence.storage_path
        )

        # Determine filing location
        cabinet = await self._find_or_create_cabinet(
            correspondence.client.entity_name
        )

        folder = await self._ensure_folder(
            cabinet.id,
            "ATO Correspondence",
            str(correspondence.issue_date.year)
        )

        # Upload document
        uploaded = await self._upload_document(
            folder.id,
            document_bytes,
            correspondence.original_filename,
            metadata={
                "DocumentType": "ATO Correspondence",
                "NoticeType": correspondence.notice_type.value,
                "IssueDate": correspondence.issue_date.isoformat(),
                "ABN": correspondence.abn,
                "Source": "ATOtrack"
            }
        )

        return FYIDocument(
            document_id=uploaded.id,
            document_url=uploaded.web_url
        )
```

#### 2.3.6 Notification Handlers

```python
class NotificationService:
    """Send notifications via multiple channels"""

    async def notify(
        self,
        correspondence: ProcessedCorrespondence,
        firm_config: FirmConfig
    ):
        """Send notifications based on firm preferences"""

        # Email notification
        if firm_config.email_notifications_enabled:
            await self._send_email_notification(
                correspondence,
                firm_config.notification_emails
            )

        # Slack notification
        if firm_config.slack_webhook_url:
            await self._send_slack_notification(
                correspondence,
                firm_config.slack_webhook_url
            )

        # Teams notification
        if firm_config.teams_webhook_url:
            await self._send_teams_notification(
                correspondence,
                firm_config.teams_webhook_url
            )

    async def _send_slack_notification(
        self,
        corr: ProcessedCorrespondence,
        webhook_url: str
    ):
        """Send Slack notification with rich formatting"""

        color = {
            "critical": "#FF0000",
            "high": "#FFA500",
            "medium": "#FFFF00",
            "low": "#00FF00"
        }.get(corr.risk_level, "#808080")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"New ATO Correspondence: {corr.notice_type.value.replace('_', ' ').title()}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Client:* {corr.client.entity_name}"},
                    {"type": "mrkdwn", "text": f"*Due Date:* {corr.deadline.due_date}"},
                    {"type": "mrkdwn", "text": f"*Risk Level:* {corr.risk_level.upper()}"},
                    {"type": "mrkdwn", "text": f"*Amount:* ${corr.amount_owing or 'N/A'}"}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in ATOtrack"},
                        "url": f"https://app.atotrack.com.au/correspondence/{corr.id}"
                    }
                ]
            }
        ]

        await httpx.post(webhook_url, json={
            "attachments": [{"color": color, "blocks": blocks}]
        })
```

---

### 2.4 Data Layer

#### 2.4.1 Database Schema

**Core Tables:**

```sql
-- Firms (tenants)
CREATE TABLE firms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    capture_email VARCHAR(255) UNIQUE NOT NULL,
    subscription_tier VARCHAR(50) NOT NULL DEFAULT 'starter',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row-level security policy
ALTER TABLE firms ENABLE ROW LEVEL SECURITY;

-- Clients (per firm)
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    entity_name VARCHAR(255) NOT NULL,
    trading_name VARCHAR(255),
    abn VARCHAR(11),
    tfn_hash VARCHAR(64),  -- Hashed for matching, never stored plaintext
    entity_type VARCHAR(50),
    contact_email VARCHAR(255),
    assigned_user_id UUID REFERENCES users(id),
    external_ids JSONB DEFAULT '{}',  -- Karbon ID, XPM ID, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT unique_abn_per_firm UNIQUE(firm_id, abn)
);

-- Enable trigram extension for fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_clients_name_trgm ON clients USING gin(entity_name gin_trgm_ops);
CREATE INDEX idx_clients_abn ON clients(abn);
CREATE INDEX idx_clients_firm ON clients(firm_id);

-- Correspondence (captured documents)
CREATE TABLE correspondence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    client_id UUID REFERENCES clients(id),

    -- Capture info
    capture_method VARCHAR(50) NOT NULL,  -- email, gmail_addon, mobile, portal
    capture_source VARCHAR(255),           -- Email address or user ID
    captured_at TIMESTAMPTZ NOT NULL,

    -- Original document
    original_filename VARCHAR(255),
    storage_path VARCHAR(500) NOT NULL,
    file_size_bytes INTEGER,
    mime_type VARCHAR(100),

    -- Processing status
    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_error TEXT,

    -- AI classification
    notice_type VARCHAR(100),
    classification_confidence DECIMAL(3,2),

    -- Extracted entities
    abn VARCHAR(11),
    entity_name VARCHAR(255),
    document_id VARCHAR(100),
    issue_date DATE,
    due_date DATE,
    amount_owing DECIMAL(12,2),
    amount_payable DECIMAL(12,2),
    action_required BOOLEAN DEFAULT false,
    action_description TEXT,

    -- Risk assessment
    risk_score INTEGER,
    risk_level VARCHAR(20),

    -- Workflow status
    workflow_status VARCHAR(50) DEFAULT 'new',  -- new, assigned, in_progress, completed, archived
    assigned_to UUID REFERENCES users(id),
    completed_at TIMESTAMPTZ,

    -- Integration status
    karbon_work_key VARCHAR(100),
    xpm_job_uuid VARCHAR(100),
    fyi_document_id VARCHAR(100),
    calendar_event_id VARCHAR(100),

    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_correspondence_firm ON correspondence(firm_id);
CREATE INDEX idx_correspondence_client ON correspondence(client_id);
CREATE INDEX idx_correspondence_status ON correspondence(workflow_status);
CREATE INDEX idx_correspondence_due_date ON correspondence(due_date);
CREATE INDEX idx_correspondence_notice_type ON correspondence(notice_type);
CREATE INDEX idx_correspondence_captured ON correspondence(captured_at DESC);

-- Row-level security
ALTER TABLE correspondence ENABLE ROW LEVEL SECURITY;
CREATE POLICY correspondence_firm_isolation ON correspondence
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- Processing audit log
CREATE TABLE processing_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correspondence_id UUID NOT NULL REFERENCES correspondence(id) ON DELETE CASCADE,
    step VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Integration sync log
CREATE TABLE integration_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id),
    correspondence_id UUID REFERENCES correspondence(id),
    integration_type VARCHAR(50) NOT NULL,  -- karbon, xpm, fyi, calendar, slack
    action VARCHAR(50) NOT NULL,            -- create, update, delete
    status VARCHAR(50) NOT NULL,            -- success, failed, pending
    request_data JSONB,
    response_data JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2.4.2 Document Storage

**S3 Structure:**

```
atotrack-documents/
├── {firm_id}/
│   ├── {year}/
│   │   ├── {month}/
│   │   │   ├── {correspondence_id}/
│   │   │   │   ├── original.pdf          # Original captured document
│   │   │   │   ├── ocr_output.json       # OCR extraction results
│   │   │   │   ├── thumbnail.png         # Preview thumbnail
│   │   │   │   └── processed.json        # Full processing results
```

**Storage Configuration:**

```python
class DocumentStorage:
    """S3-based document storage with encryption"""

    def __init__(self):
        self.s3 = boto3.client('s3', region_name='ap-southeast-2')
        self.bucket = 'atotrack-documents'

    async def store_document(
        self,
        firm_id: str,
        correspondence_id: str,
        file_bytes: bytes,
        filename: str
    ) -> str:
        """Store document with server-side encryption"""

        now = datetime.utcnow()
        key = f"{firm_id}/{now.year}/{now.month:02d}/{correspondence_id}/original{Path(filename).suffix}"

        await asyncio.to_thread(
            self.s3.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=file_bytes,
            ServerSideEncryption='aws:kms',
            SSEKMSKeyId=self._get_firm_kms_key(firm_id),
            ContentType=mimetypes.guess_type(filename)[0],
            Metadata={
                'firm_id': firm_id,
                'correspondence_id': correspondence_id,
                'original_filename': filename
            }
        )

        return key

    async def get_presigned_url(
        self,
        storage_path: str,
        expiry_seconds: int = 3600
    ) -> str:
        """Generate temporary access URL"""

        return await asyncio.to_thread(
            self.s3.generate_presigned_url,
            'get_object',
            Params={'Bucket': self.bucket, 'Key': storage_path},
            ExpiresIn=expiry_seconds
        )
```

---

### 2.5 API Layer

#### 2.5.1 API Design

**FastAPI Application Structure:**

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ATOtrack API",
    version="1.0.0",
    description="ATO Correspondence Intelligence Platform"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.atotrack.com.au"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Route modules
from app.routes import capture, correspondence, clients, integrations, webhooks

app.include_router(capture.router, prefix="/api/v1/capture", tags=["Capture"])
app.include_router(correspondence.router, prefix="/api/v1/correspondence", tags=["Correspondence"])
app.include_router(clients.router, prefix="/api/v1/clients", tags=["Clients"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
```

#### 2.5.2 Core API Endpoints

**Capture Endpoints:**

```python
# app/routes/capture.py
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks

router = APIRouter()

@router.post("/email")
async def capture_email(
    request: EmailCaptureRequest,
    background_tasks: BackgroundTasks,
    firm: Firm = Depends(get_current_firm)
):
    """Capture correspondence from email (Gmail/Outlook add-in)"""

    correspondence = await correspondence_service.create_from_email(
        firm_id=firm.id,
        email_data=request
    )

    # Queue for async processing
    background_tasks.add_task(
        processing_service.process_correspondence,
        correspondence.id
    )

    return {"id": correspondence.id, "status": "processing"}

@router.post("/upload")
async def capture_upload(
    file: UploadFile = File(...),
    client_id: Optional[str] = None,
    notes: Optional[str] = None,
    background_tasks: BackgroundTasks,
    firm: Firm = Depends(get_current_firm)
):
    """Capture correspondence from direct upload (mobile/web)"""

    correspondence = await correspondence_service.create_from_upload(
        firm_id=firm.id,
        file=file,
        client_id=client_id,
        notes=notes
    )

    background_tasks.add_task(
        processing_service.process_correspondence,
        correspondence.id
    )

    return {"id": correspondence.id, "status": "processing"}

@router.post("/webhook/mailgun")
async def mailgun_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Receive inbound email from Mailgun"""

    # Verify Mailgun signature
    if not verify_mailgun_signature(request):
        raise HTTPException(status_code=401)

    form_data = await request.form()
    email = email_parser.parse(form_data)

    firm = await firm_service.get_by_capture_email(email.recipient)
    if not firm:
        return {"status": "ignored", "reason": "unknown_recipient"}

    correspondence = await correspondence_service.create_from_email(
        firm_id=firm.id,
        email_data=email
    )

    background_tasks.add_task(
        processing_service.process_correspondence,
        correspondence.id
    )

    return {"status": "accepted", "id": correspondence.id}
```

**Correspondence Endpoints:**

```python
# app/routes/correspondence.py
from fastapi import APIRouter, Query, Depends
from typing import Optional, List

router = APIRouter()

@router.get("/")
async def list_correspondence(
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    notice_type: Optional[str] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    risk_level: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    firm: Firm = Depends(get_current_firm)
) -> PaginatedResponse[CorrespondenceSummary]:
    """List correspondence with filtering and pagination"""

    return await correspondence_service.list(
        firm_id=firm.id,
        filters=CorrespondenceFilters(
            status=status,
            client_id=client_id,
            notice_type=notice_type,
            due_before=due_before,
            due_after=due_after,
            risk_level=risk_level
        ),
        page=page,
        per_page=per_page
    )

@router.get("/{correspondence_id}")
async def get_correspondence(
    correspondence_id: str,
    firm: Firm = Depends(get_current_firm)
) -> CorrespondenceDetail:
    """Get full correspondence details"""

    correspondence = await correspondence_service.get(
        firm_id=firm.id,
        correspondence_id=correspondence_id
    )

    if not correspondence:
        raise HTTPException(status_code=404)

    return correspondence

@router.patch("/{correspondence_id}")
async def update_correspondence(
    correspondence_id: str,
    update: CorrespondenceUpdate,
    firm: Firm = Depends(get_current_firm)
) -> CorrespondenceDetail:
    """Update correspondence (assign client, change status, etc.)"""

    return await correspondence_service.update(
        firm_id=firm.id,
        correspondence_id=correspondence_id,
        update=update
    )

@router.post("/{correspondence_id}/reprocess")
async def reprocess_correspondence(
    correspondence_id: str,
    background_tasks: BackgroundTasks,
    firm: Firm = Depends(get_current_firm)
):
    """Re-run AI processing on correspondence"""

    background_tasks.add_task(
        processing_service.process_correspondence,
        correspondence_id,
        force_reprocess=True
    )

    return {"status": "reprocessing"}

@router.get("/{correspondence_id}/document")
async def get_document(
    correspondence_id: str,
    firm: Firm = Depends(get_current_firm)
) -> DocumentAccessResponse:
    """Get presigned URL to access document"""

    correspondence = await correspondence_service.get(
        firm_id=firm.id,
        correspondence_id=correspondence_id
    )

    presigned_url = await storage_service.get_presigned_url(
        correspondence.storage_path,
        expiry_seconds=3600
    )

    return DocumentAccessResponse(
        url=presigned_url,
        filename=correspondence.original_filename,
        expires_in=3600
    )
```

**Dashboard/Analytics Endpoints:**

```python
# app/routes/analytics.py
router = APIRouter()

@router.get("/dashboard")
async def get_dashboard(
    firm: Firm = Depends(get_current_firm)
) -> DashboardData:
    """Get dashboard summary data"""

    return DashboardData(
        total_pending=await correspondence_service.count(firm.id, status='pending'),
        total_overdue=await correspondence_service.count_overdue(firm.id),
        due_this_week=await correspondence_service.count_due_in_days(firm.id, 7),
        risk_breakdown=await correspondence_service.get_risk_breakdown(firm.id),
        recent_items=await correspondence_service.get_recent(firm.id, limit=10),
        deadline_calendar=await correspondence_service.get_deadlines(firm.id, days=30)
    )

@router.get("/reports/volume")
async def get_volume_report(
    start_date: date,
    end_date: date,
    group_by: str = "week",  # day, week, month
    firm: Firm = Depends(get_current_firm)
) -> VolumeReport:
    """Get correspondence volume over time"""

    return await analytics_service.get_volume_report(
        firm_id=firm.id,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by
    )

@router.get("/reports/by-type")
async def get_type_report(
    start_date: date,
    end_date: date,
    firm: Firm = Depends(get_current_firm)
) -> TypeBreakdownReport:
    """Get breakdown by notice type"""

    return await analytics_service.get_type_breakdown(
        firm_id=firm.id,
        start_date=start_date,
        end_date=end_date
    )
```

---

## 3. Security Architecture

### 3.1 Data Security

```
+------------------------------------------------------------------+
|                        Security Layers                            |
+------------------------------------------------------------------+
|                                                                   |
|  TRANSPORT LAYER                                                  |
|  +-----------------------------------------------------------+   |
|  |  TLS 1.3 for all connections                              |   |
|  |  HTTPS only (HSTS enabled)                                |   |
|  |  Certificate pinning for mobile apps                      |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
|  APPLICATION LAYER                                                |
|  +-----------------------------------------------------------+   |
|  |  JWT authentication with short-lived access tokens        |   |
|  |  Refresh token rotation                                   |   |
|  |  RBAC with firm-scoped permissions                        |   |
|  |  Rate limiting per tenant                                 |   |
|  |  Input validation and sanitization                        |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
|  DATA LAYER                                                       |
|  +-----------------------------------------------------------+   |
|  |  Row-level security (PostgreSQL RLS)                      |   |
|  |  Per-tenant encryption keys (AWS KMS)                     |   |
|  |  TFN data: hashed only, never stored plaintext            |   |
|  |  Audit logging for all data access                        |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
|  STORAGE LAYER                                                    |
|  +-----------------------------------------------------------+   |
|  |  S3 server-side encryption (SSE-KMS)                      |   |
|  |  Per-tenant KMS keys                                       |   |
|  |  Bucket policies restricting access                       |   |
|  |  Versioning enabled for document recovery                 |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
+------------------------------------------------------------------+
```

### 3.2 Authentication & Authorization

```python
# JWT-based authentication
class AuthService:

    def create_access_token(self, user: User, firm: Firm) -> str:
        payload = {
            "sub": str(user.id),
            "firm_id": str(firm.id),
            "role": user.role,
            "permissions": self._get_permissions(user.role),
            "exp": datetime.utcnow() + timedelta(minutes=15),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def create_refresh_token(self, user: User) -> str:
        payload = {
            "sub": str(user.id),
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=7),
            "jti": str(uuid.uuid4())  # Unique token ID for revocation
        }
        return jwt.encode(payload, self.refresh_secret, algorithm="HS256")

# Role-based access control
class Permission(Enum):
    CORRESPONDENCE_VIEW = "correspondence:view"
    CORRESPONDENCE_EDIT = "correspondence:edit"
    CORRESPONDENCE_DELETE = "correspondence:delete"
    CLIENT_MANAGE = "client:manage"
    INTEGRATION_MANAGE = "integration:manage"
    FIRM_ADMIN = "firm:admin"
    BILLING_MANAGE = "billing:manage"

ROLE_PERMISSIONS = {
    "admin": [p.value for p in Permission],
    "manager": [
        Permission.CORRESPONDENCE_VIEW.value,
        Permission.CORRESPONDENCE_EDIT.value,
        Permission.CLIENT_MANAGE.value,
        Permission.INTEGRATION_MANAGE.value
    ],
    "accountant": [
        Permission.CORRESPONDENCE_VIEW.value,
        Permission.CORRESPONDENCE_EDIT.value,
        Permission.CLIENT_MANAGE.value
    ],
    "readonly": [
        Permission.CORRESPONDENCE_VIEW.value
    ]
}
```

### 3.3 Audit Logging

```python
class AuditLogger:
    """Immutable audit log for compliance"""

    async def log(
        self,
        event_type: str,
        actor: User,
        resource_type: str,
        resource_id: str,
        action: str,
        details: dict = None
    ):
        """Log audit event"""

        event = AuditEvent(
            id=uuid.uuid4(),
            timestamp=datetime.utcnow(),
            firm_id=actor.firm_id,
            actor_id=actor.id,
            actor_email=actor.email,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details,
            ip_address=self._get_client_ip(),
            user_agent=self._get_user_agent()
        )

        # Store in append-only audit table
        await self.db.execute(
            """INSERT INTO audit_log
               (id, timestamp, firm_id, actor_id, actor_email, event_type,
                resource_type, resource_id, action, details, ip_address, user_agent)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
            *event.as_tuple()
        )

        # Also send to CloudWatch for real-time monitoring
        await self.cloudwatch.put_log_event(event)
```

---

## 4. Infrastructure Architecture

### 4.1 AWS Architecture (Sydney Region)

```
+------------------------------------------------------------------+
|                        AWS ap-southeast-2 (Sydney)                |
+------------------------------------------------------------------+
|                                                                   |
|  VPC (10.0.0.0/16)                                                |
|  +-----------------------------------------------------------+   |
|  |                                                            |   |
|  |  Public Subnets (10.0.1.0/24, 10.0.2.0/24)               |   |
|  |  +-----------------------------------------------------+  |   |
|  |  |  ALB (Application Load Balancer)                    |  |   |
|  |  |  - HTTPS termination                                |  |   |
|  |  |  - WAF integration                                  |  |   |
|  |  +-----------------------------------------------------+  |   |
|  |                                                            |   |
|  |  Private Subnets (10.0.10.0/24, 10.0.11.0/24)            |   |
|  |  +-----------------------------------------------------+  |   |
|  |  |                                                      |  |   |
|  |  |  ECS Cluster (Fargate)                              |  |   |
|  |  |  +----------------+  +----------------+              |  |   |
|  |  |  | API Service    |  | Worker Service |              |  |   |
|  |  |  | (FastAPI)      |  | (Processing)   |              |  |   |
|  |  |  | 2-10 tasks     |  | 2-20 tasks     |              |  |   |
|  |  |  +----------------+  +----------------+              |  |   |
|  |  |                                                      |  |   |
|  |  +-----------------------------------------------------+  |   |
|  |                                                            |   |
|  |  Database Subnets (10.0.20.0/24, 10.0.21.0/24)           |   |
|  |  +-----------------------------------------------------+  |   |
|  |  |                                                      |  |   |
|  |  |  RDS PostgreSQL (Multi-AZ)                          |  |   |
|  |  |  - db.r6g.large (8GB RAM, 2 vCPU)                   |  |   |
|  |  |  - 100GB GP3 SSD                                    |  |   |
|  |  |  - Automated backups (35 days)                      |  |   |
|  |  |                                                      |  |   |
|  |  |  ElastiCache Redis (Cluster Mode)                   |  |   |
|  |  |  - cache.r6g.large                                  |  |   |
|  |  |  - 2 shards, 1 replica each                         |  |   |
|  |  |                                                      |  |   |
|  |  +-----------------------------------------------------+  |   |
|  |                                                            |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
|  S3 Buckets                                                       |
|  +-----------------------------------------------------------+   |
|  |  atotrack-documents (encrypted, versioned)                |   |
|  |  atotrack-logs (server access logs)                       |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
|  Supporting Services                                              |
|  +-----------------------------------------------------------+   |
|  |  KMS - Customer managed keys per tenant                   |   |
|  |  Secrets Manager - API keys, OAuth credentials            |   |
|  |  CloudWatch - Logs, metrics, alarms                       |   |
|  |  SQS - Processing queue                                   |   |
|  +-----------------------------------------------------------+   |
|                                                                   |
+------------------------------------------------------------------+
```

### 4.2 Deployment Pipeline

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
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          pip install -r requirements-dev.txt
          pytest --cov=app tests/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: |
            ${{ secrets.ECR_REGISTRY }}/atotrack-api:${{ github.sha }}
            ${{ secrets.ECR_REGISTRY }}/atotrack-api:latest

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ecs-task-definition.json
          service: atotrack-api
          cluster: atotrack-production
          wait-for-service-stability: true
```

### 4.3 Monitoring & Observability

```python
# Structured logging
import structlog

logger = structlog.get_logger()

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())

    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        path=request.url.path,
        method=request.method
    )

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    logger.info(
        "request_completed",
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2)
    )

    response.headers["X-Request-ID"] = request_id
    return response

# CloudWatch metrics
class Metrics:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
        self.namespace = 'ATOtrack'

    def record_processing_time(self, notice_type: str, duration_ms: float):
        self.cloudwatch.put_metric_data(
            Namespace=self.namespace,
            MetricData=[{
                'MetricName': 'ProcessingTime',
                'Dimensions': [
                    {'Name': 'NoticeType', 'Value': notice_type}
                ],
                'Value': duration_ms,
                'Unit': 'Milliseconds'
            }]
        )

    def record_classification_confidence(self, notice_type: str, confidence: float):
        self.cloudwatch.put_metric_data(
            Namespace=self.namespace,
            MetricData=[{
                'MetricName': 'ClassificationConfidence',
                'Dimensions': [
                    {'Name': 'NoticeType', 'Value': notice_type}
                ],
                'Value': confidence,
                'Unit': 'None'
            }]
        )
```

---

## 5. Technology Stack Summary

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **API Framework** | FastAPI (Python 3.11+) | Async performance, OpenAPI docs, type hints |
| **AI/ML** | OpenAI GPT-4 Turbo | Best-in-class NLP, JSON mode, fine-tuning support |
| **OCR** | Google Cloud Vision | Industry-leading accuracy, Australian document support |
| **Database** | PostgreSQL 15 (RDS) | ACID, RLS, pg_trgm for fuzzy matching |
| **Cache/Queue** | Redis (ElastiCache) | Fast, versatile, Bull queue compatible |
| **Document Storage** | AWS S3 | Scalable, cost-effective, KMS encryption |
| **Email Processing** | Mailgun | Reliable inbound parsing, webhook delivery |
| **Frontend** | React 18 + TypeScript | Modern, maintainable, strong ecosystem |
| **Mobile** | React Native | Cross-platform, shared codebase with web |
| **Infrastructure** | AWS (Sydney) | Data sovereignty, low latency, managed services |
| **Container Orchestration** | ECS Fargate | Serverless containers, auto-scaling |
| **CI/CD** | GitHub Actions | Integrated with repo, good AWS support |
| **Monitoring** | CloudWatch + Sentry | Logs, metrics, error tracking |

---

## 6. API Contracts

### 6.1 OpenAPI Specification (Summary)

```yaml
openapi: 3.0.3
info:
  title: ATOtrack API
  version: 1.0.0
  description: ATO Correspondence Intelligence Platform API

servers:
  - url: https://api.atotrack.com.au/v1

security:
  - bearerAuth: []

paths:
  /capture/email:
    post:
      summary: Capture correspondence from email
      tags: [Capture]
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/EmailCaptureRequest'
      responses:
        '202':
          description: Accepted for processing
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CaptureResponse'

  /correspondence:
    get:
      summary: List correspondence
      tags: [Correspondence]
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [new, assigned, in_progress, completed, archived]
        - name: client_id
          in: query
          schema:
            type: string
            format: uuid
        - name: due_before
          in: query
          schema:
            type: string
            format: date
      responses:
        '200':
          description: Paginated list of correspondence
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CorrespondenceList'

  /correspondence/{id}:
    get:
      summary: Get correspondence details
      tags: [Correspondence]
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Correspondence details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CorrespondenceDetail'

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    CorrespondenceDetail:
      type: object
      properties:
        id:
          type: string
          format: uuid
        notice_type:
          type: string
        client:
          $ref: '#/components/schemas/ClientSummary'
        issue_date:
          type: string
          format: date
        due_date:
          type: string
          format: date
        amount_owing:
          type: number
        risk_level:
          type: string
          enum: [low, medium, high, critical]
        workflow_status:
          type: string
        action_required:
          type: boolean
        action_description:
          type: string
        document_url:
          type: string
          format: uri
```

---

## 7. Quality Attributes

### 7.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| API Response Time (p95) | < 200ms | CloudWatch |
| Document Processing Time | < 30 seconds | Custom metric |
| Classification Accuracy | > 95% | Validation dataset |
| Entity Extraction Accuracy | > 90% | Validation dataset |
| System Availability | 99.9% | Uptime monitoring |
| Error Rate | < 0.1% | Error tracking |

### 7.2 Scalability Targets

| Dimension | Initial | Year 1 | Year 2 |
|-----------|---------|--------|--------|
| Firms | 10 | 200 | 1,000 |
| Documents/day | 100 | 2,000 | 10,000 |
| Concurrent users | 20 | 200 | 1,000 |
| Storage (TB) | 0.1 | 2 | 10 |

### 7.3 Compliance Requirements

| Requirement | Implementation |
|-------------|----------------|
| Data Residency | All data in AWS Sydney (ap-southeast-2) |
| Encryption at Rest | AES-256 (S3, RDS, ElastiCache) |
| Encryption in Transit | TLS 1.3 |
| Access Control | RBAC with audit logging |
| Data Retention | Configurable per firm, default 7 years |
| SOC 2 Type II | Target certification by Year 2 |

---

## Appendix A: Notice Type Deadline Reference

| Notice Type | Default Days | Notes |
|-------------|--------------|-------|
| Notice of Assessment | 21 | Payment due |
| Amended Assessment | 21 | Payment due |
| Activity Statement | 21 | Amendment period |
| Audit Notification | 28 | Initial response |
| Information Request | 28 | Standard period |
| Director Penalty Notice | 21 | CRITICAL - personal liability |
| Debt Notification | 14 | Payment arrangement |
| Penalty Notice | 28 | Objection/remission period |
| Garnishee Notice | Immediate | CRITICAL |
| SG Charge Statement | 28 | Response period |

---

## Appendix B: Integration API References

| Integration | API Documentation | Auth Method |
|-------------|-------------------|-------------|
| Karbon | https://developers.karbonhq.com | API Key |
| Xero Practice Manager | https://developer.xero.com/documentation/api/practicemanager | OAuth 2.0 |
| FYI Docs | https://developers.fyidocs.com | OAuth 2.0 |
| Google Calendar | https://developers.google.com/calendar/api | OAuth 2.0 |
| Microsoft Graph (Outlook) | https://docs.microsoft.com/en-us/graph | OAuth 2.0 |
| Slack | https://api.slack.com | Webhook/OAuth |
| Microsoft Teams | https://docs.microsoft.com/en-us/microsoftteams | Webhook |

---

*This solution design provides the technical foundation for ATOtrack's ATO correspondence intelligence platform. The architecture prioritizes integration-native delivery, AI-powered processing, and enterprise-grade security while maintaining the flexibility to scale with customer growth.*
