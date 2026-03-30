'use client';

import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { TaxScenario } from '@/types/tax-planning';

interface ComparisonTableProps {
  scenarios: TaxScenario[];
}

const RISK_STYLES = {
  conservative: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  moderate: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  aggressive: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

export function ComparisonTable({ scenarios }: ComparisonTableProps) {
  if (scenarios.length < 2) return null;

  // Sort by net benefit (highest first)
  const sorted = [...scenarios].sort((a, b) => {
    const benefitA = a.impact_data?.change?.net_benefit ?? 0;
    const benefitB = b.impact_data?.change?.net_benefit ?? 0;
    return benefitB - benefitA;
  });

  const bestId = sorted[0]?.id;

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold">Scenario Comparison</h4>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[200px]">Scenario</TableHead>
              <TableHead className="text-right">Income Change</TableHead>
              <TableHead className="text-right">Tax Saving</TableHead>
              <TableHead className="text-right">Cash Flow</TableHead>
              <TableHead className="text-center">Risk</TableHead>
              <TableHead className="text-right">Net Benefit</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((scenario) => {
              const change = scenario.impact_data?.change;
              const isBest = scenario.id === bestId;
              return (
                <TableRow
                  key={scenario.id}
                  className={cn(isBest && 'bg-emerald-50/50 dark:bg-emerald-950/20')}
                >
                  <TableCell className="font-medium text-sm">
                    {scenario.title}
                    {isBest && (
                      <span className="ml-1.5 text-[10px] text-emerald-600 dark:text-emerald-400 font-normal">
                        Best
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm">
                    {formatCurrency(change?.taxable_income_change ?? 0)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm text-emerald-600 dark:text-emerald-400">
                    {formatCurrency(change?.tax_saving ?? 0)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm">
                    {scenario.cash_flow_impact != null
                      ? formatCurrency(scenario.cash_flow_impact)
                      : '-'}
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge className={cn('text-xs', RISK_STYLES[scenario.risk_rating])}>
                      {scenario.risk_rating}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm font-medium">
                    {formatCurrency(change?.net_benefit ?? 0)}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <p className="text-[11px] text-muted-foreground/70">
        All figures are estimates. Not formal tax advice.
      </p>
    </div>
  );
}
