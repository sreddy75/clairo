"""Linear annualisation of year-to-date financials.

Pure helpers consumed by the tax-planning service at ingest. Given year-to-date
income and expense totals and the number of months elapsed in the active FY,
returns projected full-year totals plus metadata. Isolated here so it can be
unit-tested without loading the service stack.

Spec 059 FR-001.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ProjectionMetadata:
    """Record of whether and how annualisation was applied to a financials snapshot.

    Stored under `financials_data["projection_metadata"]` for traceability and
    UI display ("Projected from N months of data").
    """

    applied: bool
    rule: str
    months_elapsed: int
    months_projected: int
    ytd_snapshot: dict[str, Any] = field(default_factory=dict)
    applied_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["applied_at"] = self.applied_at.isoformat()
        return payload


def annualise_linear(
    ytd_totals: dict[str, float | int | Decimal | str | dict[str, Any]],
    months_elapsed: int,
) -> tuple[dict[str, Any], ProjectionMetadata]:
    """Scale year-to-date totals to a projected full financial year.

    Args:
        ytd_totals: Mapping of numeric fields (or nested dicts of numeric fields)
            captured as at `months_elapsed` months into the FY. Non-numeric values
            are copied through unchanged.
        months_elapsed: Months into the FY at the time of capture. Capped at 12;
            floored at 1 to avoid divide-by-zero on day-one plans.

    Returns:
        A tuple `(projected_totals, metadata)` where `projected_totals` mirrors
        the input shape with numeric values scaled to full-year, and `metadata`
        records what was applied and preserves the original YTD snapshot.

    If `months_elapsed >= 12`, no scaling is applied and `metadata.applied` is
    False with `reason="months_elapsed>=12"`.
    """
    if months_elapsed >= 12:
        return (
            _deep_copy_totals(ytd_totals),
            ProjectionMetadata(
                applied=False,
                rule="linear",
                months_elapsed=12,
                months_projected=0,
                ytd_snapshot=_deep_copy_totals(ytd_totals),
                reason="months_elapsed>=12",
            ),
        )

    months = max(1, min(12, months_elapsed))
    factor = Decimal("12") / Decimal(months)
    snapshot = _deep_copy_totals(ytd_totals)
    projected = _scale_totals(ytd_totals, factor)

    metadata = ProjectionMetadata(
        applied=True,
        rule="linear",
        months_elapsed=months,
        months_projected=12 - months,
        ytd_snapshot=snapshot,
    )
    return projected, metadata


def annualise_manual(
    totals: dict[str, float | int | Decimal | str | dict[str, Any]],
) -> tuple[dict[str, Any], ProjectionMetadata]:
    """Treat manually-entered figures as confirmed full-year values.

    Produces metadata indicating no annualisation was applied. Snapshot is the
    same as totals because the accountant has already supplied the final values.
    """
    copy = _deep_copy_totals(totals)
    return (
        copy,
        ProjectionMetadata(
            applied=False,
            rule="linear",
            months_elapsed=12,
            months_projected=0,
            ytd_snapshot=_deep_copy_totals(copy),
            reason="manual_full_year",
        ),
    )


def _scale_totals(
    totals: dict[str, Any],
    factor: Decimal,
) -> dict[str, Any]:
    """Recursively scale numeric leaves by factor, copy non-numerics through."""
    result: dict[str, Any] = {}
    for key, value in totals.items():
        if isinstance(value, dict):
            result[key] = _scale_totals(value, factor)
        elif isinstance(value, (int, float, Decimal)):
            scaled = (Decimal(str(value)) * factor).quantize(Decimal("0.01"))
            result[key] = float(scaled) if not isinstance(value, Decimal) else scaled
        else:
            result[key] = value
    return result


def _deep_copy_totals(totals: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _deep_copy_totals(value) if isinstance(value, dict) else value
        for key, value in totals.items()
    }
