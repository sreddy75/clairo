'use client';

import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatCurrency } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { TaxScenario } from '@/types/tax-planning';

interface ScenarioCardProps {
  scenario: TaxScenario;
  onDelete?: (scenarioId: string) => void;
}

const RISK_STYLES = {
  conservative: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
  moderate: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  aggressive: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

export function ScenarioCard({ scenario, onDelete }: ScenarioCardProps) {
  const [expanded, setExpanded] = useState(false);
  const change = scenario.impact_data?.change;
  const taxSaving = change?.tax_saving ?? 0;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <h4 className="font-medium text-sm">{scenario.title}</h4>
            <div className="flex items-center gap-2 mt-1">
              <Badge className={cn('text-xs', RISK_STYLES[scenario.risk_rating])}>
                {scenario.risk_rating}
              </Badge>
              {taxSaving > 0 && (
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                  Save {formatCurrency(taxSaving)}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              {expanded ? 'Less' : 'More'}
            </button>
            {onDelete && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-muted-foreground hover:text-red-600"
                onClick={() => onDelete(scenario.id)}
              >
                ×
              </Button>
            )}
          </div>
        </div>

        {/* Impact summary */}
        {scenario.impact_data && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <ImpactCell
              label="Income Change"
              value={change?.taxable_income_change}
            />
            <ImpactCell
              label="Tax Saving"
              value={change?.tax_saving}
              positive
            />
            <ImpactCell
              label="Cash Flow"
              value={scenario.cash_flow_impact}
            />
          </div>
        )}

        {/* Expanded details */}
        {expanded && (
          <div className="space-y-3 pt-2 border-t">
            <p className="text-sm text-muted-foreground">{scenario.description}</p>

            {scenario.assumptions?.items && scenario.assumptions.items.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1">
                  Assumptions
                </p>
                <ul className="text-xs space-y-0.5 text-muted-foreground">
                  {scenario.assumptions.items.map((item, i) => (
                    <li key={i}>• {item}</li>
                  ))}
                </ul>
              </div>
            )}

            {scenario.compliance_notes && (
              <div className="rounded-md bg-amber-50 dark:bg-amber-950/30 p-3">
                <p className="text-xs font-medium text-amber-700 dark:text-amber-400 mb-1">
                  Compliance Notes
                </p>
                <p className="text-xs text-amber-600 dark:text-amber-300">
                  {scenario.compliance_notes}
                </p>
              </div>
            )}

            {/* Before/After breakdown */}
            {scenario.impact_data?.before && scenario.impact_data?.after && (
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="font-medium mb-1">Before</p>
                  <p>Taxable Income: {formatCurrency(scenario.impact_data.before.taxable_income)}</p>
                  <p>Tax Payable: {formatCurrency(scenario.impact_data.before.tax_payable)}</p>
                </div>
                <div>
                  <p className="font-medium mb-1">After</p>
                  <p>Taxable Income: {formatCurrency(scenario.impact_data.after.taxable_income)}</p>
                  <p>Tax Payable: {formatCurrency(scenario.impact_data.after.tax_payable)}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ImpactCell({
  label,
  value,
  positive,
}: {
  label: string;
  value?: number | null;
  positive?: boolean;
}) {
  if (value == null) return null;
  const isPositive = value > 0;
  return (
    <div>
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p
        className={cn(
          'text-sm font-medium tabular-nums',
          positive && isPositive && 'text-emerald-600 dark:text-emerald-400',
          !positive && value < 0 && 'text-red-600 dark:text-red-400',
        )}
      >
        {formatCurrency(value)}
      </p>
    </div>
  );
}
