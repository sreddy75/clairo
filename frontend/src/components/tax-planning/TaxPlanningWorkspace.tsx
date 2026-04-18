'use client';

import { useAuth } from '@clerk/nextjs';
import { Loader2 } from 'lucide-react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { AIDisclaimer } from '@/components/ui/AIDisclaimer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  type AnalysisResponse,
  approveAnalysis,
  createTaxPlan,
  deleteScenario,
  exportPlanPdf,
  generateAnalysis,
  getAnalysis,
  getTaxPlan,
  listTaxPlans,
  pullXeroFinancials,
  saveManualFinancials,
  shareAnalysis,
  updateTaxPlan,
} from '@/lib/api/tax-planning';
import { apiClient } from '@/lib/api-client';
import type {
  EntityType,
  FinancialsInput,
  TaxPlan,
} from '@/types/tax-planning';

import { AsAtDatePicker } from './AsAtDatePicker';
import { ComparisonTable } from './ComparisonTable';
import { FinancialsPanel } from './FinancialsPanel';
import { ManualEntryForm } from './ManualEntryForm';
import { PayrollSyncBanner } from './PayrollSyncBanner';
import { ReviewerWarningBanner } from './ReviewerWarningBanner';
import { ScenarioCard } from './ScenarioCard';
import { ScenarioChat } from './ScenarioChat';
import { TaxPositionCard } from './TaxPositionCard';

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
  const searchParams = useSearchParams();
  const router = useRouter();
  const [plan, setPlan] = useState<TaxPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [selectedEntityType, setSelectedEntityType] = useState<EntityType>('company');
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [showCreateNew, setShowCreateNew] = useState(false);
  const [xeroAuthNeeded, setXeroAuthNeeded] = useState(false);
  const [pullingXero, setPullingXero] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generatingStage, setGeneratingStage] = useState(0);
  const [showAnalysisDetail, setShowAnalysisDetail] = useState(false);
  const autoRefreshDone = useRef(false);

  // Load existing analysis for this plan
  const loadAnalysis = useCallback(async (planId: string) => {
    try {
      const token = await getToken();
      if (!token) return;
      const data = await getAnalysis(token, planId);
      setAnalysis(data);
    } catch {
      // No analysis yet — that's fine
      setAnalysis(null);
    }
  }, [getToken]);

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
          try {
            const fullPlan = await getTaxPlan(token, existingPlan.id);
            setPlan(fullPlan);
            // Load analysis if exists
            loadAnalysis(existingPlan.id).catch(() => {});
          } catch (planErr) {
            // GET plan failed (e.g., Xero token expired during auto-refresh)
            // Still show the plan with whatever data the list had
            console.warn('Failed to load full plan, using list data:', planErr);
            setPlan(existingPlan as unknown as TaxPlan);
          }
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
  }, [connectionId, getToken, loadAnalysis]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  // Auto-pull financials after returning from Xero re-auth
  useEffect(() => {
    if (autoRefreshDone.current) return;
    if (searchParams.get('reauth') !== 'success') return;
    if (!plan) return;

    autoRefreshDone.current = true;

    // Clean up the query param from the URL
    const url = new URL(window.location.href);
    url.searchParams.delete('reauth');
    router.replace(url.pathname + url.search, { scroll: false });

    // The backend queues a background refresh on reconnection.
    // Pull here too as a fallback (the API is idempotent).
    (async () => {
      setPullingXero(true);
      setXeroAuthNeeded(false);
      setError(null);
      try {
        const token = await getToken();
        if (!token) return;
        await pullXeroFinancials(token, plan.id, true);
        const updated = await getTaxPlan(token, plan.id);
        setPlan(updated);
      } catch {
        setError('Failed to pull financial data after reconnecting. Try the Refresh button.');
      } finally {
        setPullingXero(false);
      }
    })();
  }, [searchParams, plan, getToken, router]);

  // Initiate Xero re-auth inline (no tab switch)
  const handleReconnectXero = async () => {
    setReconnecting(true);
    try {
      const token = await getToken();
      if (!token) return;

      const callbackUrl = `${window.location.origin}/settings/integrations/xero/callback`;

      const response = await apiClient.post('/api/v1/integrations/xero/connect', {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ redirect_uri: callbackUrl }),
      });

      if (!response.ok) {
        throw new Error('Failed to initiate Xero re-authorisation');
      }

      const data = await response.json();

      // Store OAuth state for validation + return destination
      sessionStorage.setItem('xero_oauth_state', data.state);
      sessionStorage.setItem(
        'xero_reauth_return_to',
        `${window.location.pathname}?reauth=success`,
      );

      // Redirect to Xero consent screen
      window.location.href = data.auth_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start Xero re-authorisation');
      setReconnecting(false);
    }
  };

  // Generate tax plan analysis via multi-agent pipeline
  const handleGenerateAnalysis = async () => {
    if (!plan) return;
    setGenerating(true);
    setGeneratingStage(0);
    setError(null);
    try {
      const token = await getToken();
      if (!token) return;
      const result = await generateAnalysis(token, plan.id);

      // Poll for progress via SSE
      const { analysisProgressStream } = await import('@/lib/api/tax-planning');
      for await (const event of analysisProgressStream(token, plan.id, result.task_id)) {
        if (event.type === 'progress' && event.stage_number) {
          setGeneratingStage(event.stage_number);
        }
        if (event.type === 'complete') {
          setGeneratingStage(5);
          await loadAnalysis(plan.id);
          break;
        }
        if (event.type === 'error') {
          setError(event.message || 'Analysis failed');
          // Still try to load partial results
          await loadAnalysis(plan.id);
          break;
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate analysis');
    } finally {
      setGenerating(false);
    }
  };

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
        replace_existing: !!plan || showCreateNew,
      });

      setShowCreateNew(false);

      // Auto-pull financials from Xero
      if (connectionId) {
        try {
          await pullXeroFinancials(token, newPlan.id);
          const updated = await getTaxPlan(token, newPlan.id);
          setPlan(updated);
        } catch {
          // Plan created but Xero pull failed — show plan with reauth prompt
          const updated = await getTaxPlan(token, newPlan.id);
          setPlan(updated);
          setXeroAuthNeeded(true);
        }
      } else {
        setPlan(newPlan);
        setShowManualEntry(true);
      }
    } catch (e: unknown) {
      const apiErr = e as { status?: number };
      if (apiErr.status === 409) {
        // Plan already exists — reload to show it
        setError(null);
        await loadPlan();
      } else {
        setError(e instanceof Error ? e.message : 'Failed to create tax plan');
      }
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

  // No plan exists or user wants to start fresh — show creation UI
  if (!plan || showCreateNew) {
    return (
      <div className="mx-auto max-w-lg py-12">
        <Card>
          <CardContent className="space-y-6 p-6">
            <div className="text-center">
              <h3 className="text-lg font-semibold">
                {showCreateNew ? 'New Tax Plan' : 'Start Tax Plan'}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                {showCreateNew
                  ? `Start a fresh tax plan for ${clientName} — FY ${CURRENT_FY}. The existing plan will be replaced.`
                  : `Create a tax plan for ${clientName} — FY ${CURRENT_FY}`}
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
              {creating ? 'Creating...' : showCreateNew ? 'Replace & Create New Plan' : 'Create Tax Plan'}
            </Button>
            {showCreateNew && (
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => setShowCreateNew(false)}
              >
                Cancel
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Plan exists — show workspace
  const scenarioCreatedHandler = async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const updated = await getTaxPlan(token, plan.id);
      setPlan(updated);
    } catch {
      setPlan((prev) => prev ? { ...prev, scenario_count: (prev.scenario_count || 0) + 1 } : prev);
    }
  };

  const scenarioDeleteHandler = async (scenarioId: string) => {
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
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      {/* Header — fixed, never scrolls */}
      <div className="shrink-0 space-y-3 pb-3">
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCreateNew(true)}
            >
              New Plan
            </Button>
          </div>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Xero reauth banner */}
        {(plan.xero_connection_status === 'needs_reauth' || xeroAuthNeeded) && (
          <div className="rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                  Xero connection needs re-authorisation
                </p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                  {plan.financials_data
                    ? `Reconnect to pull the latest financial data. Showing data from ${
                        plan.xero_report_fetched_at
                          ? new Date(plan.xero_report_fetched_at).toLocaleDateString()
                          : 'a previous session'
                      }.`
                    : 'Reconnect Xero to pull financial data into this plan.'}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="border-amber-300 text-amber-800 hover:bg-amber-100 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-900"
                onClick={handleReconnectXero}
                disabled={reconnecting}
              >
                {reconnecting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                    Connecting...
                  </>
                ) : (
                  'Reconnect Xero'
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Stale data banner */}
        {plan.data_stale && !xeroAuthNeeded && plan.xero_connection_status !== 'needs_reauth' && (
          <div className="rounded-md border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                  Newer financial data available
                </p>
                <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
                  Xero data has been synced since this plan was last updated.
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="border-blue-300 text-blue-800 hover:bg-blue-100 dark:border-blue-700 dark:text-blue-200 dark:hover:bg-blue-900"
                onClick={async () => {
                  try {
                    const token = await getToken();
                    if (!token) return;
                    await pullXeroFinancials(token, plan.id, true);
                    const updated = await getTaxPlan(token, plan.id);
                    setPlan(updated);
                  } catch {
                    setXeroAuthNeeded(true);
                  }
                }}
              >
                Refresh from Xero
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Pulling financials from Xero after re-auth */}
      {pullingXero && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto" />
            <p className="text-sm font-medium">Pulling financial data from Xero...</p>
            <p className="text-xs text-muted-foreground">This may take a few seconds</p>
          </div>
        </div>
      )}

      {/* No financials + needs reauth — clear empty state instead of misleading $0 form */}
      {!pullingXero && !plan.financials_data && !showManualEntry &&
        (plan.xero_connection_status === 'needs_reauth' || xeroAuthNeeded) && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-4 max-w-sm">
            <div className="w-12 h-12 rounded-full bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center mx-auto">
              <svg className="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-medium">Xero connection expired</p>
              <p className="text-xs text-muted-foreground mt-1">
                Re-authorise your Xero connection to pull financial data into this plan.
                You&apos;ll be redirected back here automatically.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Button
                onClick={handleReconnectXero}
                disabled={reconnecting}
              >
                {reconnecting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
                    Connecting...
                  </>
                ) : (
                  'Reconnect Xero'
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowManualEntry(true)}
              >
                Enter financials manually instead
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Full-width workflow tabs — fills remaining viewport height */}
      {!pullingXero && plan.financials_data && !showManualEntry ? (
        <Tabs
          defaultValue="position"
          className="flex-1 min-h-0 flex flex-col"
        >
          {/* Workflow step tabs with visual cues */}
          <TabsList className="shrink-0 w-full justify-start gap-0 bg-muted/50 p-1 rounded-lg">
            <TabsTrigger value="position" className="gap-1.5 data-[state=active]:bg-background">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] font-bold">1</span>
              Position
            </TabsTrigger>
            <TabsTrigger value="strategies" className="gap-1.5 data-[state=active]:bg-background">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] font-bold">2</span>
              Explore Strategies
            </TabsTrigger>
            <TabsTrigger value="scenarios" className="gap-1.5 data-[state=active]:bg-background">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] font-bold">3</span>
              Scenarios{plan.scenarios && plan.scenarios.length > 0
                ? ` (${plan.scenarios.length})`
                : ''}
            </TabsTrigger>
            <TabsTrigger value="analysis" className="gap-1.5 data-[state=active]:bg-background">
              <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/10 text-primary text-[10px] font-bold">4</span>
              Analysis{analysis ? ` ✓` : ''}
            </TabsTrigger>
          </TabsList>

          {/* Step 1: Review current tax position & financials */}
          <TabsContent
            value="position"
            className="flex-1 overflow-y-auto mt-4 space-y-4"
          >
            {plan.xero_connection_id && (
              <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground">
                  Projection basis — BAS quarter ends give a known-clean
                  checkpoint.
                </div>
                <AsAtDatePicker
                  planId={plan.id}
                  asAtDate={plan.as_at_date ?? null}
                  reconDate={
                    plan.financials_data?.last_reconciliation_date ?? null
                  }
                  financialYear={plan.financial_year}
                  onRefreshed={loadPlan}
                />
              </div>
            )}
            <PayrollSyncBanner
              status={plan.payroll_sync_status}
              onPoll={loadPlan}
            />
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {plan.tax_position && (
                <TaxPositionCard
                  taxPosition={plan.tax_position}
                  entityType={plan.entity_type}
                  projectionMetadata={plan.financials_data?.projection_metadata}
                />
              )}
              <div className="lg:col-span-2">
                <FinancialsPanel
                  financials={plan.financials_data}
                  dataSource={plan.data_source}
                  xeroFetchedAt={plan.xero_report_fetched_at}
                  onRefreshXero={plan.xero_connection_id ? handleRefreshXero : undefined}
                  onEdit={() => setShowManualEntry(true)}
                  payrollStatus={plan.payroll_sync_status ?? null}
                />
              </div>
            </div>
          </TabsContent>

          {/* Step 2: Chat with AI to explore tax strategies */}
          <TabsContent
            value="strategies"
            className="flex-1 min-h-0 mt-4"
          >
            <ScenarioChat
              planId={plan.id}
              disabled={!plan.tax_position}
              onScenarioCreated={scenarioCreatedHandler}
              className="h-full"
            />
          </TabsContent>

          {/* Step 3: Compare and review scenarios */}
          <TabsContent
            value="scenarios"
            className="flex-1 overflow-y-auto space-y-4 mt-4"
          >
            {analysis?.review_result && (
              <ReviewerWarningBanner
                numbersVerified={analysis.review_result.numbers_verified ?? true}
                disagreements={analysis.review_result.disagreements ?? []}
              />
            )}
            {plan.scenarios && plan.scenarios.length >= 2 && (
              <div className="overflow-x-auto">
                <ComparisonTable
                  planId={plan.id}
                  scenarios={plan.scenarios}
                  disagreements={analysis?.review_result?.disagreements ?? []}
                />
              </div>
            )}
            {plan.scenarios && plan.scenarios.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {plan.scenarios.map((scenario) => (
                  <ScenarioCard
                    key={scenario.id}
                    scenario={scenario}
                    onDelete={scenarioDeleteHandler}
                  />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center py-16">
                <p className="text-sm text-muted-foreground text-center">
                  No scenarios yet.
                  <br />
                  <span className="text-xs">
                    Go to &quot;Explore Strategies&quot; to model tax scenarios with AI.
                  </span>
                </p>
              </div>
            )}
          </TabsContent>

          {/* Step 4: AI-generated comprehensive analysis */}
          <TabsContent
            value="analysis"
            className="flex-1 overflow-y-auto space-y-4 mt-4"
          >
            <AIDisclaimer />
            {!analysis && !generating && (
              <div className="flex flex-col items-center justify-center py-16 space-y-4">
                <div className="text-center">
                  <h3 className="text-lg font-semibold">Generate Comprehensive Tax Plan</h3>
                  <p className="text-sm text-muted-foreground mt-1 max-w-md">
                    Our AI analyses your client&apos;s position, evaluates 15+ tax strategies,
                    models the best options, and produces a ready-to-use brief.
                  </p>
                </div>
                <Button
                  onClick={handleGenerateAnalysis}
                  disabled={!plan.tax_position}
                  size="lg"
                >
                  Generate Tax Plan
                </Button>
                {!plan.tax_position && (
                  <p className="text-xs text-muted-foreground">
                    Load financials first to enable analysis.
                  </p>
                )}
              </div>
            )}

            {generating && (
              <GeneratingProgress stage={generatingStage} />
            )}

            {analysis && !generating && (
              <div className="space-y-4">
                {/* Summary card — click to see full analysis */}
                <Card
                  className="cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => setShowAnalysisDetail(true)}
                >
                  <CardContent className="pt-5 pb-5">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <Badge variant={analysis.review_passed ? 'default' : 'destructive'}>
                          {analysis.review_passed ? 'Quality Verified' : 'Needs Review'}
                        </Badge>
                        <Badge variant="outline">{analysis.status}</Badge>
                        {analysis.generation_time_ms && (
                          <span className="text-xs text-muted-foreground">
                            Generated in {(analysis.generation_time_ms / 1000).toFixed(1)}s
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        {analysis.status === 'draft' && (
                          <Button size="sm" variant="outline" onClick={async () => {
                            const token = await getToken();
                            if (!token) return;
                            await approveAnalysis(token, plan.id);
                            await loadAnalysis(plan.id);
                          }}>
                            Approve
                          </Button>
                        )}
                        {analysis.status === 'approved' && (
                          <Button size="sm" onClick={async () => {
                            const token = await getToken();
                            if (!token) return;
                            await shareAnalysis(token, plan.id);
                            await loadAnalysis(plan.id);
                          }}>
                            Share with Client
                          </Button>
                        )}
                        {analysis.status === 'shared' && (
                          <Badge className="bg-emerald-100 text-emerald-700">Shared to Portal</Badge>
                        )}
                        <Button
                          size="sm"
                          variant={analysis.review_passed === false ? 'outline' : 'ghost'}
                          onClick={handleGenerateAnalysis}
                        >
                          Re-generate
                        </Button>
                      </div>
                    </div>

                    {/* Reviewer issues — shown when review failed */}
                    {analysis.review_passed === false && analysis.review_result && (
                      <div
                        className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {analysis.review_result.summary && (
                          <p className="text-destructive/90 mb-2">{analysis.review_result.summary}</p>
                        )}
                        {(analysis.review_result.numbers_issues ?? []).length > 0 && (
                          <ul className="space-y-1 text-xs text-muted-foreground list-disc list-inside">
                            {(analysis.review_result.numbers_issues as string[]).slice(0, 3).map((issue, i) => (
                              <li key={i}>{issue}</li>
                            ))}
                            {(analysis.review_result.numbers_issues as string[]).length > 3 && (
                              <li className="italic">
                                +{(analysis.review_result.numbers_issues as string[]).length - 3} more — click to view full analysis
                              </li>
                            )}
                          </ul>
                        )}
                        <div className="flex items-center gap-2 mt-3">
                          <Button
                            size="sm"
                            onClick={handleGenerateAnalysis}
                          >
                            Re-generate Analysis
                          </Button>
                          {analysis.status !== 'shared' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={async (e) => {
                                e.stopPropagation();
                                const token = await getToken();
                                if (!token) return;
                                await approveAnalysis(token, plan.id);
                                await loadAnalysis(plan.id);
                              }}
                            >
                              Approve Anyway
                            </Button>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Hero metrics */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
                      <div>
                        <p className="text-3xl font-bold text-emerald-600">
                          ${(analysis.combined_strategy as Record<string, number>)?.total_tax_saving?.toLocaleString() ?? '0'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">Total Tax Saving</p>
                      </div>
                      <div>
                        <p className="text-3xl font-bold">
                          {(analysis.combined_strategy as Record<string, number>)?.strategy_count ?? 0}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">Strategies Recommended</p>
                      </div>
                      <div>
                        <p className="text-3xl font-bold">
                          {analysis.strategies_evaluated?.length ?? 0}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">Strategies Evaluated</p>
                      </div>
                    </div>

                    <p className="text-xs text-center text-muted-foreground mt-4">
                      Click to view full analysis — brief, checklist, strategies, and AI transparency
                    </p>
                  </CardContent>
                </Card>

                {/* Accountant Brief — on main page */}
                {analysis.accountant_brief && (
                  <Card>
                    <CardContent className="pt-4">
                      <h4 className="font-semibold mb-2">Accountant Brief</h4>
                      <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:my-3 prose-p:my-2 prose-li:my-0.5 prose-table:my-3 prose-td:px-3 prose-td:py-1.5 prose-th:px-3 prose-th:py-1.5">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {analysis.accountant_brief}
                        </ReactMarkdown>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Implementation Checklist — on main page */}
                {analysis.implementation_items && analysis.implementation_items.length > 0 && (
                  <Card>
                    <CardContent className="pt-4">
                      <h4 className="font-semibold mb-2">Implementation Checklist</h4>
                      <div className="space-y-2">
                        {analysis.implementation_items.map((item) => (
                          <div key={item.id} className="flex items-center justify-between rounded-md border p-3">
                            <div>
                              <p className="text-sm font-medium">{item.title}</p>
                              {item.deadline && (
                                <p className="text-xs text-muted-foreground">Deadline: {item.deadline}</p>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {item.estimated_saving && (
                                <Badge variant="outline" className="text-emerald-600">
                                  Save ${item.estimated_saving.toLocaleString()}
                                </Badge>
                              )}
                              {item.risk_rating && (
                                <Badge variant="outline" className="text-xs">{item.risk_rating}</Badge>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* View AI Analysis button */}
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setShowAnalysisDetail(true)}
                >
                  View AI Analysis — {analysis.strategies_evaluated?.length ?? 0} strategies evaluated, {analysis.recommended_scenarios?.length ?? 0} modelled
                </Button>

                {/* AI analysis modal — transparency details only */}
                <AnalysisDetailDialog
                  analysis={analysis}
                  open={showAnalysisDetail}
                  onClose={() => setShowAnalysisDetail(false)}
                />
              </div>
            )}
          </TabsContent>
        </Tabs>
      ) : !pullingXero && (showManualEntry || !(plan.xero_connection_status === 'needs_reauth' || xeroAuthNeeded)) ? (
        <div className="flex-1 overflow-y-auto">
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
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generating Progress Component
// ---------------------------------------------------------------------------

const PIPELINE_STAGES = [
  {
    num: 1,
    label: 'Profiling',
    messages: [
      'Analysing entity classification...',
      'Checking small business eligibility...',
      'Evaluating turnover thresholds...',
      'Identifying applicable concessions...',
    ],
  },
  {
    num: 2,
    label: 'Scanning Strategies',
    messages: [
      'Evaluating timing strategies...',
      'Checking depreciation opportunities...',
      'Analysing superannuation options...',
      'Reviewing income deferral strategies...',
      'Assessing capital gains timing...',
      'Checking prepayment eligibility...',
    ],
  },
  {
    num: 3,
    label: 'Modelling',
    messages: [
      'Calculating tax impact for each strategy...',
      'Running before/after tax calculations...',
      'Evaluating cash flow impact...',
      'Finding optimal strategy combination...',
      'Modelling combined tax position...',
    ],
  },
  {
    num: 4,
    label: 'Writing Brief',
    messages: [
      'Drafting executive summary...',
      'Writing per-strategy analysis...',
      'Adding ATO compliance references...',
      'Generating client-friendly summary...',
      'Building implementation timeline...',
    ],
  },
  {
    num: 5,
    label: 'Reviewing',
    messages: [
      'Verifying tax calculator numbers...',
      'Checking ATO citation accuracy...',
      'Validating strategy consistency...',
      'Confirming implementation deadlines...',
    ],
  },
];

function GeneratingProgress({ stage }: { stage: number }) {
  const [messageIndex, setMessageIndex] = useState(0);

  // Rotate messages every 3 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((prev) => prev + 1);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Reset message index when stage changes
  useEffect(() => {
    setMessageIndex(0);
  }, [stage]);

  const activeStage = PIPELINE_STAGES.find((s) => s.num === stage);
  const activeMessage = activeStage
    ? activeStage.messages[messageIndex % activeStage.messages.length]
    : 'Starting analysis...';

  return (
    <div className="flex flex-col items-center justify-center flex-1 min-h-[400px] space-y-10">
      {/* Title */}
      <div className="text-center space-y-2">
        <h3 className="text-2xl font-semibold">Generating Tax Plan...</h3>
        <p className="text-sm text-muted-foreground">
          This typically takes 2–3 minutes
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-4">
        {PIPELINE_STAGES.map((step, i) => {
          const isDone = stage > step.num;
          const isActive = stage === step.num;
          return (
            <div key={step.label} className="flex items-center gap-4">
              <div className="flex flex-col items-center">
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-500 ${
                    isDone
                      ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900 dark:text-emerald-300'
                      : isActive
                        ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/25 animate-pulse'
                        : 'bg-muted text-muted-foreground'
                  }`}
                >
                  <span className="text-sm font-bold">
                    {isDone ? '✓' : step.num}
                  </span>
                </div>
                <span
                  className={`text-xs mt-2 font-medium transition-colors ${
                    isActive
                      ? 'text-primary'
                      : isDone
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : 'text-muted-foreground'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < PIPELINE_STAGES.length - 1 && (
                <div
                  className={`w-10 h-0.5 mb-6 transition-colors duration-500 ${
                    isDone ? 'bg-emerald-300 dark:bg-emerald-700' : 'bg-border'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Rotating status message */}
      <div className="text-center h-12 flex items-center">
        <p
          key={`${stage}-${messageIndex}`}
          className="text-sm text-muted-foreground animate-in fade-in duration-500"
        >
          {activeMessage}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analysis Detail Dialog
// ---------------------------------------------------------------------------

function AnalysisDetailDialog({
  analysis,
  open,
  onClose,
}: {
  analysis: AnalysisResponse;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="w-full sm:max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>AI Analysis Detail</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          <p className="text-sm text-muted-foreground">
            Full transparency into how the AI generated this tax plan — every strategy considered, every number calculated, every source checked.
          </p>

            {analysis.client_profile && (
              <ExpandableSection title="Client Profile" subtitle="What the AI determined about this entity">
                <ProfileCard profile={analysis.client_profile as Record<string, unknown>} />
              </ExpandableSection>
            )}

            {analysis.strategies_evaluated && analysis.strategies_evaluated.length > 0 && (
              <ExpandableSection
                title={`All Strategies Evaluated (${analysis.strategies_evaluated.length})`}
                subtitle="Every strategy considered, with applicability reasoning"
              >
                <div className="space-y-2">
                  {(analysis.strategies_evaluated as Record<string, unknown>[]).map((strategy, i) => {
                    const applicable = strategy.applicable as boolean;
                    return (
                      <div key={i} className={`rounded-md border p-3 ${applicable ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-800 dark:bg-emerald-950/30' : 'border-stone-200 bg-stone-50/50 dark:border-stone-800 dark:bg-stone-950/30'}`}>
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className={`text-xs font-bold ${applicable ? 'text-emerald-600' : 'text-stone-400'}`}>
                                {applicable ? '✓ APPLICABLE' : '✗ NOT APPLICABLE'}
                              </span>
                              {Boolean(strategy.risk_rating) && (
                                <Badge variant="outline" className="text-[10px]">{String(strategy.risk_rating)}</Badge>
                              )}
                            </div>
                            <p className="text-sm font-medium mt-1">{String(strategy.name || strategy.strategy_id || `Strategy ${i + 1}`)}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{String(strategy.applicability_reason || '')}</p>
                          </div>
                          {applicable && Boolean(strategy.estimated_impact_range) && (
                            <div className="text-right shrink-0 ml-4">
                              <p className="text-xs text-muted-foreground">Est. saving</p>
                              <p className="text-sm font-medium text-emerald-600">
                                ${((strategy.estimated_impact_range as Record<string, number>).min || 0).toLocaleString()}
                                –${((strategy.estimated_impact_range as Record<string, number>).max || 0).toLocaleString()}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ExpandableSection>
            )}

            {analysis.recommended_scenarios && analysis.recommended_scenarios.length > 0 && (
              <ExpandableSection
                title={`Modelled Scenarios (${analysis.recommended_scenarios.length})`}
                subtitle="Each strategy modelled with real tax calculator numbers"
              >
                <div className="space-y-2">
                  {(analysis.recommended_scenarios as Record<string, unknown>[]).map((scenario, i) => {
                    const impact = scenario.impact as Record<string, Record<string, number>> | undefined;
                    const change = impact?.change;
                    return (
                      <div key={i} className="rounded-md border p-3">
                        <div className="flex items-start justify-between">
                          <div>
                            <p className="text-sm font-medium">{String(scenario.scenario_title || `Scenario ${i + 1}`)}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{String(scenario.description || '')}</p>
                          </div>
                          {change && (
                            <div className="text-right shrink-0 ml-4">
                              <p className="text-lg font-bold text-emerald-600">${(change.tax_saving || 0).toLocaleString()}</p>
                              <p className="text-[10px] text-muted-foreground">tax saving</p>
                            </div>
                          )}
                        </div>
                        {impact && (
                          <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
                            <span>Before: ${(impact.before?.tax_payable || 0).toLocaleString()}</span>
                            <span>→</span>
                            <span>After: ${(impact.after?.tax_payable || 0).toLocaleString()}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </ExpandableSection>
            )}

            {analysis.review_result && (
              <ExpandableSection
                title="Quality Review"
                subtitle={analysis.review_passed ? 'All checks passed' : 'Some issues found — review recommended'}
              >
                <div className="space-y-2">
                  {Object.entries(analysis.review_result as Record<string, unknown>).map(([key, value]) => {
                    if (key === 'summary') return <p key={key} className="text-sm">{String(value)}</p>;
                    if (typeof value === 'boolean') return (
                      <div key={key} className="flex items-center gap-2">
                        <span className={value ? 'text-emerald-600' : 'text-red-500'}>{value ? '✓' : '✗'}</span>
                        <span className="text-sm">{key.replace(/_/g, ' ')}</span>
                      </div>
                    );
                    if (Array.isArray(value) && value.length > 0) return (
                      <div key={key}>
                        <p className="text-xs font-medium text-muted-foreground">{key.replace(/_/g, ' ')}</p>
                        <ul className="text-sm list-disc pl-4 mt-1">
                          {value.map((item, j) => <li key={j}>{String(item)}</li>)}
                        </ul>
                      </div>
                    );
                    return null;
                  })}
                </div>
              </ExpandableSection>
            )}

            {analysis.client_summary && (
              <ExpandableSection title="Client Summary Preview" subtitle="What the client will see when you share">
                <div className="prose prose-sm dark:prose-invert max-w-none border rounded-lg p-4 bg-background">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis.client_summary}</ReactMarkdown>
                </div>
              </ExpandableSection>
            )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Expandable Section Component
// ---------------------------------------------------------------------------

function ExpandableSection({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Card>
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-muted/30 transition-colors rounded-lg"
      >
        <div>
          <p className="text-sm font-medium">{title}</p>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
        <span className={`text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`}>
          ▾
        </span>
      </button>
      {open && (
        <CardContent className="pt-0 pb-4">
          {children}
        </CardContent>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Profile Card — smart rendering of client profile data
// ---------------------------------------------------------------------------

const RATE_FIELDS = new Set(['applicable_tax_rate', 'effective_rate']);
const CURRENCY_FIELDS = new Set(['aggregated_turnover', 'total_income', 'total_expenses', 'net_profit', 'taxable_income']);
const SKIP_FIELDS = new Set(['key_thresholds', 'financials_summary']); // Render separately

function formatProfileValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return 'N/A';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (RATE_FIELDS.has(key) && typeof value === 'number') return `${(value * 100).toFixed(0)}%`;
  if (CURRENCY_FIELDS.has(key) && typeof value === 'number') return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (typeof value === 'number') return value.toLocaleString();
  return String(value);
}

function ProfileCard({ profile }: { profile: Record<string, unknown> }) {
  const mainFields = Object.entries(profile).filter(([key]) => !SKIP_FIELDS.has(key));
  const financials = profile.financials_summary as Record<string, number> | undefined;
  const thresholds = profile.key_thresholds as Record<string, Record<string, unknown>> | undefined;

  return (
    <div className="space-y-4">
      {/* Main fields */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {mainFields.map(([key, value]) => (
          <div key={key} className="rounded-md bg-muted/50 p-2.5">
            <p className="text-[10px] text-muted-foreground uppercase">{key.replace(/_/g, ' ')}</p>
            <p className="text-sm font-medium mt-0.5">{formatProfileValue(key, value)}</p>
          </div>
        ))}
      </div>

      {/* Financials summary */}
      {financials && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">FINANCIALS SUMMARY</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(financials).map(([key, value]) => (
              <div key={key} className="rounded-md bg-muted/50 p-2.5">
                <p className="text-[10px] text-muted-foreground uppercase">{key.replace(/_/g, ' ')}</p>
                <p className="text-sm font-medium mt-0.5">${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key thresholds */}
      {thresholds && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">KEY THRESHOLDS</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {Object.entries(thresholds).map(([key, info]) => {
              const val = typeof info === 'object' && info !== null ? info : { value: info };
              const threshold = (val as Record<string, unknown>).value;
              const above = (val as Record<string, unknown>).above_threshold;
              return (
                <div key={key} className="flex items-center justify-between rounded-md border p-2.5">
                  <span className="text-xs">{key.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium">
                      {typeof threshold === 'number' ? `$${threshold.toLocaleString()}` : String(threshold ?? '')}
                    </span>
                    {above !== undefined && (
                      <span className={`text-[10px] font-bold ${above ? 'text-amber-600' : 'text-emerald-600'}`}>
                        {above ? 'ABOVE' : 'BELOW'}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
