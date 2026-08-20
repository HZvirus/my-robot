"""Role-based access control for the knowledge base.

A role maps to a set of scopes; each scope is a physically isolated
ChromaDB collection named hospital_kb__scope. Retrieval only queries the
collections the caller role is allowed to see, so knowledge-base isolation
is enforced at the retrieval layer, never via the LLM prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

# Knowledge-base scopes. Each scope is a separate ChromaDB collection.
KB_SCOPES: tuple[str, ...] = ("public", "nursing", "clinical", "internal")

# Role to visible scopes. This map is a server-side constant; clients cannot
# self-assign elevated roles (see auth_service role-token gating).
ROLE_SCOPES: dict[str, frozenset[str]] = {
    "patient": frozenset({"public"}),
    "nurse": frozenset({"public", "nursing"}),
    "doctor": frozenset({"public", "clinical"}),
    "admin": frozenset({"public", "nursing", "clinical", "internal"}),
}

DEFAULT_ROLE = "patient"


@dataclass(frozen=True)
class Principal:
    """Authenticated caller: stable user id plus knowledge-base role."""

    user_id: str
    role: str


def is_valid_role(role: str) -> bool:
    return role in ROLE_SCOPES


def is_elevated(role: str) -> bool:
    return role != DEFAULT_ROLE


def scopes_for(role: str) -> frozenset[str]:
    """Return the knowledge-base scopes visible to role (empty if unknown)."""
    return ROLE_SCOPES.get(role, frozenset())
