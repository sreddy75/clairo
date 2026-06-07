"""Sync committed YAML strategy files → database rows (Spec 060 Phase 2 workflow).

`backend/app/modules/tax_strategies/data/strategies/*.yaml` is the source of
truth. Each environment (local / prod) runs the same sync against its own
Postgres. Pinecone holds vectors once — local writes them during the one-off
bulk bootstrap; prod re-uses them via the idempotent publish path (see
`tasks/tax_strategy_authoring.py::_execute_publish`).

Flow per YAML file:
    1. Parse YAML.
    2. Compute `content_signature` — a stable hash covering every field
       that ends up in chunks or Pinecone metadata. Used to detect drift.
    3. Look up the live (non-superseded) TaxStrategy row by strategy_id.
    4. No row → create + status=approved.
       Row with matching signature → no-op (or bootstrap publish, see below).
       Row with different signature → update in place (same version).
    5. Return a SyncDecision describing what happened so callers can batch
       publish dispatches afterwards.

Versioning is opt-in: a YAML with an explicit `version: N` key that differs
from the DB's live version triggers a new-version row + supersession. The
default (no `version` key) is update-in-place at v1.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.modules.tax_strategies import audit_events as events
from app.modules.tax_strategies.models import TaxStrategy
from app.modules.tax_strategies.repository import TaxStrategyRepository
from app.modules.tax_strategies.schemas import ALLOWED_CATEGORIES

logger = logging.getLogger(__name__)


DEFAULT_STRATEGIES_DIR = Path(__file__).parent / "data" / "strategies"


# Keys from the YAML file that contribute to the retrieval representation
# (chunk text + Pinecone metadata). Changes to any of these invalidate the
# vectors and trigger re-embed during publish.
_CONTENT_SIGNATURE_KEYS: tuple[str, ...] = (
    "name",
    "categories",
    "implementation_text",
    "explanation_text",
    "ato_sources",
    "case_refs",
    "entity_types",
    "income_band_min",
    "income_band_max",
    "turnover_band_min",
    "turnover_band_max",
    "age_min",
    "age_max",
    "industry_triggers",
    "financial_impact_type",
    "keywords",
)


@dataclass(frozen=True)
class SyncDecision:
    """Per-strategy outcome of a sync run."""

    strategy_id: str
    action: str  # "created" | "updated" | "unchanged" | "invalid" | "version_bump"
    needs_publish: bool
    reason: str = ""


@dataclass(frozen=True)
class SyncSummary:
    """Aggregate result of syncing a directory of YAMLs."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    invalid: int = 0
    version_bumps: int = 0
    decisions: tuple[SyncDecision, ...] = ()

    @property
    def needs_publish_ids(self) -> list[str]:
        return [d.strategy_id for d in self.decisions if d.needs_publish]


# ----------------------------------------------------------------------
# YAML loading + signature
# ----------------------------------------------------------------------


class YamlValidationError(ValueError):
    """Raised when a YAML file doesn't satisfy the minimal required shape."""


def load_yaml(path: Path) -> dict[str, Any]:
    """Parse + validate a single strategy YAML. Raises YamlValidationError."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise YamlValidationError(f"{path.name}: invalid YAML — {e}") from e
    if not isinstance(raw, dict):
        raise YamlValidationError(
            f"{path.name}: top-level must be a mapping, got {type(raw).__name__}"
        )

    strategy_id = raw.get("strategy_id")
    if not isinstance(strategy_id, str) or not strategy_id.startswith("CLR-"):
        raise YamlValidationError(f"{path.name}: missing or invalid strategy_id")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise YamlValidationError(f"{path.name}: missing or empty name")
    categories = raw.get("categories") or []
    if not isinstance(categories, list) or not categories:
        raise YamlValidationError(f"{path.name}: at least one category required")
    for c in categories:
        if c not in ALLOWED_CATEGORIES:
            raise YamlValidationError(
                f"{path.name}: unknown category {c!r}; must be one of {sorted(ALLOWED_CATEGORIES)}"
            )

    # Normalise defaults so downstream code doesn't need to handle None
    # vs missing key.
    defaults: dict[str, Any] = {
        "source_ref": None,
        "tenant_id": "platform",
        "version": 1,
        "implementation_text": "",
        "explanation_text": "",
        "ato_sources": [],
        "case_refs": [],
        "entity_types": [],
        "income_band_min": None,
        "income_band_max": None,
        "turnover_band_min": None,
        "turnover_band_max": None,
        "age_min": None,
        "age_max": None,
        "industry_triggers": [],
        "financial_impact_type": [],
        "keywords": [],
    }
    for k, v in defaults.items():
        raw.setdefault(k, v)
    return raw


def compute_content_signature(payload: dict[str, Any]) -> str:
    """Stable sha256 over the fields that drive chunks + Pinecone metadata.

    Operates identically on YAML dicts and model-derived dicts so the same
    function can compare either side.
    """
    projected = {k: payload.get(k) for k in _CONTENT_SIGNATURE_KEYS}
    # Stable JSON encode — lists kept in-order (they carry semantics for
    # categories / keywords), scalars preserved as-is.
    canonical = json.dumps(projected, sort_keys=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def strategy_to_payload(strategy: TaxStrategy) -> dict[str, Any]:
    """Project a TaxStrategy row into the same shape as the YAML payload.

    Used by `compute_content_signature` to hash both sides identically.
    """
    return {
        "name": strategy.name,
        "categories": list(strategy.categories),
        "implementation_text": strategy.implementation_text,
        "explanation_text": strategy.explanation_text,
        "ato_sources": list(strategy.ato_sources),
        "case_refs": list(strategy.case_refs),
        "entity_types": list(strategy.entity_types),
        "income_band_min": strategy.income_band_min,
        "income_band_max": strategy.income_band_max,
        "turnover_band_min": strategy.turnover_band_min,
        "turnover_band_max": strategy.turnover_band_max,
        "age_min": strategy.age_min,
        "age_max": strategy.age_max,
        "industry_triggers": list(strategy.industry_triggers),
        "financial_impact_type": list(strategy.financial_impact_type),
        "keywords": list(strategy.keywords),
    }


# ----------------------------------------------------------------------
# Sync engine
# ----------------------------------------------------------------------


async def sync_one(
    session: AsyncSession,
    yaml_path: Path,
    *,
    actor: str = "system:sync",
) -> SyncDecision:
    """Sync a single YAML file into the database.

    Returns a SyncDecision describing the action taken and whether the
    caller should enqueue a publish task.
    """
    try:
        payload = load_yaml(yaml_path)
    except YamlValidationError as exc:
        logger.warning("skip %s: %s", yaml_path.name, exc)
        return SyncDecision(
            strategy_id=yaml_path.stem,
            action="invalid",
            needs_publish=False,
            reason=str(exc),
        )

    repo = TaxStrategyRepository(session)
    audit = AuditService(session)
    strategy_id = payload["strategy_id"]
    yaml_sig = compute_content_signature(payload)
    yaml_version = int(payload.get("version") or 1)

    existing = await repo.get_live_version(strategy_id)

    if existing is None:
        # Create fresh row, status=approved (these have been human-curated
        # via the PDF catalogue; they're not LLM drafts). Skips the normal
        # research→draft→enrich pipeline — this is a bulk-import bypass,
        # documented in the seeder module.
        created = await repo.create(
            {
                "strategy_id": strategy_id,
                "source_ref": payload.get("source_ref"),
                "tenant_id": payload.get("tenant_id", "platform"),
                "name": payload["name"],
                "categories": list(payload["categories"]),
                "implementation_text": payload["implementation_text"],
                "explanation_text": payload["explanation_text"],
                "ato_sources": list(payload["ato_sources"]),
                "case_refs": list(payload["case_refs"]),
                "entity_types": list(payload["entity_types"]),
                "income_band_min": payload["income_band_min"],
                "income_band_max": payload["income_band_max"],
                "turnover_band_min": payload["turnover_band_min"],
                "turnover_band_max": payload["turnover_band_max"],
                "age_min": payload["age_min"],
                "age_max": payload["age_max"],
                "industry_triggers": list(payload["industry_triggers"]),
                "financial_impact_type": list(payload["financial_impact_type"]),
                "keywords": list(payload["keywords"]),
                "version": yaml_version,
                "status": "approved",
            }
        )
        await audit.log_event(
            event_type=events.TAX_STRATEGY_CREATED,
            event_category="data",
            actor_type="user",
            resource_type="tax_strategy",
            resource_id=created.id,
            action="create",
            outcome="success",
            metadata={
                "strategy_id": strategy_id,
                "version": yaml_version,
                "source": "sync_from_yaml",
                "content_signature": yaml_sig,
            },
        )
        return SyncDecision(strategy_id=strategy_id, action="created", needs_publish=True)

    if yaml_version > existing.version:
        # Explicit version bump in the YAML — supersede the old row and
        # create the new one. Old vectors stay in Pinecone until cleanup;
        # retrieval filters `is_superseded=true` out.
        existing.superseded_by_strategy_id = strategy_id
        await session.flush()
        created = await repo.create(
            {
                "strategy_id": strategy_id,
                "source_ref": payload.get("source_ref"),
                "tenant_id": payload.get("tenant_id", "platform"),
                "name": payload["name"],
                "categories": list(payload["categories"]),
                "implementation_text": payload["implementation_text"],
                "explanation_text": payload["explanation_text"],
                "ato_sources": list(payload["ato_sources"]),
                "case_refs": list(payload["case_refs"]),
                "entity_types": list(payload["entity_types"]),
                "income_band_min": payload["income_band_min"],
                "income_band_max": payload["income_band_max"],
                "turnover_band_min": payload["turnover_band_min"],
                "turnover_band_max": payload["turnover_band_max"],
                "age_min": payload["age_min"],
                "age_max": payload["age_max"],
                "industry_triggers": list(payload["industry_triggers"]),
                "financial_impact_type": list(payload["financial_impact_type"]),
                "keywords": list(payload["keywords"]),
                "version": yaml_version,
                "status": "approved",
            }
        )
        await audit.log_event(
            event_type=events.TAX_STRATEGY_SUPERSEDED,
            event_category="data",
            actor_type="user",
            resource_type="tax_strategy",
            resource_id=existing.id,
            action="update",
            outcome="success",
            metadata={
                "strategy_id": strategy_id,
                "old_version": existing.version,
                "new_version": yaml_version,
                "source": "sync_from_yaml",
            },
        )
        return SyncDecision(
            strategy_id=strategy_id,
            action="version_bump",
            needs_publish=True,
            reason=f"v{existing.version} → v{yaml_version}",
        )

    # Same version — compare signatures.
    existing_sig = compute_content_signature(strategy_to_payload(existing))
    if existing_sig == yaml_sig:
        # In-sync. Flag needs_publish True anyway on first-run / bootstrap:
        # caller decides whether to publish based on status. A row with
        # status != published needs a publish regardless of drift.
        needs_publish = existing.status != "published"
        return SyncDecision(
            strategy_id=strategy_id,
            action="unchanged",
            needs_publish=needs_publish,
            reason="no content drift; publish required for bootstrap" if needs_publish else "",
        )

    # Drift — update in place.
    existing.name = payload["name"]
    existing.categories = list(payload["categories"])
    existing.implementation_text = payload["implementation_text"]
    existing.explanation_text = payload["explanation_text"]
    existing.ato_sources = list(payload["ato_sources"])
    existing.case_refs = list(payload["case_refs"])
    existing.entity_types = list(payload["entity_types"])
    existing.income_band_min = payload["income_band_min"]
    existing.income_band_max = payload["income_band_max"]
    existing.turnover_band_min = payload["turnover_band_min"]
    existing.turnover_band_max = payload["turnover_band_max"]
    existing.age_min = payload["age_min"]
    existing.age_max = payload["age_max"]
    existing.industry_triggers = list(payload["industry_triggers"])
    existing.financial_impact_type = list(payload["financial_impact_type"])
    existing.keywords = list(payload["keywords"])
    if payload.get("source_ref") is not None:
        existing.source_ref = payload["source_ref"]
    existing.updated_at = datetime.now(UTC)
    await session.flush()

    await audit.log_event(
        event_type=events.TAX_STRATEGY_STATUS_CHANGED,
        event_category="data",
        actor_type="user",
        resource_type="tax_strategy",
        resource_id=existing.id,
        action="update",
        outcome="success",
        metadata={
            "strategy_id": strategy_id,
            "version": existing.version,
            "source": "sync_from_yaml",
            "old_signature": existing_sig,
            "new_signature": yaml_sig,
        },
    )
    return SyncDecision(
        strategy_id=strategy_id,
        action="updated",
        needs_publish=True,
        reason="content signature changed",
    )


async def sync_all(
    session: AsyncSession,
    strategies_dir: Path | None = None,
    *,
    actor: str = "system:sync",
    strategy_ids: set[str] | None = None,
) -> SyncSummary:
    """Sync every YAML file in the directory.

    `strategy_ids`, when provided, restricts the run to those ids (handy
    for pilot testing). The caller commits the session.
    """
    root = strategies_dir or DEFAULT_STRATEGIES_DIR
    if not root.exists():
        raise FileNotFoundError(f"Strategies directory not found: {root}")

    decisions: list[SyncDecision] = []
    for yaml_path in sorted(root.glob("*.yaml")):
        # Skip audit sidecars that happen to live alongside the real YAMLs.
        if yaml_path.name.endswith(".audit.yaml"):
            continue
        if strategy_ids is not None and yaml_path.stem not in strategy_ids:
            continue
        decisions.append(await sync_one(session, yaml_path, actor=actor))

    counts: dict[str, int] = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "invalid": 0,
        "version_bumps": 0,
    }
    for d in decisions:
        if d.action == "version_bump":
            counts["version_bumps"] += 1
        else:
            counts[d.action] = counts.get(d.action, 0) + 1

    return SyncSummary(
        created=counts["created"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
        invalid=counts["invalid"],
        version_bumps=counts["version_bumps"],
        decisions=tuple(decisions),
    )


# ----------------------------------------------------------------------
# Staleness report — read-only drift detection
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class StalenessEntry:
    strategy_id: str
    reason: str  # "missing_row" | "content_drift" | "version_ahead" | "yaml_missing"


async def compute_staleness_report(
    session: AsyncSession,
    strategies_dir: Path | None = None,
) -> list[StalenessEntry]:
    """Return per-strategy drift report without making any writes.

    Drives the admin UI banner + optional CI check. Three cases:
    - yaml_missing: DB has a row but no YAML exists for it.
    - missing_row: YAML exists but DB has no live row.
    - content_drift: both exist, signatures differ.
    - version_ahead: YAML version > DB version (explicit bump pending).
    """
    root = strategies_dir or DEFAULT_STRATEGIES_DIR
    entries: list[StalenessEntry] = []

    yaml_by_id: dict[str, dict[str, Any]] = {}
    if root.exists():
        for yaml_path in sorted(root.glob("*.yaml")):
            if yaml_path.name.endswith(".audit.yaml"):
                continue
            try:
                payload = load_yaml(yaml_path)
            except YamlValidationError:
                continue
            yaml_by_id[payload["strategy_id"]] = payload

    repo = TaxStrategyRepository(session)
    for strategy_id, payload in yaml_by_id.items():
        existing = await repo.get_live_version(strategy_id)
        if existing is None:
            entries.append(StalenessEntry(strategy_id=strategy_id, reason="missing_row"))
            continue
        yaml_version = int(payload.get("version") or 1)
        if yaml_version > existing.version:
            entries.append(StalenessEntry(strategy_id=strategy_id, reason="version_ahead"))
            continue
        if compute_content_signature(payload) != compute_content_signature(
            strategy_to_payload(existing)
        ):
            entries.append(StalenessEntry(strategy_id=strategy_id, reason="content_drift"))

    # Rows that exist in DB but have no corresponding YAML — potential
    # orphans if someone deleted a YAML without going through the admin
    # supersede/archive flow. Surface these so you can decide manually.
    all_live = await repo.list_with_filters(
        status=None, category=None, tenant_id=None, query=None, offset=0, limit=10_000
    )
    live_rows, _ = all_live
    for row in live_rows:
        if row.strategy_id not in yaml_by_id:
            entries.append(StalenessEntry(strategy_id=row.strategy_id, reason="yaml_missing"))

    return entries
