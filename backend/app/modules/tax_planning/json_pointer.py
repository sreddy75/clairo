"""Minimal JSON Pointer (RFC 6901) read/write helpers over nested dict/list
structures.

Used by the scenario provenance flow: source_tags keys are JSON Pointers
addressing into `impact_data` and `assumptions`. The PATCH endpoint flips an
individual field's provenance from `estimated` → `confirmed` and optionally
updates the value at that path.

We implement only the subset we need (dict-key + list-index traversal, plus
RFC 6901 escape sequences `~0` / `~1`) rather than pulling in a dependency.

Spec 059 US2 T033.
"""

from __future__ import annotations

from typing import Any


def _unescape(token: str) -> str:
    """Decode an RFC 6901 reference token.

    `~1` decodes to `/`, `~0` decodes to `~`. Order matters — `~01` must
    decode to `~1`, not `/`.
    """
    return token.replace("~1", "/").replace("~0", "~")


def _parse(pointer: str) -> list[str]:
    """Split a JSON Pointer into its decoded reference tokens.

    Accepts either a canonical pointer (`/a/b/0`) or a convenience dotted
    form (`a.b.0`) — the latter is what the existing source_tags keys use
    (`impact_data.modified_expenses.operating_expenses`).
    """
    if not pointer:
        return []
    if pointer.startswith("/"):
        return [_unescape(t) for t in pointer[1:].split("/")]
    # Dotted form — our own convention. No escapes.
    return pointer.split(".")


def resolve(root: Any, pointer: str) -> Any:
    """Return the value at `pointer`, or raise `KeyError` if the path is
    unreachable. Used for validating the PATCH target is a real leaf before
    writing to it."""
    tokens = _parse(pointer)
    node: Any = root
    for token in tokens:
        if isinstance(node, list):
            try:
                idx = int(token)
            except ValueError as e:
                raise KeyError(f"Expected numeric index at {token!r} in pointer {pointer!r}") from e
            if idx < 0 or idx >= len(node):
                raise KeyError(f"Index {idx} out of range in pointer {pointer!r}")
            node = node[idx]
        elif isinstance(node, dict):
            if token not in node:
                raise KeyError(f"Missing key {token!r} in pointer {pointer!r}")
            node = node[token]
        else:
            raise KeyError(f"Cannot traverse into {type(node).__name__} at pointer {pointer!r}")
    return node


def set_at(root: Any, pointer: str, value: Any) -> Any:
    """Write `value` at `pointer` on a deep-copied root and return the new
    root. The input `root` is left untouched — callers that need mutate-in-place
    semantics can reassign the returned value.

    Raises `KeyError` on an unreachable parent path (we do not create
    intermediate dicts; a provenance confirm is always against an existing
    leaf).
    """
    import copy

    new_root = copy.deepcopy(root)
    tokens = _parse(pointer)
    if not tokens:
        return value
    node: Any = new_root
    for token in tokens[:-1]:
        if isinstance(node, list):
            idx = int(token)
            node = node[idx]
        elif isinstance(node, dict):
            if token not in node:
                raise KeyError(f"Missing key {token!r} in pointer {pointer!r}")
            node = node[token]
        else:
            raise KeyError(f"Cannot traverse into {type(node).__name__} at pointer {pointer!r}")
    last = tokens[-1]
    if isinstance(node, list):
        node[int(last)] = value
    elif isinstance(node, dict):
        node[last] = value
    else:
        raise KeyError(f"Cannot write into {type(node).__name__} at pointer {pointer!r}")
    return new_root
