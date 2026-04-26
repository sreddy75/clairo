"""Unit tests for seed_from_csv (Spec 060 T057, T060)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.tax_strategies.exceptions import SeedValidationError

# Three rows: one with multi-category, one with unknown category (should
# fail), one with malformed id. We write focused CSV fixtures per test.


def _write_csv(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


def _valid_csv_content() -> str:
    return (
        "strategy_id,name,categories,source_ref\n"
        "CLR-012,Concessional super contributions,Recommendations|Investors_retirees,STP-012\n"
        "CLR-241,Change PSI to PSB,Business,STP-241\n"
    )


def test_invalid_strategy_id_raises_seed_validation_error(
    tmp_path: Path,
) -> None:
    """Non CLR-XXX ids must fail the whole run."""
    csv_path = _write_csv(
        tmp_path / "bad_id.csv",
        "strategy_id,name,categories,source_ref\n"
        "CLR-012,Concessional super contributions,Recommendations,STP-012\n"
        "BADCODE,Invalid id row,Business,STP-999\n",
    )
    # We need to only exercise the parser + validator (no session touch).
    # The helper raises SeedValidationError BEFORE hitting the DB when any
    # row fails — we can assert on that without a real session fixture.
    import asyncio

    from app.modules.tax_strategies.service import seed_from_csv

    async def run() -> None:
        class _FakeSession:
            pass

        with pytest.raises(SeedValidationError) as excinfo:
            await seed_from_csv(
                session=_FakeSession(),  # type: ignore[arg-type]
                triggered_by="user_test",
                csv_path=csv_path,
            )
        assert any("BADCODE" in e for e in excinfo.value.errors)

    asyncio.run(run())


def test_unknown_category_raises_seed_validation_error(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "bad_cat.csv",
        "strategy_id,name,categories,source_ref\n"
        "CLR-042,Test strategy,MadeUpCategory|Business,STP-042\n",
    )

    import asyncio

    from app.modules.tax_strategies.service import seed_from_csv

    async def run() -> None:
        class _FakeSession:
            pass

        with pytest.raises(SeedValidationError) as excinfo:
            await seed_from_csv(
                session=_FakeSession(),  # type: ignore[arg-type]
                triggered_by="user_test",
                csv_path=csv_path,
            )
        assert any("MadeUpCategory" in e for e in excinfo.value.errors)

    asyncio.run(run())


def test_duplicate_strategy_id_within_csv_raises(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "dup.csv",
        "strategy_id,name,categories,source_ref\n"
        "CLR-012,Original,Recommendations,STP-012\n"
        "CLR-012,Duplicate in same file,Business,STP-012b\n",
    )

    import asyncio

    from app.modules.tax_strategies.service import seed_from_csv

    async def run() -> None:
        class _FakeSession:
            pass

        with pytest.raises(SeedValidationError) as excinfo:
            await seed_from_csv(
                session=_FakeSession(),  # type: ignore[arg-type]
                triggered_by="user_test",
                csv_path=csv_path,
            )
        assert any("duplicate" in e.lower() for e in excinfo.value.errors)

    asyncio.run(run())


def test_missing_name_raises(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "no_name.csv",
        "strategy_id,name,categories,source_ref\nCLR-555,,Recommendations,STP-555\n",
    )

    import asyncio

    from app.modules.tax_strategies.service import seed_from_csv

    async def run() -> None:
        class _FakeSession:
            pass

        with pytest.raises(SeedValidationError):
            await seed_from_csv(
                session=_FakeSession(),  # type: ignore[arg-type]
                triggered_by="user_test",
                csv_path=csv_path,
            )

    asyncio.run(run())


def test_missing_file_raises_file_not_found() -> None:
    import asyncio

    from app.modules.tax_strategies.service import seed_from_csv

    async def run() -> None:
        class _FakeSession:
            pass

        with pytest.raises(FileNotFoundError):
            await seed_from_csv(
                session=_FakeSession(),  # type: ignore[arg-type]
                triggered_by="user_test",
                csv_path=Path("/nonexistent/path/to/seed.csv"),
            )

    asyncio.run(run())


def test_missing_header_columns_raises(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path / "bad_header.csv",
        "id,title\nCLR-012,Concessional super\n",
    )

    import asyncio

    from app.modules.tax_strategies.service import seed_from_csv

    async def run() -> None:
        class _FakeSession:
            pass

        with pytest.raises(SeedValidationError) as excinfo:
            await seed_from_csv(
                session=_FakeSession(),  # type: ignore[arg-type]
                triggered_by="user_test",
                csv_path=csv_path,
            )
        # Error message mentions the missing columns.
        assert any("missing" in e.lower() or "header" in e.lower() for e in excinfo.value.errors)

    asyncio.run(run())


def test_valid_csv_parses_without_error_up_to_db_access(tmp_path: Path) -> None:
    """A fully valid CSV should pass the parse + validate phase. We can't
    exercise the DB-insert phase without a real session, so this test
    confirms validation alone doesn't raise on good input.
    """
    csv_path = _write_csv(tmp_path / "valid.csv", _valid_csv_content())

    import asyncio

    from app.modules.tax_strategies.service import seed_from_csv

    async def run() -> None:
        class _FakeSession:
            # Parser passes validation cleanly, then tries to hit the DB
            # via TaxStrategyRepository(session). That raises AttributeError
            # on our fake — which proves we got past validation (the rows
            # were considered valid, pre-DB).
            pass

        with pytest.raises(AttributeError):
            await seed_from_csv(
                session=_FakeSession(),  # type: ignore[arg-type]
                triggered_by="user_test",
                csv_path=csv_path,
            )

    asyncio.run(run())
