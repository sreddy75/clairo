'use client';

/**
 * Admin Usage Analytics Page
 *
 * Displays aggregate platform usage metrics and top users.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import { BarChart3, RefreshCw } from 'lucide-react';

import { usePlatformUsage } from '@/hooks/useAdminDashboard';

import { TopUsersTable } from '../components/TopUsersTable';
import { UsageAnalytics } from '../components/UsageAnalytics';

/**
 * Usage analytics page.
 */
export default function AnalyticsPage() {
  const { refetch, isFetching } = usePlatformUsage();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-3">
            <BarChart3 className="w-7 h-7 text-purple-600" />
            Usage Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Monitor platform-wide usage metrics and top tenants
          </p>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 bg-muted text-foreground rounded-lg hover:bg-muted/80 transition-colors disabled:opacity-50"
        >
          <RefreshCw
            className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`}
          />
          Refresh
        </button>
      </div>

      {/* Usage analytics */}
      <UsageAnalytics />

      {/* Top users table */}
      <TopUsersTable limit={15} />
    </div>
  );
}
