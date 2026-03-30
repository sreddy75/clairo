'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatCurrency, formatPercentage } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { EntityType, TaxPosition } from '@/types/tax-planning';

interface TaxPositionCardProps {
  taxPosition: TaxPosition;
  entityType: EntityType;
}

const METHOD_LABELS: Record<string, string> = {
  company_small_business: 'Company — Small Business 25%',
  company_standard: 'Company — Standard 30%',
  individual_marginal: 'Individual — Marginal Rates',
  trust_undistributed: 'Trust — 47% Undistributed',
  partnership_single_partner: 'Partnership — Individual Rates',
};

export function TaxPositionCard({ taxPosition, entityType }: TaxPositionCardProps) {
  const isRefundable = taxPosition.net_position < 0;
  const methodLabel = METHOD_LABELS[taxPosition.calculation_method] || taxPosition.calculation_method;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold">Tax Position</CardTitle>
          <Badge variant="outline" className="text-xs">
            {methodLabel}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Net Position — hero number */}
        <div
          className={cn(
            'rounded-lg p-4 text-center',
            isRefundable
              ? 'bg-emerald-50 dark:bg-emerald-950/30'
              : 'bg-amber-50 dark:bg-amber-950/30',
          )}
        >
          <p className="text-sm text-muted-foreground">
            {isRefundable ? 'Estimated Refund' : 'Estimated Tax Payable'}
          </p>
          <p
            className={cn(
              'text-3xl font-bold',
              isRefundable
                ? 'text-emerald-700 dark:text-emerald-400'
                : 'text-amber-700 dark:text-amber-400',
            )}
          >
            {formatCurrency(Math.abs(taxPosition.net_position))}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Effective rate: {formatPercentage(taxPosition.effective_rate_pct)}
          </p>
        </div>

        {/* Calculation breakdown */}
        <div className="space-y-2 text-sm">
          <Row label="Taxable Income" value={taxPosition.taxable_income} />
          <Row label="Gross Tax" value={taxPosition.gross_tax} />

          {/* Offsets (individual only) */}
          {taxPosition.offsets?.lito && taxPosition.offsets.lito > 0 && (
            <Row
              label="Low Income Tax Offset (LITO)"
              value={-taxPosition.offsets.lito}
              className="text-emerald-600 dark:text-emerald-400"
            />
          )}

          {/* Medicare Levy (individual/partnership) */}
          {entityType !== 'company' && entityType !== 'trust' && taxPosition.medicare_levy > 0 && (
            <Row label="Medicare Levy (2%)" value={taxPosition.medicare_levy} />
          )}

          {/* HELP repayment */}
          {taxPosition.help_repayment > 0 && (
            <Row label="HELP Repayment" value={taxPosition.help_repayment} />
          )}

          <div className="border-t pt-2">
            <Row label="Total Tax Payable" value={taxPosition.total_tax_payable} bold />
          </div>

          {/* Credits */}
          {taxPosition.credits_applied.total > 0 && (
            <>
              <p className="pt-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Credits Applied
              </p>
              {taxPosition.credits_applied.payg_instalments > 0 && (
                <Row
                  label="PAYG Instalments"
                  value={-taxPosition.credits_applied.payg_instalments}
                  className="text-emerald-600 dark:text-emerald-400"
                />
              )}
              {taxPosition.credits_applied.payg_withholding > 0 && (
                <Row
                  label="PAYG Withholding"
                  value={-taxPosition.credits_applied.payg_withholding}
                  className="text-emerald-600 dark:text-emerald-400"
                />
              )}
              {taxPosition.credits_applied.franking_credits > 0 && (
                <Row
                  label="Franking Credits"
                  value={-taxPosition.credits_applied.franking_credits}
                  className="text-emerald-600 dark:text-emerald-400"
                />
              )}
            </>
          )}
        </div>

        {/* Disclaimer */}
        <p className="text-[11px] leading-tight text-muted-foreground/70">
          This is an estimate only and does not constitute formal tax advice.
          Please consult your tax professional for specific advice.
        </p>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  value,
  bold,
  className,
}: {
  label: string;
  value: number;
  bold?: boolean;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center justify-between', className)}>
      <span className={cn(bold && 'font-semibold')}>{label}</span>
      <span className={cn('tabular-nums', bold && 'font-semibold')}>
        {formatCurrency(value)}
      </span>
    </div>
  );
}
