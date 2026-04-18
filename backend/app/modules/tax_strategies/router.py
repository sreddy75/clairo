"""API router for the tax_strategies module (Spec 060).

Phase 1 scaffolding — endpoints land in T034..T036.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/tax-strategies", tags=["tax-strategies"])
