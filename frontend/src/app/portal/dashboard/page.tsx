'use client';

import { Building2, ClipboardList, LogOut, Loader2, RefreshCw, AlertCircle, WifiOff } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, useCallback } from 'react';

import { DashboardStats, BASStatusCard, RecentRequestsCard } from '@/components/portal/DashboardCards';
import { OfflineIndicator
 } from '@/components/pwa';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import {
  portalApi,
  portalTokenStorage,
  PortalApiError,
  type DashboardResponse,
  type BASStatusResponse,
} from '@/lib/api/portal';
import {
  updateDashboardCache,
  getOfflineDashboard,
  formatCacheAge,
} from '@/lib/pwa/cached-dashboard';
import { isIndexedDBAvailable } from '@/lib/pwa/db';

export default function PortalDashboardPage() {
  const router = useRouter();
  const { isOnline } = useNetworkStatus();
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [basStatus, setBASStatus] = useState<BASStatusResponse | null>(null);
  const [businessName, setBusinessName] = useState<string | null>(null);
  const [isOfflineData, setIsOfflineData] = useState(false);
  const [cacheAge, setCacheAge] = useState<string | null>(null);
  const [pendingClassifications, setPendingClassifications] = useState<Array<{
    id: string;
    status: string;
    transaction_count: number;
    classified_count: number;
    message: string | null;
    expires_at: string | null;
  }>>([]);

  // Load cached data for offline fallback
  const loadCachedData = useCallback(async () => {
    if (!isIndexedDBAvailable()) return false;

    try {
      const cached = await getOfflineDashboard();
      if (cached?.data) {
        // Convert cached data to DashboardResponse format
        const cachedData = cached.data;
        setDashboard({
          connection_id: cachedData.connectionId,
          organization_name: cachedData.organizationName,
          pending_requests: cachedData.pendingRequests,
          unread_requests: cachedData.unreadRequests,
          total_documents: cachedData.totalDocuments,
          recent_requests: cachedData.recentRequests.map((r) => ({
            id: r.id,
            connection_id: cachedData.connectionId,
            template_id: null,
            title: r.title,
            description: r.description,
            status: r.status as 'draft' | 'sent' | 'viewed' | 'in_progress' | 'completed' | 'cancelled',
            priority: r.priority as 'low' | 'normal' | 'high' | 'urgent',
            due_date: r.dueDate,
            sent_at: r.sentAt,
            viewed_at: r.viewedAt,
            responded_at: r.respondedAt,
            completed_at: null,
            is_overdue: r.isOverdue,
            days_until_due: r.daysUntilDue,
            created_at: r.sentAt || new Date().toISOString(),
            updated_at: r.respondedAt || r.viewedAt || r.sentAt || new Date().toISOString(),
          })),
          last_activity_at: null,
        });
        setBusinessName(cachedData.organizationName);
        setIsOfflineData(true);
        if (cached.cacheAge) {
          setCacheAge(formatCacheAge(cached.cacheAge));
        }
        return true;
      }
    } catch (err) {
      console.warn('[Dashboard] Failed to load cached data:', err);
    }
    return false;
  }, []);

  const fetchDashboardData = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) {
      setIsRefreshing(true);
    }
    setError(null);

    try {
      const [dashboardData, basData] = await Promise.all([
        portalApi.dashboard.getDashboard(),
        portalApi.dashboard.getBASStatus(),
      ]);

      setDashboard(dashboardData);
      setBASStatus(basData);
      setBusinessName(dashboardData.organization_name);
      setIsOfflineData(false);
      setCacheAge(null);

      // Fetch pending classification requests
      try {
        const classificationData = await portalApi.classify.getPending();
        setPendingClassifications(classificationData);
      } catch {
        // Non-critical — don't block dashboard if this fails
      }

      // Cache dashboard data for offline use
      if (isIndexedDBAvailable()) {
        try {
          await updateDashboardCache(dashboardData);
        } catch (err) {
          console.warn('[Dashboard] Failed to cache data:', err);
        }
      }
    } catch (err) {
      if (err instanceof PortalApiError) {
        if (err.status === 401) {
          // Token expired, try to refresh
          const refreshToken = portalTokenStorage.getRefreshToken();
          if (refreshToken) {
            try {
              const refreshResponse = await portalApi.auth.refreshToken(refreshToken);
              portalTokenStorage.setTokens(
                refreshResponse.access_token,
                refreshToken
              );
              // Retry the request
              await fetchDashboardData();
              return;
            } catch {
              // Refresh failed, redirect to login
              portalTokenStorage.clearTokens();
              router.push('/portal/login');
              return;
            }
          }
          router.push('/portal/login');
          return;
        }
        setError(err.message);
      } else {
        // Network error - try to load from cache
        const hasCachedData = await loadCachedData();
        if (!hasCachedData) {
          setError('You are offline and no cached data is available.');
        }
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [router, loadCachedData]);

  useEffect(() => {
    // Check if authenticated
    if (!portalTokenStorage.isAuthenticated()) {
      router.push('/portal/login');
      return;
    }

    // Get stored business name while loading
    setBusinessName(portalTokenStorage.getBusinessName());

    // If offline, try to load cached data first
    if (!navigator.onLine) {
      loadCachedData().then((hasCached) => {
        if (hasCached) {
          setIsLoading(false);
        } else {
          fetchDashboardData();
        }
      });
    } else {
      fetchDashboardData();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogout = async () => {
    try {
      const accessToken = portalTokenStorage.getAccessToken();
      if (accessToken) {
        await portalApi.auth.logout(accessToken);
      }
    } catch {
      // Ignore logout errors
    } finally {
      portalTokenStorage.clearTokens();
      router.push('/portal/login');
    }
  };

  const handleRefresh = () => {
    fetchDashboardData(true);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-2 text-muted-foreground">Loading your portal...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Building2 className="h-6 w-6 text-primary" />
              <div>
                <h1 className="font-semibold text-lg">{businessName || 'Client Portal'}</h1>
                <p className="text-xs text-muted-foreground">Client Portal</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4 mr-2" />
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Offline Indicator */}
      <OfflineIndicator />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Offline Data Warning */}
        {isOfflineData && (
          <Alert className="mb-6 border-status-warning/20 bg-status-warning/10">
            <WifiOff className="h-4 w-4 text-status-warning" />
            <AlertTitle className="text-status-warning">
              Viewing Cached Data
            </AlertTitle>
            <AlertDescription className="text-status-warning">
              You&apos;re viewing cached data{cacheAge ? ` from ${cacheAge}` : ''}.
              {isOnline
                ? ' Pull to refresh for the latest data.'
                : ' Connect to the internet to sync.'}
            </AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {dashboard && (
          <div className="space-y-6">
            {/* Welcome */}
            <div>
              <h2 className="text-2xl font-bold">Welcome back!</h2>
              <p className="text-muted-foreground">
                Here&apos;s an overview of your business activity and pending items.
              </p>
            </div>

            {/* Stats */}
            <DashboardStats data={dashboard} />

            {/* Pending Classification Requests */}
            {pendingClassifications.length > 0 && (
              <div className="space-y-3">
                {pendingClassifications.map((req) => (
                  <Card key={req.id} className="border-amber-200 bg-amber-50">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <ClipboardList className="h-5 w-5 text-amber-600" />
                          <div>
                            <p className="font-medium text-sm">
                              Your accountant needs you to classify {req.transaction_count} transaction{req.transaction_count !== 1 ? 's' : ''}
                            </p>
                            {req.message && (
                              <p className="text-xs text-muted-foreground mt-0.5">{req.message}</p>
                            )}
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {req.classified_count > 0
                                ? `${req.classified_count} of ${req.transaction_count} done`
                                : 'Not started yet'}
                            </p>
                          </div>
                        </div>
                        <Link href={`/portal/classify/${req.id}`}>
                          <Button size="sm" className="shrink-0">
                            {req.classified_count > 0 ? 'Continue' : 'Start'}
                          </Button>
                        </Link>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Main Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* BAS Status */}
              {basStatus && <BASStatusCard data={basStatus} />}

              {/* Quick Actions */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Quick Actions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button className="w-full justify-start" variant="outline">
                    <Building2 className="h-4 w-4 mr-2" />
                    View All Requests
                  </Button>
                  <Button className="w-full justify-start" variant="outline">
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Upload Documents
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Recent Requests */}
            <RecentRequestsCard requests={dashboard.recent_requests} />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto py-6 text-center text-sm text-muted-foreground border-t">
        <p>Secure access provided by your accountant</p>
        <p className="mt-1">&copy; {new Date().getFullYear()} Clairo</p>
      </footer>
    </div>
  );
}
