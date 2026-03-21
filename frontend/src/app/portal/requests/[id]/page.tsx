'use client';

import { useQuery } from '@tanstack/react-query';
import { format, formatDistanceToNow } from 'date-fns';
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
} from 'lucide-react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { RespondForm } from '@/components/portal/RespondForm';
import { NotificationPermission } from '@/components/pwa/NotificationPermission';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  type DocumentRequest,
  portalApi,
  portalTokenStorage,
} from '@/lib/api/portal';
import { cn } from '@/lib/utils';

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: React.ReactNode }
> = {
  draft: {
    label: 'Draft',
    color: 'bg-muted text-muted-foreground',
    icon: <FileText className="h-4 w-4" />,
  },
  pending: {
    label: 'Pending',
    color: 'bg-status-warning/10 text-status-warning',
    icon: <Clock className="h-4 w-4" />,
  },
  sent: {
    label: 'Sent',
    color: 'bg-status-warning/10 text-status-warning',
    icon: <Clock className="h-4 w-4" />,
  },
  viewed: {
    label: 'Viewed',
    color: 'bg-primary/10 text-primary',
    icon: <FileText className="h-4 w-4" />,
  },
  in_progress: {
    label: 'In Progress',
    color: 'bg-primary/10 text-primary',
    icon: <Clock className="h-4 w-4" />,
  },
  completed: {
    label: 'Complete',
    color: 'bg-status-success/10 text-status-success',
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  cancelled: {
    label: 'Cancelled',
    color: 'bg-muted text-muted-foreground',
    icon: <AlertCircle className="h-4 w-4" />,
  },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  low: { label: 'Low', color: 'bg-muted text-muted-foreground' },
  normal: { label: 'Normal', color: 'bg-primary/10 text-primary' },
  high: { label: 'High', color: 'bg-status-warning/10 text-status-warning' },
  urgent: { label: 'Urgent', color: 'bg-status-danger/10 text-status-danger' },
};

function RequestDetailSkeleton() {
  return (
    <div className="container max-w-4xl py-8 space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="space-y-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}

function canRespond(request: DocumentRequest): boolean {
  const status = request.status.toLowerCase();
  return ['pending', 'viewed', 'in_progress'].includes(status);
}

export default function PortalRequestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const requestId = params.id as string;
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  // Check authentication on client only
  useEffect(() => {
    const authenticated = portalTokenStorage.isAuthenticated();
    setIsAuthenticated(authenticated);
    if (!authenticated) {
      router.push('/portal/login');
    }
  }, [router]);

  // Mark that user has viewed a request (for notification prompt trigger)
  useEffect(() => {
    if (isAuthenticated) {
      localStorage.setItem('pwa-has-viewed-request', 'true');
    }
  }, [isAuthenticated]);

  const {
    data: request,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['portal-request', requestId],
    queryFn: () => portalApi.requests.get(requestId),
    staleTime: 1000 * 60, // 1 minute
    enabled: isAuthenticated === true,
  });

  const { data: responsesData } = useQuery({
    queryKey: ['portal-request-responses', requestId],
    queryFn: () => portalApi.requests.listResponses(requestId),
    enabled: isAuthenticated === true && !!request,
  });

  // Show loading while checking authentication
  if (isAuthenticated === null || isLoading) {
    return <RequestDetailSkeleton />;
  }

  // If not authenticated, useEffect will redirect
  if (!isAuthenticated) {
    return <RequestDetailSkeleton />;
  }

  if (error || !request) {
    return (
      <div className="container max-w-4xl py-8">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Failed to load request'}
          </AlertDescription>
        </Alert>
        <Button asChild className="mt-4">
          <Link href="/portal/dashboard">Back to Dashboard</Link>
        </Button>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[request.status] ?? STATUS_CONFIG.pending;
  const priorityConfig = PRIORITY_CONFIG[request.priority] ?? PRIORITY_CONFIG.normal;

  // TypeScript guards - these are guaranteed to exist due to fallbacks
  if (!statusConfig || !priorityConfig) {
    throw new Error('Invalid status or priority configuration');
  }

  return (
    <div className="container max-w-4xl py-8">
      {/* Back Button */}
      <Button variant="ghost" size="sm" asChild className="mb-6">
        <Link href="/portal/dashboard">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Dashboard
        </Link>
      </Button>

      {/* Request Header */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold">{request.title}</h1>
          <Badge className={cn('gap-1', statusConfig.color)}>
            {statusConfig.icon}
            {statusConfig.label}
          </Badge>
          <Badge variant="outline" className={priorityConfig.color}>
            {priorityConfig.label} Priority
          </Badge>
        </div>

        {request.is_overdue && (
          <Alert variant="destructive" className="mt-4">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Overdue</AlertTitle>
            <AlertDescription>
              This request is overdue. Please respond as soon as possible.
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Request Details Card */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Request Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Description */}
          <div>
            <h3 className="font-medium text-sm text-muted-foreground mb-2">
              Description
            </h3>
            <p className="whitespace-pre-wrap">{request.description}</p>
          </div>

          <Separator />

          {/* Metadata */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            {request.due_date && (
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">Due Date:</span>
                <span className={cn(request.is_overdue && 'text-destructive font-medium')}>
                  {format(new Date(request.due_date), 'PPP')}
                  {request.days_until_due !== null && (
                    <span className="ml-1 text-muted-foreground">
                      ({request.days_until_due > 0
                        ? `${request.days_until_due} days left`
                        : request.days_until_due === 0
                          ? 'Due today'
                          : `${Math.abs(request.days_until_due)} days overdue`})
                    </span>
                  )}
                </span>
              </div>
            )}

            {request.sent_at && (
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">Received:</span>
                <span>
                  {formatDistanceToNow(new Date(request.sent_at), { addSuffix: true })}
                </span>
              </div>
            )}

            {request.viewed_at && (
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">Viewed:</span>
                <span>
                  {formatDistanceToNow(new Date(request.viewed_at), { addSuffix: true })}
                </span>
              </div>
            )}

            {request.responded_at && (
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">First Response:</span>
                <span>
                  {formatDistanceToNow(new Date(request.responded_at), { addSuffix: true })}
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Previous Responses */}
      {responsesData && responsesData.total > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Your Responses</CardTitle>
            <CardDescription>
              You have submitted {responsesData.total} response{responsesData.total !== 1 ? 's' : ''}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {responsesData.responses.map((response) => (
                <div
                  key={response.id}
                  className="p-3 border rounded-lg bg-muted/30"
                >
                  {response.message && (
                    <p className="text-sm whitespace-pre-wrap">{response.message}</p>
                  )}
                  {response.submitted_at && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Submitted {formatDistanceToNow(new Date(response.submitted_at), { addSuffix: true })}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Response Form */}
      {canRespond(request) ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Submit Response</CardTitle>
            <CardDescription>
              Provide a message and/or upload documents to respond to this request.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RespondForm
              requestId={requestId}
              onSuccess={() => refetch()}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            {request.status.toLowerCase() === 'complete' && (
              <div className="flex flex-col items-center gap-2">
                <CheckCircle2 className="h-8 w-8 text-status-success" />
                <p>This request has been completed.</p>
              </div>
            )}
            {request.status.toLowerCase() === 'cancelled' && (
              <div className="flex flex-col items-center gap-2">
                <AlertCircle className="h-8 w-8 text-muted-foreground" />
                <p>This request has been cancelled.</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Push Notification Permission Prompt */}
      <NotificationPermission trigger="after-first-request" />
    </div>
  );
}
