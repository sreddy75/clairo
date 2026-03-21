'use client';

/**
 * Internal Admin Dashboard Home Page
 *
 * Overview page showing key metrics and quick actions.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import {
  ArrowDownIcon,
  ArrowUpIcon,
  TrendingUp,
  Users,
  DollarSign,
  BarChart3,
  Loader2,
  AlertCircle,
  Building2,
} from 'lucide-react';
import Link from 'next/link';

import { useAdminDashboard } from '@/hooks/useAdminDashboard';

/**
 * Format cents to AUD currency string.
 */
function formatCurrency(cents: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

/**
 * Metric card component for dashboard.
 */
function MetricCard({
  title,
  value,
  change,
  changeLabel,
  icon: Icon,
  iconBg,
}: {
  title: string;
  value: string;
  change?: number;
  changeLabel?: string;
  icon: React.ComponentType<{ className?: string }>;
  iconBg: string;
}) {
  const isPositive = (change ?? 0) >= 0;

  return (
    <div className="bg-card rounded-xl border border-border p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
          {change !== undefined && (
            <div className="flex items-center gap-1 mt-2">
              {isPositive ? (
                <ArrowUpIcon className="w-4 h-4 text-status-success" />
              ) : (
                <ArrowDownIcon className="w-4 h-4 text-status-danger" />
              )}
              <span
                className={`text-sm font-medium ${
                  isPositive ? 'text-status-success' : 'text-status-danger'
                }`}
              >
                {Math.abs(change).toFixed(1)}%
              </span>
              {changeLabel && (
                <span className="text-sm text-muted-foreground">{changeLabel}</span>
              )}
            </div>
          )}
        </div>
        <div className={`p-3 rounded-lg ${iconBg}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );
}

/**
 * Quick action link component.
 */
function QuickAction({
  href,
  icon: Icon,
  label,
  iconColor,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  iconColor: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 p-4 bg-card rounded-xl border border-border hover:border-primary/30 hover:shadow-sm transition-all"
    >
      <div className={`p-2 rounded-lg ${iconColor}`}>
        <Icon className="w-5 h-5" />
      </div>
      <span className="text-sm font-medium text-foreground">{label}</span>
    </Link>
  );
}

/**
 * Admin dashboard home page.
 */
export default function AdminDashboardPage() {
  const {
    tenants,
    totalTenants,
    mrr,
    mrrChange,
    churnRate,
    activeTenants,
    isLoading,
    error,
  } = useAdminDashboard({ limit: 5 });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-status-danger" />
          <p className="text-status-danger">Failed to load dashboard data</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-status-danger/10 rounded-lg">
              <Building2 className="w-6 h-6 text-status-danger" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Admin Dashboard</h1>
              <p className="text-muted-foreground">Platform-wide metrics and management</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Monthly Recurring Revenue"
            value={formatCurrency(mrr)}
            change={mrrChange}
            changeLabel="vs last month"
            icon={DollarSign}
            iconBg="bg-status-success"
          />
          <MetricCard
            title="Active Tenants"
            value={activeTenants.toLocaleString()}
            icon={Users}
            iconBg="bg-primary"
          />
          <MetricCard
            title="Total Tenants"
            value={totalTenants.toLocaleString()}
            icon={Building2}
            iconBg="bg-purple-600"
          />
          <MetricCard
            title="Churn Rate"
            value={`${churnRate.toFixed(1)}%`}
            change={-churnRate}
            icon={TrendingUp}
            iconBg="bg-orange-600"
          />
        </div>

        {/* Quick Actions */}
        <div>
          <h2 className="text-lg font-semibold text-foreground mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <QuickAction
              href="/internal/admin/customers"
              icon={Users}
              label="View All Customers"
              iconColor="bg-primary/10 text-primary"
            />
            <QuickAction
              href="/internal/admin/revenue"
              icon={TrendingUp}
              label="Revenue Analytics"
              iconColor="bg-status-success/10 text-status-success"
            />
            <QuickAction
              href="/internal/admin/analytics"
              icon={BarChart3}
              label="Usage Analytics"
              iconColor="bg-purple-100 text-purple-600"
            />
            <QuickAction
              href="/dashboard"
              icon={Building2}
              label="Back to App"
              iconColor="bg-muted text-muted-foreground"
            />
          </div>
        </div>

        {/* Recent Tenants */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground">Recent Tenants</h2>
            <Link
              href="/internal/admin/customers"
              className="text-sm text-primary hover:text-primary/80 font-medium"
            >
              View all →
            </Link>
          </div>
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            <table className="w-full">
              <thead className="bg-muted border-b border-border">
                <tr>
                  <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase">
                    Tenant
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase">
                    Tier
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase">
                    Clients
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase">
                    MRR
                  </th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-muted-foreground uppercase">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tenants.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-muted-foreground">
                      No tenants found
                    </td>
                  </tr>
                ) : (
                  tenants.map((tenant) => (
                    <tr key={tenant.id} className="hover:bg-muted">
                      <td className="px-6 py-4">
                        <Link
                          href={`/internal/admin/customers/${tenant.id}`}
                          className="text-sm font-medium text-foreground hover:text-primary"
                        >
                          {tenant.name}
                        </Link>
                        {tenant.owner_email && (
                          <p className="text-sm text-muted-foreground">{tenant.owner_email}</p>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary capitalize">
                          {tenant.tier}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-foreground">
                        {tenant.client_count}
                        {tenant.client_limit && (
                          <span className="text-muted-foreground">/{tenant.client_limit}</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-foreground">
                        {formatCurrency(tenant.mrr_cents)}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            tenant.is_active
                              ? 'bg-status-success/10 text-status-success'
                              : 'bg-muted text-muted-foreground'
                          }`}
                        >
                          {tenant.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
