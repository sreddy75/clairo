'use client';

/**
 * Request Detail Page
 *
 * Shows details of a specific document request including status,
 * responses, and uploaded documents.
 */

import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  Eye,
  FileText,
  Loader2,
  Mail,
  MessageSquare,
  MoreHorizontal,
  Send,
  Upload,
  XCircle,
} from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
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
import { Separator } from '@/components/ui/separator';
import {
  type DocumentRequestDetail,
  type RequestPriority,
  type RequestStatus,
  useRequestsApi,
} from '@/lib/api/requests';
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

// Event type configuration for activity timeline
const getEventConfig = (eventType: string): { label: string; color: string; icon: React.ElementType } => {
  const configs: Record<string, { label: string; color: string; icon: React.ElementType }> = {
    CREATED: { label: 'Request created', color: 'text-muted-foreground', icon: FileText },
    SENT: { label: 'Request sent', color: 'text-status-warning', icon: Send },
    VIEWED: { label: 'Request viewed', color: 'text-primary', icon: Eye },
    RESPONDED: { label: 'Response submitted', color: 'text-status-success', icon: Upload },
    COMPLETED: { label: 'Request completed', color: 'text-status-success', icon: CheckCircle2 },
    CANCELLED: { label: 'Request cancelled', color: 'text-status-danger', icon: XCircle },
    REMINDER_SENT: { label: 'Reminder sent', color: 'text-status-warning', icon: Clock },
    UPDATED: { label: 'Request updated', color: 'text-accent-foreground', icon: FileText },
    // Portal specific events
    PORTAL_VIEWED: { label: 'Viewed in portal', color: 'text-primary', icon: Eye },
    DOCUMENT_UPLOADED: { label: 'Document uploaded', color: 'text-status-success', icon: Upload },
  };

  return configs[eventType] || { label: eventType, color: 'text-muted-foreground', icon: Clock };
};

export default function RequestDetailPage() {
  const params = useParams();
  const connectionId = params.id as string;
  const requestId = params.requestId as string;
  const api = useRequestsApi();

  const [request, setRequest] = useState<DocumentRequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Normalize status/priority to lowercase for config lookups
  const normalizeStatus = (status: string) => status.toLowerCase() as RequestStatus;
  const normalizePriority = (priority: string) => priority.toLowerCase() as RequestPriority;

  // Fetch request details
  const fetchRequest = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.requests.get(requestId);
      setRequest(data);
    } catch (err) {
      console.error('Failed to fetch request:', err);
      setError('Failed to load request details');
    } finally {
      setLoading(false);
    }
  }, [api.requests, requestId]);

  useEffect(() => {
    fetchRequest();
  }, [fetchRequest]);

  // Action handlers
  const handleSend = async () => {
    setActionLoading(true);
    try {
      await api.requests.send(requestId);
      await fetchRequest();
    } catch (err) {
      console.error('Failed to send request:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    setActionLoading(true);
    try {
      await api.requests.cancel(requestId);
      await fetchRequest();
    } catch (err) {
      console.error('Failed to cancel request:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = async () => {
    setActionLoading(true);
    try {
      await api.requests.complete(requestId);
      await fetchRequest();
    } catch (err) {
      console.error('Failed to complete request:', err);
    } finally {
      setActionLoading(false);
    }
  };

  // Format date
  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatDateTime = (dateStr: string | null | undefined) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('en-AU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Handle document download
  const handleDownload = async (documentId: string, filename: string) => {
    try {
      await api.documents.download(documentId, filename);
    } catch (err) {
      console.error('Failed to download document:', err);
    }
  };

  if (loading) {
    return (
      <div className="container max-w-4xl py-6">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error || !request) {
    return (
      <div className="container max-w-4xl py-6">
        <Card>
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-status-danger mx-auto mb-4" />
            <p className="text-muted-foreground">{error || 'Request not found'}</p>
            <Link href={`/clients/${connectionId}/requests`}>
              <Button variant="outline" className="mt-4">
                Back to Requests
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const status = normalizeStatus(request.status);
  const priority = normalizePriority(request.priority);
  const statusConfig = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const priorityConfig = PRIORITY_CONFIG[priority] || PRIORITY_CONFIG.normal;
  const StatusIcon = statusConfig.icon;

  return (
    <div className="container max-w-4xl py-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Link href={`/clients/${connectionId}/requests`}>
            <Button variant="ghost" size="sm" className="gap-1 -ml-2">
              <ArrowLeft className="h-4 w-4" />
              Back to Requests
            </Button>
          </Link>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <h1 className="text-2xl font-bold tracking-tight">{request.title}</h1>
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
                <Badge className="text-xs bg-status-danger/10 text-status-danger">Overdue</Badge>
              )}
            </div>
            <p className="text-muted-foreground">Request ID: {request.id}</p>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" disabled={actionLoading}>
                {actionLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <MoreHorizontal className="h-4 w-4 mr-2" />
                )}
                Actions
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {status === 'draft' && (
                <DropdownMenuItem onClick={handleSend}>
                  <Send className="h-4 w-4 mr-2" />
                  Send Request
                </DropdownMenuItem>
              )}

              {['pending', 'viewed', 'in_progress'].includes(status) && (
                <>
                  <DropdownMenuItem onClick={handleComplete}>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Mark Complete
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleCancel} className="text-status-danger">
                    <XCircle className="h-4 w-4 mr-2" />
                    Cancel Request
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="grid gap-6">
        {/* Request Details */}
        <Card>
          <CardHeader>
            <CardTitle>Request Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-1">Description</h4>
              <p className="text-sm whitespace-pre-wrap">{request.description}</p>
            </div>

            <Separator />

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  <Mail className="h-3 w-3 inline mr-1" />
                  Recipient
                </h4>
                <p className="text-sm">{request.recipient_email}</p>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  <Calendar className="h-3 w-3 inline mr-1" />
                  Due Date
                </h4>
                <p className="text-sm">{formatDate(request.due_date)}</p>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  <Send className="h-3 w-3 inline mr-1" />
                  Sent
                </h4>
                <p className="text-sm">{formatDateTime(request.sent_at)}</p>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-1">
                  <Eye className="h-3 w-3 inline mr-1" />
                  First Viewed
                </h4>
                <p className="text-sm">{formatDateTime(request.first_viewed_at)}</p>
              </div>
            </div>

            {(request.period_start || request.period_end) && (
              <>
                <Separator />
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-1">
                      Period Start
                    </h4>
                    <p className="text-sm">{formatDate(request.period_start)}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground mb-1">
                      Period End
                    </h4>
                    <p className="text-sm">{formatDate(request.period_end)}</p>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Responses & Documents */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Responses & Documents
            </CardTitle>
            <CardDescription>
              Documents uploaded by the client in response to this request
            </CardDescription>
          </CardHeader>
          <CardContent>
            {request.responses && request.responses.length > 0 ? (
              <div className="space-y-4">
                {request.responses.map((response) => (
                  <div
                    key={response.id}
                    className="border rounded-lg p-4 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-status-success" />
                        <span className="font-medium">Response Submitted</span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {formatDateTime(response.submitted_at)}
                      </span>
                    </div>
                    {response.note && (
                      <div className="flex items-start gap-2 pl-6">
                        <MessageSquare className="h-4 w-4 text-muted-foreground mt-0.5" />
                        <p className="text-sm text-muted-foreground">
                          {response.note}
                        </p>
                      </div>
                    )}
                    {response.documents && response.documents.length > 0 && (
                      <div className="pl-6 space-y-2">
                        <div className="text-sm font-medium text-muted-foreground">
                          Attached Documents:
                        </div>
                        {response.documents.map((doc) => (
                          <div
                            key={doc.id}
                            className="flex items-center justify-between bg-muted/50 rounded-md p-2"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <FileText className="h-4 w-4 text-primary flex-shrink-0" />
                              <div className="min-w-0">
                                <p className="text-sm font-medium truncate">
                                  {doc.original_filename}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {formatFileSize(doc.file_size)} • {doc.content_type.split('/')[1]?.toUpperCase() || doc.content_type}
                                </p>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDownload(doc.id, doc.original_filename)}
                              className="flex-shrink-0"
                            >
                              <Download className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                <div className="pt-2 border-t">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <FileText className="h-4 w-4" />
                    <span>Total: {request.document_count} document(s) uploaded</span>
                  </div>
                </div>
              </div>
            ) : request.document_count > 0 ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  <span>{request.document_count} document(s) uploaded</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <Upload className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No documents uploaded yet</p>
                <p className="text-sm mt-1">
                  Documents will appear here once the client uploads them
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Activity Timeline */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Show events from API (sorted by newest first) */}
              {request.events && request.events.length > 0 ? (
                [...request.events]
                  .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                  .map((event) => {
                    const eventConfig = getEventConfig(event.event_type);
                    const EventIcon = eventConfig.icon;
                    return (
                      <div key={event.id} className="flex items-start gap-3">
                        <EventIcon className={cn('h-5 w-5 mt-0.5', eventConfig.color)} />
                        <div>
                          <p className="text-sm font-medium">
                            {eventConfig.label}
                            {event.actor_type === 'CLIENT' && (
                              <span className="text-muted-foreground font-normal"> by client</span>
                            )}
                          </p>
                          {event.event_data && typeof event.event_data.document_count === 'number' && (
                            <p className="text-xs text-muted-foreground">
                              {event.event_data.document_count as number} document(s) attached
                            </p>
                          )}
                          <p className="text-xs text-muted-foreground">
                            {formatDateTime(event.created_at)}
                          </p>
                        </div>
                      </div>
                    );
                  })
              ) : (
                // Fallback to basic timeline from request fields
                <>
                  {request.completed_at && (
                    <div className="flex items-start gap-3">
                      <CheckCircle2 className="h-5 w-5 text-status-success mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Request completed</p>
                        <p className="text-xs text-muted-foreground">
                          {formatDateTime(request.completed_at)}
                        </p>
                      </div>
                    </div>
                  )}

                  {request.first_viewed_at && (
                    <div className="flex items-start gap-3">
                      <Eye className="h-5 w-5 text-primary mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">First viewed by client</p>
                        <p className="text-xs text-muted-foreground">
                          {formatDateTime(request.first_viewed_at)}
                        </p>
                      </div>
                    </div>
                  )}

                  {request.sent_at && (
                    <div className="flex items-start gap-3">
                      <Send className="h-5 w-5 text-status-warning mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Request sent to {request.recipient_email}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatDateTime(request.sent_at)}
                        </p>
                      </div>
                    </div>
                  )}

                  <div className="flex items-start gap-3">
                    <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="text-sm font-medium">Request created</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDateTime(request.created_at)}
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
