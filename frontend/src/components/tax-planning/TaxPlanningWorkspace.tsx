'use client';

import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ComparisonTable } from './ComparisonTable';
import { FinancialsPanel } from './FinancialsPanel';
import { ManualEntryForm } from './ManualEntryForm';
import { ScenarioCard } from './ScenarioCard';
import { ScenarioChat } from './ScenarioChat';
import { TaxPositionCard } from './TaxPositionCard';
import {
  createTaxPlan,
  deleteScenario,
  exportPlanPdf,
  getTaxPlan,
  listTaxPlans,
  pullXeroFinancials,
  saveManualFinancials,
  updateTaxPlan,
} from '@/lib/api/tax-planning';
import type {
  EntityType,
  FinancialsInput,
  TaxPlan,
  TaxScenario,
} from '@/types/tax-planning';

interface TaxPlanningWorkspaceProps {
  connectionId: string;
  clientName: string;
}

const CURRENT_FY = '2025-26';

const ENTITY_TYPE_LABELS: Record<EntityType, string> = {
  company: 'Company',
  individual: 'Individual / Sole Trader',
  trust: 'Trust',
  partnership: 'Partnership',
};

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300',
  in_progress: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  finalised: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
};

export function TaxPlanningWorkspace({
  connectionId,
  clientName,
}: TaxPlanningWorkspaceProps) {
  const { getToken } = useAuth();
  const [plan, setPlan] = useState<TaxPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [selectedEntityType, setSelectedEntityType] = useState<EntityType>('company');
  const [showManualEntry, setShowManualEntry] = useState(false);

  // Load existing plan for this connection + FY
  const loadPlan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) return;

      // Check if plan exists for this connection + FY
      try {
        const response = await listTaxPlans(token, {
          financial_year: CURRENT_FY,
        });

        const existingPlan = response.items.find(
          (p) => p.xero_connection_id === connectionId,
        );

        if (existingPlan) {
          const fullPlan = await getTaxPlan(token, existingPlan.id);
          setPlan(fullPlan);
        }
      } catch (listErr) {
        // If listing fails (e.g., no plans yet), that's OK — show creation UI
        console.warn('Failed to list tax plans:', listErr);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load tax plan');
    } finally {
      setLoading(false);
    }
  }, [connectionId, getToken]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  // Create new plan
  const handleCreatePlan = async () => {
    setCreating(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) return;

      const newPlan = await createTaxPlan(token, {
        xero_connection_id: connectionId,
        financial_year: CURRENT_FY,
        entity_type: selectedEntityType,
        data_source: 'xero',
        replace_existing: !!plan,
      });

      // Auto-pull financials from Xero
      if (connectionId) {
        try {
          const result = await pullXeroFinancials(token, newPlan.id);
          const updated = await getTaxPlan(token, newPlan.id);
          setPlan(updated);
        } catch {
          // Plan created but Xero pull failed — show plan anyway
          const updated = await getTaxPlan(token, newPlan.id);
          setPlan(updated);
          setError('Plan created but Xero data pull failed. You can enter data manually.');
        }
      } else {
        setPlan(newPlan);
        setShowManualEntry(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create tax plan');
    } finally {
      setCreating(false);
    }
  };

  // Refresh Xero data
  const handleRefreshXero = async () => {
    if (!plan) return;
    const token = await getToken();
    if (!token) return;
    await pullXeroFinancials(token, plan.id, true);
    const updated = await getTaxPlan(token, plan.id);
    setPlan(updated);
  };

  // Save manual financials
  const handleSaveManual = async (data: FinancialsInput) => {
    if (!plan) return;
    const token = await getToken();
    if (!token) return;
    await saveManualFinancials(token, plan.id, data);
    const updated = await getTaxPlan(token, plan.id);
    setPlan(updated);
    setShowManualEntry(false);
  };

  // Status update
  const handleStatusChange = async (newStatus: 'in_progress' | 'finalised') => {
    if (!plan) return;
    const token = await getToken();
    if (!token) return;
    const updated = await updateTaxPlan(token, plan.id, { status: newStatus });
    setPlan({ ...plan, ...updated });
  };

  // Export PDF
  const handleExport = async () => {
    if (!plan) return;
    const token = await getToken();
    if (!token) return;
    try {
      const blob = await exportPlanPdf(token, plan.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tax-plan-${clientName.toLowerCase().replace(/\s+/g, '-')}-${plan.financial_year}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed');
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="text-sm text-muted-foreground">Loading tax plan...</div>
      </div>
    );
  }

  // No plan exists — show creation UI
  if (!plan) {
    return (
      <div className="mx-auto max-w-lg py-12">
        <Card>
          <CardContent className="space-y-6 p-6">
            <div className="text-center">
              <h3 className="text-lg font-semibold">Start Tax Plan</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Create a tax plan for {clientName} — FY {CURRENT_FY}
              </p>
            </div>

            {error && (
              <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">Entity Type</label>
              <Select
                value={selectedEntityType}
                onValueChange={(v) => setSelectedEntityType(v as EntityType)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.entries(ENTITY_TYPE_LABELS) as [EntityType, string][]).map(
                    ([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ),
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Data Source</label>
              <p className="text-sm text-muted-foreground">
                {connectionId
                  ? 'Xero P&L will be pulled automatically'
                  : 'No Xero connection — enter financials manually'}
              </p>
              {!connectionId && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Connect Xero for automatic data import
                </p>
              )}
            </div>

            <Button
              className="w-full"
              onClick={handleCreatePlan}
              disabled={creating}
            >
              {creating ? 'Creating...' : 'Create Tax Plan'}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Plan exists — show workspace
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">
            Tax Plan — {clientName}
          </h3>
          <Badge className={STATUS_COLORS[plan.status] || ''}>
            {plan.status === 'in_progress'
              ? 'In Progress'
              : plan.status.charAt(0).toUpperCase() + plan.status.slice(1)}
          </Badge>
          <Badge variant="outline">
            {ENTITY_TYPE_LABELS[plan.entity_type]} • FY {plan.financial_year}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {plan.status === 'in_progress' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleStatusChange('finalised')}
            >
              Finalise
            </Button>
          )}
          {plan.status === 'finalised' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleStatusChange('in_progress')}
            >
              Reopen
            </Button>
          )}
          {plan.tax_position && (
            <Button variant="outline" size="sm" onClick={handleExport}>
              Export PDF
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Row 1: Financials + Tax Position side by side */}
      {plan.financials_data && !showManualEntry ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <FinancialsPanel
              financials={plan.financials_data}
              dataSource={plan.data_source}
              xeroFetchedAt={plan.xero_report_fetched_at}
              onRefreshXero={plan.xero_connection_id ? handleRefreshXero : undefined}
              onEdit={() => setShowManualEntry(true)}
            />
          </div>
          {plan.tax_position && (
            <div>
              <TaxPositionCard
                taxPosition={plan.tax_position}
                entityType={plan.entity_type}
              />
            </div>
          )}
        </div>
      ) : (
        <ManualEntryForm
          onSubmit={handleSaveManual}
          onCancel={plan.financials_data ? () => setShowManualEntry(false) : undefined}
          initialValues={
            plan.financials_data
              ? {
                  revenue: plan.financials_data.income.revenue,
                  other_income: plan.financials_data.income.other_income,
                  cost_of_sales: plan.financials_data.expenses.cost_of_sales,
                  operating_expenses: plan.financials_data.expenses.operating_expenses,
                  payg_instalments: plan.financials_data.credits.payg_instalments,
                  payg_withholding: plan.financials_data.credits.payg_withholding,
                  franking_credits: plan.financials_data.credits.franking_credits,
                  turnover: plan.financials_data.turnover,
                }
              : undefined
          }
        />
      )}

      {/* Row 2: AI Chat — full width */}
      <ScenarioChat
        planId={plan.id}
        disabled={!plan.tax_position}
        onScenarioCreated={async () => {
          // Reload full plan to get properly formatted scenarios
          try {
            const token = await getToken();
            if (!token) return;
            const updated = await getTaxPlan(token, plan.id);
            setPlan(updated);
          } catch {
            // Increment count as fallback
            setPlan((prev) => prev ? { ...prev, scenario_count: (prev.scenario_count || 0) + 1 } : prev);
          }
        }}
      />

      {/* Row 3: Scenarios */}
      {plan.scenarios && plan.scenarios.length > 0 && (
        <div className="space-y-4">
          {/* Comparison table first (if 2+) */}
          {plan.scenarios.length >= 2 && (
            <ComparisonTable scenarios={plan.scenarios} />
          )}

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {plan.scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.id}
                scenario={scenario}
                onDelete={async (scenarioId) => {
                  try {
                    const token = await getToken();
                    if (!token) return;
                    await deleteScenario(token, plan.id, scenarioId);
                  } catch (e) {
                    console.warn('Delete scenario failed:', e);
                  }
                  try {
                    const token = await getToken();
                    if (!token) return;
                    const updated = await getTaxPlan(token, plan.id);
                    setPlan(updated);
                  } catch {
                    setPlan((prev) => {
                      if (!prev) return prev;
                      return {
                        ...prev,
                        scenarios: prev.scenarios.filter((s) => s.id !== scenarioId),
                        scenario_count: Math.max(0, (prev.scenario_count || 0) - 1),
                      };
                    });
                  }
                }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
