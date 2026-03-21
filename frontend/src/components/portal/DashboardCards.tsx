'use client';

import { FileText, Bell, Upload, Calendar, Clock, AlertTriangle } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { DashboardResponse, BASStatusResponse, DocumentRequest } from '@/lib/api/portal';

interface DashboardStatsProps {
  data: DashboardResponse;
}

export function DashboardStats({ data }: DashboardStatsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Pending Requests */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Pending Requests
          </CardTitle>
          <Bell className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{data.pending_requests}</div>
          {data.unread_requests > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              <span className="text-status-warning font-medium">{data.unread_requests} unread</span>
            </p>
          )}
        </CardContent>
      </Card>

      {/* Total Documents */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Documents
          </CardTitle>
          <Upload className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{data.total_documents}</div>
          <p className="text-xs text-muted-foreground mt-1">
            Uploaded to your portal
          </p>
        </CardContent>
      </Card>

      {/* Last Activity */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Last Activity
          </CardTitle>
          <Clock className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {data.last_activity_at
              ? new Date(data.last_activity_at).toLocaleDateString()
              : 'Never'}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Portal activity
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

interface BASStatusCardProps {
  data: BASStatusResponse;
}

export function BASStatusCard({ data }: BASStatusCardProps) {
  const statusColors: Record<string, string> = {
    pending: 'bg-status-warning/10 text-status-warning',
    in_progress: 'bg-primary/10 text-primary',
    submitted: 'bg-status-success/10 text-status-success',
    overdue: 'bg-status-danger/10 text-status-danger',
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">BAS Status</CardTitle>
            <CardDescription>{data.current_quarter}</CardDescription>
          </div>
          <Badge className={statusColors[data.status] || statusColors.pending}>
            {data.status.replace('_', ' ').toUpperCase()}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Due Date</span>
          <span className="font-medium flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            {new Date(data.due_date).toLocaleDateString('en-AU', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </span>
        </div>

        {data.items_pending > 0 && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-status-warning/10">
            <AlertTriangle className="h-4 w-4 text-status-warning" />
            <span className="text-sm text-status-warning">
              {data.items_pending} item{data.items_pending > 1 ? 's' : ''} pending your action
            </span>
          </div>
        )}

        <div className="border-t pt-3 text-sm text-muted-foreground">
          Last lodged: {data.last_lodged} ({new Date(data.last_lodged_date).toLocaleDateString('en-AU')})
        </div>
      </CardContent>
    </Card>
  );
}

interface RecentRequestsCardProps {
  requests: DocumentRequest[];
}

export function RecentRequestsCard({ requests }: RecentRequestsCardProps) {
  const router = useRouter();

  const priorityColors: Record<string, string> = {
    low: 'bg-muted text-muted-foreground',
    normal: 'bg-primary/10 text-primary',
    high: 'bg-status-warning/10 text-status-warning',
    urgent: 'bg-status-danger/10 text-status-danger',
  };

  const statusIcons: Record<string, string> = {
    sent: 'text-primary',
    viewed: 'text-status-warning',
    in_progress: 'text-accent-foreground',
    completed: 'text-status-success',
  };

  if (requests.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Requests</CardTitle>
          <CardDescription>Document requests from your accountant</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>No document requests yet</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Recent Requests</CardTitle>
        <CardDescription>Document requests from your accountant</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {requests.map((request) => (
            <div
              key={request.id}
              className="flex items-start gap-3 p-3 rounded-lg border hover:bg-muted/50 transition-colors cursor-pointer"
              onClick={() => router.push(`/portal/requests/${request.id}`)}
            >
              <div className={`mt-1 ${statusIcons[request.status] || 'text-muted-foreground'}`}>
                <FileText className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium truncate">{request.title}</span>
                  <Badge variant="outline" className={priorityColors[request.priority]}>
                    {request.priority}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground truncate">
                  {request.description}
                </p>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                  {request.due_date && (
                    <span className={request.is_overdue ? 'text-status-danger' : ''}>
                      Due: {new Date(request.due_date).toLocaleDateString('en-AU')}
                    </span>
                  )}
                  <span>{request.status.replace('_', ' ')}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
