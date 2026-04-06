'use client';

import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCurrency, formatRelativeTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { DataSource, FinancialsData } from '@/types/tax-planning';

interface FinancialsPanelProps {
  financials: FinancialsData;
  dataSource: DataSource;
  xeroFetchedAt: string | null;
  onRefreshXero?: () => Promise<void>;
  onEdit?: () => void;
}

export function FinancialsPanel({
  financials,
  dataSource,
  xeroFetchedAt,
  onRefreshXero,
  onEdit,
}: FinancialsPanelProps) {
  const [refreshing, setRefreshing] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const handleRefresh = async () => {
    if (!onRefreshXero) return;
    setRefreshing(true);
    try {
      await onRefreshXero();
    } finally {
      setRefreshing(false);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  };

  const sourceLabel = dataSource === 'xero'
    ? 'From Xero'
    : dataSource === 'xero_with_adjustments'
      ? 'Xero + Adjustments'
      : 'Manual Entry';

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">Financials</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {sourceLabel}
            </Badge>
            {onEdit && (
              <Button variant="ghost" size="sm" onClick={onEdit}>
                Edit
              </Button>
            )}
            {dataSource !== 'manual' && onRefreshXero && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
              >
                {refreshing ? 'Refreshing...' : 'Refresh'}
              </Button>
            )}
          </div>
        </div>
        {xeroFetchedAt && (
          <p className="text-xs text-muted-foreground">
            Last synced {formatRelativeTime(xeroFetchedAt)}
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Period Coverage (FR-018) */}
        {financials.period_coverage && (
          <div className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            {financials.period_coverage}
          </div>
        )}

        {/* Income */}
        <Section
          title="Income"
          items={[
            { label: 'Revenue', value: financials.income.revenue },
            { label: 'Other Income', value: financials.income.other_income },
          ]}
          total={financials.income.total_income}
          totalLabel="Total Income"
          breakdown={financials.income.breakdown}
          expanded={expandedSections.has('income')}
          onToggle={() => toggleSection('income')}
          positive
        />

        {/* Expenses */}
        <Section
          title="Expenses"
          items={[
            { label: 'Cost of Sales', value: financials.expenses.cost_of_sales },
            { label: 'Operating Expenses', value: financials.expenses.operating_expenses },
          ]}
          total={financials.expenses.total_expenses}
          totalLabel="Total Expenses"
          breakdown={financials.expenses.breakdown}
          expanded={expandedSections.has('expenses')}
          onToggle={() => toggleSection('expenses')}
        />

        {/* Net */}
        <div className="border-t pt-3">
          <div className="flex items-center justify-between font-semibold">
            <span>Net Profit</span>
            <span className="tabular-nums">
              {formatCurrency(financials.income.total_income - financials.expenses.total_expenses)}
            </span>
          </div>
        </div>

        {/* Credits */}
        {(financials.credits.payg_instalments > 0 ||
          financials.credits.payg_withholding > 0 ||
          financials.credits.franking_credits > 0) && (
          <div className="border-t pt-3 space-y-1.5">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Tax Credits
            </p>
            {financials.credits.payg_instalments > 0 && (
              <SummaryRow label="PAYG Instalments" value={financials.credits.payg_instalments} />
            )}
            {financials.credits.payg_withholding > 0 && (
              <SummaryRow label="PAYG Withholding" value={financials.credits.payg_withholding} />
            )}
            {financials.credits.franking_credits > 0 && (
              <SummaryRow label="Franking Credits" value={financials.credits.franking_credits} />
            )}
          </div>
        )}

        {/* Adjustments */}
        {financials.adjustments.length > 0 && (
          <div className="border-t pt-3 space-y-1.5">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Adjustments
            </p>
            {financials.adjustments.map((adj, i) => (
              <SummaryRow
                key={i}
                label={`${adj.description} (${adj.type === 'add_back' ? '+' : '-'})`}
                value={adj.type === 'add_back' ? adj.amount : -adj.amount}
              />
            ))}
          </div>
        )}

        {/* Bank Position */}
        <div className="border-t pt-3 space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Bank Position
            </p>
            {financials.last_reconciliation_date && (
              <span className="text-xs text-muted-foreground">
                Reconciled to {new Date(financials.last_reconciliation_date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}
              </span>
            )}
          </div>
          {financials.total_bank_balance != null ? (
            <>
              {financials.bank_balances?.map((acct, i) => (
                <SummaryRow key={i} label={acct.account_name} value={acct.closing_balance} />
              ))}
              <div className="flex items-center justify-between font-medium">
                <span>Total Bank Balance</span>
                <span className="tabular-nums">{formatCurrency(financials.total_bank_balance)}</span>
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground italic">Bank data not available</p>
          )}
        </div>

        {/* Full Year Projection (Spec 056 - US2) */}
        {financials.projection && (
          <div className="border-t pt-3 space-y-1.5">
            <div className="flex items-center gap-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Projected Full Year
              </p>
              <Badge variant="outline" className="text-xs text-blue-600 border-blue-300">
                Projected ({financials.projection.months_used}mo avg)
              </Badge>
            </div>
            <SummaryRow label="Projected Revenue" value={financials.projection.projected_revenue} />
            <SummaryRow label="Projected Expenses" value={financials.projection.projected_expenses} />
            <div className="flex items-center justify-between font-medium">
              <span>Projected Net Profit</span>
              <span className={cn('tabular-nums', financials.projection.projected_net_profit >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                {formatCurrency(financials.projection.projected_net_profit)}
              </span>
            </div>
          </div>
        )}

        {/* Prior Year Comparison (Spec 056 - US3) */}
        {financials.prior_year_ytd && (
          <div className="border-t pt-3 space-y-1.5">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              vs Same Period Last Year
            </p>
            <p className="text-xs text-muted-foreground">{financials.prior_year_ytd.period_coverage}</p>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Revenue</span>
              <span className="tabular-nums">
                {formatCurrency(financials.prior_year_ytd.revenue)}
                <span className={cn('ml-2 text-xs', financials.prior_year_ytd.changes.revenue_pct >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                  {financials.prior_year_ytd.changes.revenue_pct >= 0 ? '↑' : '↓'}{Math.abs(financials.prior_year_ytd.changes.revenue_pct)}%
                </span>
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Expenses</span>
              <span className="tabular-nums">
                {formatCurrency(financials.prior_year_ytd.total_expenses)}
                <span className={cn('ml-2 text-xs', financials.prior_year_ytd.changes.expenses_pct <= 0 ? 'text-emerald-600' : 'text-red-600')}>
                  {financials.prior_year_ytd.changes.expenses_pct >= 0 ? '↑' : '↓'}{Math.abs(financials.prior_year_ytd.changes.expenses_pct)}%
                </span>
              </span>
            </div>
            <div className="flex items-center justify-between text-sm font-medium">
              <span>Net Profit</span>
              <span className="tabular-nums">
                {formatCurrency(financials.prior_year_ytd.net_profit)}
                <span className={cn('ml-2 text-xs', financials.prior_year_ytd.changes.profit_pct >= 0 ? 'text-emerald-600' : 'text-red-600')}>
                  {financials.prior_year_ytd.changes.profit_pct >= 0 ? '↑' : '↓'}{Math.abs(financials.prior_year_ytd.changes.profit_pct)}%
                </span>
              </span>
            </div>
          </div>
        )}

        {/* Multi-Year Trends (Spec 056 - US4) */}
        {financials.prior_years && financials.prior_years.length > 0 && (
          <div className="border-t pt-3 space-y-1.5">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Year-on-Year Trends
            </p>
            <div className="text-xs space-y-1">
              {financials.prior_years.map((py) => (
                <div key={py.financial_year} className="flex items-center justify-between">
                  <span className="text-muted-foreground">{py.financial_year}</span>
                  <span className="tabular-nums">
                    Rev {formatCurrency(py.revenue)} · Exp {formatCurrency(py.expenses)} · Net {formatCurrency(py.net_profit)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Payroll Summary (Spec 056 - US6) */}
        {financials.payroll_summary && (
          <div className="border-t pt-3 space-y-1.5">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Payroll
            </p>
            <SummaryRow label={`Employees (${financials.payroll_summary.employee_count})`} value={financials.payroll_summary.total_wages_ytd} />
            <SummaryRow label="Superannuation YTD" value={financials.payroll_summary.total_super_ytd} />
            <SummaryRow label="PAYG Withheld YTD" value={financials.payroll_summary.total_tax_withheld_ytd} />
            {financials.payroll_summary.has_owners && (
              <p className="text-xs text-amber-600">Includes owner/director employees</p>
            )}
          </div>
        )}

        {/* Unreconciled Summary (FR-017) */}
        {financials.unreconciled_summary && financials.unreconciled_summary.transaction_count > 0 && (
          <div className="border-t pt-3 space-y-1.5">
            <div className="flex items-center gap-2">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Unreconciled ({financials.unreconciled_summary.quarter})
              </p>
              <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                Provisional
              </Badge>
            </div>
            <SummaryRow label="Income" value={financials.unreconciled_summary.unreconciled_income} />
            <SummaryRow label="Expenses" value={financials.unreconciled_summary.unreconciled_expenses} />
            <SummaryRow label="Est. GST Collected" value={financials.unreconciled_summary.gst_collected_estimate} />
            <SummaryRow label="Est. GST Paid" value={financials.unreconciled_summary.gst_paid_estimate} />
            <p className="text-xs text-muted-foreground">
              {financials.unreconciled_summary.transaction_count} unreconciled transactions
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Section({
  title,
  items,
  total,
  totalLabel,
  breakdown,
  expanded,
  onToggle,
  positive,
}: {
  title: string;
  items: { label: string; value: number }[];
  total: number;
  totalLabel: string;
  breakdown?: { category: string; amount: number }[];
  expanded: boolean;
  onToggle: () => void;
  positive?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </p>
        {breakdown && breakdown.length > 0 && (
          <button
            onClick={onToggle}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {expanded ? 'Hide detail' : 'Show detail'}
          </button>
        )}
      </div>
      {items.map((item) => (
        <SummaryRow key={item.label} label={item.label} value={item.value} />
      ))}
      {expanded && breakdown && breakdown.length > 0 && (
        <div className="ml-4 space-y-1 border-l pl-3">
          {breakdown.map((item, i) => (
            <SummaryRow key={i} label={item.category} value={item.amount} muted />
          ))}
        </div>
      )}
      <div className={cn('flex items-center justify-between font-medium', positive && 'text-emerald-700 dark:text-emerald-400')}>
        <span>{totalLabel}</span>
        <span className="tabular-nums">{formatCurrency(total)}</span>
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  muted,
}: {
  label: string;
  value: number;
  muted?: boolean;
}) {
  return (
    <div className={cn('flex items-center justify-between text-sm', muted && 'text-muted-foreground text-xs')}>
      <span>{label}</span>
      <span className="tabular-nums">{formatCurrency(value)}</span>
    </div>
  );
}
