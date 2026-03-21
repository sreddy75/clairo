"""Pydantic schemas for client-context chat API.

Defines request/response models for the client chat endpoints.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Client Search
# =============================================================================


class ClientSearchResult(BaseModel):
    """A client search result."""

    id: UUID
    name: str
    abn: str | None = None
    connection_id: UUID
    organization_name: str | None = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class ClientSearchResponse(BaseModel):
    """Response for client search endpoint."""

    results: list[ClientSearchResult]
    total: int
    query: str


# =============================================================================
# Client Profile
# =============================================================================


class ClientProfileData(BaseModel):
    """Client profile data for display."""

    id: UUID
    name: str
    abn: str | None = None
    entity_type: str | None = None
    industry_code: str | None = None
    gst_registered: bool = False
    revenue_bracket: str | None = None
    employee_count: int = 0


class ConnectionStatus(BaseModel):
    """Xero connection status."""

    status: str
    organization_name: str | None = None
    last_sync: str | None = None
    needs_reauth: bool = False


class ClientProfileResponse(BaseModel):
    """Response for client profile endpoint."""

    profile: ClientProfileData
    connection: ConnectionStatus
    data_freshness: str | None = None
    is_stale: bool = False


# =============================================================================
# Client Chat
# =============================================================================


class ChatMessage(BaseModel):
    """A chat message in conversation history."""

    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")


class ClientChatRequest(BaseModel):
    """Request for client-context chat."""

    client_id: UUID = Field(description="The client ID to provide context for")
    query: str = Field(min_length=1, max_length=4000, description="The user's question")
    conversation_history: list[ChatMessage] | None = Field(
        default=None, description="Previous messages in the conversation"
    )
    collections: list[str] | None = Field(
        default=None, description="Knowledge base collections to search (defaults to all)"
    )


class ClientChatRequestWithConversation(ClientChatRequest):
    """Chat request with optional conversation ID for persistence."""

    conversation_id: UUID | None = Field(
        default=None, description="Existing conversation ID to continue"
    )


# =============================================================================
# Citations
# =============================================================================


class ClientChatCitation(BaseModel):
    """A citation from the knowledge base."""

    number: int
    title: str | None = None
    url: str
    source_type: str
    effective_date: str | None = None
    text_preview: str
    score: float


# =============================================================================
# Chat Response Metadata
# =============================================================================


class ClientChatMetadata(BaseModel):
    """Metadata about a client-context chat response."""

    client_id: UUID
    client_name: str
    query_intent: str = Field(
        description="Detected query intent: tax_deductions, cash_flow, gst_bas, compliance, general"
    )
    context_token_count: int = Field(description="Tokens used for client context")
    rag_token_count: int = Field(description="Tokens used for RAG context")
    data_freshness: str | None = Field(description="ISO timestamp of last data sync")
    is_stale: bool = Field(description="True if data is older than 24 hours")


class ClientChatResponse(BaseModel):
    """Non-streaming chat response."""

    response: str
    citations: list[ClientChatCitation]
    metadata: ClientChatMetadata
    query: str


# =============================================================================
# SSE Event Types
# =============================================================================


class ClientChatStreamEvent(BaseModel):
    """SSE event for streaming chat response.

    Event types:
    - 'text': Partial response text
    - 'done': Final event with metadata and citations
    - 'error': Error event
    """

    type: str = Field(description="Event type: text, done, or error")
    content: str | None = Field(default=None, description="Text content for 'text' events")
    citations: list[ClientChatCitation] | None = Field(
        default=None, description="Citations for 'done' events"
    )
    metadata: ClientChatMetadata | None = Field(
        default=None, description="Response metadata for 'done' events"
    )
    query: str | None = Field(default=None, description="Original query for 'done' events")
    conversation_id: UUID | None = Field(
        default=None, description="Conversation ID for persistent chat"
    )
    message: str | None = Field(default=None, description="Error message for 'error' events")


# =============================================================================
# Error Response
# =============================================================================


class ClientChatError(BaseModel):
    """Error response for client chat endpoints."""

    error: str
    code: str
    details: dict | None = None
