# Feature Specification: Voice Feedback Portal

**Feature Branch**: `048-voice-feedback-portal`
**Created**: 2026-03-16
**Status**: Draft
**Input**: Voice-powered feedback portal for SME advisors built into Clairo's Support & Feedback section. Users upload voice memos or record directly, choose a mode (Feature Request or Bug/Enhancement), the system transcribes and an AI agent engages in a clarification conversation until a structured brief is produced. Lightweight kanban board for team prioritisation.

## User Scenarios & Testing

### User Story 1 — Submit Voice Feedback (Priority: P1)

A domain expert (Vik, Unni, or any future platform user) notices something while working — a missing feature, a workflow gap, or a bug. They navigate to the Support & Feedback section, tap "New Submission", select the mode (Feature Request or Bug/Enhancement), and either upload a pre-recorded voice memo or record one directly in the browser. The system transcribes the audio and an AI agent immediately begins a structured conversation: it summarises what it understood, identifies gaps in the information, and asks targeted follow-up questions. The user responds via text or additional voice messages until the agent confirms it has enough detail. The agent then generates a structured brief and the user reviews and confirms it. The submission is saved.

**Why this priority**: This is the entire value proposition. Without voice capture and AI-structured conversation, there is no feature. Everything else builds on this.

**Independent Test**: Can be fully tested by recording a voice memo describing a feature idea, completing the AI conversation, and verifying the structured brief is saved and viewable.

**Acceptance Scenarios**:

1. **Given** a logged-in user on the feedback page, **When** they select "Feature Request" and upload a 90-second voice memo, **Then** the system transcribes the audio within 30 seconds and the AI agent presents a summary with follow-up questions.
2. **Given** a logged-in user on the feedback page, **When** they select "Bug / Enhancement" and record audio directly in the browser, **Then** the recording is captured, transcribed, and the AI agent begins the structured conversation.
3. **Given** an active AI conversation, **When** the user answers all follow-up questions, **Then** the agent generates a structured brief matching the selected mode template (feature request or bug report format).
4. **Given** a generated brief, **When** the user reviews and confirms it, **Then** the submission is saved to the database with status "New" and visible on the kanban board.
5. **Given** a voice memo with unclear or incomplete information, **When** the AI agent cannot determine key details, **Then** it asks specific follow-up questions rather than guessing, and does not generate the brief until minimum required fields are captured.

---

### User Story 2 — AI Clarification Conversation (Priority: P1)

The AI agent operates in one of two modes depending on the user's selection:

**Feature Request mode (PM hat)**: The agent extracts and asks about: the user scenario or workflow being described, who is affected, what the current behaviour is, what the desired behaviour would be, how often the situation occurs, and the perceived business impact. The output brief contains: title, user story, current behaviour, desired behaviour, domain context, estimated frequency/impact, and any open questions.

**Bug / Enhancement mode (Engineer hat)**: The agent extracts and asks about: what the user was doing when they noticed the issue, what happened vs what should have happened, whether it's blocking their work, and any business rules or compliance logic that are relevant. The output brief contains: title, type (bug/enhancement/logic error), observed behaviour, expected behaviour, business rule (if applicable), severity assessment, and reproduction context.

The conversation continues until the agent has populated all required fields in the brief template. The user can provide answers via text typing or additional voice recordings within the same conversation.

**Why this priority**: The quality of the structured brief is what makes the entire system valuable. A poor conversation produces a poor brief, which defeats the purpose.

**Independent Test**: Can be tested by submitting the same raw feedback in each mode and verifying the output briefs contain the correct fields and ask the right follow-up questions.

**Acceptance Scenarios**:

1. **Given** a Feature Request mode conversation, **When** the initial transcript mentions a workflow gap but doesn't specify who is affected, **Then** the agent asks specifically about the affected user role and workflow context.
2. **Given** a Bug / Enhancement mode conversation, **When** the initial transcript describes unexpected behaviour, **Then** the agent asks about reproduction steps, expected behaviour, and severity.
3. **Given** either mode, **When** the user provides a follow-up answer via a new voice recording, **Then** the system transcribes it and the agent incorporates the new information into the evolving brief.
4. **Given** a completed conversation, **When** the agent generates the final brief, **Then** all required template fields are populated and the brief is presented for user review before saving.

---

### User Story 3 — View and Manage Submissions on Kanban Board (Priority: P2)

Team members (Suren, and eventually other authorised users) can view all submissions on a kanban board organised by status: New, In Review, Planned, In Progress, Done. Each card shows the submission title, type (feature/bug), submitter name, date, and severity/impact indicator. Cards can be moved between columns to update status. Clicking a card opens the full brief with the original transcript and conversation history.

**Why this priority**: Without a way to view and track submissions, the feedback disappears into the database. The kanban provides visibility and prioritisation for the team.

**Independent Test**: Can be tested by creating several submissions and verifying they appear as cards on the board, can be moved between columns, and display correct details when opened.

**Acceptance Scenarios**:

1. **Given** multiple saved submissions, **When** a team member opens the feedback board, **Then** submissions appear as cards in the correct status column, sorted by most recent first within each column.
2. **Given** a submission card on the board, **When** a team member drags it from "New" to "In Review", **Then** the status is updated in the database and the card moves to the new column.
3. **Given** a submission card, **When** a team member clicks on it, **Then** a detail view opens showing the full structured brief, the original audio transcript, the AI conversation history, and submission metadata.
4. **Given** the kanban board, **When** submissions exist across multiple types, **Then** cards are visually distinguished by type (feature request vs bug/enhancement) using colour-coded badges.

---

### User Story 4 — Submission List and Filtering (Priority: P2)

Users can view their own past submissions in a list view as an alternative to the kanban. The list supports filtering by type (feature request, bug/enhancement), status (new, in review, planned, in progress, done), and date range. Submitters see only their own submissions. Team administrators see all submissions across all submitters.

**Why this priority**: As submission volume grows, filtering and list view become necessary for finding specific items. Also gives submitters visibility into the status of their own feedback.

**Independent Test**: Can be tested by creating submissions of different types and statuses, then verifying filters correctly narrow results.

**Acceptance Scenarios**:

1. **Given** a submitter viewing their submissions, **When** they filter by "Bug / Enhancement", **Then** only bug/enhancement submissions are shown.
2. **Given** an administrator viewing all submissions, **When** they sort by date, **Then** submissions appear in chronological or reverse-chronological order.
3. **Given** a submitter, **When** they view the feedback page, **Then** they see only their own submissions — not submissions from other users.

---

### User Story 5 — Team Notes and Comments (Priority: P3)

Team members can add internal notes or comments to any submission. These notes are visible only to the team (not to the original submitter if they are a non-team user in the future). Notes support basic text and are timestamped with the author's name.

**Why this priority**: Enables team discussion around submissions without needing external tools. Lower priority because the team can use Slack or other channels initially.

**Independent Test**: Can be tested by adding a comment to a submission and verifying it appears in the detail view with correct author and timestamp.

**Acceptance Scenarios**:

1. **Given** a submission detail view, **When** a team member adds a note, **Then** the note appears in the notes section with timestamp and author name.
2. **Given** a submission with multiple notes, **When** viewing the detail, **Then** notes appear in chronological order.

---

### User Story 6 — Brief Export for Speckit (Priority: P3)

A team member can export a completed brief as a markdown document formatted for use as input to the speckit specification workflow. The export includes all structured fields from the brief in a format that can be directly pasted into a `/speckit.specify` command or saved as a reference document.

**Why this priority**: This closes the loop from voice feedback to actionable specification. Lower priority because copy-paste from the detail view works as a manual fallback.

**Independent Test**: Can be tested by exporting a brief and verifying the markdown output contains all required fields in the expected format.

**Acceptance Scenarios**:

1. **Given** a completed submission brief, **When** a team member clicks "Export for Spec", **Then** a markdown document is generated containing the structured brief in speckit-compatible format.
2. **Given** an exported brief, **When** it is used as input to `/speckit.specify`, **Then** the specification workflow can proceed without requiring additional context from the original submitter.

---

### Edge Cases

- What happens when a voice memo is too short (under 5 seconds) or contains only silence/noise? The system rejects it with a clear message asking the user to re-record.
- What happens when the voice memo is in a language other than English? The system attempts transcription and notifies the user if confidence is low.
- What happens when the user abandons the AI conversation before completing it? The submission is saved as a draft that can be resumed later.
- What happens when the AI agent cannot determine the category from the transcript? The agent asks the user to clarify rather than guessing.
- What happens when a voice memo exceeds the maximum length? The system enforces a maximum recording duration (5 minutes) and notifies the user before they start recording.
- What happens when the browser does not support audio recording? The system falls back to upload-only mode with a message explaining why recording is unavailable.
- What happens when network connectivity is lost during recording? The recording is saved locally in the browser and the user is prompted to retry upload when connectivity returns.

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow users to upload pre-recorded audio files (MP3, M4A, WAV, WebM) up to 25MB in size.
- **FR-002**: System MUST allow users to record audio directly in the browser using the device microphone, with a maximum recording duration of 5 minutes.
- **FR-003**: System MUST transcribe uploaded or recorded audio to text using a speech-to-text service, completing transcription within 30 seconds for recordings under 3 minutes.
- **FR-004**: System MUST provide two submission modes: "Feature Request" and "Bug / Enhancement", selectable before or after recording.
- **FR-005**: System MUST initiate an AI-powered clarification conversation immediately after transcription, using mode-specific prompts (PM hat for feature requests, Engineer hat for bugs/enhancements).
- **FR-006**: The AI agent MUST ask targeted follow-up questions until all required brief template fields are populated, rather than generating incomplete briefs.
- **FR-007**: Users MUST be able to respond to AI follow-up questions via text input or additional voice recordings within the same conversation.
- **FR-008**: System MUST generate a structured brief from the completed conversation, matching the template for the selected mode.
- **FR-009**: Users MUST be able to review the generated brief and confirm or request revisions before the submission is saved.
- **FR-010**: System MUST save confirmed submissions with status "New" and associate them with the submitting user and their tenant.
- **FR-011**: System MUST store the original audio file reference, transcript, full conversation history, and structured brief for each submission.
- **FR-012**: System MUST display submissions on a kanban board with columns: New, In Review, Planned, In Progress, Done.
- **FR-013**: Authorised team members MUST be able to move submission cards between kanban columns to update status.
- **FR-014**: System MUST provide a list view alternative to the kanban with filtering by type, status, and date range.
- **FR-015**: Submitters MUST see only their own submissions. Administrators MUST see all submissions within their tenant.
- **FR-016**: Team members MUST be able to add internal notes/comments to any submission.
- **FR-017**: System MUST support exporting a completed brief as a markdown document formatted for speckit input.
- **FR-018**: System MUST save incomplete conversations as drafts that can be resumed later.
- **FR-019**: System MUST enforce tenant isolation — submissions are scoped to the tenant of the submitting user.
- **FR-020**: System MUST display a visual recording indicator (duration timer, waveform) during in-browser recording.

### Key Entities

- **Feedback Submission**: A single piece of feedback from a user. Contains: title, type (feature_request / bug_enhancement), status (new / in_review / planned / in_progress / done), submitter reference, tenant reference, severity/impact assessment, structured brief content, original transcript, audio file reference, creation and update timestamps.
- **Feedback Conversation**: The AI-driven clarification conversation associated with a submission. Contains: ordered sequence of messages (user messages and AI messages), each with role, content, and timestamp. Linked to exactly one submission.
- **Feedback Comment**: An internal team note on a submission. Contains: author reference, comment text, timestamp. Linked to exactly one submission. Visible only to team members.

## Auditing & Compliance Checklist

### Audit Events Required

- [ ] **Authentication Events**: No — uses existing platform authentication.
- [x] **Data Access Events**: Yes — submissions may contain domain-sensitive information (workflow details, compliance logic, client references).
- [x] **Data Modification Events**: Yes — submission creation, status changes, and comment additions should be tracked.
- [ ] **Integration Events**: No — no external system sync (transcription is a utility call, not a data integration).
- [ ] **Compliance Events**: No — this feature does not affect BAS lodgements or compliance status.

### Audit Implementation Requirements

| Event Type              | Trigger                        | Data Captured                                     | Retention | Sensitive Data |
| ----------------------- | ------------------------------ | ------------------------------------------------- | --------- | -------------- |
| feedback.created        | Submission confirmed and saved | Submission ID, type, submitter, tenant            | 7 years   | None           |
| feedback.status_change  | Card moved on kanban           | Submission ID, old status, new status, changed_by  | 7 years   | None           |
| feedback.comment_added  | Team note added                | Submission ID, comment author, timestamp          | 7 years   | None           |
| feedback.exported       | Brief exported as markdown     | Submission ID, exported_by                        | 7 years   | None           |

### Compliance Considerations

- **ATO Requirements**: None directly. This feature captures product feedback, not financial or compliance data. However, submissions may incidentally reference client scenarios — the audio and transcript storage should follow standard data retention.
- **Data Retention**: Audio files and transcripts retained for the life of the submission. Deleted submissions should have audio files removed within 30 days.
- **Access Logging**: Standard access logging. No elevated audit requirements beyond what is specified above.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A domain expert can go from "I have an idea" to a saved structured brief in under 5 minutes (including recording, transcription, and AI conversation).
- **SC-002**: 80% of generated briefs contain enough detail to proceed to specification without requiring a follow-up call or meeting with the submitter.
- **SC-003**: Transcription completes within 30 seconds for recordings under 3 minutes.
- **SC-004**: The AI conversation requires no more than 5 follow-up exchanges on average to produce a complete brief.
- **SC-005**: Team members can view and prioritise all pending submissions within 30 seconds of opening the feedback board.
- **SC-006**: Submission volume from SME advisors increases by at least 3x compared to the pre-feature baseline (informal Slack/verbal feedback frequency).
- **SC-007**: Time from "feedback received" to "actionable specification created" reduces by at least 50% compared to manual processing.

## Assumptions

- Users will primarily use this feature on desktop browsers. Mobile browser recording is supported but not the primary use case.
- The platform already has authenticated user sessions — no new authentication mechanism is needed.
- Audio file storage will use the existing infrastructure (cloud storage bucket). No new storage service is required.
- The AI clarification conversation uses the existing Anthropic Claude integration. No new AI vendor is needed.
- Transcription will use an external speech-to-text API. The specific provider is an implementation decision.
- The initial user base is 2-3 SME advisors. The feature is designed to scale to all platform users but initial UX decisions can favour the small-team use case.
- Kanban drag-and-drop will use a client-side library. The specific library is an implementation decision.
- The "Export for Spec" format aligns with the current speckit input expectations and may evolve as the speckit workflow evolves.
