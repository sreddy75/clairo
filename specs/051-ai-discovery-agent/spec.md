# Feature Specification: Discovery Agent

**Feature Branch**: `051-ai-discovery-agent`
**Created**: 2026-04-04
**Status**: Draft (v2 — standalone service rewrite)
**Input**: Standalone AI-powered interview platform that conducts expert-grade discovery conversations with domain professionals, extracts structured product requirements using JTBD methodology, and aggregates insights across multiple interviewees. Domain-configurable for any vertical (accounting, legal, healthcare, etc.).

## Product Vision

A standalone service that any product team can deploy to interview domain experts at scale. The agent is not a chatbot with a question list — it is a forensic interviewer that reconstructs specific past events, decodes solution-talk into problem statements, and produces structured specifications grounded in real practitioner behaviour.

**Core principle**: When someone says "I need a spreadsheet template," the agent hears a problem to be defined: *"Minimize the time it takes to categorise 200 transactions without errors."* Every solution described by an interviewee is treated as a symptom. The agent's job is to find the underlying job-to-be-done.

**Domain-configurable**: The same engine serves accounting (Clairo), legal (EzyLegal), or any future vertical. Domain-specific elements (terminology, extraction dimensions, prompts) are configuration, not code.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Guided Discovery Conversation (Priority: P1)

A product owner invites a domain expert (e.g., an accountant) by email. The expert clicks the link, verifies their email, and enters a clean chat interface. The agent greets them like a documentary filmmaker, not a survey administrator: *"I don't have a list of questions — I just want to hear your story. Imagine I'm filming a documentary about how you actually do your work."*

The conversation follows a structured-but-invisible methodology:

1. **Their World** — Open context, rapport, vocabulary calibration. "Tell me about your practice."
2. **Struggling Moments** — The agent asks for a specific, concrete recent event: "Think about the last time something in your workflow really frustrated you. Walk me through what happened." The agent anchors to sensory detail (time, place, who was there) to trigger episodic memory, not rationalised narrative.
3. **Solution Redirection** — When the expert describes a solution ("I need a tool that does X"), the agent acknowledges then systematically unwinds: "Before you started looking for a tool, what was breaking down? What happened specifically?"
4. **Job Map Walkthrough** — Systematically covers Define → Locate → Prepare → Confirm → Execute → Monitor → Modify → Conclude for each identified workflow, extracting desired outcome statements at each step.
5. **Outcome Harvesting** — The agent reads back structured JTBD outcome statements ("Minimize the time it takes to identify which transactions need manual review") and seeks the "That's right" signal.
6. **Four Forces** — For any switching event: Push (what's broken), Pull (what's attractive), Anxiety (what's scary about changing), Habit (what's comfortable about the status quo).

The agent uses a dual-process architecture: System 1 (fast, reactive) maintains natural conversation flow; System 2 (deliberative) decides what to explore next based on the coverage map, detects solution-language, and triggers extraction.

**Why this priority**: Without the conversation engine, nothing else exists.

**Independent Test**: Invite a test expert, complete auth, have a 20-minute conversation, verify the agent reconstructed at least one specific past event, redirected at least one solution-statement to a problem-statement, and produced at least 3 JTBD outcome statements.

**Acceptance Scenarios**:

1. **Given** a product owner has configured a project, **When** they enter an expert's email, **Then** the expert receives a branded invitation email with a one-click access link.
2. **Given** the expert enters the chat, **When** the agent greets them, **Then** the greeting frames the session as collaborative storytelling, not interrogation, and asks about their world before any problem discussion.
3. **Given** the expert describes a past event, **When** the agent probes, **Then** it asks for sensory details (time, place, who was there) to anchor the memory and avoid rationalised generalities.
4. **Given** the expert says "I need a tool that does X," **When** the agent responds, **Then** it acknowledges the idea then redirects: "What's the situation that makes you want that? Walk me through the last time."
5. **Given** the expert describes a workflow, **When** the agent has sufficient detail, **Then** it reads back JTBD outcome statements in the format "Minimize/Increase [metric] of [object] when [context]" and seeks explicit confirmation.
6. **Given** the expert uses vague language ("it's annoying," "it takes too long"), **When** the agent responds, **Then** it unpacks the adjective: "'Too long' compared to what? Which specific part?"

---

### User Story 2 — Visual Confirmation of Understanding (Priority: P2)

As the conversation progresses and the agent forms a structured understanding, it renders visual confirmations inline in the chat. A picture speaks 1000 words — instead of reading back a text summary, the agent shows the expert a visual representation of what it understood and asks them to confirm.

Each visual has three response options: **Agree** (high-confidence data point), **Not Quite** (opens inline editor — the modification is the most valuable insight), **Wrong** (agent re-explores).

Visual confirmation types:
- **Workflow diagram** — Process steps as a visual flow. Appears after job map walkthrough.
- **Four Forces quadrant** — Push/Pull/Anxiety/Habit mapped visually. Appears after forces discussion.
- **Pain severity map** — Ranked pain points with magnitude bars. Appears after multiple pain points surfaced.
- **Outcome statement cards** — Individual JTBD outcomes as confirmable cards. Appears during outcome harvesting.
- **Data flow diagram** — How information moves through their process. Appears when data formats discussed.
- **Timeline reconstruction** — Switch interview events on a visual timeline. Appears after timeline reconstruction.

Each confirmed/modified/rejected visual is a structured data point that compounds across interviewees. When the admin views the aggregated workflow, they see: "7/10 experts agreed with this flow, 2 modified step 3, 1 said it was wrong."

**Why this priority**: Visual confirmation produces higher-accuracy data than verbal confirmation. Modifications to visuals reveal precisely where understanding was wrong — each edit is more valuable than 10 minutes of conversation.

**Independent Test**: Have a conversation about a 5-step workflow, verify the agent renders a workflow diagram, modify step 3, verify the modification is captured as a structured data point.

**Acceptance Scenarios**:

1. **Given** the agent has extracted 4+ process steps for a workflow, **When** it presents a summary, **Then** it renders a visual workflow diagram with Agree/Not Quite/Wrong options.
2. **Given** the expert clicks "Not Quite" on a workflow diagram, **When** the editor opens, **Then** they can drag to reorder steps, edit step names, add missing steps, or remove incorrect ones.
3. **Given** the expert clicks "Agree" on a visual, **Then** the data is recorded with high confidence and linked to the expert's confirmation.
4. **Given** the expert clicks "Wrong," **Then** the agent acknowledges and asks what's off, re-entering the exploration phase for that topic.
5. **Given** pain points have been discussed, **When** a pain severity map appears, **Then** the expert can drag to reorder priorities and the final ranking is captured.
6. **Given** the agent reads back JTBD outcome statements, **When** they appear as individual cards, **Then** each card can be independently confirmed, edited, or rejected.

---

### User Story 3 — Multi-Session Continuity (Priority: P3)

Discovery conversations span days or weeks across multiple sessions. The system maintains a "living discovery state" — a structured summary of everything captured, organised by workflow. The agent reads this at session start and computes a diff since the last session, including any cross-interview insights from other experts.

On return, the agent greets with specific context: *"Last time you mentioned a reconciliation spreadsheet you give clients — did you get a chance to dig that up? Also, since we spoke, another accountant described a similar workflow but skips step 3 entirely. I'd love to understand why you include it."*

**Why this priority**: Without continuity, multi-session interviews are impossible and experts must repeat themselves.

**Independent Test**: Complete session 1 about a topic, return in session 2, verify agent references 2+ specific details from session 1 and identifies at least one gap to explore.

**Acceptance Scenarios**:

1. **Given** session 1 covered data inputs for a workflow, **When** the expert returns in session 2, **Then** the agent's greeting references specific data formats mentioned and identifies the next coverage gap.
2. **Given** the expert promised to upload a file, **When** they return, **Then** the agent follows up on that commitment.
3. **Given** another expert described the same workflow between sessions, **When** the returning expert starts session 2, **Then** the agent surfaces relevant cross-interview insights as natural conversation hooks.
4. **Given** 30+ days of inactivity, **When** the expert returns, **Then** the agent provides a fuller recap before continuing.

---

### User Story 4 — Artifact Collection via Dynamic UI (Priority: P4)

During conversation, the agent surfaces interactive components inline when concrete artifacts would be more valuable than words. File uploads when data formats are discussed, workflow builders for process confirmation, schema previews when files are uploaded.

**Why this priority**: Artifacts (sample files, templates) turn vague descriptions into implementable specifications.

**Independent Test**: Mention "we receive CSVs" in conversation, verify file upload component appears inline, upload a file, verify the agent previews its structure.

**Acceptance Scenarios**:

1. **Given** the expert mentions a data format, **When** the agent responds, **Then** a file upload component appears inline.
2. **Given** a CSV is uploaded, **When** processing completes, **Then** the agent shows a schema preview (column headers, sample rows) and asks clarifying questions.
3. **Given** the expert describes process steps, **When** the agent has enough detail, **Then** a visual workflow builder appears for confirmation (same as User Story 2 workflow diagram).
4. **Given** a file upload fails, **Then** the agent acknowledges and offers to retry or continue without it.

---

### User Story 5 — Project Configuration and Admin Dashboard (Priority: P5)

Product owners configure their project with domain-specific settings: terminology, extraction dimensions, agent persona. The admin dashboard shows all contacts, sessions, completion status, and aggregated insights across interviewees.

**Why this priority**: Insights are only valuable if accessible, aggregated, and domain-appropriate.

**Independent Test**: Configure a project for "accounting" domain, conduct sessions with two experts about the same workflow, verify the admin dashboard shows aggregated data with per-expert confirmation counts.

**Acceptance Scenarios**:

1. **Given** a product owner creates a project, **When** they configure domain settings, **Then** the agent uses the specified terminology, extraction dimensions, and persona in all conversations.
2. **Given** sessions with multiple experts, **When** the admin views the dashboard, **Then** they see contacts with session count, last active date, and overall completeness.
3. **Given** two experts discussed the same workflow, **When** the admin views that workflow, **Then** they see an aggregated specification with per-data-point confirmation counts and divergences highlighted.
4. **Given** the admin views the coverage matrix, **Then** they see topics (rows) vs experts (columns) with complete/partial/not-started indicators.

---

### User Story 6 — Cross-Expert Aggregation and Spec Export (Priority: P6)

The system recognises when different experts describe the same underlying pattern using different terminology. It produces aggregated specifications per workflow type and exports them as structured documents that can feed directly into a project's planning process.

**Why this priority**: This is the strategic payoff — market-level pattern recognition, not just one expert's view. Only valuable after 3+ experts.

**Independent Test**: Three experts describe variations of the same workflow, verify the system links them, produces an aggregated spec with frequency counts, and exports a structured document.

**Acceptance Scenarios**:

1. **Given** two experts describe similar workflows with different terminology, **When** semantic analysis runs, **Then** the system suggests linking them (with admin confirmation, never auto-merge).
2. **Given** 3+ experts contributed to a workflow, **When** the admin views the aggregation, **Then** each data point shows confirmation count, confidence score, and any divergences.
3. **Given** the admin requests a spec export, **When** it generates, **Then** the output is a structured document (Markdown/JSON) with: JTBD outcome statements, workflow steps, pain points (ranked by frequency), data format inventory, volume estimates, and source attribution.
4. **Given** a consuming project (e.g., Clairo) has a webhook configured, **When** a workflow reaches completeness threshold, **Then** the service pushes a notification with the structured spec.

---

### Edge Cases

- What happens when an expert uses only solution-language for an extended period? The agent acknowledges each solution but persists in redirecting to problems. After 3 consecutive redirects without progress, it explicitly names the pattern: "I notice you have a really clear picture of what the solution should look like. That's valuable. Can we spend a few minutes on what life looks like today *without* that solution?"
- What happens when an expert contradicts themselves across sessions? The agent surfaces it naturally: "Last time you mentioned step 3 comes before step 4, but today it sounds like the order is reversed. Help me understand — does it depend on the situation?"
- What happens when the expert is a poor storyteller and only gives short answers? The agent switches to more specific probes: "Let me ask about something concrete — what did you do yesterday morning when you sat down at your desk?"
- What happens when sensitive personal data is shared? The agent reminds them not to share real client data and the system flags the message for review.
- What happens when a visual confirmation is ignored (no response)? The agent gently circles back: "I showed a workflow diagram earlier — would you mind taking a quick look to see if I got it right?"
- What happens when the domain config is minimal? The agent operates in a domain-agnostic mode, using generic JTBD methodology without domain-specific terminology.

## Requirements *(mandatory)*

### Functional Requirements

**Platform & Multi-Tenancy**

- **FR-001**: System MUST operate as a standalone service with its own authentication, database, and UI — independent of any consuming project.
- **FR-002**: System MUST support multiple projects, each with its own domain configuration, contacts, and data isolation.
- **FR-003**: Product owners MUST be able to configure per-project: domain name, terminology glossary, extraction dimensions, agent persona description, and completeness thresholds.
- **FR-004**: System MUST expose an integration API for consuming projects to query insights, download artifacts, and receive webhook notifications.

**Authentication & Access**

- **FR-005**: System MUST provide passwordless email-based authentication for interviewees (one-time verification code, valid for 10 minutes).
- **FR-006**: System MUST allow authenticated interviewees to access the chat from any browser or device using only their email.
- **FR-007**: System MUST maintain sessions that persist across page refreshes (7-day duration, renewable).
- **FR-008**: Product owners MUST be able to invite interviewees by email, with a branded invitation.

**Interview Methodology — Conversation Engine**

- **FR-009**: The agent MUST open conversations with a framing that establishes collaborative storytelling, not interrogation. It MUST ask about the expert's world before any problem discussion.
- **FR-010**: The agent MUST anchor discussions to specific, concrete past events. When the expert uses generalities ("usually," "always," "would"), the agent MUST redirect to a specific recent instance.
- **FR-011**: When the expert describes a solution, the agent MUST acknowledge it then redirect to the underlying problem using one of: "Before the tool" redirect, "What are you trying to accomplish?" redirect, "Imagine it doesn't exist" redirect, or "Walk me through the last time" redirect. Solution-talk MUST NOT persist for more than one exchange without redirection.
- **FR-012**: The agent MUST use sensory detail probes (time, place, who was present, what device) to trigger episodic memory and anchor the conversation in real recall.
- **FR-013**: The agent MUST unpack vague adjectives. When the expert says "faster," "better," "easier," or "annoying," the agent MUST probe: "Compared to what? Which specific part?"
- **FR-014**: The agent MUST systematically walk through the Universal Job Map (Define, Locate, Prepare, Confirm, Execute, Monitor, Modify, Conclude) for each identified workflow, extracting desired outcome statements at each step.
- **FR-015**: The agent MUST produce JTBD outcome statements in the format: "[Direction: Minimize/Increase] the [metric] of [object of control] when [contextual clarifier]."
- **FR-016**: The agent MUST never ask "Why?" directly. It MUST use event-form alternatives: "What happened?", "How come?", "What led to that?", "Tell me more about that."
- **FR-017**: The agent MUST never ask hypothetical questions ("Would you use X?"). All questions MUST reference past behaviour or current reality.
- **FR-018**: The agent MUST never ask leading or yes/no questions. Every question MUST invite a narrative response.
- **FR-019**: The agent MUST use reflective listening: mirroring (repeat last key phrase as a question), labeling ("It sounds like..."), paraphrasing, and summarising. It MUST seek the "That's right" confirmation signal before recording insights.
- **FR-020**: The agent MUST occasionally use amplified reflection (slight exaggeration) to test the boundary of a problem. The expert's correction reveals the precise magnitude.
- **FR-021**: The agent MUST use a dual-process architecture: System 1 (reactive) maintains conversation flow; System 2 (deliberative) steers based on the coverage map, detects solution-language, and triggers extraction/visualisation.

**Visual Confirmation**

- **FR-022**: The agent MUST render visual confirmations inline in the chat when it has formed a structured understanding of a topic. Visuals MUST include Agree / Not Quite / Wrong response options.
- **FR-023**: System MUST support these visual confirmation types: workflow diagram, four forces quadrant, pain severity map, outcome statement cards, data flow diagram, timeline reconstruction.
- **FR-024**: When the expert clicks "Not Quite," the system MUST open an inline editor appropriate to the visual type (drag-reorder for workflows, text edit for outcomes, add/remove for pain points).
- **FR-025**: Every Agree/Not Quite/Wrong interaction MUST be captured as a structured data point with: visual type, expert ID, timestamp, original content, modified content (if applicable), and confidence level.
- **FR-026**: Visual confirmations MUST compound across experts. The admin view MUST show per-element confirmation counts (e.g., "Step 3: 7 agreed, 2 modified, 1 rejected").

**Multi-Session Continuity**

- **FR-027**: System MUST persist all conversation messages across sessions.
- **FR-028**: System MUST maintain a structured "living discovery state" per interviewee: identified workflows, completeness per workflow, confirmed extractions, open threads, and pending follow-ups.
- **FR-029**: The agent MUST read the discovery state at session start and greet the expert with specific references to prior session details.
- **FR-030**: The agent MUST update the discovery state at session end.
- **FR-031**: System MUST compute a session diff — what changed since the expert's last session, including cross-interview insights — and use this to drive the opening.

**Artifact Collection**

- **FR-032**: The agent MUST render file upload components inline when data formats are discussed.
- **FR-033**: System MUST accept: CSV, XLSX, PDF, images (PNG, JPG), and plain text. Maximum 25MB per file.
- **FR-034**: When a file is uploaded, the agent MUST analyse its structure (column headers, content summary) and present a preview for confirmation before linking to a workflow.
- **FR-035**: All artifacts MUST be linked to session, expert, and workflow.

**Admin & Integration**

- **FR-036**: System MUST provide an admin dashboard with: contact list, session history, per-workflow completeness, coverage matrix, and aggregated insights.
- **FR-037**: System MUST allow admins to manually link or unlink workflow types across experts.
- **FR-038**: System MUST use semantic similarity to suggest workflow type matches across experts.
- **FR-039**: System MUST detect contradictions within and across experts and flag them for review.
- **FR-040**: System MUST produce confidence scores for aggregated data points based on: confirmation count, artifact support, and absence of contradictions.
- **FR-041**: System MUST export structured specifications per workflow type as Markdown or JSON, suitable for feeding into a project's planning process.
- **FR-042**: System MUST support webhook notifications to consuming projects when: a workflow reaches a completeness threshold, a new contradiction is detected, or a new artifact is uploaded.

**Interview Anti-Patterns (Negative Requirements)**

- **FR-043**: The agent MUST NOT accept "I like it" or "It's fine" as answers. It MUST probe deeper.
- **FR-044**: The agent MUST NOT project its own hypothesis. It MUST say "It sounds like the struggle is Y" not "I think you need X."
- **FR-045**: The agent MUST NOT fill silence. After a question, it MUST wait for the expert's response before continuing.
- **FR-046**: The agent MUST NOT stack multiple questions in a single message. One question at a time.

### Key Entities

- **Project**: A configured domain instance (e.g., "Clairo — Accounting Discovery"). Has domain settings, terminology, extraction dimensions, and admin users.
- **Interviewee (Contact)**: A domain expert being interviewed. Identified by email. Belongs to a project. Lightweight identity with name, role, organisation, and practice size.
- **Session**: A single conversation sitting. Has start/end times, message count, and AI-generated summary. Belongs to one interviewee.
- **Message**: An individual message in a session. Includes content, role, timestamp, optional visual confirmation payload, and optional A2UI component.
- **Discovery State**: Living structured summary per interviewee. Organised by workflow. Updated at session end. Read at session start.
- **Workflow**: A type of domain workflow identified during conversations. Shared across interviewees. Has name, description, embedding for semantic matching, and completeness tracking.
- **Contribution**: Join entity linking interviewees to workflows (many-to-many).
- **Extraction**: Atomic unit of insight from conversation. Has: type (outcome_statement, workflow_step, pain_point, tool_mention, volume_estimate, data_format, edge_case), content, confidence, expert feedback (accepted/modified/rejected), and source message link.
- **Visual Confirmation**: A record of each visual presented to an expert with their response (agree/not_quite/wrong), the original content, and any modifications.
- **Artifact**: File uploaded during a session. Linked to session, interviewee, and workflow. Has filename, type, size, storage reference, and AI analysis result.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: Passwordless email verification for interviewees.
- [ ] **Data Access Events**: Conversations do not access sensitive data. Interviewees are reminded not to share PII.
- [x] **Data Modification Events**: Creation of contacts, sessions, messages, workflows, extractions, visual confirmations, artifacts, and state updates.
- [x] **Integration Events**: Webhook notifications to consuming projects. API queries from consuming projects.
- [ ] **Compliance Events**: No regulatory compliance changes.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|---|---|---|---|---|
| discovery.contact.created | Admin invites an expert | Email, project, timestamp | 3 years | Email (PII) |
| discovery.contact.authenticated | Expert verifies email | Contact ID, IP, user agent | 3 years | IP address |
| discovery.session.started | Expert opens a new session | Contact ID, session ID | 3 years | None |
| discovery.session.ended | Expert leaves / idle timeout | Session ID, duration, message count | 3 years | None |
| discovery.visual.confirmed | Expert responds to visual | Visual type, response, modifications | 3 years | None |
| discovery.artifact.uploaded | Expert uploads a file | Artifact ID, filename, type, size | 3 years | File may contain PII |
| discovery.state.updated | Agent updates living state | Contact ID, workflows affected, delta | 3 years | None |
| discovery.webhook.sent | Notification sent to project | Project ID, event type, payload summary | 3 years | None |

### Compliance Considerations

- **Data Retention**: 3 years for discovery data. Not subject to industry-specific retention (this is product research, not regulated data).
- **PII Handling**: If interviewees inadvertently share client PII, the system flags the message for review and the agent reminds them to use anonymised examples.
- **Access Control**: Project admins see only their project's data. Platform admins see all.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An expert goes from invitation email to first conversation in under 3 minutes.
- **SC-002**: The agent successfully redirects solution-language to problem-language in 80%+ of instances (measured by: expert provides a past-behaviour response after redirect).
- **SC-003**: The agent captures at least 5 JTBD outcome statements per workflow, each confirmed by the expert via visual confirmation.
- **SC-004**: A complete workflow specification (all extraction dimensions covered) is captured within 2-3 sessions.
- **SC-005**: When an expert returns after a break, the agent references at least 2 specific details from prior sessions.
- **SC-006**: At least 1 artifact is collected per workflow type on average.
- **SC-007**: Visual confirmation interactions (Agree/Not Quite/Wrong) are completed for 80%+ of rendered visuals (not ignored).
- **SC-008**: "Not Quite" modifications produce at least 1 novel insight per session that was not captured in conversation text.
- **SC-009**: After 3+ experts discuss the same workflow, the aggregated specification is detailed enough to draft a product feature spec without follow-up interviews.
- **SC-010**: The service can be configured for a new domain (different terminology, extraction dimensions) and produce a working interview agent within 1 hour of configuration.

## Assumptions

- The first interviewee (an accountant) has already expressed interest and will be guided through the process by Suren initially.
- Interviewees are domain experts — they have deep practical knowledge but may not be able to articulate it well without structured probing.
- The service requires an LLM API (Claude or equivalent) for the conversation engine and extraction.
- File storage uses S3-compatible object storage (MinIO or cloud S3).
- Email sending uses a transactional email service (Resend or equivalent).
- The number of concurrent interviewees will be small (<50) in the near term.
- Consuming projects integrate via REST API and webhooks — no direct database coupling.

## Design Influences

This specification was informed by:
- **Bob Moesta's Switch Interview** — timeline reconstruction, four forces of progress, sensory detail probing
- **The Mom Test (Rob Fitzpatrick)** — past behaviour only, no hypotheticals, emotion mining, fluff detection
- **Motivational Interviewing (OARS)** — open questions, affirmations, reflections, summaries
- **Tony Ulwick's Outcome-Driven Innovation** — Universal Job Map, desired outcome statement format
- **Chris Voss's reflective listening** — mirroring, labeling, "That's right" signal, amplified reflection
- **Teresa Torres' Opportunity Solution Trees** — solution-to-problem inversion techniques
- **EzyLegal feature proposals** — skill-based architecture, accept/modify/reject feedback loop, cross-case intelligence, coverage matrix
- **PageIndex** — reasoning-based navigation of structured knowledge (applied to discovery state navigation)
- **LLMREI academic research** — finding that less guidance produces better discovery in AI-led interviews
