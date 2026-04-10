'use client';

import { useAuth } from '@clerk/nextjs';
import { Download, ScrollText } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatDate } from '@/lib/formatters';

interface AuditEvent {
  id: string;
  occurred_at: string;
  event_type: string;
  event_category: string;
  actor_email: string | null;
  resource_type: string | null;
  resource_id: string | null;
  action: string;
  outcome: string;
  metadata: Record<string, unknown> | null;
}

interface AuditSummary {
  total_events: number;
  by_category: Record<string, number>;
  ai_suggestions: {
    approved: number;
    modified: number;
    rejected: number;
    total: number;
  };
}

export default function AuditLogPage() {
  const { getToken } = useAuth();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Filters
  const [eventType, setEventType] = useState<string>('');
  const [category, setCategory] = useState<string>('all');

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const token = await getToken();
      const params = new URLSearchParams({
        page: String(page),
        per_page: '50',
      });
      if (eventType) params.set('event_type', eventType);
      if (category && category !== 'all') params.set('event_category', category);

      const res = await fetch(`/api/v1/admin/audit?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setEvents(data.items);
        setTotalPages(data.pages);
        setTotal(data.total);
      }
    } catch {
      // ignore
    }
    setLoading(false);
  }, [getToken, page, eventType, category]);

  const fetchSummary = useCallback(async () => {
    try {
      const token = await getToken();
      const res = await fetch('/api/v1/admin/audit/summary', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setSummary(await res.json());
    } catch {
      // ignore
    }
  }, [getToken]);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  async function handleExport() {
    const token = await getToken();
    const params = new URLSearchParams();
    if (eventType) params.set('event_type', eventType);
    if (category && category !== 'all') params.set('event_category', category);

    const res = await fetch(`/api/v1/admin/audit/export?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit_log.csv';
      a.click();
      URL.revokeObjectURL(url);
    }
  }

  const categoryColor = (cat: string) => {
    switch (cat) {
      case 'auth': return 'secondary';
      case 'data': return 'default';
      case 'compliance': return 'destructive';
      case 'integration': return 'outline';
      default: return 'secondary' as const;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ScrollText className="h-6 w-6" />
            Audit Log
          </h1>
          <p className="text-sm text-muted-foreground">
            Immutable record of all platform events
          </p>
        </div>
        <Button variant="outline" onClick={handleExport}>
          <Download className="h-4 w-4 mr-2" />
          Export CSV
        </Button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Events</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{summary.total_events.toLocaleString()}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">AI Approved</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-green-600">{summary.ai_suggestions.approved}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">AI Modified</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-amber-600">{summary.ai_suggestions.modified}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">AI Rejected</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-600">{summary.ai_suggestions.rejected}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-4">
        <Input
          placeholder="Filter by event type (e.g. ai.tax_planning)"
          value={eventType}
          onChange={(e) => { setEventType(e.target.value); setPage(1); }}
          className="max-w-xs"
        />
        <Select value={category} onValueChange={(v) => { setCategory(v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="auth">Auth</SelectItem>
            <SelectItem value="data">Data</SelectItem>
            <SelectItem value="compliance">Compliance</SelectItem>
            <SelectItem value="integration">Integration</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Events Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-auto">Time</TableHead>
                <TableHead>Event</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Outcome</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Loading...
                  </TableCell>
                </TableRow>
              ) : events.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    No audit events found
                  </TableCell>
                </TableRow>
              ) : (
                events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(event.occurred_at)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {event.event_type}
                    </TableCell>
                    <TableCell>
                      <Badge variant={categoryColor(event.event_category)}>
                        {event.event_category}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {event.actor_email || '—'}
                    </TableCell>
                    <TableCell className="text-xs">{event.action}</TableCell>
                    <TableCell>
                      <Badge variant={event.outcome === 'success' ? 'default' : 'destructive'}>
                        {event.outcome}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {total.toLocaleString()} events total
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <span className="flex items-center text-sm px-2">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
