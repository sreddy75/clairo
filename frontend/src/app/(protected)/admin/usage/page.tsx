'use client';

import { useAuth, useUser } from '@clerk/nextjs';
import {
  AlertCircle,
  ArrowUpRight,
  BarChart3,
  Loader2,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { getAdminUsageStats, getUpsellOpportunities, setAuthToken } from '@/lib/api/billing';
import type { AdminUsageStats, SubscriptionTier, UpsellOpportunity } from '@/types/billing';

/**
 * Admin Usage Analytics Page
 *
 * Spec 020 - User Story 4: Usage Analytics for Admins
 *
 * Provides platform-level usage analytics:
 * - Aggregate statistics across all tenants
 * - Tenants by tier distribution
 * - Upsell opportunities (tenants approaching limits)
 */
export default function AdminUsagePage() {
  const router = useRouter();
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [stats, setStats] = useState<AdminUsageStats | null>(null);
  const [opportunities, setOpportunities] = useState<UpsellOpportunity[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTier, setSelectedTier] = useState<SubscriptionTier | ''>('');

  // Check super admin role
  useEffect(() => {
    if (!isLoaded) return;

    if (!isSignedIn) {
      router.push('/sign-in');
      return;
    }

    // Check for super_admin role in public metadata
    const role = user?.publicMetadata?.role as string | undefined;
    const isSuperAdmin = role === 'super_admin';

    if (!isSuperAdmin) {
      setIsAuthorized(false);
    } else {
      setIsAuthorized(true);
    }
  }, [isLoaded, isSignedIn, user, router]);

  // Fetch data
  useEffect(() => {
    async function fetchData() {
      if (!isAuthorized) return;

      try {
        setIsLoading(true);
        const token = await getToken();
        setAuthToken(token);

        const [statsData, opportunitiesData] = await Promise.all([
          getAdminUsageStats(),
          getUpsellOpportunities(80, selectedTier || undefined),
        ]);

        setStats(statsData);
        setOpportunities(opportunitiesData.opportunities);
      } catch (err) {
        console.error('Failed to fetch admin usage data:', err);
        setError('Failed to load usage analytics');
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [isAuthorized, getToken, selectedTier]);

  // Loading state
  if (!isLoaded || isAuthorized === null) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  // Unauthorized state
  if (!isAuthorized) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 bg-status-danger/10 rounded-full flex items-center justify-center mx-auto">
            <AlertCircle className="w-8 h-8 text-status-danger" />
          </div>
          <h1 className="mt-6 text-xl font-bold text-foreground">Access Denied</h1>
          <p className="mt-3 text-muted-foreground">
            You don&apos;t have permission to access Usage Analytics.
            This page is restricted to super administrators only.
          </p>
          <button
            onClick={() => router.push('/dashboard')}
            className="mt-6 px-6 py-2.5 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/90 transition-colors"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const tierColors: Record<SubscriptionTier, string> = {
    starter: 'bg-muted text-muted-foreground',
    professional: 'bg-primary/10 text-primary',
    growth: 'bg-accent text-accent-foreground',
    enterprise: 'bg-status-warning/10 text-status-warning',
  };

  return (
    <div className="space-y-5">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-bold text-foreground">Usage Analytics</h1>
        <p className="text-muted-foreground mt-1">
          Platform-wide usage statistics and upsell opportunities
        </p>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 bg-status-danger/10 border border-status-danger/20 rounded-lg text-status-danger">
          {error}
        </div>
      )}

      {/* Loading State */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : stats ? (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-card rounded-lg border border-border p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                  <Users className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Total Tenants</p>
                  <p className="text-2xl font-bold text-foreground tabular-nums">{stats.total_tenants}</p>
                </div>
              </div>
            </div>

            <div className="bg-card rounded-lg border border-border p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-status-success/10 rounded-lg flex items-center justify-center">
                  <BarChart3 className="w-5 h-5 text-status-success" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Total Clients</p>
                  <p className="text-2xl font-bold text-foreground tabular-nums">{stats.total_clients}</p>
                </div>
              </div>
            </div>

            <div className="bg-card rounded-lg border border-border p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-status-warning/10 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-status-warning" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Avg Clients/Tenant</p>
                  <p className="text-2xl font-bold text-foreground tabular-nums">
                    {stats.average_clients_per_tenant.toFixed(1)}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-card rounded-lg border border-border p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-status-danger/10 rounded-lg flex items-center justify-center">
                  <AlertCircle className="w-5 h-5 text-status-danger" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">At Limit</p>
                  <p className="text-2xl font-bold text-foreground tabular-nums">
                    {stats.tenants_at_limit}
                    <span className="text-sm font-normal text-muted-foreground ml-1">
                      ({stats.tenants_approaching_limit} approaching)
                    </span>
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Tier Distribution */}
          <div className="bg-card rounded-lg border border-border p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">
              Tenants by Tier
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {(['starter', 'professional', 'growth', 'enterprise'] as SubscriptionTier[]).map(
                (tier) => (
                  <div
                    key={tier}
                    className={`p-4 rounded-lg ${tierColors[tier]}`}
                  >
                    <p className="text-sm font-medium capitalize">{tier}</p>
                    <p className="text-2xl font-bold tabular-nums">
                      {stats.tenants_by_tier[tier] || 0}
                    </p>
                  </div>
                )
              )}
            </div>
          </div>

          {/* Upsell Opportunities */}
          <div className="bg-card rounded-lg border border-border">
            <div className="p-6 border-b border-border">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    Upsell Opportunities
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Tenants at 80%+ of their client limit
                  </p>
                </div>
                <select
                  value={selectedTier}
                  onChange={(e) => setSelectedTier(e.target.value as SubscriptionTier | '')}
                  className="rounded-lg border border-border bg-card text-foreground px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                >
                  <option value="">All tiers</option>
                  <option value="starter">Starter</option>
                  <option value="professional">Professional</option>
                  <option value="growth">Growth</option>
                </select>
              </div>
            </div>

            {opportunities.length === 0 ? (
              <div className="p-8 text-center">
                <TrendingUp className="h-12 w-12 text-muted-foreground/40 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-foreground mb-2">
                  No upsell opportunities
                </h3>
                <p className="text-muted-foreground">
                  No tenants are currently approaching their client limits.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-muted">
                      <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Tenant
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Owner
                      </th>
                      <th className="px-4 py-2 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Tier
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Usage
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Percentage
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {opportunities.map((opp) => (
                      <tr
                        key={opp.tenant_id}
                        className="hover:bg-muted cursor-pointer"
                        onClick={() =>
                          router.push(`/admin/usage/${opp.tenant_id}`)
                        }
                      >
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-foreground">
                              {opp.tenant_name}
                            </span>
                            <ArrowUpRight className="h-4 w-4 text-muted-foreground" />
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-sm text-muted-foreground">
                          {opp.owner_email}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${tierColors[opp.current_tier]}`}
                          >
                            {opp.current_tier}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-sm text-foreground text-right">
                          {opp.client_count} / {opp.client_limit}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-24 bg-muted rounded-full h-2">
                              <div
                                className={`h-2 rounded-full ${
                                  opp.percentage_used >= 100
                                    ? 'bg-status-danger'
                                    : opp.percentage_used >= 90
                                      ? 'bg-status-warning'
                                      : 'bg-primary'
                                }`}
                                style={{
                                  width: `${Math.min(opp.percentage_used, 100)}%`,
                                }}
                              />
                            </div>
                            <span
                              className={`text-sm font-medium ${
                                opp.percentage_used >= 100
                                  ? 'text-status-danger'
                                  : opp.percentage_used >= 90
                                    ? 'text-status-warning'
                                    : 'text-foreground'
                              }`}
                            >
                              {opp.percentage_used.toFixed(0)}%
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
