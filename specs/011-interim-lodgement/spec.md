# Requirements Document: Interim Lodgement

## Introduction

This document defines the requirements for the Interim Lodgement feature in Clairo. This feature completes the BAS workflow end-to-end by **enhancing existing BAS export capabilities** with ATO-compliant formatting, adding CSV export, and providing comprehensive lodgement status tracking.

**Strategic Context:**
- This is Phase A: Foundation Complete (Weeks 1-2) per ROADMAP.md
- Goal: Close out R1 quickly so we can sprint to AI features (THE MOAT)
- Completes the BAS workflow from Xero connection through to lodgement
- Enables accountants to use Clairo as their primary BAS preparation tool

**Key Dependencies:**
- Spec 009: BAS Preparation Workflow (COMPLETE) - provides BASSession, BASCalculation, BASPeriod models
- **BAS Exporter Module (IMPLEMENTED)** - provides PDF and Excel working paper exports
- BASSessionStatus includes APPROVED and LODGED states

**Exit Criteria:**
- Accountant can export BAS data in ATO-compliant format and lodge via Xero/ATO portal
- Lodgement status tracked in system with full audit trail
- Complete BAS workflow from connection to lodgement is operational

---

## Problem Statement

Currently, the BAS workflow ends at the "Approved" status. While accountants **CAN export BAS data** (PDF working papers and Excel exports with calculations already exist), these exports lack:

1. **ATO-compliant formatting** - Current exports are working papers, not formatted for ATO portal data entry
2. **Lodgement summary view** - No dedicated view optimized for transcribing figures to ATO
3. **CSV export format** - No CSV option for data transfer or import into other systems
4. **Lodgement tracking** - No way to record which BAS periods have been lodged versus pending
5. **Lodgement confirmation details** - No storage for ATO reference numbers or lodgement dates
6. **Deadline monitoring** - No visibility into approaching lodgement deadlines across clients

This creates a workflow gap where accountants must manually format export data and track lodgement status outside of Clairo, reducing the platform's value proposition and creating compliance risk through missed deadlines.

---

## User Scenarios & Testing

### User Story 1: Lodgement Status Tracking (Priority: P1)

As an accountant, I want to track the lodgement status of each BAS session, so that I know which clients have been lodged and which are still pending.

**Why this priority**: This is the core feature that closes the BAS workflow loop. Without status tracking, accountants cannot use Clairo as their single source of truth for BAS progress.

**Independent Test**: Can be tested by marking a BAS session as lodged and verifying the status is displayed correctly with all lodgement details captured.

**Acceptance Scenarios:**

1. **Given** a new BAS session is created, **When** I view the session, **Then** the lodgement status displays as "Not Lodged" by default.

2. **Given** I am viewing an APPROVED BAS session, **When** I click "Record Lodgement", **Then** I see a form requiring:
   - Lodgement date
   - Lodgement method (ATO Portal, Xero, Other)
   - Optional: ATO reference number

3. **Given** I complete the lodgement recording form, **When** I submit it, **Then** the system:
   - Updates the BAS session status to "Lodged"
   - Stores the lodgement date, method, and reference number
   - Creates an audit log entry with full lodgement details

4. **Given** I select "Other" as the lodgement method, **When** the form displays, **Then** I can enter an optional free-text description of the lodgement method.

5. **Given** a BAS session is marked as lodged, **When** I view the session, **Then** I see:
   - Lodgement status badge
   - Lodgement date
   - Lodgement method
   - ATO reference number (if recorded)
   - User who recorded the lodgement

6. **Given** I need to update lodgement details after recording, **When** I edit the lodgement, **Then** I can modify:
   - ATO reference number (can be added after initial lodgement)
   - Lodgement notes
   - But I cannot change lodgement date or method after recording

7. **Given** any lodgement status change occurs, **When** the change is saved, **Then** the system creates an immutable audit log entry capturing:
   - Previous status
   - New status
   - User who made the change
   - Timestamp
   - All lodgement details at time of change

---

### User Story 2: Enhanced BAS Export for Lodgement (Priority: P1)

As an accountant, I want my existing BAS exports enhanced with ATO-compliant lodgement summary views, so that I can efficiently transcribe figures into the ATO portal or Xero for lodgement.

**Why this priority**: Enhanced exports are essential for the actual lodgement process. Without ATO-compliant formatting, accountants must manually reformat data before lodging.

**Independent Test**: Can be tested by exporting an approved BAS session and verifying the output contains all required ATO fields in the correct format.

#### Context: What Already Exists

The BAS exporter module currently provides:
- **PDF Export**: Working paper format with BAS calculations and supporting details
- **Excel Export**: Spreadsheet with BAS calculations, formulas, and data

#### Enhancement Scope

This requirement enhances existing exports with:
- **ATO-compliant lodgement summary** added to PDF and Excel exports
- **New CSV export format** for data transfer (see User Story 5)

**Acceptance Scenarios:**

1. **Given** I am viewing an APPROVED BAS session, **When** I click on export options, **Then** I see enhanced export options for PDF, Excel, and CSV formats with "Lodgement Summary" labeling.

2. **Given** I export BAS data as PDF, **When** the export completes, **Then** the PDF includes an ATO-compliant lodgement summary section containing:
   - Client name and ABN
   - BAS period (quarter/month and financial year)
   - Period dates (start and end)
   - All GST fields (G1, G2, G3, G10, G11, 1A, 1B) formatted for ATO portal entry
   - PAYG withholding fields (W1, W2) if applicable
   - Net GST payable/refundable
   - Total amount payable/refundable to ATO
   - Clear field labels matching ATO BAS form terminology
   - All amounts rounded to whole dollars (per ATO requirements)

3. **Given** I export BAS data as Excel, **When** the export completes, **Then** the Excel includes a dedicated "Lodgement Summary" sheet containing:
   - Summary of all BAS fields and values in ATO form order
   - Clear formatting for easy manual data entry reference
   - Field descriptions matching ATO terminology
   - Amounts rounded to whole dollars

4. **Given** a BAS session is not in APPROVED status, **When** I attempt to export for lodgement, **Then** the system prevents the lodgement-format export and displays a message indicating the BAS must be approved first.

5. **Given** an export is generated, **When** the download completes, **Then** the system logs an audit event recording the export type, timestamp, and user who performed the export.

---

### User Story 3: Workflow Integration (Priority: P2)

As an accountant, I want lodgement status integrated into my existing BAS workflow, so that I have a complete view of all BAS progress across clients.

**Why this priority**: Dashboard visibility improves workflow efficiency, but core lodgement tracking and export features must work first.

**Independent Test**: Can be tested by viewing the BAS dashboard and verifying lodgement status is visible and filterable.

**Acceptance Scenarios:**

1. **Given** I am viewing the BAS dashboard, **When** the page loads, **Then** I see lodgement status for each BAS session alongside existing status information.

2. **Given** I want to filter BAS sessions, **When** I use the filter controls, **Then** I can filter by lodgement status:
   - Not Lodged
   - Lodged

3. **Given** I am viewing a client's BAS history, **When** the page loads, **Then** I see lodgement status with visual indicators:
   - Not Lodged: Yellow/warning indicator
   - Lodged: Green/success indicator

4. **Given** a BAS is in APPROVED status, **When** I view the session, **Then** I see a prominent "Record Lodgement" action button.

5. **Given** I click "Record Lodgement", **When** I complete the form and submit, **Then** the BAS transitions from APPROVED to LODGED status.

6. **Given** I try to transition a BAS to LODGED without completing the lodgement form, **When** I submit, **Then** the system prevents the transition and displays a validation message.

7. **Given** I am viewing BAS session details, **When** the page loads, **Then** I see a clear workflow timeline showing:
   - Session created
   - Calculations completed
   - Approved (with approver and timestamp)
   - Lodged (with lodgement details)

---

### User Story 4: Enhanced PDF Export with ATO Portal Formatting (Priority: P2)

As an accountant, I want the existing PDF export enhanced with ATO portal-specific formatting, so that I can efficiently transcribe figures without errors.

**Why this priority**: This is a refinement of the basic enhanced export, adding polish to the ATO-compliant formatting after core export functionality is established.

**Independent Test**: Can be tested by exporting a lodgement PDF and verifying field order matches ATO BAS form exactly.

#### Context

This requirement enhances the existing PDF export functionality with ATO-compliant formatting. The base PDF generation capability already exists in the BAS exporter module.

**Acceptance Scenarios:**

1. **Given** I generate a lodgement PDF export, **When** the PDF is created, **Then** it includes a lodgement summary section formatted to match ATO BAS form field order and terminology.

2. **Given** the PDF displays GST fields in the lodgement summary, **When** I view the section, **Then** I see:
   - All amounts rounded to whole dollars (per ATO requirements)
   - Fields displayed in ATO form order (G1, G2, G3, G10, G11, 1A, 1B)
   - Clear field labels matching ATO terminology

3. **Given** the client has PAYG withholding data, **When** the PDF displays PAYG fields, **Then** I see:
   - W1 (Total salary, wages and other payments)
   - W2 (Amount withheld from payments)
   - PAYG section only appears if W1 > 0

4. **Given** the PDF displays the summary section, **When** I view the totals, **Then** I see clearly labeled:
   - Total GST payable or refundable
   - Total PAYG withholding
   - Net amount payable to ATO or refundable

5. **Given** a lodgement PDF is generated, **When** I view the document, **Then** I see:
   - "APPROVED FOR LODGEMENT" watermark/stamp on lodgement summary page
   - Approval date and approver name
   - Generation timestamp
   - Page numbers if multi-page

---

### User Story 5: CSV Export for Data Transfer (Priority: P3)

As an accountant, I want to export BAS data as CSV, so that I can import it into other systems or use it for data analysis.

**Why this priority**: CSV export is a convenience feature for data transfer. Core lodgement workflow functions are more important.

**Independent Test**: Can be tested by exporting a BAS as CSV and importing it into Excel to verify format correctness.

#### Context

This is a new export format that does not currently exist in the BAS exporter module.

**Acceptance Scenarios:**

1. **Given** I export an approved BAS as CSV, **When** the export completes, **Then** the file contains the following columns:
   - Field Code (G1, G2, G3, etc.)
   - Field Description
   - Amount (rounded to whole dollars)

2. **Given** I export as CSV, **When** I open the file, **Then** I see metadata rows at the top:
   - Client Name
   - ABN
   - Period
   - Export Date

3. **Given** the CSV is generated, **When** I inspect the file, **Then** it uses standard CSV formatting:
   - UTF-8 encoding
   - Comma-separated values
   - Quoted text fields
   - Numeric fields without currency symbols

4. **Given** I open the exported CSV in Excel, **When** the file loads, **Then** amounts display correctly as numbers (not text).

---

### User Story 6: Lodgement Deadline Notifications (Priority: P3)

As an accountant, I want to be notified when BAS lodgement deadlines are approaching, so that I can ensure timely lodgement for all clients.

**Why this priority**: Deadline notifications are helpful for compliance but are a nice-to-have feature compared to core lodgement tracking and export.

**Independent Test**: Can be tested by setting up a BAS with an approaching deadline and verifying a notification is generated.

**Acceptance Scenarios:**

1. **Given** a BAS period has an approaching deadline (configurable: 7 days, 3 days, 1 day), **When** the deadline check runs, **Then** the system generates a notification for the accountant if the BAS is not yet lodged.

2. **Given** I view my notifications, **When** deadline notifications exist, **Then** I see:
   - Client name
   - BAS period
   - Due date
   - Days remaining until deadline
   - Current BAS status

3. **Given** a BAS is lodged, **When** the lodgement is recorded, **Then** the system dismisses any pending deadline notifications for that BAS period.

4. **Given** multiple BAS periods are approaching deadline, **When** I view notifications, **Then** I see a consolidated summary view showing all approaching deadlines.

5. **Given** I want to configure notification preferences, **When** I access settings, **Then** I can:
   - Enable/disable deadline notifications
   - Configure notification timing (days before deadline)

---

### User Story 7: Notifications & Actions Dashboard (Priority: P2)

As an accountant managing hundreds of clients, I want a dedicated page to view, filter, and prioritize all notifications and pending actions, so that I can efficiently manage my workload across my entire client base.

**Why this priority**: Accountants managing 1000+ clients could have hundreds of notifications. The bell dropdown is insufficient for this volume - a dedicated page with filtering, search, and priority sorting is essential for workflow management.

**Independent Test**: Can be tested by creating multiple notifications of various types and verifying the page displays them with correct filtering, sorting, and search functionality.

**Acceptance Scenarios:**

1. **Given** I am logged in as an accountant, **When** I click "View all notifications" from the notification bell dropdown, **Then** I am navigated to a dedicated Notifications & Actions page.

2. **Given** I am on the Notifications page, **When** the page loads, **Then** I see a table view with columns:
   - Priority indicator (high/medium/low based on urgency)
   - Notification type icon
   - Title/Description
   - Client name
   - Due date (if applicable)
   - Days remaining/overdue
   - Status (unread/read/actioned)
   - Created date
   - Quick actions

3. **Given** I want to filter notifications, **When** I use the filter controls, **Then** I can filter by:
   - Status (unread, read, all)
   - Type (deadline approaching, overdue, review assigned, etc.)
   - Priority (high, medium, low)
   - Client (searchable dropdown)
   - Date range

4. **Given** I want to search notifications, **When** I type in the search box, **Then** the table filters to show notifications matching:
   - Client name
   - Notification title
   - Notification message content

5. **Given** I want to sort notifications, **When** I click column headers, **Then** I can sort by:
   - Priority (default: high to low)
   - Due date (soonest first)
   - Created date (newest first)
   - Client name (alphabetical)

6. **Given** there are more than 50 notifications, **When** I scroll or paginate, **Then** the table loads additional notifications efficiently without performance degradation.

7. **Given** I view a notification in the table, **When** I click on it, **Then** I am navigated to the relevant entity (e.g., client BAS page for deadline notifications).

8. **Given** I want to take bulk actions, **When** I select multiple notifications, **Then** I can:
   - Mark selected as read
   - Dismiss selected
   - (Optional) Export selected to CSV

9. **Given** I view the notifications page, **When** new notifications arrive, **Then** the page shows a subtle indicator that new items are available (without auto-refreshing and losing my place).

10. **Given** I have configured notification preferences, **When** I view the notifications page, **Then** I see a link to notification settings.

11. **Given** notifications exist for different priority levels, **When** I view the page, **Then** I see visual priority indicators:
    - High priority (red): Overdue items, due today, due tomorrow
    - Medium priority (amber): Due within 7 days
    - Low priority (blue): Informational notifications, items due beyond 7 days

12. **Given** I am on the notifications page, **When** I view the summary section, **Then** I see aggregated counts:
    - Total unread notifications
    - High priority items requiring attention
    - Overdue items count
    - Items due this week

---

### User Story 8: BAS Lodgement Workboard (Priority: P1)

As an accountant managing hundreds of clients, I want a centralized workboard showing all BAS periods with their deadlines and statuses, so that I can proactively prioritize my lodgement work across my entire client portfolio.

**Why this priority**: This is the accountant's primary work queue. Unlike reactive notifications, this gives a proactive view of ALL upcoming deadlines across 1000+ clients, enabling strategic workload planning.

**Independent Test**: Can be tested by creating multiple clients with BAS periods at various statuses and due dates, then verifying the workboard displays them correctly with filtering and sorting.

**Acceptance Scenarios:**

1. **Given** I am logged in as an accountant, **When** I click "BAS Lodgements" in the sidebar, **Then** I see a workboard showing all clients' current BAS periods.

2. **Given** I am on the Lodgement Workboard, **When** the page loads, **Then** I see a table with columns:
   - Client name (organization)
   - BAS Period (e.g., "Q1 FY2025")
   - Due Date
   - Days Remaining (with urgency color coding)
   - BAS Status (Not Started, Calculating, Needs Review, Approved, Lodged)
   - Quality Score (if calculated)
   - Net GST Amount (if calculated)
   - Quick Actions

3. **Given** I view the workboard, **When** looking at the Days Remaining column, **Then** I see urgency indicators:
   - Red: Overdue (negative days)
   - Red: Due Today or Tomorrow
   - Amber: Due within 7 days
   - Yellow: Due within 14 days
   - Green: Due beyond 14 days

4. **Given** I want to filter the workboard, **When** I use filter controls, **Then** I can filter by:
   - Quarter/Period (Q1, Q2, Q3, Q4 or specific FY quarter)
   - Status (Not Started, In Progress, Needs Review, Approved, Lodged, All)
   - Urgency (Overdue, Due This Week, Due This Month, All)
   - Search by client name

5. **Given** I want to prioritize my work, **When** I sort the table, **Then** I can sort by:
   - Due Date (default: soonest first)
   - Client Name (alphabetical)
   - Status
   - Net GST Amount (largest payable first)

6. **Given** I view a client row, **When** I want to take action, **Then** I can:
   - Click client name to navigate to client detail page
   - Click "Start BAS" for clients with no BAS session
   - Click "Review" for clients needing review
   - Click "Lodge" for approved clients ready to lodge
   - Click "View" for already lodged clients

7. **Given** I view the workboard, **When** I look at the summary section, **Then** I see:
   - Total clients in portfolio
   - Overdue count (red badge)
   - Due this week count
   - Ready to lodge count (approved, not yet lodged)
   - Already lodged count

8. **Given** there are clients with no BAS session for the current quarter, **When** I view the workboard, **Then** these clients appear with status "Not Started" and I can initiate BAS preparation.

9. **Given** I select a different quarter from the quarter picker, **When** the filter applies, **Then** the workboard shows BAS periods for that specific quarter across all clients.

10. **Given** I want to see historical lodgements, **When** I select "Lodged" status filter, **Then** I see all completed lodgements with their lodgement dates.

11. **Given** I am on the workboard, **When** new data syncs from Xero, **Then** I can refresh the view to see updated calculations without losing my filter/sort preferences.

12. **Given** there are more than 50 clients, **When** I scroll or paginate, **Then** the workboard loads efficiently with proper pagination.

---

### Edge Cases

- **What happens if an accountant tries to export an unapproved BAS?** The system blocks the lodgement-format export with a message indicating approval is required first. (Note: basic working paper exports may still be available for draft review.)
- **What happens if lodgement is recorded but the ATO reference is not yet available?** The system allows lodgement recording without reference number; reference can be added later.
- **What happens if multiple users try to record lodgement simultaneously?** The system uses optimistic locking to prevent race conditions; first successful submission wins.
- **What happens if a lodged BAS needs to be amended?** The current BAS remains lodged; user must create a new amendment BAS (future scope).
- **What happens if the BAS deadline has passed?** The system still allows lodgement recording; displays overdue warning but does not block.
- **What happens if a BAS period has no due date set?** The system skips deadline notifications for that period; prompts user to set due date.

---

## Functional Requirements

- **FR-001**: System MUST only allow ATO-compliant lodgement export when session status is APPROVED.

- **FR-002**: System MUST enhance existing PDF and Excel exports with ATO-compliant lodgement summary sections.

- **FR-003**: System MUST provide new CSV export format for approved BAS data.

- **FR-004**: System MUST track lodgement status (Not Lodged, Lodged) for each BAS session.

- **FR-005**: System MUST record lodgement details including date, method, and optional ATO reference number.

- **FR-006**: System MUST maintain an immutable audit trail for all lodgement status changes.

- **FR-007**: System MUST allow filtering BAS sessions by lodgement status on the dashboard.

- **FR-008**: System MUST generate notifications for approaching BAS lodgement deadlines.

- **FR-009**: System MUST dismiss deadline notifications when a BAS is marked as lodged.

- **FR-010**: System MUST round all BAS field amounts to whole dollars in lodgement exports (per ATO requirements).

- **FR-011**: System MUST display lodgement status prominently in BAS session views.

- **FR-012**: System MUST prevent BAS status transition to LODGED without completing lodgement recording form.

- **FR-013**: System MUST allow addition of ATO reference number after initial lodgement recording.

- **FR-014**: System MUST provide a dedicated Notifications & Actions page accessible from the main navigation and notification bell dropdown.

- **FR-015**: System MUST support filtering notifications by status, type, priority, client, and date range.

- **FR-016**: System MUST support full-text search across notification title, message, and client name.

- **FR-017**: System MUST support sorting notifications by priority, due date, created date, and client name.

- **FR-018**: System MUST support pagination for efficient loading of large notification volumes (1000+).

- **FR-019**: System MUST provide bulk actions (mark as read, dismiss) for selected notifications.

- **FR-020**: System MUST display priority indicators based on urgency (overdue = high, due within 7 days = medium, others = low).

- **FR-021**: System MUST display aggregated notification counts (unread, high priority, overdue, due this week).

---

## Non-Functional Requirements

### Performance

1. Enhanced PDF export generation SHALL complete within 5 seconds for any BAS session.

2. CSV export generation SHALL complete within 2 seconds for any BAS session.

3. Enhanced Excel export generation SHALL complete within 5 seconds for any BAS session.

4. Dashboard filtering by lodgement status SHALL return results within 1 second.

5. Lodgement status updates SHALL be reflected in the UI within 500 milliseconds.

6. Notifications page SHALL load initial 50 notifications within 1 second for tenants with 1000+ notifications.

7. Notification search SHALL return results within 500 milliseconds.

8. Notification filtering SHALL apply within 300 milliseconds.

### Security

1. Export files SHALL NOT contain sensitive data beyond what is necessary for BAS lodgement (no bank account details, no employee personal information).

2. All export actions SHALL be logged in the audit trail with user identification.

3. Lodgement recording SHALL only be accessible to users with appropriate tenant permissions.

4. Export downloads SHALL use secure, time-limited URLs to prevent unauthorized access.

### Reliability

1. Export generation SHALL retry on failure (max 3 retries) before reporting an error.

2. Lodgement status updates SHALL be atomic to prevent partial updates.

3. Audit log entries SHALL be written synchronously with status changes to ensure data integrity.

### Usability

1. Export buttons SHALL be clearly labeled with format type (PDF, Excel, CSV) and indicate lodgement-ready format.

2. Lodgement recording form SHALL provide clear validation messages for required fields.

3. Deadline notifications SHALL be dismissible and not interfere with primary workflow.

4. Lodgement status indicators SHALL use consistent color coding across all views.

### Compliance

1. All lodgement records SHALL be retained for minimum 7 years per ATO requirements.

2. Audit logs for lodgement events SHALL be immutable and timestamped.

3. Exported documents SHALL include generation timestamp for audit purposes.

---

## Data Model Additions

### Lodgement Method Enum

```
LodgementMethod:
  - ATO_PORTAL: Direct lodgement via ATO Business Portal
  - XERO: Lodgement through Xero integration
  - OTHER: Other lodgement method (requires description)
```

### BAS Session Extensions

The existing BASSession model will be extended with:

```
BASSession (additions):
  - lodged_at: datetime (nullable)
  - lodged_by: UUID (foreign key to users)
  - lodgement_method: LodgementMethod (nullable)
  - lodgement_method_description: string (nullable, for "Other" method)
  - ato_reference_number: string (nullable)
  - lodgement_notes: text (nullable)
```

### Audit Events

New audit event types:

```
BASAuditEventType (additions):
  - EXPORT_PDF_LODGEMENT_GENERATED: Enhanced PDF export with lodgement summary created
  - EXPORT_CSV_GENERATED: CSV export created (new format)
  - EXPORT_EXCEL_LODGEMENT_GENERATED: Enhanced Excel export with lodgement summary created
  - LODGEMENT_RECORDED: BAS marked as lodged
  - LODGEMENT_UPDATED: Lodgement details updated
  - DEADLINE_NOTIFICATION_SENT: Deadline notification generated
```

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **Direct ATO API Lodgement** - Automatic submission to ATO (future GovReports integration)
2. **Xero BAS Lodgement API** - Automatic lodgement through Xero (requires separate integration)
3. **BAS Amendment Workflow** - Handling corrections to lodged BAS
4. **Bulk Lodgement Recording** - Recording lodgement for multiple clients at once
5. **Email Notifications** - Email delivery of deadline notifications (uses in-app notifications only)
6. **Lodgement Receipt Storage** - Storing ATO confirmation documents/receipts
7. **Payment Tracking** - Tracking whether BAS amounts have been paid to ATO
8. **New PDF/Excel Export Engine** - Base export functionality already exists; this spec only enhances it

---

## Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Spec 009: BAS Prep Workflow | BASSession, BASCalculation models | COMPLETE |
| BAS Exporter Module | PDF and Excel export functionality | **IMPLEMENTED** |
| BASSessionStatus.LODGED | Existing status in workflow | Available |
| Notification System | In-app notification infrastructure | Available |
| Audit Trail System | Audit logging for BAS events | Available |

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of approved BAS sessions can be exported with enhanced ATO-compliant lodgement summary (PDF, Excel, CSV)
- **SC-002**: Lodgement status accurately tracked for all BAS sessions
- **SC-003**: Audit trail captures all lodgement events with full details
- **SC-004**: Deadline notifications generated for 100% of approaching deadlines
- **SC-005**: Zero data loss on lodgement status updates

---

## Glossary

| Term | Definition |
|------|------------|
| **Lodgement** | The act of submitting a BAS to the ATO |
| **ATO Reference Number** | Unique identifier provided by ATO upon successful lodgement |
| **Interim Lodgement** | Manual lodgement process pending direct API integration |
| **ATO Portal** | Australian Taxation Office Business Portal for online lodgement |
| **BAS Form** | Business Activity Statement form with GST and PAYG fields |
| **Lodgement Summary** | ATO-compliant section added to exports for easy portal data entry |
| **Working Paper** | Existing PDF/Excel export with detailed calculations (not ATO-formatted) |
