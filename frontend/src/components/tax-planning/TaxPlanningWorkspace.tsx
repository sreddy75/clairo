'use client';

import { useAuth } from '@clerk/nextjs';
import { useCallback, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
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
import type {
  EntityType,
  FinancialsInput,
  TaxPlan,
} from '@/types/tax-planning';

import { ComparisonTable } from './ComparisonTable';
import { FinancialsPanel } from './FinancialsPanel';
import { ManualEntryForm } from './ManualEntryForm';
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
  const [plan, setPlan] = useState<TaxPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [selectedEntityType, setSelectedEntityType] = useState<EntityType>('company');
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [showCreateNew, setShowCreateNew] = useState(false);
  const [xeroAuthNeeded, setXeroAuthNeeded] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generatingStage, setGeneratingStage] = useState(0);

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
  }, [connectionId, getToken]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

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
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="border-amber-300 text-amber-800 hover:bg-amber-100 dark:border-amber-700 dark:text-amber-200 dark:hover:bg-amber-900"
                  onClick={() => window.open('/settings/integrations', '_blank')}
                >
                  Reconnect Xero
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    try {
                      setXeroAuthNeeded(false);
                      setError(null);
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
                  Retry Pull
                </Button>
              </div>
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

      {/* Full-width workflow tabs — fills remaining viewport height */}
      {plan.financials_data && !showManualEntry ? (
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
            className="flex-1 overflow-y-auto mt-4"
          >
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {plan.tax_position && (
                <TaxPositionCard
                  taxPosition={plan.tax_position}
                  entityType={plan.entity_type}
                />
              )}
              <div className="lg:col-span-2">
                <FinancialsPanel
                  financials={plan.financials_data}
                  dataSource={plan.data_source}
                  xeroFetchedAt={plan.xero_report_fetched_at}
                  onRefreshXero={plan.xero_connection_id ? handleRefreshXero : undefined}
                  onEdit={() => setShowManualEntry(true)}
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
            {plan.scenarios && plan.scenarios.length >= 2 && (
              <div className="overflow-x-auto">
                <ComparisonTable scenarios={plan.scenarios} />
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
                {/* Status bar */}
                <div className="flex items-center justify-between">
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
                  <div className="flex items-center gap-2">
                    {analysis.status === 'draft' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          const token = await getToken();
                          if (!token) return;
                          await approveAnalysis(token, plan.id);
                          await loadAnalysis(plan.id);
                        }}
                      >
                        Approve
                      </Button>
                    )}
                    {analysis.status === 'approved' && (
                      <Button
                        size="sm"
                        onClick={async () => {
                          const token = await getToken();
                          if (!token) return;
                          await shareAnalysis(token, plan.id);
                          await loadAnalysis(plan.id);
                        }}
                      >
                        Share with Client
                      </Button>
                    )}
                    {analysis.status === 'shared' && (
                      <Badge className="bg-emerald-100 text-emerald-700">
                        Shared to Portal
                      </Badge>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleGenerateAnalysis}
                    >
                      Re-generate
                    </Button>
                  </div>
                </div>

                {/* Combined strategy summary */}
                {analysis.combined_strategy && (
                  <Card>
                    <CardContent className="pt-4">
                      <h4 className="font-semibold mb-2">Combined Strategy Impact</h4>
                      <div className="grid grid-cols-3 gap-4 text-center">
                        <div>
                          <p className="text-2xl font-bold text-emerald-600">
                            ${(analysis.combined_strategy as Record<string, number>).total_tax_saving?.toLocaleString() ?? '0'}
                          </p>
                          <p className="text-xs text-muted-foreground">Total Tax Saving</p>
                        </div>
                        <div>
                          <p className="text-2xl font-bold">
                            {(analysis.combined_strategy as Record<string, number>).strategy_count ?? 0}
                          </p>
                          <p className="text-xs text-muted-foreground">Strategies</p>
                        </div>
                        <div>
                          <p className="text-2xl font-bold">
                            {analysis.strategies_evaluated?.length ?? 0}
                          </p>
                          <p className="text-xs text-muted-foreground">Evaluated</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Accountant Brief */}
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

                {/* Implementation Checklist */}
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
                                <p className="text-xs text-muted-foreground">
                                  Deadline: {item.deadline}
                                </p>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {item.estimated_saving && (
                                <Badge variant="outline" className="text-emerald-600">
                                  Save ${item.estimated_saving.toLocaleString()}
                                </Badge>
                              )}
                              {item.risk_rating && (
                                <Badge variant="outline" className="text-xs">
                                  {item.risk_rating}
                                </Badge>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>
      ) : (
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
      )}
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
