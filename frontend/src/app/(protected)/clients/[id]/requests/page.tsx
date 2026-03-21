'use client';

/**
 * Client Requests List Page
 *
 * Shows all document requests for a specific client with filtering
 * and quick actions.
 */

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  Eye,
  FileText,
  Loader2,
  MoreHorizontal,
  Plus,
  Send,
  XCircle,
} from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  type DocumentRequest,
  type RequestPriority,
  type RequestStatus,
  useRequestsApi,
} from '@/lib/api/requests';
import { apiClient } from '@/lib/api-client';
import { cn } from '@/lib/utils';

// Status configuration
const STATUS_CONFIG: Record<
  RequestStatus,
  { label: string; color: string; icon: React.ElementType }
> = {
  draft: { label: 'Draft', color: 'bg-muted text-muted-foreground', icon: FileText },
  pending: { label: 'Pending', color: 'bg-status-warning/10 text-status-warning', icon: Send },
  viewed: { label: 'Viewed', color: 'bg-primary/10 text-primary', icon: Eye },
  in_progress: { label: 'In Progress', color: 'bg-accent text-accent-foreground', icon: Clock },
  complete: { label: 'Complete', color: 'bg-status-success/10 text-status-success', icon: CheckCircle2 },
  cancelled: { label: 'Cancelled', color: 'bg-status-danger/10 text-status-danger', icon: XCircle },
};

const PRIORITY_CONFIG: Record<RequestPriority, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-muted text-muted-foreground' },
  normal: { label: 'Normal', color: 'bg-primary/10 text-primary' },
  high: { label: 'High', color: 'bg-status-warning/10 text-status-warning' },
  urgent: { label: 'Urgent', color: 'bg-status-danger/10 text-status-danger' },
};

interface ClientInfo {
  id: string;
  organization_name: string;
}

export default function ClientRequestsPage() {
  const params = useParams();
  const router = useRouter();
  const connectionId = params.id as string;
  const { getToken } = useAuth();
  const api = useRequestsApi();

  const [requests, setRequests] = useState<DocumentRequest[]>([]);
  const [client, setClient] = useState<ClientInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<RequestStatus | 'all'>('all');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Fetch client info
  const fetchClient = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const response = await apiClient.get(
        `/api/v1/clients/${connectionId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await apiClient.handleResponse<ClientInfo>(response);
      setClient(data);
    } catch (err) {
      console.error('Failed to fetch client:', err);
    }
  }, [connectionId, getToken]);

  // Fetch requests
  const fetchRequests = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.requests.listByClient(connectionId, {
        status: statusFilter === 'all' ? undefined : statusFilter,
      });
      setRequests(response.requests);
    } catch (err) {
      console.error('Failed to fetch requests:', err);
      setError('Failed to load requests');
    } finally {
      setLoading(false);
    }
  }, [api.requests, connectionId, statusFilter]);

  useEffect(() => {
    fetchClient();
    fetchRequests();
  }, [fetchClient, fetchRequests]);

  // Action handlers
  const handleSend = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      await api.requests.send(requestId);
      await fetchRequests();
    } catch (err) {
      console.error('Failed to send request:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      await api.requests.cancel(requestId);
      await fetchRequests();
    } catch (err) {
      console.error('Failed to cancel request:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleComplete = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      await api.requests.complete(requestId);
      await fetchRequests();
    } catch (err) {
      console.error('Failed to complete request:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // Format date
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  // Normalize status/priority to lowercase for config lookups
  const normalizeStatus = (status: string) => status.toLowerCase() as RequestStatus;
  const normalizePriority = (priority: string) => priority.toLowerCase() as RequestPriority;

  // Get counts by status (normalize to lowercase)
  const statusCounts = requests.reduce(
    (acc, req) => {
      const status = normalizeStatus(req.status);
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const pendingCount =
    (statusCounts['pending'] || 0) +
    (statusCounts['viewed'] || 0) +
    (statusCounts['in_progress'] || 0);

  return (
    <div className="container max-w-6xl py-6">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Link href={`/clients/${connectionId}`}>
              <Button variant="ghost" size="sm" className="gap-1 -ml-2">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            </Link>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Document Requests</h1>
          <p className="text-muted-foreground">
            {client?.organization_name || 'Loading...'} - Manage document requests
          </p>
        </div>
        <Link href={`/clients/${connectionId}/requests/new`}>
          <Button className="gap-2">
            <Plus className="h-4 w-4" />
            New Request
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{requests.length}</div>
            <p className="text-sm text-muted-foreground">Total Requests</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-status-warning">{pendingCount}</div>
            <p className="text-sm text-muted-foreground">Awaiting Response</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-status-success">
              {statusCounts['complete'] || 0}
            </div>
            <p className="text-sm text-muted-foreground">Completed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-status-danger">
              {requests.filter((r) => r.is_overdue).length}
            </div>
            <p className="text-sm text-muted-foreground">Overdue</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter(v as RequestStatus | 'all')}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="viewed">Viewed</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="complete">Complete</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Request List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-status-danger mx-auto mb-4" />
            <p className="text-muted-foreground">{error}</p>
            <Button variant="outline" className="mt-4" onClick={() => fetchRequests()}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      ) : requests.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="font-semibold mb-2">No requests found</h3>
            <p className="text-muted-foreground mb-4">
              {statusFilter === 'all'
                ? "You haven't created any document requests for this client yet."
                : `No requests with status "${STATUS_CONFIG[statusFilter].label}".`}
            </p>
            <Link href={`/clients/${connectionId}/requests/new`}>
              <Button className="gap-2">
                <Plus className="h-4 w-4" />
                Create First Request
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Requests ({requests.length})</CardTitle>
            <CardDescription>
              Click on a request to view details and responses
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {requests.map((request) => {
                const status = normalizeStatus(request.status);
                const priority = normalizePriority(request.priority);
                const statusConfig = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
                const priorityConfig = PRIORITY_CONFIG[priority] || PRIORITY_CONFIG.normal;
                const StatusIcon = statusConfig.icon;

                return (
                  <div
                    key={request.id}
                    className="py-4 first:pt-0 last:pb-0 hover:bg-muted/50 -mx-6 px-6 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-medium truncate">{request.title}</h4>
                          <Badge className={cn('text-xs', statusConfig.color)}>
                            <StatusIcon className="h-3 w-3 mr-1" />
                            {statusConfig.label}
                          </Badge>
                          {priority !== 'normal' && (
                            <Badge className={cn('text-xs', priorityConfig.color)}>
                              {priorityConfig.label}
                            </Badge>
                          )}
                          {request.is_overdue && (
                            <Badge className="text-xs bg-status-danger/10 text-status-danger">
                              Overdue
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                          {request.description}
                        </p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            Due: {formatDate(request.due_date)}
                          </span>
                          {request.sent_at && (
                            <span className="flex items-center gap-1">
                              <Send className="h-3 w-3" />
                              Sent: {formatDate(request.sent_at)}
                            </span>
                          )}
                          {request.document_count > 0 && (
                            <span className="flex items-center gap-1">
                              <FileText className="h-3 w-3" />
                              {request.document_count} document
                              {request.document_count !== 1 ? 's' : ''} uploaded
                            </span>
                          )}
                        </div>
                      </div>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled={actionLoading === request.id}
                          >
                            {actionLoading === request.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <MoreHorizontal className="h-4 w-4" />
                            )}
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() =>
                              router.push(`/clients/${connectionId}/requests/${request.id}`)
                            }
                          >
                            <Eye className="h-4 w-4 mr-2" />
                            View Details
                          </DropdownMenuItem>

                          {status === 'draft' && (
                            <DropdownMenuItem onClick={() => handleSend(request.id)}>
                              <Send className="h-4 w-4 mr-2" />
                              Send Request
                            </DropdownMenuItem>
                          )}

                          {['pending', 'viewed', 'in_progress'].includes(status) && (
                            <>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => handleComplete(request.id)}>
                                <CheckCircle2 className="h-4 w-4 mr-2" />
                                Mark Complete
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => handleCancel(request.id)}
                                className="text-status-danger"
                              >
                                <XCircle className="h-4 w-4 mr-2" />
                                Cancel Request
                              </DropdownMenuItem>
                            </>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
