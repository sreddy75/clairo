# Research: Spec 047 — Client Transaction Classification

## R1: Where Do New Models Live?

**Decision**: New models (`ClassificationRequest`, `ClientClassification`) live in the `bas/` module. Client-facing API endpoints extend the `portal/` module.

**Rationale**: The classification request is BAS-preparation-scoped — it ties directly to a BAS session and its unresolved transactions. The `bas/` module already owns `TaxCodeSuggestion` and `TaxCodeOverride`. The portal module only provides the client auth and delivery mechanism.

**Alternatives considered**:
- New `classification/` module: Over-engineering for 2 models that are tightly coupled to BAS
- All in `portal/`: Wrong ownership — classification is a BAS workflow concern, not a portal concern

**Cross-module pattern**: `bas/` owns models + accountant-facing service. `portal/` gets new client-facing endpoints that call `bas/` service layer (same pattern as portal dashboard calling xero services).

## R2: Magic Link Strategy

**Decision**: Create a `PortalInvitation` for each classification request using the existing `MagicLinkService`. The `ClassificationRequest` model stores a FK to `PortalInvitation.id`.

**Rationale**: The magic link infrastructure (token generation, hashing, verification, session creation) is production-ready. Creating a dedicated invitation per classification request gives us:
- Separate expiry (7 days, not 24 hours — override the default)
- Status tracking (sent, viewed, accepted)
- Reuse of the portal verify flow

**Key gap to fix**: Email sending is not wired up in the portal invitation flow. `InvitationService.create_invitation()` creates the record and returns the URL, but never calls `EmailService`. We need to wire this up — follow the pattern from `auth/service.py:1133` (synchronous send within try/except).

**Alternatives considered**:
- Separate token system: Redundant with existing magic link
- Extending `DocumentRequest`: Wrong semantics — document requests are about uploading files, not classifying transactions

## R3: AI Mapping Trigger

**Decision**: Synchronous during accountant review, not on client submit. When the client submits classifications, we store them as `ClientClassification` records. When the accountant opens the review screen, the system runs AI mapping for any unprocessed classifications.

**Rationale**:
- Client submit should be instant — no waiting for LLM calls
- The accountant review screen is where AI suggestions are consumed anyway
- This lets us batch all classifications into a single LLM call (efficient)
- If AI mapping fails, the accountant still sees the client's raw descriptions

**Implementation**: New method `TaxCodeService.map_client_classifications()` that:
1. Takes client descriptions + categories + transaction context
2. Calls the LLM with enhanced prompt including client's input
3. Creates/updates `TaxCodeSuggestion` records with `confidence_tier = "client_classified"`
4. Returns suggestions for the review screen

**Alternatives considered**:
- Async via Celery on submit: Adds complexity, accountant may open review before task completes
- Real-time on submit: Blocks client UX, 3-10 second LLM call

## R4: Category Taxonomy Storage

**Decision**: Hardcoded as a Python constant (backend) and TypeScript constant (frontend). Categories are the same for all tenants.

**Rationale**: At this stage, the categories are standard Australian BAS expense types. Every accountant deals with the same ATO tax codes. Tenant-configurable categories adds significant complexity (admin UI, validation, migration) for no clear benefit.

**Implementation**: `CLASSIFICATION_CATEGORIES` dict in `bas/constants.py` with structure:
```python
{"id": "office_supplies", "label": "Office supplies & stationery", "group": "expense", "typical_tax_type": "GST on Expenses"}
```
Matching array in `frontend/src/lib/constants/classification-categories.ts`.

**Alternatives considered**:
- DB-configurable per tenant: Over-engineering — revisit when a tenant explicitly asks
- AI-generated categories per transaction: Interesting but unpredictable UX

## R5: Portal Auth → BAS Data Access

**Decision**: Portal session's `connection_id` is the access control boundary. The `ClassificationRequest` stores `connection_id`, and client API endpoints verify `request.connection_id == session.connection_id`.

**Rationale**: Portal sessions are already scoped to `connection_id` (from `MagicLinkService`). BAS sessions are also scoped to `connection_id`. The join is natural. No new auth mechanism needed.

**Security check**: Client can only see transactions from their own Xero connection. They cannot see other clients' data. RLS on `tenant_id` provides the second layer.

## R6: Save Progress Mechanism

**Decision**: Server-side draft storage. Each classification is saved individually as the client works. A `submitted_at` timestamp on the `ClassificationRequest` marks final submission.

**Rationale**: Server-side saves work across devices (client starts on phone, finishes on laptop). The magic link session handles auth. No complex localStorage sync needed.

**Implementation**:
- `PUT /client-portal/classify/{request_id}/transactions/{classification_id}` saves individual classifications
- `POST /client-portal/classify/{request_id}/submit` marks the request as submitted
- Frontend auto-saves on each category selection (debounced)

**Alternatives considered**:
- localStorage + sync: Fails if client switches devices. PWA offline support can be added later via the existing service worker.

## R7: Integration with Spec 046 Suggestion Engine

**Decision**: Create `TaxCodeSuggestion` records with a new confidence tier `client_classified`. The accountant reviews them using the EXISTING approve/reject/override flow from spec 046.

**Rationale**: The entire review + approval + override + audit trail infrastructure already exists. By creating standard `TaxCodeSuggestion` records, we get:
- Same review UI patterns
- Same `apply_and_recalculate()` flow
- Same audit events
- Same `TaxCodeOverride` creation
- Zero new review infrastructure

**New confidence tier**: `client_classified` with confidence range 0.70-0.90, depending on whether the client selected a category (higher) or typed free text (lower).

**LLM prompt enhancement**: When mapping client descriptions, the prompt includes:
- The client's selected category (if any)
- The client's free-text description (if any)
- Standard transaction context (amount, account, payee, date)
- Instruction: "The business owner has classified this transaction as {category}. Map to the correct Xero tax type."

## R8: Email Sending

**Decision**: Wire up email sending in `InvitationService.create_invitation()` using the existing `EmailService` + `PortalEmailTemplates` pattern. Add a new template `transaction_classification_request` for this specific use case.

**Rationale**: The email infrastructure exists but is disconnected. This spec is the perfect opportunity to wire it up. The pattern from `auth/service.py` (synchronous send within try/except) is simple and proven.

**New template**: Based on the existing `document_request` template pattern but with different copy:
- Subject: "{Practice Name} needs you to classify some transactions"
- Body: Transaction count, optional message from accountant, CTA button to magic link
- Due date highlight if accountant set one

**Alternatives considered**:
- Celery async email task: Over-engineering for a single email per request
- Skip email, just return URL: Defeats the purpose — the whole point is automated delivery
