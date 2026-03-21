# Feature Specification: Email Integration & OAuth

**Feature Branch**: `026-email-integration-oauth`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: E.5 (ATOtrack)

## Overview

Enable accountants to connect their email accounts (Gmail/Google Workspace or Microsoft 365/Outlook) to Clairo for automatic capture of ATO correspondence. This is the foundation for ATOtrack - ensuring practices never miss an ATO deadline or notice.

**Why This Matters**:
- ATO sends critical notices via email (activity statements, audits, penalties, debt notices)
- Missing a deadline can result in fines and interest charges
- Accountants managing 50+ clients receive hundreds of ATO emails per month
- Manual tracking is error-prone and time-consuming
- ATOtrack = post-lodgement intelligence (know what happens AFTER you lodge)

**Disruption Level**: Medium (new integration pattern)

---

## User Scenarios & Testing

### User Story 1 - Connect Gmail Account (Priority: P1)

As an accountant, I want to connect my Gmail or Google Workspace account so that Clairo can automatically capture ATO emails.

**Why this priority**: Gmail is the most common email provider for small-medium practices in Australia.

**Independent Test**: Click "Connect Gmail" → complete OAuth flow → see connection status as "Active".

**Acceptance Scenarios**:

1. **Given** I'm on the email connections page, **When** I click "Connect Gmail", **Then** I'm redirected to Google's OAuth consent screen.

2. **Given** I authorize the app in Google, **When** the OAuth flow completes, **Then** I'm returned to Clairo with connection status "Active".

3. **Given** my Gmail is connected, **When** I view connection details, **Then** I see the connected email address and last sync time.

---

### User Story 2 - Connect Microsoft 365 Account (Priority: P1)

As an accountant using Outlook/Microsoft 365, I want to connect my email account so that ATO correspondence is captured.

**Why this priority**: Microsoft 365 is the primary email platform for larger accounting firms.

**Independent Test**: Click "Connect Outlook" → complete Microsoft OAuth flow → see connection status as "Active".

**Acceptance Scenarios**:

1. **Given** I'm on the email connections page, **When** I click "Connect Outlook", **Then** I'm redirected to Microsoft's OAuth consent screen.

2. **Given** I authorize the app in Microsoft, **When** the OAuth flow completes, **Then** I'm returned to Clairo with connection status "Active".

3. **Given** my Outlook is connected, **When** I view connection details, **Then** I see the connected email address and last sync time.

---

### User Story 3 - Initial Email Backfill (Priority: P1)

As an accountant, I want Clairo to import my existing ATO emails from the past 12 months so that I have a complete history.

**Why this priority**: Historical context is essential for understanding ongoing matters and outstanding obligations.

**Independent Test**: After connecting email → see historical ATO emails appear in the inbox within minutes.

**Acceptance Scenarios**:

1. **Given** I just connected my email, **When** initial sync runs, **Then** ATO emails from the last 12 months are imported.

2. **Given** initial sync is running, **When** I check sync status, **Then** I see progress indicator with count of emails found.

3. **Given** initial sync completes, **When** I view ATO inbox, **Then** all historical emails are visible with correct dates.

---

### User Story 4 - Automatic Email Sync (Priority: P1)

As an accountant, I want new ATO emails to be captured automatically so that I don't have to manually check.

**Why this priority**: Real-time capture ensures no emails are missed between manual checks.

**Independent Test**: Receive new ATO email → appears in Clairo inbox within 15 minutes.

**Acceptance Scenarios**:

1. **Given** my email is connected, **When** a new ATO email arrives, **Then** it appears in Clairo within 15 minutes (polling) or real-time (webhook).

2. **Given** new emails are synced, **When** I view the ATO inbox, **Then** new emails are marked as "New" until viewed.

3. **Given** sync runs periodically, **When** I check connection status, **Then** I see "Last synced: X minutes ago".

---

### User Story 5 - Email Forwarding Fallback (Priority: P2)

As an accountant who cannot use OAuth, I want to forward ATO emails to Clairo so that they are still captured.

**Why this priority**: Some organizations have security policies preventing OAuth connections. Forwarding is a fallback option.

**Independent Test**: Forward an ATO email to ingest address → email appears in Clairo inbox.

**Acceptance Scenarios**:

1. **Given** I cannot use OAuth, **When** I view connection options, **Then** I see a unique forwarding email address for my practice.

2. **Given** I set up a mail rule to forward @ato.gov.au emails, **When** an ATO email arrives, **Then** it's forwarded and captured by Clairo.

3. **Given** a forwarded email is received, **When** I view it in Clairo, **Then** the original sender (@ato.gov.au) is preserved, not the forwarder.

---

### User Story 6 - Connection Management (Priority: P2)

As an accountant, I want to manage my email connections so that I can reconnect or disconnect as needed.

**Why this priority**: Token expiry and organizational changes require connection management.

**Independent Test**: View connected accounts → disconnect one → reconnect with different account.

**Acceptance Scenarios**:

1. **Given** I have a connected email, **When** I click "Disconnect", **Then** the connection is removed and no new emails are synced.

2. **Given** a connection's token has expired, **When** I view connections, **Then** I see "Reconnection Required" status with a re-authorize button.

3. **Given** I have multiple email accounts, **When** I view connections, **Then** I can see and manage each connection independently.

---

### User Story 7 - Token Refresh (Priority: P1)

As an accountant, I want my email connection to stay active without manual intervention so that I don't miss emails due to expired tokens.

**Why this priority**: OAuth tokens expire. Automatic refresh ensures uninterrupted service.

**Independent Test**: Token expires → is automatically refreshed → sync continues without user action.

**Acceptance Scenarios**:

1. **Given** a token is approaching expiry, **When** refresh runs, **Then** the token is renewed before it expires.

2. **Given** token refresh fails (revoked), **When** sync attempts, **Then** connection status changes to "Reconnection Required" and user is notified.

3. **Given** refresh token is valid, **When** access token expires, **Then** a new access token is obtained without user interaction.

---

### Edge Cases

- What if the user revokes access in Google/Microsoft?
  → Next sync fails, connection marked as "Revoked", user notified to reconnect

- What if the user has multiple email accounts (personal + practice)?
  → Allow multiple connections, tag each with a label, sync all

- How are shared mailboxes handled?
  → For Microsoft, support delegated access if user has permissions

- What if an email is deleted after being synced?
  → Keep the synced copy in Clairo (ATO compliance requires retention)

- How are very large attachments handled?
  → Store attachment metadata, download on demand, max 25MB per attachment

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST support Gmail/Google Workspace OAuth connection
- **FR-002**: System MUST support Microsoft 365/Outlook OAuth connection
- **FR-003**: System MUST filter emails to only capture from @ato.gov.au domains
- **FR-004**: System MUST perform initial backfill of last 12 months
- **FR-005**: System MUST sync new emails within 15 minutes (polling) or real-time (webhook)
- **FR-006**: System MUST automatically refresh OAuth tokens before expiry
- **FR-007**: System MUST encrypt all tokens at rest
- **FR-008**: System MUST provide email forwarding as fallback option
- **FR-009**: System MUST allow disconnect and reconnect of email accounts
- **FR-010**: System SHOULD support multiple email connections per tenant
- **FR-011**: System MUST preserve original sender when processing forwarded emails
- **FR-012**: System MUST notify user when connection requires re-authorization

### Key Entities

- **EmailConnection**: OAuth connection with encrypted tokens
- **EmailSyncJob**: Sync job tracking for backfill and incremental
- **RawEmail**: Stored email with metadata (before parsing)
- **EmailAttachment**: Attachment metadata and storage reference

### Non-Functional Requirements

- **NFR-001**: OAuth flow MUST complete in <30 seconds
- **NFR-002**: Email sync MUST process at least 100 emails/minute
- **NFR-003**: Tokens MUST be encrypted with AES-256
- **NFR-004**: All email data MUST be retained for 7 years (ATO compliance)
- **NFR-005**: Sync failures MUST be retried with exponential backoff

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Data Access Events**: Yes - accessing email is sensitive
- [x] **Data Modification Events**: Yes - syncing and storing emails
- [x] **Integration Events**: Yes - OAuth connections to external providers
- [x] **Compliance Events**: Yes - email retention for ATO compliance

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `email.connection.created` | OAuth flow complete | tenant_id, provider, email | 7 years | Email address |
| `email.connection.revoked` | User disconnects | tenant_id, connection_id | 7 years | None |
| `email.connection.expired` | Token refresh failed | tenant_id, connection_id, reason | 7 years | None |
| `email.sync.completed` | Sync job completes | connection_id, email_count | 7 years | None |
| `email.received` | New email synced | tenant_id, email_id, from_domain | 7 years | None (no content) |

### Compliance Considerations

- **Token Security**: All OAuth tokens encrypted at rest, never logged
- **Email Privacy**: Only sync emails from @ato.gov.au (no personal emails)
- **Data Retention**: 7-year retention per ATO requirements
- **User Consent**: Clear OAuth consent with listed permissions

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Gmail OAuth connection success rate >95%
- **SC-002**: Microsoft OAuth connection success rate >95%
- **SC-003**: Initial backfill completes in <10 minutes for typical inbox
- **SC-004**: New emails captured within 15 minutes of receipt
- **SC-005**: Token refresh success rate >99%
- **SC-006**: Zero ATO emails missed due to connection issues

---

## Technical Notes (for Plan phase)

### OAuth Scopes

**Gmail (Google Workspace)**:
```
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.labels
```

**Microsoft 365 (Outlook)**:
```
Mail.Read
Mail.ReadBasic
User.Read
offline_access
```

### Email Filtering

**Gmail Query**:
```
from:(@ato.gov.au OR @notifications.ato.gov.au) newer_than:365d
```

**Microsoft Graph Filter**:
```
$filter=from/emailAddress/address contains 'ato.gov.au'
```

### Token Storage

```python
class EmailConnection(Base):
    id: UUID
    tenant_id: UUID
    provider: EmailProvider  # GMAIL, OUTLOOK, FORWARDING
    email_address: str
    access_token_encrypted: str  # AES-256 encrypted
    refresh_token_encrypted: str  # AES-256 encrypted
    token_expires_at: datetime
    last_sync_at: datetime
    sync_cursor: str  # Gmail historyId or Graph deltaToken
    status: ConnectionStatus  # ACTIVE, EXPIRED, REVOKED
```

### Forwarding Address Format

```
{tenant_slug}@ingest.clairo.ai
```

Example: `smithandco@ingest.clairo.ai`

---

## Dependencies

- **Spec 003 (Xero OAuth)**: Reference - similar OAuth pattern
- **Spec 027 (ATO Parsing)**: Dependent - consumes synced emails
- **Spec 028 (ATOtrack)**: Dependent - uses parsed correspondence
