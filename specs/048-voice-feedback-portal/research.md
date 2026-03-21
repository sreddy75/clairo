# Research: Voice Feedback Portal

**Feature**: 048-voice-feedback-portal
**Date**: 2026-03-16

## Decision 1: Speech-to-Text Provider

**Decision**: OpenAI Whisper API

**Rationale**:
- Industry-leading accuracy for English speech recognition, including Australian accents
- Simple API: upload audio file, receive transcript — no session management or streaming complexity
- Supports all required formats (MP3, M4A, WAV, WebM) natively
- Cost-effective: ~$0.006/minute of audio — a 5-minute memo costs $0.03
- 25MB file size limit aligns exactly with our spec requirement
- Response time typically under 10 seconds for recordings under 3 minutes
- Already a Python SDK available (`openai` package), lightweight integration

**Alternatives considered**:
- **Deepgram**: Faster real-time transcription, but more complex API and higher cost. Better suited for live transcription use cases, not our upload-and-process pattern.
- **Google Cloud Speech-to-Text**: Comparable accuracy but requires GCP credentials and more complex setup. No advantage over Whisper for this use case.
- **AssemblyAI**: Good accuracy and speaker diarization, but overkill — we don't need speaker separation since each memo is one person.
- **Browser Web Speech API**: Free but inconsistent accuracy across browsers, requires online connection, no file upload support. Not reliable enough.

---

## Decision 2: In-Browser Audio Recording

**Decision**: MediaRecorder API (native browser) with WebM/Opus output

**Rationale**:
- Native browser API — no additional library needed
- Supported in all modern browsers (Chrome, Firefox, Safari 14.1+, Edge)
- WebM/Opus is the default output format and is directly supported by Whisper API
- Simple API: `navigator.mediaDevices.getUserMedia()` → `MediaRecorder` → `Blob`
- Audio visualisation (waveform) achievable via `AnalyserNode` from Web Audio API

**Alternatives considered**:
- **RecordRTC**: Library wrapper around MediaRecorder with more features (pause/resume, WAV output). Adds dependency for features we don't need. Can add later if MediaRecorder proves insufficient.
- **Opus Recorder (via WASM)**: Lower-level control but complex setup. Unnecessary.

**Implementation notes**:
- Check `navigator.mediaDevices` availability and fall back to upload-only if missing
- Request `audio/webm;codecs=opus` as preferred MIME type, fall back to `audio/webm`
- Use `AudioContext` + `AnalyserNode` for real-time waveform visualisation during recording
- Store recording as `Blob`, convert to `File` for upload

---

## Decision 3: AI Conversation Architecture

**Decision**: Synchronous Claude API calls with conversation history stored in the database

**Rationale**:
- Non-streaming (synchronous) responses are simpler and sufficient — this is a structured Q&A conversation, not a free-form chat. Users expect a considered response, not streaming tokens.
- Conversation history stored in `feedback_messages` table so conversations can be resumed across sessions (supports the "draft" requirement).
- System prompt switches between PM hat and Engineer hat based on submission type, set at conversation start and consistent throughout.
- Claude is called with the full conversation history on each turn (standard messages array pattern). Given conversations are short (5-10 exchanges), context window is not a concern.
- Uses existing `anthropic.Anthropic` client pattern from the `agents` module.
- Brief generation is a final Claude call with a structured output prompt, requesting the brief in a specific JSON format that maps to the brief template.

**Alternatives considered**:
- **Streaming responses**: Adds frontend complexity (SSE handling, progressive rendering) for marginal UX benefit in a structured Q&A flow. Not worth it for v1.
- **Celery background task**: Unnecessary — Claude API calls complete in 2-5 seconds, well within HTTP request timeout. No need for async task processing.
- **Separate "brief generation" step**: Considered having the conversation and brief generation as separate stages. Decided against — the agent should generate the brief as the natural conclusion of the conversation, seamlessly.

**Implementation notes**:
- System prompt includes the brief template fields so the agent knows what to collect
- Agent tracks which fields are populated and which are missing across the conversation
- Final turn: agent calls Claude with instruction to produce structured JSON brief from the full conversation
- Brief is validated against the template schema before presenting to user
- If user requests revisions to the brief, a new Claude call incorporates revision instructions

---

## Decision 4: Audio File Storage

**Decision**: MinIO (existing S3-compatible storage) with structured key paths

**Rationale**:
- MinIO is already deployed and used by the portal documents module for file uploads
- S3-compatible API means the same `boto3`/`aioboto3` patterns work
- File key structure: `feedback/{tenant_id}/{submission_id}/audio.{ext}`
- Files are internal (not served directly to clients) — accessed via backend API endpoint that enforces auth and tenant isolation

**Alternatives considered**:
- **PostgreSQL BYTEA**: Storing audio blobs in the database. Bad idea for files up to 25MB — bloats the database, complicates backups.
- **Local filesystem**: Not portable across deployments. MinIO is already available.
- **Direct S3**: Possible for production, but MinIO provides local dev parity and we can switch to S3 by changing the endpoint URL.

---

## Decision 5: Kanban Drag-and-Drop Library

**Decision**: @dnd-kit/core + @dnd-kit/sortable

**Rationale**:
- Most popular React drag-and-drop library for kanban-style interfaces
- Built for React from the ground up (not a wrapper around a DOM library)
- Lightweight (~15KB gzipped for core + sortable)
- Accessible by default (keyboard support, screen reader announcements)
- Supports both sortable lists (reordering within columns) and transferable items (moving between columns)
- Active maintenance, wide community adoption
- Works well with shadcn/ui components — no style conflicts

**Alternatives considered**:
- **react-beautiful-dnd**: Deprecated by Atlassian (archived 2024). No longer maintained.
- **react-dnd**: Lower-level API, requires more boilerplate. Better for complex custom drag interactions, overkill for a kanban board.
- **Pragmatic drag and drop** (Atlassian): Successor to react-beautiful-dnd but newer with less community adoption. Good alternative if dnd-kit proves insufficient.
- **Native HTML5 drag-and-drop**: Inconsistent browser behaviour, poor mobile support, no animation. Not suitable.

---

## Decision 6: Conversation Storage Model

**Decision**: Store individual messages in a `feedback_messages` table (normalised) rather than a JSON array on the submission

**Rationale**:
- Enables resuming conversations (query messages by submission_id, ordered by created_at)
- Enables future analytics (e.g., average messages per conversation, common follow-up patterns)
- Consistent with the existing agent conversation pattern in the codebase
- Each message has: `submission_id`, `role` (user/assistant/system), `content`, `content_type` (text/transcript), `created_at`
- Transcript messages are marked with `content_type = "transcript"` to distinguish from typed responses

**Alternatives considered**:
- **JSONB array on submission**: Simpler schema but harder to query, no individual message timestamps, harder to resume conversations.
- **Separate conversation entity**: Overkill — there's exactly one conversation per submission. The `feedback_messages` table directly references the submission.

---

## Decision 7: Brief Format and Storage

**Decision**: Store the structured brief as JSONB on the `feedback_submissions` table, with a separate `brief_markdown` text field for the rendered version

**Rationale**:
- JSONB (`brief_data`) allows structured querying of individual brief fields (e.g., find all submissions with severity "high")
- Text field (`brief_markdown`) stores the pre-rendered markdown for quick display and export — avoids re-rendering from JSON on every view
- Both fields are populated when the user confirms the brief
- Export endpoint simply returns the `brief_markdown` field

**Brief schema (Feature Request mode)**:
```json
{
  "title": "string",
  "user_story": "string",
  "current_behaviour": "string",
  "desired_behaviour": "string",
  "domain_context": "string",
  "frequency": "string",
  "impact": "string",
  "open_questions": ["string"]
}
```

**Brief schema (Bug/Enhancement mode)**:
```json
{
  "title": "string",
  "type": "bug | enhancement | logic_error",
  "observed_behaviour": "string",
  "expected_behaviour": "string",
  "business_rule": "string | null",
  "severity": "low | medium | high | critical",
  "reproduction_context": "string",
  "open_questions": ["string"]
}
```

---

## Decision 8: Access Control Model

**Decision**: Role-based visibility using existing Clerk user roles

**Rationale**:
- **Submitters** (any authenticated user) can create submissions and view/resume their own
- **Team members** (users with `admin` or `super_admin` role within the tenant) can view all submissions, move cards on the kanban, and add comments
- This maps cleanly to existing role checks in the codebase (`get_current_practice_user` returns role info)
- No new role or permission system needed

**Implementation notes**:
- List endpoint accepts `mine_only` query param — defaults to `true` for non-admin users, `false` for admins
- Status update endpoint requires admin role
- Comment creation requires admin role
- Submission creation is open to all authenticated users within the tenant
