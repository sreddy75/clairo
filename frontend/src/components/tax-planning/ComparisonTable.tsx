'use client';

import { AlertTriangle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { ReviewerDisagreement } from '@/lib/api/tax-planning';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { Provenance, TaxScenario } from '@/types/tax-planning';

import { ProvenanceBadge } from './ProvenanceBadge';
import { RequiresGroupModelNotice } from './RequiresGroupModelNotice';

interface ComparisonTableProps {
  scenarios: TaxScenario[];
  // Spec 059 FR-013 — per-scenario reviewer disagreements surface as a
  // "Verification flagged" badge next to the scenario title.
  disagreements?: ReviewerDisagreement[];
}

const RISK_STYLES = {
  conservative: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  moderate: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  aggressive: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

export function ComparisonTable({ scenarios, disagreements = [] }: ComparisonTableProps) {
  if (scenarios.length < 2) return null;

  // Sort by net benefit (highest first). Flagged scenarios sort last so the
  // accountant's eye lands on honest comparable rows first.
  const sorted = [...scenarios].sort((a, b) => {
    const aFlagged = a.requires_group_model ? 1 : 0;
    const bFlagged = b.requires_group_model ? 1 : 0;
    if (aFlagged !== bFlagged) return aFlagged - bFlagged;
    const benefitA = a.impact_data?.change?.net_benefit ?? 0;
    const benefitB = b.impact_data?.change?.net_benefit ?? 0;
    return benefitB - benefitA;
  });

  const excludedCount = scenarios.filter((s) => s.requires_group_model).length;
  const bestId = sorted.find((s) => !s.requires_group_model)?.id;

  // Group disagreements by scenario id for O(1) lookup per row.
  const disagreementsByScenario = new Map<string, ReviewerDisagreement[]>();
  for (const d of disagreements) {
    const existing = disagreementsByScenario.get(d.scenario_id) ?? [];
    existing.push(d);
    disagreementsByScenario.set(d.scenario_id, existing);
  }

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
              const isFlagged = Boolean(scenario.requires_group_model);
              return (
                <TableRow
                  key={scenario.id}
                  className={cn(
                    isBest && 'bg-emerald-50/50 dark:bg-emerald-950/20',
                    isFlagged && 'opacity-60',
                  )}
                >
                  <TableCell className="font-medium text-sm">
                    {scenario.title}
                    {isBest && (
                      <span className="ml-1.5 text-[10px] text-emerald-600 dark:text-emerald-400 font-normal">
                        Best
                      </span>
                    )}
                    {isFlagged && (
                      <RequiresGroupModelNotice className="ml-1.5" compact />
                    )}
                    {(() => {
                      const scenarioDisagreements =
                        disagreementsByScenario.get(scenario.id) ?? [];
                      const first = scenarioDisagreements[0];
                      if (!first) return null;
                      return (
                        <span
                          className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] text-amber-700 dark:text-amber-300"
                          title={scenarioDisagreements
                            .map(
                              (d) =>
                                `${d.field_path} differs by $${d.delta.toLocaleString()}`,
                            )
                            .join('\n')}
                        >
                          <AlertTriangle className="h-3 w-3" />
                          Verification flagged: {first.field_path.split('.').pop()}
                          {' '}differs by ${first.delta.toLocaleString()}
                        </span>
                      );
                    })()}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm">
                    <span className="inline-flex items-center gap-1.5">
                      {formatCurrency(change?.taxable_income_change ?? 0)}
                      <ProvenanceBadge
                        provenance={
                          scenario.source_tags?.[
                            'impact_data.change.taxable_income_change'
                          ] as Provenance | undefined
                        }
                      />
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm text-emerald-600 dark:text-emerald-400">
                    <span className="inline-flex items-center gap-1.5">
                      {formatCurrency(change?.tax_saving ?? 0)}
                      <ProvenanceBadge
                        provenance={
                          scenario.source_tags?.[
                            'impact_data.change.tax_saving'
                          ] as Provenance | undefined
                        }
                      />
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm">
                    {scenario.cash_flow_impact != null ? (
                      <span className="inline-flex items-center gap-1.5">
                        {formatCurrency(scenario.cash_flow_impact)}
                        <ProvenanceBadge
                          provenance={
                            scenario.source_tags?.['cash_flow_impact'] as
                              | Provenance
                              | undefined
                          }
                        />
                      </span>
                    ) : (
                      '-'
                    )}
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
      {excludedCount > 0 && (
        <p className="text-[11px] text-stone-600">
          {excludedCount} scenario{excludedCount === 1 ? '' : 's'} excluded from
          combined total — requires group tax model.
        </p>
      )}
      <p className="text-[11px] text-muted-foreground/70">
        All figures are estimates. Not formal tax advice.
      </p>
    </div>
  );
}
