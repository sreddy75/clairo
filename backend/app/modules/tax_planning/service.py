"""Service layer for Tax Planning module.

Orchestrates Xero data pull, tax calculation, plan CRUD, and AI chat.
"""

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.models import XeroConnection
from app.modules.integrations.xero.service import XeroReportService
from app.modules.tax_planning.exceptions import (
    NoXeroConnectionError,
    TaxPlanExistsError,
    TaxPlanNotFoundError,
    TaxRateConfigNotFoundError,
    TaxScenarioNotFoundError,
    XeroPullError,
)
from app.modules.tax_planning.models import TaxPlan
from app.modules.tax_planning.repository import (
    TaxPlanMessageRepository,
    TaxPlanRepository,
    TaxRateConfigRepository,
    TaxScenarioRepository,
)
from app.modules.tax_planning.schemas import (
    FinancialsInput,
    TaxPlanCreate,
    TaxPlanUpdate,
)
from app.modules.tax_planning.tax_calculator import calculate_tax_position

logger = logging.getLogger(__name__)


class TaxPlanningService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.plan_repo = TaxPlanRepository(session)
        self.scenario_repo = TaxScenarioRepository(session)
        self.message_repo = TaxPlanMessageRepository(session)
        self.rate_repo = TaxRateConfigRepository(session)

    # ------------------------------------------------------------------
    # Plan CRUD
    # ------------------------------------------------------------------

    async def create_plan(self, tenant_id: uuid.UUID, data: TaxPlanCreate) -> TaxPlan:
        """Create a new tax plan. Raises TaxPlanExistsError if one already exists."""
        existing = await self.plan_repo.get_by_client_fy(
            xero_connection_id=data.xero_connection_id,
            financial_year=data.financial_year,
            tenant_id=tenant_id,
        )

        if existing and not data.replace_existing:
            raise TaxPlanExistsError(existing.id)

        if existing and data.replace_existing:
            await self.plan_repo.delete(existing)

        plan = await self.plan_repo.create(
            {
                "tenant_id": tenant_id,
                "xero_connection_id": data.xero_connection_id,
                "financial_year": data.financial_year,
                "entity_type": data.entity_type.value,
                "status": "draft",
                "data_source": data.data_source.value,
            }
        )
        return plan

    async def get_plan(self, plan_id: uuid.UUID, tenant_id: uuid.UUID) -> TaxPlan:
        plan = await self.plan_repo.get_by_id(plan_id, tenant_id)
        if not plan:
            raise TaxPlanNotFoundError(plan_id)
        return plan

    async def is_plan_data_stale(self, plan: TaxPlan) -> bool:
        """Check if a plan's P&L data is stale relative to the last Xero sync.

        Returns True if:
        - Plan is Xero-sourced and active (not finalised)
        - Connection has been synced after the plan's last P&L fetch
        """
        if plan.data_source != "xero" or plan.status == "finalised":
            return False
        if not plan.xero_connection_id:
            return False

        connection = await self.session.get(XeroConnection, plan.xero_connection_id)
        if not connection or not connection.last_full_sync_at:
            return False

        # Don't attempt refresh if Xero connection needs reauthorization
        if connection.status.value != "active":
            return False

        # Don't attempt refresh if token is expired — the Xero API call will
        # fail, trigger a token refresh that corrupts the session. The status
        # field may still say "active" even when the token has expired; the
        # needs_refresh property checks actual token_expires_at.
        if connection.needs_refresh:
            return False

        # No P&L data yet — definitely stale
        if not plan.xero_report_fetched_at:
            return True

        return connection.last_full_sync_at > plan.xero_report_fetched_at

    async def get_plan_for_connection(
        self,
        xero_connection_id: uuid.UUID,
        financial_year: str,
        tenant_id: uuid.UUID,
    ) -> TaxPlan | None:
        return await self.plan_repo.get_by_client_fy(xero_connection_id, financial_year, tenant_id)

    async def list_plans(
        self,
        tenant_id: uuid.UUID,
        status: str | None = None,
        financial_year: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[TaxPlan], int]:
        return await self.plan_repo.list_by_tenant(
            tenant_id, status, financial_year, search, page, page_size
        )

    async def update_plan(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: TaxPlanUpdate,
    ) -> TaxPlan:
        plan = await self.get_plan(plan_id, tenant_id)
        update_data = data.model_dump(exclude_unset=True)
        return await self.plan_repo.update(plan, update_data)

    async def delete_plan(self, plan_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        plan = await self.get_plan(plan_id, tenant_id)
        await self.plan_repo.delete(plan)

    # ------------------------------------------------------------------
    # Financials: Xero pull
    # ------------------------------------------------------------------

    async def pull_xero_financials(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Pull P&L from Xero and calculate tax position."""
        # Use repo directly to avoid get_plan's auto-refresh (which calls us)
        plan = await self.plan_repo.get_by_id(plan_id, tenant_id)
        if not plan:
            raise TaxPlanNotFoundError(plan_id)

        if not plan.xero_connection_id:
            raise NoXeroConnectionError()

        report_service = XeroReportService(self.session, self.settings)

        # Fetch reconciliation date first so we can cap the P&L period.
        # On accrual basis, Xero includes all approved invoices within the
        # date range — sales invoices created ahead of time inflate income
        # beyond what has actually been reconciled.
        try:
            recon_date = await report_service.get_last_reconciliation_date(
                plan.xero_connection_id,
            )
        except Exception:
            logger.warning("Reconciliation date fetch failed, using today", exc_info=True)
            recon_date = None

        # Cap P&L to_date at the earlier of reconciliation date or today
        effective_to = (
            min(recon_date, date.today()).isoformat() if recon_date else date.today().isoformat()
        )

        try:
            report_data = await report_service.get_report(
                connection_id=plan.xero_connection_id,
                report_type="profit_and_loss",
                period_key=f"{plan.financial_year[:4]}-FY",
                force_refresh=force_refresh,
                to_date_override=effective_to,
            )
        except Exception as e:
            logger.error("Xero P&L pull failed", exc_info=True)
            import contextlib

            with contextlib.suppress(Exception):
                await self.session.rollback()
            raise XeroPullError(str(e)) from e

        # Transform Xero summary into financials_data format
        summary = report_data.get("summary") or {}
        rows = report_data.get("rows", [])

        financials_data = self._transform_xero_to_financials(summary, rows)
        now = datetime.now(UTC)

        # Calculate actual months of data and projection (Spec 056 - US2)
        fy_start_year = int(plan.financial_year[:4])
        fy_start_date = date(fy_start_year, 7, 1)
        effective_date = recon_date or date.today()
        months_elapsed = (effective_date.year - fy_start_date.year) * 12 + (
            effective_date.month - fy_start_date.month
        )
        months_elapsed = max(1, min(months_elapsed, 12))

        financials_data["months_data_available"] = months_elapsed
        financials_data["is_annualised"] = months_elapsed < 12

        if months_elapsed >= 3 and months_elapsed < 12:
            total_income = financials_data["income"]["total_income"]
            total_expenses = financials_data["expenses"]["total_expenses"]
            monthly_avg_rev = total_income / months_elapsed
            monthly_avg_exp = total_expenses / months_elapsed
            financials_data["projection"] = {
                "projected_revenue": round(monthly_avg_rev * 12, 2),
                "projected_expenses": round(monthly_avg_exp * 12, 2),
                "projected_net_profit": round((monthly_avg_rev - monthly_avg_exp) * 12, 2),
                "monthly_avg_revenue": round(monthly_avg_rev, 2),
                "monthly_avg_expenses": round(monthly_avg_exp, 2),
                "months_used": months_elapsed,
                "projection_method": "linear_average",
            }
        else:
            financials_data["projection"] = None

        # Fetch bank context (FR-015, FR-016, FR-017, FR-018)
        # recon_date was already fetched above for the P&L date cap
        try:
            bank_balances = await report_service.get_bank_balances(plan.xero_connection_id)
            unreconciled = await self._get_unreconciled_summary(
                plan.xero_connection_id, plan.financial_year
            )

            total_bank_balance = (
                sum(a["closing_balance"] for a in bank_balances) if bank_balances else None
            )
            recon_date_str = recon_date.isoformat() if recon_date else None

            # Build period coverage string
            fy_start_year = int(plan.financial_year[:4])
            period_start = f"1 Jul {fy_start_year}"
            if recon_date:
                period_coverage = f"{period_start} – {recon_date.strftime('%-d %b %Y')} — Reconciled to {recon_date.strftime('%-d %b %Y')}"
            else:
                period_coverage = f"{period_start} – current (no reconciliation data)"

            financials_data["bank_balances"] = bank_balances
            financials_data["total_bank_balance"] = total_bank_balance
            financials_data["last_reconciliation_date"] = recon_date_str
            financials_data["period_coverage"] = period_coverage
            financials_data["unreconciled_summary"] = unreconciled
        except Exception:
            logger.warning("Bank context fetch failed, proceeding without", exc_info=True)
            # Rollback to clear any failed transaction state from bank context queries
            try:
                await self.session.rollback()
                # Re-fetch plan since rollback expires ORM objects
                plan = await self.plan_repo.get_by_id(plan_id, tenant_id)
            except Exception:
                pass

        # Prior year YTD comparison (Spec 056 - US3)
        try:
            prior_fy_year = fy_start_year - 1
            prior_fy_key = f"{prior_fy_year}-FY"
            # Shift to_date back by 1 year for same-period comparison
            prior_to_date = effective_date.replace(year=effective_date.year - 1).isoformat()
            prior_report = await report_service.get_report(
                connection_id=plan.xero_connection_id,
                report_type="profit_and_loss",
                period_key=prior_fy_key,
                to_date_override=prior_to_date,
            )
            prior_summary = prior_report.get("summary") or {}
            prior_revenue = float(prior_summary.get("revenue", 0))
            prior_total_income = float(prior_summary.get("total_income", 0))
            prior_total_expenses = float(prior_summary.get("total_expenses", 0))
            prior_net_profit = prior_total_income - prior_total_expenses
            cur_revenue = financials_data["income"]["revenue"]
            cur_expenses = financials_data["expenses"]["total_expenses"]
            cur_profit = financials_data["income"]["total_income"] - cur_expenses

            financials_data["prior_year_ytd"] = {
                "revenue": prior_revenue,
                "total_income": prior_total_income,
                "total_expenses": prior_total_expenses,
                "net_profit": prior_net_profit,
                "period_coverage": f"1 Jul {prior_fy_year} – {effective_date.replace(year=effective_date.year - 1).strftime('%-d %b %Y')}",
                "changes": {
                    "revenue_pct": round((cur_revenue - prior_revenue) / prior_revenue * 100, 1)
                    if prior_revenue
                    else 0,
                    "expenses_pct": round(
                        (cur_expenses - prior_total_expenses) / prior_total_expenses * 100, 1
                    )
                    if prior_total_expenses
                    else 0,
                    "profit_pct": round(
                        (cur_profit - prior_net_profit) / abs(prior_net_profit) * 100, 1
                    )
                    if prior_net_profit
                    else 0,
                },
            }
        except Exception:
            logger.debug("Prior year YTD pull failed or unavailable", exc_info=True)
            financials_data["prior_year_ytd"] = None

        # Multi-year full FY trends (Spec 056 - US4)
        prior_years = []
        for offset in [1, 2]:
            try:
                yr = fy_start_year - offset
                fy_report = await report_service.get_report(
                    connection_id=plan.xero_connection_id,
                    report_type="profit_and_loss",
                    period_key=f"{yr}-FY",
                )
                fy_summary = fy_report.get("summary") or {}
                fy_revenue = float(fy_summary.get("revenue", 0))
                fy_income = float(fy_summary.get("total_income", 0))
                fy_expenses = float(fy_summary.get("total_expenses", 0))
                if fy_income > 0 or fy_expenses > 0:
                    prior_years.append(
                        {
                            "financial_year": f"FY{yr + 1}",
                            "revenue": fy_revenue,
                            "expenses": fy_expenses,
                            "net_profit": fy_income - fy_expenses,
                        }
                    )
            except Exception:
                logger.debug(f"Prior FY {yr} pull failed or unavailable", exc_info=True)
        financials_data["prior_years"] = prior_years if prior_years else None

        # Strategy context (Spec 056 - US5)
        total_bank = financials_data.get("total_bank_balance")
        monthly_opex = financials_data["expenses"]["total_expenses"] / max(months_elapsed, 1)
        cash_buffer = monthly_opex * 3
        asset_keywords = {
            "equipment",
            "depreciation",
            "asset",
            "computer",
            "furniture",
            "vehicle",
            "plant",
        }
        existing_asset_spend = sum(
            abs(item["amount"])
            for item in financials_data["expenses"].get("breakdown", [])
            if any(kw in item["category"].lower() for kw in asset_keywords)
        )
        financials_data["strategy_context"] = {
            "available_cash": total_bank,
            "monthly_operating_expenses": round(monthly_opex, 2),
            "cash_buffer_3mo": round(cash_buffer, 2),
            "max_strategy_budget": round(total_bank - cash_buffer, 2)
            if total_bank and total_bank > cash_buffer
            else None,
            "existing_asset_spend": round(existing_asset_spend, 2),
        }

        # Payroll intelligence (Spec 056 - US6)
        try:
            from app.modules.integrations.xero.models import XeroEmployee, XeroPayRun

            connection = await self.session.get(XeroConnection, plan.xero_connection_id)
            if connection and getattr(connection, "has_payroll_access", False):
                # Query pay runs for current FY
                pay_run_result = await self.session.execute(
                    select(XeroPayRun).where(
                        XeroPayRun.connection_id == connection.id,
                        XeroPayRun.period_start >= fy_start_date,
                    )
                )
                pay_runs = list(pay_run_result.scalars().all())

                # Query active employees
                emp_result = await self.session.execute(
                    select(XeroEmployee).where(
                        XeroEmployee.connection_id == connection.id,
                        XeroEmployee.status == "active",
                    )
                )
                employees = list(emp_result.scalars().all())

                owner_titles = {"director", "owner", "principal", "partner", "managing director"}
                has_owners = any(
                    e.job_title and any(t in e.job_title.lower() for t in owner_titles)
                    for e in employees
                )

                financials_data["payroll_summary"] = {
                    "employee_count": len(employees),
                    "total_wages_ytd": sum(float(pr.total_wages or 0) for pr in pay_runs),
                    "total_super_ytd": sum(float(pr.total_super or 0) for pr in pay_runs),
                    "total_tax_withheld_ytd": sum(float(pr.total_tax or 0) for pr in pay_runs),
                    "has_owners": has_owners,
                    "employees": [
                        {
                            "name": e.full_name,
                            "job_title": e.job_title,
                            "status": e.status.value
                            if hasattr(e.status, "value")
                            else str(e.status),
                        }
                        for e in employees[:20]  # Cap at 20 for JSONB size
                    ],
                }
            else:
                financials_data["payroll_summary"] = None
        except Exception:
            logger.debug("Payroll data fetch failed or unavailable", exc_info=True)
            financials_data["payroll_summary"] = None

        await self.plan_repo.update(
            plan,
            {
                "financials_data": financials_data,
                "xero_report_fetched_at": now,
                "data_source": "xero",
            },
        )

        # Calculate tax position
        tax_position = await self._calculate_and_save_position(plan)

        fetched_at = report_data.get("fetched_at")
        is_stale = report_data.get("is_stale", False)

        return {
            "financials_data": financials_data,
            "tax_position": tax_position,
            "data_freshness": {
                "fetched_at": str(fetched_at) if fetched_at else str(now),
                "is_fresh": not is_stale,
                "cache_age_minutes": None,
            },
        }

    def _transform_xero_to_financials(self, summary: dict, rows: list) -> dict[str, Any]:
        """Transform Xero P&L summary data into financials_data JSONB format."""
        revenue = float(summary.get("revenue", 0))
        other_income = float(summary.get("other_income", 0))
        total_income = float(summary.get("total_income", 0)) or (revenue + other_income)
        cost_of_sales = float(summary.get("cost_of_sales", 0))
        operating_expenses = float(summary.get("operating_expenses", 0))
        total_expenses = float(summary.get("total_expenses", 0)) or (
            cost_of_sales + operating_expenses
        )

        # Extract line-item breakdown from rows
        income_breakdown = self._extract_breakdown(rows, "income")
        expense_breakdown = self._extract_breakdown(rows, "expense")

        return {
            "income": {
                "revenue": revenue,
                "other_income": other_income,
                "total_income": total_income,
                "breakdown": income_breakdown,
            },
            "expenses": {
                "cost_of_sales": cost_of_sales,
                "operating_expenses": operating_expenses,
                "total_expenses": total_expenses,
                "breakdown": expense_breakdown,
            },
            "credits": {
                "payg_instalments": 0,
                "payg_withholding": 0,
                "franking_credits": 0,
            },
            "adjustments": [],
            "turnover": total_income,
            "months_data_available": 12,  # Overridden after transform
            "is_annualised": False,  # Overridden after transform
        }

    def _extract_breakdown(self, rows: list, section_type: str) -> list[dict[str, Any]]:
        """Extract line-item breakdown from Xero report rows."""
        breakdown: list[dict[str, Any]] = []
        income_titles = {"income", "revenue", "trading income", "other income", "other revenue"}
        expense_titles = {
            "less cost of sales",
            "cost of sales",
            "cost of goods sold",
            "less operating expenses",
            "operating expenses",
            "expenses",
        }

        target_titles = income_titles if section_type == "income" else expense_titles

        for row in rows:
            if row.get("RowType") == "Section":
                title = (row.get("Title") or "").lower().strip()
                if title in target_titles:
                    for sub_row in row.get("Rows", []):
                        if sub_row.get("RowType") == "Row":
                            cells = sub_row.get("Cells", [])
                            if len(cells) >= 2:
                                name = cells[0].get("Value", "")
                                value = cells[1].get("Value", "0")
                                try:
                                    amount = float(value.replace(",", ""))
                                except (ValueError, AttributeError):
                                    amount = 0
                                if name and amount != 0:
                                    breakdown.append({"category": name, "amount": amount})

        return breakdown

    async def _get_unreconciled_summary(
        self,
        connection_id: uuid.UUID,
        financial_year: str,
    ) -> dict[str, Any]:
        """Aggregate unreconciled bank transactions for GST estimation (FR-017).

        Returns provisional estimates of GST collected/paid and
        income/expenses from unreconciled transactions in the current
        BAS quarter.
        """
        from decimal import Decimal

        from sqlalchemy import case, func, select

        from app.modules.integrations.xero.models import XeroBankTransaction

        # Determine current quarter boundaries within the FY
        fy_start_year = int(financial_year[:4])
        now = datetime.now(UTC)
        # Australian BAS quarters: Jul-Sep, Oct-Dec, Jan-Mar, Apr-Jun
        month = now.month
        if month in (7, 8, 9):
            q_start = datetime(fy_start_year, 7, 1, tzinfo=UTC)
            q_end = datetime(fy_start_year, 9, 30, tzinfo=UTC)
        elif month in (10, 11, 12):
            q_start = datetime(fy_start_year, 10, 1, tzinfo=UTC)
            q_end = datetime(fy_start_year, 12, 31, tzinfo=UTC)
        elif month in (1, 2, 3):
            q_start = datetime(fy_start_year + 1, 1, 1, tzinfo=UTC)
            q_end = datetime(fy_start_year + 1, 3, 31, tzinfo=UTC)
        else:
            q_start = datetime(fy_start_year + 1, 4, 1, tzinfo=UTC)
            q_end = datetime(fy_start_year + 1, 6, 30, tzinfo=UTC)

        result = await self.session.execute(
            select(
                func.count(XeroBankTransaction.id).label("count"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                XeroBankTransaction.transaction_type == "receive",
                                XeroBankTransaction.total_amount,
                            ),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("income"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                XeroBankTransaction.transaction_type == "spend",
                                XeroBankTransaction.total_amount,
                            ),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("expenses"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                XeroBankTransaction.transaction_type == "receive",
                                XeroBankTransaction.tax_amount,
                            ),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("gst_collected"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                XeroBankTransaction.transaction_type == "spend",
                                XeroBankTransaction.tax_amount,
                            ),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("gst_paid"),
            ).where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.is_reconciled.is_(False),
                XeroBankTransaction.transaction_date >= q_start,
                XeroBankTransaction.transaction_date <= q_end,
            )
        )
        row = result.one()

        return {
            "transaction_count": row.count,
            "unreconciled_income": float(row.income),
            "unreconciled_expenses": float(row.expenses),
            "gst_collected_estimate": float(row.gst_collected),
            "gst_paid_estimate": float(row.gst_paid),
            "quarter": f"{q_start.strftime('%b %Y')} – {q_end.strftime('%b %Y')}",
            "is_provisional": True,
        }

    # ------------------------------------------------------------------
    # Financials: Manual entry
    # ------------------------------------------------------------------

    async def save_manual_financials(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: FinancialsInput,
    ) -> dict[str, Any]:
        """Save manually entered financials and calculate tax position."""
        plan = await self.get_plan(plan_id, tenant_id)

        # Build financials_data from input
        income = data.income
        expenses = data.expenses
        credits = data.credits

        total_income = float(
            Decimal(str(income.get("revenue", 0))) + Decimal(str(income.get("other_income", 0)))
        )
        total_expenses = float(
            Decimal(str(expenses.get("cost_of_sales", 0)))
            + Decimal(str(expenses.get("operating_expenses", 0)))
        )

        financials_data: dict[str, Any] = {
            "income": {
                "revenue": float(income.get("revenue", 0)),
                "other_income": float(income.get("other_income", 0)),
                "total_income": total_income,
                "breakdown": income.get("breakdown", []),
            },
            "expenses": {
                "cost_of_sales": float(expenses.get("cost_of_sales", 0)),
                "operating_expenses": float(expenses.get("operating_expenses", 0)),
                "total_expenses": total_expenses,
                "breakdown": expenses.get("breakdown", []),
            },
            "credits": {
                "payg_instalments": float(credits.get("payg_instalments", 0)),
                "payg_withholding": float(credits.get("payg_withholding", 0)),
                "franking_credits": float(credits.get("franking_credits", 0)),
            },
            "adjustments": [adj.model_dump() for adj in data.adjustments],
            "turnover": float(data.turnover),
            "months_data_available": 12,
            "is_annualised": False,
        }

        new_source = "manual"
        if plan.data_source == "xero":
            new_source = "xero_with_adjustments"

        await self.plan_repo.update(
            plan,
            {"financials_data": financials_data, "data_source": new_source},
        )

        tax_position = await self._calculate_and_save_position(
            plan, has_help_debt=data.has_help_debt
        )

        return {
            "financials_data": financials_data,
            "tax_position": tax_position,
        }

    # ------------------------------------------------------------------
    # Tax calculation
    # ------------------------------------------------------------------

    async def _calculate_and_save_position(
        self,
        plan: TaxPlan,
        has_help_debt: bool = False,
    ) -> dict[str, Any]:
        """Load rate configs and calculate tax position."""
        rate_configs = await self._load_rate_configs(plan.financial_year)

        tax_position = calculate_tax_position(
            entity_type=plan.entity_type,
            financials_data=plan.financials_data,
            rate_configs=rate_configs,
            has_help_debt=has_help_debt,
        )

        await self.plan_repo.update(plan, {"tax_position": tax_position})

        # Transition draft → in_progress
        if plan.status == "draft":
            await self.plan_repo.update(plan, {"status": "in_progress"})

        return tax_position

    async def _load_rate_configs(self, financial_year: str) -> dict[str, dict]:
        """Load all rate configs for a financial year as a dict keyed by rate_type."""
        configs = await self.rate_repo.get_rates_for_year(financial_year)
        if not configs:
            raise TaxRateConfigNotFoundError(financial_year)

        result: dict[str, dict] = {"_financial_year": financial_year}  # type: ignore[dict-item]
        for config in configs:
            result[config.rate_type] = config.rates_data

        return result

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    async def list_scenarios(self, plan_id: uuid.UUID, tenant_id: uuid.UUID) -> list:
        await self.get_plan(plan_id, tenant_id)  # Verify access
        return await self.scenario_repo.list_by_plan(plan_id, tenant_id)

    async def delete_scenario(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scenario_id: uuid.UUID,
    ) -> None:
        await self.get_plan(plan_id, tenant_id)  # Verify access
        scenario = await self.scenario_repo.get_by_id(scenario_id, tenant_id)
        if not scenario or scenario.tax_plan_id != plan_id:
            raise TaxScenarioNotFoundError(scenario_id)
        await self.scenario_repo.delete(scenario)

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def list_messages(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list, int]:
        await self.get_plan(plan_id, tenant_id)  # Verify access
        return await self.message_repo.list_by_plan(plan_id, tenant_id, page, page_size)

    # ------------------------------------------------------------------
    # RAG Retrieval
    # ------------------------------------------------------------------

    _CONVERSATIONAL_PATTERNS = {
        "thanks",
        "thank you",
        "ok",
        "okay",
        "got it",
        "sure",
        "yes",
        "no",
        "hi",
        "hello",
        "hey",
        "cheers",
        "great",
        "good",
        "cool",
        "noted",
    }

    async def _retrieve_tax_knowledge(
        self,
        query: str,
        entity_type: str,
    ) -> tuple[list[dict], str]:
        """Retrieve relevant knowledge base content for a tax planning query.

        Returns:
            Tuple of (raw_chunks, formatted_reference_material).
            Empty list and empty-KB message if retrieval fails or is skipped.
        """
        from app.modules.tax_planning.prompts import format_reference_material

        # Skip retrieval for conversational messages
        if (
            len(query.strip()) < 10
            or query.strip().lower().rstrip("!.?") in self._CONVERSATIONAL_PATTERNS
        ):
            return [], format_reference_material([])

        try:
            from app.core.pinecone_service import PineconeService
            from app.core.voyage import VoyageService
            from app.modules.knowledge.schemas import (
                KnowledgeSearchFilters,
                KnowledgeSearchRequest,
            )
            from app.modules.knowledge.service import KnowledgeService

            pinecone = PineconeService(self.settings.pinecone)
            voyage = VoyageService(self.settings.voyage)
            knowledge_service = KnowledgeService(self.session, pinecone, voyage)

            # Build metadata filters based on entity type
            entity_filter = {
                "company": ["company"],
                "individual": ["sole_trader", "individual"],
                "trust": ["trust"],
                "partnership": ["partnership"],
            }.get(entity_type, [])

            search_request = KnowledgeSearchRequest(
                query=query,
                filters=KnowledgeSearchFilters(
                    entity_types=entity_filter or None,
                    exclude_superseded=True,
                ),
                limit=8,
            )

            response = await knowledge_service.search_knowledge(search_request)
            results = response.get("results", [])

            # Take top 5 after reranking
            chunks = []
            for result in results[:5]:
                chunks.append(
                    {
                        "chunk_id": str(result.get("chunk_id", "")),
                        "source_type": result.get("source_type", ""),
                        "title": result.get("title", ""),
                        "ruling_number": result.get("ruling_number"),
                        "section_ref": result.get("section_ref"),
                        "text": result.get("text", ""),
                        "relevance_score": result.get("relevance_score", 0.0),
                        "is_superseded": result.get("is_superseded", False),
                    }
                )

            logger.info(
                "RAG retrieval: query=%s entity=%s results=%d",
                query[:80],
                entity_type,
                len(chunks),
            )

            return chunks, format_reference_material(chunks)

        except Exception as e:
            logger.warning("RAG retrieval failed, proceeding without references: %s", e)
            return [], format_reference_material([])

    def _build_citation_verification(
        self,
        response_content: str,
        retrieved_chunks: list[dict],
    ) -> dict:
        """Verify citations in the response against retrieved chunks.

        Returns a citation verification result dict.
        """
        import re

        if not response_content or not retrieved_chunks:
            return {
                "total_citations": 0,
                "verified_count": 0,
                "unverified_count": 0,
                "verification_rate": 0.0,
                "status": "no_citations",
            }

        # Extract citations: [Source: ...] patterns
        citation_pattern = r"\[Source:\s*([^\]]+)\]"
        citations = re.findall(citation_pattern, response_content)

        if not citations:
            return {
                "total_citations": 0,
                "verified_count": 0,
                "unverified_count": 0,
                "verification_rate": 0.0,
                "status": "no_citations",
            }

        # Build a set of identifiers from retrieved chunks
        chunk_identifiers = set()
        for chunk in retrieved_chunks:
            if chunk.get("ruling_number"):
                chunk_identifiers.add(chunk["ruling_number"].lower().strip())
            if chunk.get("section_ref"):
                chunk_identifiers.add(chunk["section_ref"].lower().strip())
            if chunk.get("title"):
                chunk_identifiers.add(chunk["title"].lower().strip())

        # Verify each citation
        verified_count = 0
        for citation in citations:
            citation_lower = citation.lower().strip()
            if any(
                identifier in citation_lower or citation_lower in identifier
                for identifier in chunk_identifiers
            ):
                verified_count += 1

        total = len(citations)
        unverified = total - verified_count
        rate = verified_count / total if total > 0 else 0.0

        if rate >= 0.9:
            status = "verified"
        elif rate >= 0.5:
            status = "partially_verified"
        else:
            status = "unverified"

        return {
            "total_citations": total,
            "verified_count": verified_count,
            "unverified_count": unverified,
            "verification_rate": rate,
            "status": status,
        }

    # ------------------------------------------------------------------
    # AI Chat
    # ------------------------------------------------------------------

    async def send_chat_message(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        message: str,
        file: Any | None = None,
    ) -> dict[str, Any]:
        """Send a message to the AI agent and get scenario responses."""
        from app.modules.tax_planning.agent import TaxPlanningAgent

        plan = await self.get_plan(plan_id, tenant_id)
        if not plan.financials_data:
            from app.core.exceptions import ValidationError

            raise ValidationError("Load financials before using AI chat")

        # Process file attachment
        attachment = None
        attachment_metadata: dict[str, Any] = {}
        if file and file.filename:
            from app.modules.tax_planning.file_processor import process_chat_attachment

            attachment = await process_chat_attachment(
                file,
                tenant_id,
                "tax-planning",
                plan_id,
                f"msg-{uuid.uuid4().hex[:12]}",
            )
            attachment_metadata = {
                "attachment": {
                    "object_key": attachment.object_key,
                    "filename": attachment.filename,
                    "media_type": attachment.media_type,
                    "category": attachment.category,
                    "size_bytes": attachment.size_bytes,
                }
            }

        # Load context
        rate_configs = await self._load_rate_configs(plan.financial_year)
        recent_messages = await self.message_repo.get_recent_messages(plan_id, max_tokens=24000)
        scenarios = await self.scenario_repo.list_by_plan(plan_id, tenant_id)

        conversation_history = self._build_conversation_history(recent_messages)

        # Save user message
        await self.message_repo.create(
            {
                "tenant_id": tenant_id,
                "tax_plan_id": plan_id,
                "role": "user",
                "content": message,
                "scenario_ids": [],
                "token_count": len(message) // 4,
                "metadata_": attachment_metadata,
            }
        )

        # RAG retrieval
        retrieved_chunks, reference_material = await self._retrieve_tax_knowledge(
            message,
            plan.entity_type,
        )

        # Call AI agent
        api_key = self.settings.anthropic.api_key.get_secret_value()
        agent = TaxPlanningAgent(api_key=api_key)

        response = await agent.process_message(
            message=message,
            plan_financials=plan.financials_data,
            plan_tax_position=plan.tax_position,
            entity_type=plan.entity_type,
            financial_year=plan.financial_year,
            conversation_history=conversation_history,
            existing_scenarios=scenarios,
            rate_configs=rate_configs,
            reference_material=reference_material,
            content_blocks=attachment.content_blocks if attachment else None,
        )

        # Citation verification
        citation_verification = self._build_citation_verification(
            response.content,
            retrieved_chunks,
        )
        source_chunks_used = [
            {k: v for k, v in chunk.items() if k != "text" and k != "is_superseded"}
            for chunk in retrieved_chunks
        ] or None

        # Confidence-based decline (matches knowledge chatbot pattern)
        scores = [c.get("score", 0.0) for c in retrieved_chunks if c.get("score")]
        top_score = scores[0] if scores else 0.0
        mean_top5 = sum(scores[:5]) / min(len(scores), 5) if scores else 0.0
        verification_rate = citation_verification.get("verification_rate", 0.0)
        confidence_score = 0.4 * top_score + 0.3 * mean_top5 + 0.3 * verification_rate
        if confidence_score < 0.5 and retrieved_chunks:
            # Low confidence — replace AI response with decline message
            response.content = (
                "I don't have enough reliable tax compliance information to "
                "answer this confidently. The response may rely on general "
                "knowledge rather than current ATO guidance. Please consult "
                "the ATO website (ato.gov.au) or your compliance resources "
                "for authoritative information."
            )
            response.scenarios = []
            citation_verification["status"] = "low_confidence"
            citation_verification["confidence_score"] = confidence_score
        else:
            citation_verification["confidence_score"] = confidence_score

        # Create scenario records
        created_scenarios = []
        scenario_ids = []
        for scenario_data in response.scenarios:
            sort_order = await self.scenario_repo.get_next_sort_order(plan_id)
            scenario = await self.scenario_repo.create(
                {
                    "tenant_id": tenant_id,
                    "tax_plan_id": plan_id,
                    "title": scenario_data["scenario_title"],
                    "description": scenario_data.get("description", ""),
                    "assumptions": scenario_data.get("assumptions", {}),
                    "impact_data": scenario_data.get("impact_data", {}),
                    "risk_rating": scenario_data.get("risk_rating", "moderate"),
                    "compliance_notes": scenario_data.get("compliance_notes"),
                    "cash_flow_impact": scenario_data.get("cash_flow_impact"),
                    "sort_order": sort_order,
                }
            )
            created_scenarios.append(scenario)
            scenario_ids.append(scenario.id)

        # Save assistant message with RAG metadata
        assistant_msg = await self.message_repo.create(
            {
                "tenant_id": tenant_id,
                "tax_plan_id": plan_id,
                "role": "assistant",
                "content": response.content,
                "scenario_ids": scenario_ids,
                "token_count": len(response.content) // 4,
                "metadata_": response.token_usage,
                "source_chunks_used": source_chunks_used,
                "citation_verification": citation_verification,
            }
        )

        # Audit log AI interaction
        try:
            from app.core.audit import AuditService

            audit = AuditService(self.session)
            await audit.log_event(
                event_type="ai.tax_planning.chat",
                event_category="data",
                tenant_id=tenant_id,
                resource_type="tax_plan",
                resource_id=plan_id,
                action="create",
                outcome="success",
                metadata={
                    "model": response.token_usage.get("model", "claude-sonnet")
                    if response.token_usage
                    else None,
                    "input_tokens": response.token_usage.get("input_tokens")
                    if response.token_usage
                    else None,
                    "output_tokens": response.token_usage.get("output_tokens")
                    if response.token_usage
                    else None,
                    "scenarios_count": len(response.scenarios),
                },
            )
        except Exception:
            pass  # Never let audit failure break the main flow

        return {
            "message": assistant_msg,
            "scenarios_created": created_scenarios,
            "updated_tax_position": None,
        }

    async def send_chat_message_streaming(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        message: str,
        attachment: Any | None = None,
    ) -> Any:
        """Stream AI response via SSE events."""
        from app.modules.tax_planning.agent import TaxPlanningAgent

        plan = await self.get_plan(plan_id, tenant_id)
        if not plan.financials_data:
            from app.core.exceptions import ValidationError

            raise ValidationError("Load financials before using AI chat")

        rate_configs = await self._load_rate_configs(plan.financial_year)
        recent_messages = await self.message_repo.get_recent_messages(plan_id, max_tokens=24000)
        scenarios = await self.scenario_repo.list_by_plan(plan_id, tenant_id)

        conversation_history = self._build_conversation_history(recent_messages)

        # Build attachment metadata for persistence
        attachment_metadata: dict[str, Any] = {}
        if attachment:
            attachment_metadata = {
                "attachment": {
                    "object_key": attachment.object_key,
                    "filename": attachment.filename,
                    "media_type": attachment.media_type,
                    "category": attachment.category,
                    "size_bytes": attachment.size_bytes,
                }
            }

        # Save user message
        await self.message_repo.create(
            {
                "tenant_id": tenant_id,
                "tax_plan_id": plan_id,
                "role": "user",
                "content": message,
                "scenario_ids": [],
                "token_count": len(message) // 4,
                "metadata_": attachment_metadata,
            }
        )

        # RAG retrieval
        retrieved_chunks, reference_material = await self._retrieve_tax_knowledge(
            message,
            plan.entity_type,
        )

        api_key = self.settings.anthropic.api_key.get_secret_value()
        agent = TaxPlanningAgent(api_key=api_key)

        full_content = ""
        created_scenario_ids: list[uuid.UUID] = []

        async for event in agent.process_message_streaming(
            message=message,
            plan_financials=plan.financials_data,
            plan_tax_position=plan.tax_position,
            entity_type=plan.entity_type,
            financial_year=plan.financial_year,
            conversation_history=conversation_history,
            existing_scenarios=scenarios,
            rate_configs=rate_configs,
            reference_material=reference_material,
            content_blocks=attachment.content_blocks if attachment else None,
        ):
            if event["type"] == "content":
                full_content += event.get("content", "")
            elif event["type"] == "scenario":
                scenario_data = event["scenario"]
                sort_order = await self.scenario_repo.get_next_sort_order(plan_id)
                scenario = await self.scenario_repo.create(
                    {
                        "tenant_id": tenant_id,
                        "tax_plan_id": plan_id,
                        "title": scenario_data["scenario_title"],
                        "description": scenario_data.get("description", ""),
                        "assumptions": scenario_data.get("assumptions", {}),
                        "impact_data": scenario_data.get("impact_data", {}),
                        "risk_rating": scenario_data.get("risk_rating", "moderate"),
                        "compliance_notes": scenario_data.get("compliance_notes"),
                        "cash_flow_impact": scenario_data.get("cash_flow_impact"),
                        "sort_order": sort_order,
                    }
                )
                created_scenario_ids.append(scenario.id)
                event["scenario"]["id"] = str(scenario.id)

            yield event

        # Citation verification and save assistant message
        if full_content:
            citation_verification = self._build_citation_verification(
                full_content,
                retrieved_chunks,
            )
            source_chunks_used = [
                {k: v for k, v in chunk.items() if k != "text" and k != "is_superseded"}
                for chunk in retrieved_chunks
            ] or None

            await self.message_repo.create(
                {
                    "tenant_id": tenant_id,
                    "tax_plan_id": plan_id,
                    "role": "assistant",
                    "content": full_content,
                    "scenario_ids": created_scenario_ids,
                    "token_count": len(full_content) // 4,
                    "source_chunks_used": source_chunks_used,
                    "citation_verification": citation_verification,
                }
            )

            # Yield verification event for frontend
            yield {
                "type": "verification",
                "data": citation_verification,
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_conversation_history(
        messages: list[Any],
    ) -> list[dict[str, Any]]:
        """Build conversation history with multimodal content blocks.

        For messages with file attachments stored in metadata_, reconstructs
        the content as Anthropic-compatible content blocks. For plain text
        messages, uses a simple string.
        """
        from app.modules.tax_planning.file_processor import (
            build_content_blocks_from_metadata,
        )

        history: list[dict[str, Any]] = []
        for msg in messages:
            metadata = getattr(msg, "metadata_", None) or {}
            attachment_blocks = build_content_blocks_from_metadata(metadata)

            if attachment_blocks and msg.role == "user":
                # Multimodal message: file blocks + text
                content_parts = attachment_blocks + [{"type": "text", "text": msg.content}]
                history.append({"role": msg.role, "content": content_parts})
            else:
                history.append({"role": msg.role, "content": msg.content})

        return history

    async def get_client_name(self, xero_connection_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
        """Get the organisation name from the XeroConnection."""
        result = await self.session.execute(
            select(XeroConnection).where(
                XeroConnection.id == xero_connection_id,
                XeroConnection.tenant_id == tenant_id,
            )
        )
        connection = result.scalar_one_or_none()
        return connection.organization_name if connection else ""

    async def get_connection_status(self, xero_connection_id: uuid.UUID) -> str | None:
        """Get the Xero connection status (active, needs_reauth, disconnected)."""
        connection = await self.session.get(XeroConnection, xero_connection_id)
        if not connection:
            return None
        return connection.status.value if connection.status else None

    # ------------------------------------------------------------------
    # PDF Export
    # ------------------------------------------------------------------

    async def export_plan_pdf(
        self,
        plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        include_scenarios: bool = True,
        include_conversation: bool = False,
    ) -> bytes:
        """Generate a PDF export of the tax plan."""
        from pathlib import Path

        import weasyprint
        from jinja2 import Environment, FileSystemLoader

        plan = await self.get_plan(plan_id, tenant_id)
        if not plan.tax_position:
            from app.modules.tax_planning.exceptions import TaxPlanExportError

            raise TaxPlanExportError()

        client_name = await self.get_client_name(plan.xero_connection_id, tenant_id)

        # Load scenarios and messages if needed
        scenarios = []
        if include_scenarios:
            scenarios = await self.scenario_repo.list_by_plan(plan_id, tenant_id)

        messages_list = []
        if include_conversation:
            msgs, _ = await self.message_repo.list_by_plan(
                plan_id, tenant_id, page=1, page_size=200
            )
            messages_list = msgs

        # Load tenant for practice name
        practice_name = "Your Practice"  # Default
        try:
            from app.modules.auth.models import Tenant

            result = await self.session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant and tenant.name:
                practice_name = tenant.name
        except Exception:
            pass

        entity_type_labels = {
            "company": "Company",
            "individual": "Individual / Sole Trader",
            "trust": "Trust",
            "partnership": "Partnership",
        }

        # Render template
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
        template = env.get_template("tax_plan_export.html")

        # Make tax_position a namespace-like dict for Jinja dot access
        class DotDict(dict):
            __getattr__ = dict.get

        tax_pos = DotDict(plan.tax_position)
        tax_pos["credits_applied"] = DotDict(plan.tax_position.get("credits_applied", {}))
        tax_pos["offsets"] = DotDict(plan.tax_position.get("offsets", {}))

        from app.core.constants import AI_DISCLAIMER_TEXT

        html = template.render(
            practice_name=practice_name,
            client_name=client_name,
            financial_year=plan.financial_year,
            entity_type_label=entity_type_labels.get(plan.entity_type, plan.entity_type),
            tax_position=tax_pos,
            scenarios=scenarios,
            include_scenarios=include_scenarios,
            messages=messages_list,
            include_conversation=include_conversation,
            generated_date=datetime.now(UTC).strftime("%d %B %Y"),
            ai_disclaimer=AI_DISCLAIMER_TEXT,
        )

        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        return pdf_bytes

    # ------------------------------------------------------------------
    # Xero change detection (for US5 resume)
    # ------------------------------------------------------------------

    async def check_xero_changes(self, plan_id: uuid.UUID, tenant_id: uuid.UUID) -> dict | None:
        """Compare stored financials with current Xero data."""
        plan = await self.get_plan(plan_id, tenant_id)

        if not plan.xero_connection_id or plan.data_source == "manual":
            return None

        if not plan.financials_data:
            return None

        try:
            report_service = XeroReportService(self.session, self.settings)
            report_data = await report_service.get_report(
                connection_id=plan.xero_connection_id,
                report_type="profit_and_loss",
                period_key=f"{plan.financial_year[:4]}-FY",
                force_refresh=False,
            )
        except Exception:
            return None

        summary = report_data.get("summary") or {}
        stored_income = plan.financials_data.get("income", {})
        stored_expenses = plan.financials_data.get("expenses", {})

        changes: dict[str, dict] = {}
        field_map = {
            "revenue": ("income", "revenue"),
            "other_income": ("income", "other_income"),
            "cost_of_sales": ("expenses", "cost_of_sales"),
            "operating_expenses": ("expenses", "operating_expenses"),
        }

        for xero_key, (section, field) in field_map.items():
            current_val = float(summary.get(xero_key, 0))
            stored_section = stored_income if section == "income" else stored_expenses
            stored_val = float(stored_section.get(field, 0))
            if abs(current_val - stored_val) > 0.01:
                changes[field] = {"old": stored_val, "new": current_val}

        return changes if changes else None
