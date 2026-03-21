'use client';

/**
 * Traffic Light Dashboard - Client Overview (Compact Version)
 *
 * A color-coded dashboard that lets accountants scan client health instantly.
 * Uses traffic light colors (green/yellow/red) for immediate status recognition.
 * Optimized for space efficiency and mobile responsiveness.
 */

import { motion } from 'framer-motion';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  DollarSign,
  FileText,
  Lightbulb,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Users,
  XCircle,
} from 'lucide-react';
import Link from 'next/link';
import React from 'react';

import { formatCurrency } from '@/lib/formatters';
import type { QualityIssue } from '@/lib/quality';
import type { Insight } from '@/types/insights';

// =============================================================================
// Types
// =============================================================================

type TrafficLight = 'green' | 'yellow' | 'red';

interface ClientData {
  // GST
  total_sales: string;
  total_purchases: string;
  gst_collected: string;
  gst_paid: string;
  net_gst: string;
  // PAYG
  has_payroll: boolean;
  total_wages: string;
  total_tax_withheld: string;
  total_super: string;
  pay_run_count: number;
  employee_count: number;
  // Quality
  quality_score: string | null;
  critical_issues: number;
  // Status
  bas_status: string;
  last_full_sync_at: string | null;
  // Counts
  invoice_count: number;
  transaction_count: number;
  quarter_label: string;
}

interface TrafficLightDashboardProps {
  client: ClientData;
  qualityIssues: QualityIssue[];
  insights: Insight[];
  onViewAllIssues: () => void;
  onViewAllInsights: () => void;
  onRefreshData: () => void;
  isRefreshing?: boolean;
  clientId: string;
}

// =============================================================================
// Helper Functions
// =============================================================================

function getGSTStatus(netGst: string, criticalIssues: number): TrafficLight {
  if (criticalIssues > 0) return 'red';
  const gst = parseFloat(netGst);
  if (isNaN(gst)) return 'yellow';
  return 'green';
}

function getPAYGStatus(hasPayroll: boolean, payRunCount: number): TrafficLight {
  if (!hasPayroll) return 'green'; // N/A case
  if (payRunCount === 0) return 'yellow';
  return 'green';
}

function getQualityStatus(score: string | null, criticalIssues: number): TrafficLight {
  if (criticalIssues > 0) return 'red';
  if (!score) return 'yellow';
  const s = parseFloat(score);
  if (s >= 80) return 'green';
  if (s >= 50) return 'yellow';
  return 'red';
}

function getBASReadiness(
  basStatus: string,
  qualityScore: string | null,
  criticalIssues: number
): TrafficLight {
  if (criticalIssues > 0) return 'red';
  if (basStatus === 'ready') return 'green';
  if (basStatus === 'needs_review') return 'yellow';
  if (!qualityScore || parseFloat(qualityScore) < 50) return 'red';
  return 'yellow';
}

function getTimeSince(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

// =============================================================================
// Status Card Component
// =============================================================================

interface StatusCardProps {
  title: string;
  status: TrafficLight;
  mainValue: string;
  subtext: string;
  icon: React.ElementType;
  actionLabel?: string;
  onAction?: () => void;
  trend?: 'up' | 'down' | null;
  disabled?: boolean;
}

function StatusCard({
  title,
  status,
  mainValue,
  subtext,
  icon: Icon,
  actionLabel,
  onAction,
  trend,
  disabled,
}: StatusCardProps) {
  const statusColors = {
    green: {
      bg: 'bg-status-success/5',
      border: 'border-status-success/20',
      icon: 'bg-status-success/10 text-status-success',
      indicator: 'bg-status-success',
      text: 'text-status-success',
    },
    yellow: {
      bg: 'bg-status-warning/5',
      border: 'border-status-warning/20',
      icon: 'bg-status-warning/10 text-status-warning',
      indicator: 'bg-status-warning',
      text: 'text-status-warning',
    },
    red: {
      bg: 'bg-status-danger/5',
      border: 'border-status-danger/20',
      icon: 'bg-status-danger/10 text-status-danger',
      indicator: 'bg-status-danger',
      text: 'text-status-danger',
    },
  };

  const colors = statusColors[status];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`relative rounded-xl border ${colors.border} ${colors.bg} p-3 sm:p-4`}
    >
      {/* Status indicator dot */}
      <div className="absolute top-3 right-3">
        <span className={`w-2 h-2 rounded-full ${colors.indicator}`} />
      </div>

      {/* Header row: Icon + Title */}
      <div className="flex items-center gap-2 mb-2">
        <div className={`inline-flex items-center justify-center w-8 h-8 rounded-lg ${colors.icon}`}>
          <Icon className="w-4 h-4" />
        </div>
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{title}</p>
      </div>

      {/* Main value */}
      <div className="flex items-baseline gap-2">
        <p className={`text-xl sm:text-2xl font-bold tabular-nums ${colors.text}`}>{mainValue}</p>
        {trend && (
          <span className={trend === 'up' ? 'text-status-success' : 'text-status-danger'}>
            {trend === 'up' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          </span>
        )}
      </div>

      {/* Subtext */}
      <p className="text-xs text-muted-foreground mt-0.5 truncate">{subtext}</p>

      {/* Action button - compact */}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          disabled={disabled}
          className={`mt-2 w-full py-1.5 px-2 rounded-lg text-xs font-medium transition-all ${
            status === 'green'
              ? 'bg-status-success hover:bg-status-success/90 text-white'
              : status === 'yellow'
              ? 'bg-status-warning hover:bg-status-warning/90 text-white'
              : 'bg-status-danger hover:bg-status-danger/90 text-white'
          } disabled:opacity-50`}
        >
          {actionLabel}
        </button>
      )}
    </motion.div>
  );
}

// =============================================================================
// Issue Row Component
// =============================================================================

interface IssueRowProps {
  issue: QualityIssue;
  clientId: string;
}

function IssueRow({ issue, clientId }: IssueRowProps) {
  const severityIcon = issue.severity === 'critical' ? (
    <span className="w-1.5 h-1.5 rounded-full bg-status-danger flex-shrink-0" />
  ) : issue.severity === 'error' ? (
    <span className="w-1.5 h-1.5 rounded-full bg-status-danger/70 flex-shrink-0" />
  ) : (
    <span className="w-1.5 h-1.5 rounded-full bg-status-warning flex-shrink-0" />
  );

  return (
    <div className="flex items-center justify-between py-1.5 px-2 hover:bg-card/50 rounded transition-colors group">
      <div className="flex items-center gap-2 min-w-0">
        {severityIcon}
        <p className="text-xs text-foreground truncate">{issue.title}</p>
      </div>
      <Link
        href={`/clients/${clientId}?tab=quality`}
        className="flex-shrink-0 text-[10px] font-medium text-primary hover:text-primary/80 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        Fix
      </Link>
    </div>
  );
}

// =============================================================================
// Insight Row Component
// =============================================================================

interface InsightRowProps {
  insight: Insight;
}

function InsightRowComponent({ insight }: InsightRowProps) {
  const priorityConfig = {
    high: { label: '!', color: 'bg-status-danger text-white' },
    medium: { label: '•', color: 'bg-status-warning text-white' },
    low: { label: '○', color: 'bg-primary text-white' },
  };

  const config = priorityConfig[insight.priority];

  return (
    <div className="flex items-center gap-2 py-1.5 px-2 hover:bg-card/50 rounded transition-colors">
      <span className={`w-4 h-4 rounded text-[10px] font-bold flex items-center justify-center flex-shrink-0 ${config.color}`}>
        {config.label}
      </span>
      <p className="text-xs text-foreground truncate">{insight.title}</p>
    </div>
  );
}

// =============================================================================
// Main Dashboard Component
// =============================================================================

export function TrafficLightDashboard({
  client,
  qualityIssues,
  insights,
  onViewAllIssues,
  onViewAllInsights,
  onRefreshData,
  isRefreshing,
  clientId,
}: TrafficLightDashboardProps) {
  // Calculate statuses
  const gstStatus = getGSTStatus(client.net_gst, client.critical_issues);
  const paygStatus = getPAYGStatus(client.has_payroll, client.pay_run_count);
  const qualityStatus = getQualityStatus(client.quality_score, client.critical_issues);
  const basReadiness = getBASReadiness(client.bas_status, client.quality_score, client.critical_issues);

  // Separate issues by severity
  const criticalIssues = qualityIssues.filter((i) => i.severity === 'critical' && !i.dismissed);
  const warningIssues = qualityIssues.filter(
    (i) => (i.severity === 'warning' || i.severity === 'error') && !i.dismissed
  );

  // Get top insights
  const topInsights = insights
    .filter((i) => i.status === 'new' || i.status === 'viewed')
    .slice(0, 5);

  const netGst = parseFloat(client.net_gst);
  const isRefund = netGst < 0;

  return (
    <div className="space-y-4">
      {/* Status Cards Row - 2x2 on mobile, 4 on desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatusCard
          title="GST"
          status={gstStatus}
          mainValue={formatCurrency(client.net_gst)}
          subtext={isRefund ? 'Refund from ATO' : 'Payable to ATO'}
          icon={DollarSign}
        />
        <StatusCard
          title="PAYG"
          status={paygStatus}
          mainValue={client.has_payroll ? formatCurrency(client.total_tax_withheld) : 'N/A'}
          subtext={client.has_payroll ? `${client.pay_run_count} pay runs` : 'No payroll'}
          icon={Users}
        />
        <StatusCard
          title="Quality"
          status={qualityStatus}
          mainValue={client.quality_score ? `${Math.round(parseFloat(client.quality_score))}` : '—'}
          subtext={client.critical_issues > 0 ? `${client.critical_issues} issues` : 'Healthy'}
          icon={Shield}
        />
        <StatusCard
          title="BAS"
          status={basReadiness}
          mainValue={basReadiness === 'green' ? 'Ready' : basReadiness === 'yellow' ? 'Review' : 'Fix'}
          subtext={`Sync: ${getTimeSince(client.last_full_sync_at)}`}
          icon={basReadiness === 'green' ? CheckCircle2 : basReadiness === 'yellow' ? Clock : XCircle}
          actionLabel={isRefreshing ? 'Syncing...' : 'Refresh'}
          onAction={onRefreshData}
          disabled={isRefreshing}
        />
      </div>

      {/* Issues Row - Stack on mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Critical Issues */}
        <div className="rounded-xl border border-status-danger/20 bg-status-danger/5 overflow-hidden">
          <div className="px-3 py-2 border-b border-status-danger/10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-status-danger" />
              <span className="text-sm font-medium text-foreground">Critical Issues</span>
            </div>
            {criticalIssues.length > 0 && (
              <span className="px-2 py-0.5 bg-status-danger text-white text-xs font-bold rounded-full">
                {criticalIssues.length}
              </span>
            )}
          </div>
          <div className="p-2 min-h-[60px] max-h-[140px] overflow-y-auto">
            {criticalIssues.length === 0 ? (
              <div className="py-3 text-center">
                <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto mb-1" />
                <p className="text-xs text-muted-foreground">No critical issues</p>
              </div>
            ) : (
              <div className="space-y-1">
                {criticalIssues.slice(0, 3).map((issue) => (
                  <IssueRow key={issue.id} issue={issue} clientId={clientId} />
                ))}
              </div>
            )}
          </div>
          {criticalIssues.length > 0 && (
            <button
              onClick={onViewAllIssues}
              className="w-full px-3 py-2 border-t border-status-danger/10 text-xs font-medium text-status-danger hover:bg-status-danger/5 flex items-center justify-center gap-1"
            >
              View All <ChevronRight className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Warnings */}
        <div className="rounded-xl border border-status-warning/20 bg-status-warning/5 overflow-hidden">
          <div className="px-3 py-2 border-b border-status-warning/10 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-status-warning" />
              <span className="text-sm font-medium text-foreground">Warnings</span>
            </div>
            {warningIssues.length > 0 && (
              <span className="px-2 py-0.5 bg-status-warning text-white text-xs font-bold rounded-full">
                {warningIssues.length}
              </span>
            )}
          </div>
          <div className="p-2 min-h-[60px] max-h-[140px] overflow-y-auto">
            {warningIssues.length === 0 ? (
              <div className="py-3 text-center">
                <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto mb-1" />
                <p className="text-xs text-muted-foreground">No warnings</p>
              </div>
            ) : (
              <div className="space-y-1">
                {warningIssues.slice(0, 3).map((issue) => (
                  <IssueRow key={issue.id} issue={issue} clientId={clientId} />
                ))}
              </div>
            )}
          </div>
          {warningIssues.length > 0 && (
            <button
              onClick={onViewAllIssues}
              className="w-full px-3 py-2 border-t border-status-warning/10 text-xs font-medium text-status-warning hover:bg-status-warning/5 flex items-center justify-center gap-1"
            >
              View All <ChevronRight className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* AI Insights - Compact */}
      <div className="rounded-xl border border-primary/20 bg-primary/5 overflow-hidden">
        <div className="px-3 py-2 border-b border-primary/10 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-foreground">AI Insights</span>
          </div>
          {insights.filter((i) => i.status === 'new').length > 0 && (
            <span className="px-2 py-0.5 bg-primary text-primary-foreground text-xs font-bold rounded-full">
              {insights.filter((i) => i.status === 'new').length} New
            </span>
          )}
        </div>
        <div className="p-2 min-h-[60px] max-h-[140px] overflow-y-auto">
          {topInsights.length === 0 ? (
            <div className="py-3 text-center">
              <Lightbulb className="w-6 h-6 text-muted-foreground/40 mx-auto mb-1" />
              <p className="text-xs text-muted-foreground">Click &ldquo;Analyze&rdquo; to generate insights</p>
            </div>
          ) : (
            <div className="space-y-1">
              {topInsights.slice(0, 3).map((insight) => (
                <InsightRowComponent key={insight.id} insight={insight} />
              ))}
            </div>
          )}
        </div>
        {insights.length > 0 && (
          <button
            onClick={onViewAllInsights}
            className="w-full px-3 py-2 border-t border-primary/10 text-xs font-medium text-primary hover:bg-primary/5 flex items-center justify-center gap-1"
          >
            View All ({insights.length}) <ChevronRight className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* Quick Stats Footer - Compact */}
      <div className="rounded-xl border border-border bg-card p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
            <FileText className="w-3 h-3" />
            {client.quarter_label} Summary
          </span>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2">
          <div className="text-center p-2 rounded-lg bg-muted">
            <p className="text-sm sm:text-base font-bold tabular-nums text-status-success">{formatCurrency(client.total_sales)}</p>
            <p className="text-[10px] text-muted-foreground">Sales</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-muted">
            <p className="text-sm sm:text-base font-bold tabular-nums text-status-danger">{formatCurrency(client.total_purchases)}</p>
            <p className="text-[10px] text-muted-foreground">Purchases</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-muted">
            <p className="text-sm sm:text-base font-bold tabular-nums text-foreground">{client.invoice_count}</p>
            <p className="text-[10px] text-muted-foreground">Invoices</p>
          </div>
          <div className="text-center p-2 rounded-lg bg-muted">
            <p className="text-sm sm:text-base font-bold tabular-nums text-foreground">{client.transaction_count}</p>
            <p className="text-[10px] text-muted-foreground">Transactions</p>
          </div>
          {client.has_payroll && (
            <>
              <div className="text-center p-2 rounded-lg bg-muted">
                <p className="text-sm sm:text-base font-bold tabular-nums text-primary">{formatCurrency(client.total_wages)}</p>
                <p className="text-[10px] text-muted-foreground">Wages (W1)</p>
              </div>
              <div className="text-center p-2 rounded-lg bg-muted">
                <p className="text-sm sm:text-base font-bold tabular-nums text-primary">{formatCurrency(client.total_super)}</p>
                <p className="text-[10px] text-muted-foreground">Super</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default TrafficLightDashboard;
