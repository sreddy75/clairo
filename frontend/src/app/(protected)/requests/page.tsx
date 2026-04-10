'use client';

import { useQuery } from '@tanstack/react-query';
import { Plus, RefreshCw, Search } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { RequestStatusBadge } from '@/components/requests/RequestStatusBadge';
import { RequestTrackingTable, TrackingStats } from '@/components/requests/RequestTrackingTable';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  type RequestStatus,
  type TrackingRequestItem,
  useRequestsApi,
} from '@/lib/api/requests';

export default function RequestsTrackingPage() {
  const api = useRequestsApi();
  const [statusFilter, setStatusFilter] = useState<RequestStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch tracking data
  const {
    data: trackingData,
    isLoading,
    error,
    refetch,
    isRefetching,
  } = useQuery({
    queryKey: ['requests-tracking', statusFilter],
    queryFn: () =>
      api.tracking.getData({
        status: statusFilter === 'all' ? undefined : statusFilter,
        page_size: 100,
      }),
    staleTime: 30000, // 30 seconds
  });

  // Filter requests by search query
  const filteredRequests =
    trackingData?.groups
      .flatMap((g) => g.requests)
      .filter((request) => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return (
          request.title.toLowerCase().includes(query) ||
          request.organization_name.toLowerCase().includes(query)
        );
      }) || [];

  // Group filtered requests by status
  const groupedByStatus = filteredRequests.reduce(
    (acc, request) => {
      const status = request.status;
      if (!acc[status]) acc[status] = [];
      acc[status].push(request);
      return acc;
    },
    {} as Record<RequestStatus, TrackingRequestItem[]>
  );

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Document Requests</h1>
          <p className="text-muted-foreground">
            Track and manage all document requests across your clients
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            disabled={isRefetching}
          >
            <RefreshCw className={`h-4 w-4 ${isRefetching ? 'animate-spin' : ''}`} />
          </Button>
          <Button asChild>
            <Link href="/requests/bulk">
              <Plus className="h-4 w-4 mr-2" />
              Bulk Request
            </Link>
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      {isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-20" />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : trackingData ? (
        <Card>
          <CardContent className="pt-6">
            <TrackingStats summary={trackingData.summary} />
          </CardContent>
        </Card>
      ) : null}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search requests or clients..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-status-danger/20 bg-status-danger/10">
          <CardContent className="pt-6">
            <p className="text-status-danger">
              Failed to load tracking data. Please try refreshing.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Tabbed View */}
      {!isLoading && trackingData && (
        <Tabs
          defaultValue="all"
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as RequestStatus | 'all')}
        >
          <TabsList>
            <TabsTrigger value="all">
              All ({trackingData.summary.total})
            </TabsTrigger>
            <TabsTrigger value="pending">
              Pending ({trackingData.summary.pending})
            </TabsTrigger>
            <TabsTrigger value="viewed">
              Viewed ({trackingData.summary.viewed})
            </TabsTrigger>
            <TabsTrigger value="in_progress">
              In Progress ({trackingData.summary.in_progress})
            </TabsTrigger>
            <TabsTrigger value="complete">
              Complete ({trackingData.summary.completed})
            </TabsTrigger>
          </TabsList>

          {/* All Requests */}
          <TabsContent value="all" className="space-y-4">
            {Object.entries(groupedByStatus).length === 0 ? (
              <RequestTrackingTable
                requests={[]}
                emptyMessage="No requests found matching your criteria"
              />
            ) : (
              Object.entries(groupedByStatus)
                .filter(([status]) => status !== 'draft' && status !== 'cancelled')
                .sort(([a], [b]) => {
                  // Sort order: pending, viewed, in_progress, complete
                  const order: Record<string, number> = {
                    pending: 0,
                    viewed: 1,
                    in_progress: 2,
                    complete: 3,
                  };
                  return (order[a] || 99) - (order[b] || 99);
                })
                .map(([status, requests]) => (
                  <Card key={status}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center gap-2">
                        <RequestStatusBadge status={status as RequestStatus} />
                        <span className="text-muted-foreground">
                          ({requests.length})
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <RequestTrackingTable requests={requests} />
                    </CardContent>
                  </Card>
                ))
            )}
          </TabsContent>

          {/* Filtered by Status */}
          {(['pending', 'viewed', 'in_progress', 'complete'] as RequestStatus[]).map(
            (status) => (
              <TabsContent key={status} value={status}>
                <Card>
                  <CardContent className="pt-6">
                    <RequestTrackingTable
                      requests={filteredRequests.filter((r) => r.status === status)}
                      emptyMessage={`No ${status.replace('_', ' ')} requests`}
                    />
                  </CardContent>
                </Card>
              </TabsContent>
            )
          )}
        </Tabs>
      )}

      {/* Loading State */}
      {isLoading && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
