"""Deterministic Anthropic SDK double for tax-planning agent tests.

Replaces real Claude calls in unit/integration tests with a scripted responder
keyed by a hash of the input messages. Supports streamed and non-streamed
responses plus tool-use loops.

Usage::

    client = FakeAnthropicClient()
    client.register(
        prompt_signature="explore trust distribution",
        response=ToolUseResponse(tool_name="calculate_tax_position", input=...),
    )
    # Inject via monkeypatch or dependency injection into the agent under test.

Spec 059 task T006 (research.md R11).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextResponse:
    """Represents a plain text response from Claude (stop_reason='end_turn')."""

    text: str
    stop_reason: str = "end_turn"
    usage: dict[str, int] = field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
    )


@dataclass
class ToolUseResponse:
    """Represents a tool_use response from Claude (stop_reason='tool_use')."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str = "toolu_fake_001"
    stop_reason: str = "tool_use"
    text: str = ""
    usage: dict[str, int] = field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
    )


ScriptedResponse = TextResponse | ToolUseResponse


class FakeAnthropicClient:
    """A scripted Anthropic SDK replacement.

    Register responses keyed by a prompt_signature (any substring present in the
    serialised input messages). The first matching signature wins; falls back to
    the default response when no signature matches.
    """

    def __init__(self, default_response: ScriptedResponse | None = None) -> None:
        self._scripts: list[tuple[str, ScriptedResponse | list[ScriptedResponse]]] = []
        self._default = default_response or TextResponse(
            text="(no scripted response — FakeAnthropicClient default)",
        )
        self.call_log: list[dict[str, Any]] = []

    def register(
        self,
        prompt_signature: str,
        response: ScriptedResponse | list[ScriptedResponse],
    ) -> None:
        """Associate a prompt signature substring with a scripted response.

        If `response` is a list, each entry is consumed on successive calls that
        match the signature (useful for multi-turn tool-use loops).
        """
        self._scripts.append((prompt_signature, response))

    # ------------------------------------------------------------------
    # Anthropic SDK-shaped surface
    # ------------------------------------------------------------------

    class _Messages:
        def __init__(self, parent: FakeAnthropicClient) -> None:
            self._parent = parent

        def create(self, **kwargs: Any) -> _FakeResponse:
            return self._parent._handle_call(kwargs)

    @property
    def messages(self) -> _Messages:
        return FakeAnthropicClient._Messages(self)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _handle_call(self, kwargs: dict[str, Any]) -> _FakeResponse:
        serialised = self._serialise(kwargs)
        self.call_log.append(
            {
                "system": kwargs.get("system"),
                "messages": kwargs.get("messages"),
                "tools": kwargs.get("tools"),
                "signature": serialised,
            }
        )
        script = self._resolve(serialised)
        return _FakeResponse(script)

    def _serialise(self, kwargs: dict[str, Any]) -> str:
        parts: list[str] = []
        if system := kwargs.get("system"):
            parts.append(system if isinstance(system, str) else json.dumps(system))
        for message in kwargs.get("messages", []):
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
            else:
                parts.append(json.dumps(content))
        return "\n".join(parts)

    def _resolve(self, serialised: str) -> ScriptedResponse:
        for signature, response in self._scripts:
            if signature in serialised:
                if isinstance(response, list):
                    if not response:
                        continue
                    return response.pop(0)
                return response
        return self._default

    def signature_of(self, text: str) -> str:
        """Stable hash for a serialised prompt, used by callers that want to key on content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class _FakeResponse:
    """Mimics the shape returned by `anthropic.Anthropic().messages.create()`."""

    def __init__(self, script: ScriptedResponse) -> None:
        self.stop_reason = script.stop_reason
        self.usage = type("_Usage", (), script.usage)
        if isinstance(script, TextResponse):
            self.content = [_TextBlock(script.text)]
        else:
            self.content = [
                _ToolUseBlock(
                    name=script.tool_name,
                    input=script.tool_input,
                    tool_use_id=script.tool_use_id,
                ),
            ]
            if script.text:
                self.content.insert(0, _TextBlock(script.text))


@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _ToolUseBlock:
    name: str
    input: dict[str, Any]
    tool_use_id: str
    type: str = "tool_use"

    @property
    def id(self) -> str:  # SDK exposes `.id` on tool-use blocks
        return self.tool_use_id
