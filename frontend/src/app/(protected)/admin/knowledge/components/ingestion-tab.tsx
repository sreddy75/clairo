'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock,
  Database,
  Eye,
  Gavel,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  Scale,
  Trash2,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  type FreshnessReport,
  type FreshnessSourceReport,
  type IngestionTaskStatus,
  deleteJob,
  getFreshness,
  getIngestionTaskStatus,
  restartJob,
  triggerAtoLegalDbIngestion,
  triggerCaseLawIngestion,
  triggerLegislationIngestion,
  triggerTaxPlanningTopicsIngestion,
  triggerTpbTreasuryIngestion,
} from '@/lib/api/knowledge';
import { JOB_STATUS_CONFIG, type JobStatus } from '@/types/knowledge';

import { useJobs } from '../hooks/use-jobs';

import { JobDetailModal } from './job-detail-modal';

type IngestionSource = 'legislation' | 'case_law' | 'ato_legal_db' | 'tpb_treasury' | 'tax_planning_topics';

interface IngestionAction {
  key: IngestionSource;
  label: string;
  description: string;
  icon: typeof Scale;
  trigger: (token: string, devMode: boolean) => Promise<{ data: { job_id: string; message: string } }>;
}

const INGESTION_ACTIONS: IngestionAction[] = [
  {
    key: 'ato_legal_db',
    label: 'ATO Legal Database',
    description: 'Ingest all ATO rulings (TRs, GSTRs, TDs, PCGs, CLRs) from the ATO Legal Database',
    icon: BookOpen,
    trigger: (token, devMode) => triggerAtoLegalDbIngestion(token, devMode),
  },
  {
    key: 'legislation',
    label: 'Australian Legislation',
    description: 'Ingest 7 key tax acts from legislation.gov.au (ITAA 1997, ITAA 1936, GST Act, FBT, TAA, SIS, SGAA)',
    icon: Scale,
    trigger: (token, devMode) => triggerLegislationIngestion(token, undefined, undefined, devMode),
  },
  {
    key: 'case_law',
    label: 'Case Law',
    description: 'Ingest tax-relevant case law from Open Australian Legal Corpus and Federal Court RSS',
    icon: Gavel,
    trigger: (token, devMode) => triggerCaseLawIngestion(token, undefined, undefined, devMode),
  },
  {
    key: 'tpb_treasury',
    label: 'TPB & Treasury',
    description: 'Ingest TPB practitioner guidance and Treasury exposure drafts',
    icon: BookOpen,
    trigger: (token, devMode) => triggerTpbTreasuryIngestion(token, devMode),
  },
  {
    key: 'tax_planning_topics',
    label: 'Tax Planning Topics',
    description: 'Ingest ~16 key ATO guidance pages for tax planning (instant asset write-off, prepaid expenses, Div 7A, CGT concessions, etc.)',
    icon: Scale,
    trigger: (token) => triggerTaxPlanningTopicsIngestion(token),
  },
];

const FRESHNESS_CONFIG: Record<string, { icon: typeof Scale; color: string }> = {
  legislation: { icon: Scale, color: 'blue' },
  ato_legal_db: { icon: BookOpen, color: 'amber' },
  case_law: { icon: Gavel, color: 'purple' },
  ato_rss: { icon: Database, color: 'green' },
  tpb_treasury: { icon: BookOpen, color: 'teal' },
  tax_planning_topics: { icon: Scale, color: 'emerald' },
};

const SOURCE_LABELS: Record<string, string> = {
  ato_legal_db: 'ATO Legal Database',
  legislation: 'Australian Legislation',
  case_law: 'Case Law',
  tpb_treasury: 'TPB & Treasury',
  tax_planning_topics: 'Tax Planning Topics',
};

interface ActiveJob {
  taskId: string;
  sourceKey: IngestionSource;
  startedAt: number;
  status: IngestionTaskStatus | null;
}

function FreshnessStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'fresh':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-status-success bg-status-success/10 rounded-full">
          <CheckCircle2 className="w-3 h-3" />
          Fresh
        </span>
      );
    case 'stale':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-status-warning bg-status-warning/10 rounded-full">
          <Clock className="w-3 h-3" />
          Stale
        </span>
      );
    case 'error':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-status-danger bg-status-danger/10 rounded-full">
          <XCircle className="w-3 h-3" />
          Error
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-muted-foreground bg-muted rounded-full">
          <Clock className="w-3 h-3" />
          Never Ingested
        </span>
      );
  }
}

function TaskStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'PENDING':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-muted-foreground bg-muted rounded-full">
          <Clock className="w-3 h-3" />
          Queued
        </span>
      );
    case 'STARTED':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-primary bg-primary/10 rounded-full">
          <Loader2 className="w-3 h-3 animate-spin" />
          Starting
        </span>
      );
    case 'PROGRESS':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-primary bg-primary/10 rounded-full">
          <Loader2 className="w-3 h-3 animate-spin" />
          Running
        </span>
      );
    case 'SUCCESS':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-status-success bg-status-success/10 rounded-full">
          <CheckCircle2 className="w-3 h-3" />
          Complete
        </span>
      );
    case 'FAILURE':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-status-danger bg-status-danger/10 rounded-full">
          <XCircle className="w-3 h-3" />
          Failed
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-muted-foreground bg-muted rounded-full">
          {status}
        </span>
      );
  }
}

function ProgressCard({ job, onDismiss }: { job: ActiveJob; onDismiss: () => void }) {
  const progress = job.status?.progress;
  const isTerminal = job.status?.status === 'SUCCESS' || job.status?.status === 'FAILURE';

  // Force re-render every second for the elapsed timer
  const [, setTick] = useState(0);
  useEffect(() => {
    if (isTerminal) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [isTerminal]);

  const elapsed = Math.round((Date.now() - job.startedAt) / 1000);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;

  return (
    <div className={`rounded-lg border p-4 ${
      job.status?.status === 'FAILURE'
        ? 'bg-status-danger/10 border-status-danger/20'
        : job.status?.status === 'SUCCESS'
          ? 'bg-status-success/10 border-status-success/20'
          : 'bg-primary/10 border-primary/20'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {SOURCE_LABELS[job.sourceKey] || job.sourceKey}
          </span>
          <TaskStatusBadge status={job.status?.status || 'PENDING'} />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground font-mono">
            {minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`}
          </span>
          {isTerminal && (
            <button
              onClick={onDismiss}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>

      {/* Stats grid */}
      {progress && (
        <div className="grid grid-cols-5 gap-3 mb-2">
          <div className="text-center">
            <div className="text-lg font-semibold font-mono text-foreground">
              {progress.processed}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Processed
            </div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold font-mono text-status-success">
              {progress.added}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Added
            </div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold font-mono text-primary">
              {progress.updated}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Updated
            </div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold font-mono text-muted-foreground">
              {progress.skipped}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Skipped
            </div>
          </div>
          <div className="text-center">
            <div className={`text-lg font-semibold font-mono ${
              progress.failed > 0 ? 'text-status-danger' : 'text-muted-foreground'
            }`}>
              {progress.failed}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Failed
            </div>
          </div>
        </div>
      )}

      {/* Current item */}
      {progress?.current_item && !isTerminal && (
        <div className="mt-2 flex items-center gap-2">
          <Loader2 className="w-3 h-3 animate-spin text-primary flex-shrink-0" />
          <span className="text-xs text-muted-foreground truncate">
            {progress.current_item}
          </span>
        </div>
      )}

      {/* Error message */}
      {job.status?.error && (
        <div className="mt-2 text-xs text-status-danger bg-status-danger/10 rounded p-2">
          {job.status.error}
        </div>
      )}
    </div>
  );
}

export function IngestionTab() {
  const { getToken } = useAuth();
  const [freshness, setFreshness] = useState<FreshnessReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggeringKey, setTriggeringKey] = useState<IngestionSource | null>(null);
  const [devMode, setDevMode] = useState(false);
  const [activeJobs, setActiveJobs] = useState<ActiveJob[]>([]);
  const activeJobsRef = useRef<ActiveJob[]>([]);
  activeJobsRef.current = activeJobs;

  const fetchFreshness = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const data = await getFreshness(token);
      setFreshness(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch freshness');
    } finally {
      setIsLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchFreshness();
  }, [fetchFreshness]);

  // Poll active jobs
  const hasActiveJobs = activeJobs.some(
    (j) => !j.status || !['SUCCESS', 'FAILURE', 'REVOKED'].includes(j.status.status)
  );

  useEffect(() => {
    if (!hasActiveJobs) return;

    const pollInterval = setInterval(async () => {
      const token = await getToken();
      if (!token) return;

      const currentJobs = activeJobsRef.current;
      const jobsToPoll = currentJobs.filter(
        (j) => !j.status || !['SUCCESS', 'FAILURE', 'REVOKED'].includes(j.status.status)
      );

      if (jobsToPoll.length === 0) return;

      const updates = await Promise.all(
        jobsToPoll.map(async (j) => {
          try {
            const status = await getIngestionTaskStatus(token, j.taskId);
            return { taskId: j.taskId, status };
          } catch {
            return { taskId: j.taskId, status: null };
          }
        })
      );

      setActiveJobs((prev) =>
        prev.map((j) => {
          const update = updates.find((u) => u.taskId === j.taskId);
          if (update?.status) {
            return { ...j, status: update.status };
          }
          return j;
        })
      );

      // If any job just completed, refresh freshness
      const justCompleted = updates.some(
        (u) => u.status && ['SUCCESS', 'FAILURE'].includes(u.status.status)
      );
      if (justCompleted) {
        fetchFreshness();
      }
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [hasActiveJobs, getToken, fetchFreshness]);

  const handleTrigger = async (action: IngestionAction) => {
    setTriggeringKey(action.key);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const result = await action.trigger(token, devMode);

      // Add to active jobs for tracking
      setActiveJobs((prev) => [
        {
          taskId: result.data.job_id,
          sourceKey: action.key,
          startedAt: Date.now(),
          status: { task_id: result.data.job_id, status: 'PENDING', progress: { processed: 0, added: 0, updated: 0, skipped: 0, failed: 0, source_type: action.key } },
        },
        ...prev,
      ]);
    } catch (err) {
      setActiveJobs((prev) => [
        {
          taskId: `error-${Date.now()}`,
          sourceKey: action.key,
          startedAt: Date.now(),
          status: { task_id: '', status: 'FAILURE', progress: { processed: 0, added: 0, updated: 0, skipped: 0, failed: 0, source_type: action.key }, error: err instanceof Error ? err.message : 'Unknown error' },
        },
        ...prev,
      ]);
    } finally {
      setTriggeringKey(null);
    }
  };

  const dismissJob = (taskId: string) => {
    setActiveJobs((prev) => prev.filter((j) => j.taskId !== taskId));
  };

  const isSourceRunning = (key: IngestionSource) =>
    activeJobs.some(
      (j) => j.sourceKey === key && j.status && !['SUCCESS', 'FAILURE', 'REVOKED'].includes(j.status.status)
    );

  const sources = freshness?.data?.sources || [];
  const totalChunks = freshness?.data?.total_chunks || 0;

  if (isLoading && !freshness) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error && !freshness) {
    return (
      <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4">
        <div className="flex items-center gap-2 text-status-danger">
          <AlertCircle className="w-5 h-5" />
          <span className="font-medium">Error loading freshness data</span>
        </div>
        <p className="text-status-danger text-sm mt-1">{error}</p>
        <button
          onClick={() => fetchFreshness()}
          className="mt-3 px-3 py-1.5 text-sm bg-status-danger/10 hover:bg-status-danger/20 text-status-danger rounded-md transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Knowledge Base Ingestion
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Trigger ingestion pipelines and monitor content freshness.
            Total chunks: <span className="font-mono font-medium">{totalChunks.toLocaleString()}</span>
          </p>
        </div>
        <button
          onClick={() => fetchFreshness()}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Active Jobs Progress */}
      {activeJobs.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-foreground">
            Active Jobs
          </h4>
          {activeJobs.map((job) => (
            <ProgressCard
              key={job.taskId}
              job={job}
              onDismiss={() => dismissJob(job.taskId)}
            />
          ))}
        </div>
      )}

      {/* Freshness Status Table */}
      {sources.length > 0 && (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <div className="px-4 py-3 bg-muted border-b border-border">
            <h4 className="text-sm font-semibold text-foreground">Content Freshness</h4>
          </div>
          <table className="w-full">
            <thead className="border-b border-border">
              <tr>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Chunks</th>
                <th className="text-right px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Errors</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Last Ingested</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sources.map((source: FreshnessSourceReport) => {
                const config = FRESHNESS_CONFIG[source.source_type] || { icon: Database, color: 'gray' };
                const Icon = config.icon;
                return (
                  <tr key={source.source_type} className="hover:bg-muted">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm font-medium text-foreground">{source.source_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <FreshnessStatusBadge status={source.freshness_status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-mono text-muted-foreground">{source.chunk_count.toLocaleString()}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`text-sm font-mono ${source.error_count > 0 ? 'text-status-danger' : 'text-muted-foreground'}`}>
                        {source.error_count}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-muted-foreground">
                        {source.last_ingested_at ? formatDate(source.last_ingested_at) : 'Never'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Ingestion Actions */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="px-4 py-3 bg-muted border-b border-border flex items-center justify-between">
          <h4 className="text-sm font-semibold text-foreground">Trigger Ingestion</h4>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={devMode}
              onChange={(e) => setDevMode(e.target.checked)}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary/20"
            />
            <span className="text-xs font-medium text-status-warning">
              Dev Mode (small subset)
            </span>
          </label>
        </div>
        <div className="divide-y divide-border">
          {INGESTION_ACTIONS.map((action) => {
            const Icon = action.icon;
            const isTriggering = triggeringKey === action.key;
            const running = isSourceRunning(action.key);
            return (
              <div key={action.key} className="flex items-center justify-between px-4 py-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    running
                      ? 'bg-primary/10'
                      : 'bg-primary/10'
                  }`}>
                    {running ? (
                      <Loader2 className="w-5 h-5 text-primary animate-spin" />
                    ) : (
                      <Icon className="w-5 h-5 text-primary" />
                    )}
                  </div>
                  <div>
                    <h5 className="text-sm font-medium text-foreground">{action.label}</h5>
                    <p className="text-xs text-muted-foreground mt-0.5 max-w-md">{action.description}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleTrigger(action)}
                  disabled={isTriggering || running}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isTriggering ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  {isTriggering ? 'Starting...' : running ? 'Running' : 'Run'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Job History */}
      <JobHistory />

      {/* Scheduled Jobs Info */}
      <div className="bg-muted rounded-xl border border-border p-4">
        <h4 className="text-sm font-semibold text-foreground mb-2">Automated Schedule</h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            <span>ATO RSS Monitor: Every 4 hours</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            <span>ATO Legal DB Delta Crawl: Weekly (Sun 2am)</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            <span>Legislation Sync: Monthly (1st, 3am)</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            <span>Federal Court RSS: Daily (6am)</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-3.5 h-3.5" />
            <span>Supersession Check: Weekly (Mon 4am)</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function JobHistory() {
  const { getToken } = useAuth();
  const {
    jobs,
    isLoading,
    error,
    refresh,
    filter,
    setFilter,
    selectedJob,
    selectJob,
    clearSelectedJob,
    isLoadingJob,
  } = useJobs();

  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleRestart = async (jobId: string) => {
    setActionLoading(jobId);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      await restartJob(token, jobId);
      await refresh();
    } catch {
      // Silently fail — job list will refresh
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (jobId: string) => {
    if (!confirm('Delete this job record?')) return;
    setActionLoading(jobId);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      await deleteJob(token, jobId);
      await refresh();
    } catch {
      // Silently fail
    } finally {
      setActionLoading(null);
    }
  };

  const STATUS_OPTIONS: { value: JobStatus | ''; label: string }[] = [
    { value: '', label: 'All' },
    { value: 'pending', label: 'Pending' },
    { value: 'running', label: 'Running' },
    { value: 'completed', label: 'Completed' },
    { value: 'failed', label: 'Failed' },
  ];

  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-3 bg-muted border-b border-border flex items-center justify-between">
        <h4 className="text-sm font-semibold text-foreground">Job History</h4>
        <div className="flex items-center gap-2">
          <select
            value={filter.status || ''}
            onChange={(e) => setFilter({ ...filter, status: (e.target.value || undefined) as JobStatus | undefined })}
            className="px-2 py-1 text-xs border border-border bg-card text-foreground rounded-md"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <button
            onClick={() => refresh()}
            disabled={isLoading}
            className="p-1.5 text-muted-foreground hover:bg-muted rounded-md"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="px-4 py-2 text-xs text-status-danger bg-status-danger/10 border-b border-status-danger/20">
          {error}
        </div>
      )}

      {isLoading && jobs.length === 0 ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-primary" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="px-4 py-8 text-center text-sm text-muted-foreground">
          No ingestion jobs yet. Trigger one above to get started.
        </div>
      ) : (
        <table className="w-full">
          <thead className="border-b border-border">
            <tr>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Started</th>
              <th className="text-right px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Processed</th>
              <th className="text-right px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Added</th>
              <th className="text-center px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {jobs.map((job) => {
              const statusConfig = JOB_STATUS_CONFIG[job.status];
              return (
                <tr key={job.id} className="hover:bg-muted">
                  <td className="px-4 py-2.5">
                    <span className="text-sm font-medium text-foreground">{job.source_name}</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${statusConfig.bgColor} ${statusConfig.color}`}>
                      {job.status === 'running' && <Loader2 className="w-3 h-3 animate-spin" />}
                      {job.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                      {job.status === 'failed' && <XCircle className="w-3 h-3" />}
                      {job.status === 'pending' && <Clock className="w-3 h-3" />}
                      {statusConfig.label}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-xs text-muted-foreground">
                      {job.started_at ? formatRelativeTime(job.started_at) : 'Queued'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="text-sm font-mono text-foreground">{job.items_processed}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="text-sm font-mono text-status-success">+{job.items_added}</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => selectJob(job.id)}
                        className="p-1 text-muted-foreground hover:bg-muted rounded transition-colors"
                        title="View Details"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      {(job.status === 'failed' || job.status === 'completed') && (
                        <button
                          onClick={() => handleRestart(job.id)}
                          disabled={actionLoading === job.id}
                          className="p-1 text-primary hover:bg-primary/10 rounded transition-colors disabled:opacity-50"
                          title="Restart"
                        >
                          {actionLoading === job.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                        </button>
                      )}
                      {job.status !== 'running' && (
                        <button
                          onClick={() => handleDelete(job.id)}
                          disabled={actionLoading === job.id}
                          className="p-1 text-status-danger hover:bg-status-danger/10 rounded transition-colors disabled:opacity-50"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <JobDetailModal job={selectedJob} isLoading={isLoadingJob} onClose={clearSelectedJob} />
    </div>
  );
}

function formatRelativeTime(dateString: string): string {
  const diffMs = Date.now() - new Date(dateString).getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateString);
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
