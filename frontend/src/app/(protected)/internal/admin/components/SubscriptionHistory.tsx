'use client';

/**
 * SubscriptionHistory Component
 *
 * Timeline of billing events for a tenant.
 *
 * Spec 022: Admin Dashboard (Internal)
 */

import {
  ArrowUpCircle,
  ArrowDownCircle,
  CreditCard,
  DollarSign,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
} from 'lucide-react';

import type { BillingEventSummary, ActivityItem } from '@/types/admin';

interface SubscriptionHistoryProps {
  events: BillingEventSummary[];
  activity: ActivityItem[];
  isLoading: boolean;
}

/**
 * Get icon for event type.
 */
function getEventIcon(eventType: string): React.ComponentType<{ className?: string }> {
  const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
    'subscription.created': CheckCircle,
    'subscription.updated': RefreshCw,
    'subscription.canceled': XCircle,
    'tier.upgraded': ArrowUpCircle,
    'tier.downgraded': ArrowDownCircle,
    'credit.applied': DollarSign,
    'payment.succeeded': CreditCard,
    'payment.failed': AlertTriangle,
    'admin.tier_changed': RefreshCw,
    'admin.credit_applied': DollarSign,
  };

  return iconMap[eventType] || RefreshCw;
}

/**
 * Get color for event type.
 */
function getEventColor(eventType: string): string {
  if (eventType.includes('upgraded') || eventType.includes('succeeded') || eventType.includes('created')) {
    return 'text-status-success bg-status-success/10';
  }
  if (eventType.includes('downgraded') || eventType.includes('canceled')) {
    return 'text-status-warning bg-status-warning/10';
  }
  if (eventType.includes('failed')) {
    return 'text-status-danger bg-status-danger/10';
  }
  if (eventType.includes('credit')) {
    return 'text-primary bg-primary/10';
  }
  return 'text-muted-foreground bg-muted';
}

/**
 * Format date to relative or absolute string.
 */
function formatEventDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return 'Today';
  } else if (diffDays === 1) {
    return 'Yesterday';
  } else if (diffDays < 7) {
    return `${diffDays} days ago`;
  } else {
    return date.toLocaleDateString('en-AU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }
}

/**
 * Format event type to readable string.
 */
function formatEventType(eventType: string): string {
  return eventType
    .replace(/\./g, ' ')
    .replace(/_/g, ' ')
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Event timeline item component.
 */
function EventItem({ event }: { event: BillingEventSummary }) {
  const Icon = getEventIcon(event.event_type);
  const colorClass = getEventColor(event.event_type);

  return (
    <div className="flex gap-4">
      {/* Icon */}
      <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${colorClass}`}>
        <Icon className="w-5 h-5" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">
              {formatEventType(event.event_type)}
            </p>
            {event.details && Object.keys(event.details).length > 0 && (
              <div className="mt-1 space-y-0.5">
                {Object.entries(event.details).map(([key, value]) => (
                  <p key={key} className="text-xs text-muted-foreground">
                    <span className="capitalize">{key.replace(/_/g, ' ')}</span>:{' '}
                    <span className="text-foreground">
                      {typeof value === 'number' && key.includes('cents')
                        ? `$${(value / 100).toFixed(2)}`
                        : String(value)}
                    </span>
                  </p>
                ))}
              </div>
            )}
          </div>
          <span className="text-xs text-muted-foreground flex-shrink-0">
            {formatEventDate(event.created_at)}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Activity timeline item component.
 */
function ActivityItemRow({ item }: { item: ActivityItem }) {
  return (
    <div className="flex gap-4">
      {/* Dot */}
      <div className="flex-shrink-0 w-10 flex justify-center">
        <div className="w-2 h-2 mt-2 rounded-full bg-muted" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-foreground">{item.description}</p>
            {item.user && (
              <p className="text-xs text-muted-foreground mt-0.5">by {item.user}</p>
            )}
          </div>
          <span className="text-xs text-muted-foreground flex-shrink-0">
            {formatEventDate(item.timestamp)}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Loading skeleton.
 */
function SubscriptionHistorySkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {[1, 2].map((i) => (
        <div
          key={i}
          className="bg-card rounded-xl border border-border"
        >
          <div className="px-6 py-4 border-b border-border">
            <div className="h-5 bg-muted rounded w-40 animate-pulse" />
          </div>
          <div className="p-6 space-y-4">
            {[1, 2, 3].map((j) => (
              <div key={j} className="flex gap-4 animate-pulse">
                <div className="w-10 h-10 bg-muted rounded-full" />
                <div className="flex-1">
                  <div className="h-4 bg-muted rounded w-3/4 mb-2" />
                  <div className="h-3 bg-muted rounded w-1/2" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Main SubscriptionHistory component.
 */
export function SubscriptionHistory({
  events,
  activity,
  isLoading,
}: SubscriptionHistoryProps) {
  if (isLoading) {
    return <SubscriptionHistorySkeleton />;
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Billing Events */}
      <div className="bg-card rounded-xl border border-border">
        <div className="px-6 py-4 border-b border-border">
          <h3 className="text-lg font-semibold text-foreground">Billing History</h3>
        </div>
        <div className="p-6">
          {events.length === 0 ? (
            <p className="text-muted-foreground text-center py-4">No billing events</p>
          ) : (
            <div className="space-y-6">
              {events.slice(0, 10).map((event) => (
                <EventItem key={event.id} event={event} />
              ))}
              {events.length > 10 && (
                <p className="text-center text-sm text-muted-foreground">
                  Showing 10 of {events.length} events
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-card rounded-xl border border-border">
        <div className="px-6 py-4 border-b border-border">
          <h3 className="text-lg font-semibold text-foreground">Recent Activity</h3>
        </div>
        <div className="p-6">
          {activity.length === 0 ? (
            <p className="text-muted-foreground text-center py-4">No recent activity</p>
          ) : (
            <div className="space-y-4">
              {activity.slice(0, 10).map((item, index) => (
                <ActivityItemRow key={index} item={item} />
              ))}
              {activity.length > 10 && (
                <p className="text-center text-sm text-muted-foreground">
                  Showing 10 of {activity.length} activities
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SubscriptionHistory;
