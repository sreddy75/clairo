/**
 * Queue Status Component
 *
 * Shows upload queue status with pending/failed counts.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { Cloud, CloudOff, Upload, AlertCircle, Loader2, RefreshCw } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { useOfflineQueue } from '@/hooks/useOfflineQueue';
import { cn } from '@/lib/utils';

interface QueueStatusProps {
  /** Upload function for processing queue */
  uploadFn?: (requestId: string, file: File, message?: string) => Promise<{ id: string }>;
  /** Compact mode (just badge) */
  compact?: boolean;
  /** Custom class name */
  className?: string;
}

export function QueueStatus({
  uploadFn,
  compact = false,
  className,
}: QueueStatusProps) {
  const { isOnline } = useNetworkStatus();
  const { stats, isProcessing, hasPending, processNow, retryFailed } = useOfflineQueue(uploadFn);

  // Nothing to show if queue is empty
  if (stats.total === 0) {
    return null;
  }

  // Format size
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Compact mode - just show a badge
  if (compact) {
    if (!hasPending && stats.failed === 0) {
      return null;
    }

    return (
      <Badge
        variant={stats.failed > 0 ? 'destructive' : 'secondary'}
        className={cn('gap-1', className)}
      >
        {isProcessing ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : stats.failed > 0 ? (
          <AlertCircle className="h-3 w-3" />
        ) : !isOnline ? (
          <CloudOff className="h-3 w-3" />
        ) : (
          <Upload className="h-3 w-3" />
        )}
        {stats.pending + stats.failed}
      </Badge>
    );
  }

  // Full status card
  return (
    <div
      className={cn(
        'rounded-lg border p-4 space-y-3',
        stats.failed > 0
          ? 'border-destructive/50 bg-destructive/5'
          : 'border-muted bg-muted/30',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isProcessing ? (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          ) : !isOnline ? (
            <CloudOff className="h-5 w-5 text-muted-foreground" />
          ) : stats.failed > 0 ? (
            <AlertCircle className="h-5 w-5 text-destructive" />
          ) : (
            <Cloud className="h-5 w-5 text-primary" />
          )}
          <span className="font-medium">Upload Queue</span>
        </div>

        {isOnline && (stats.pending > 0 || stats.failed > 0) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              if (stats.failed > 0) {
                retryFailed();
              }
              processNow();
            }}
            disabled={isProcessing}
          >
            <RefreshCw className={cn('h-4 w-4 mr-1', isProcessing && 'animate-spin')} />
            {isProcessing ? 'Uploading...' : 'Sync Now'}
          </Button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-muted-foreground">Pending</p>
          <p className="font-medium">{stats.pending}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Failed</p>
          <p className={cn('font-medium', stats.failed > 0 && 'text-destructive')}>
            {stats.failed}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Size</p>
          <p className="font-medium">{formatSize(stats.totalSize)}</p>
        </div>
      </div>

      {/* Status message */}
      <p className="text-sm text-muted-foreground">
        {isProcessing
          ? 'Uploading files...'
          : !isOnline
            ? 'Waiting for network connection'
            : stats.failed > 0
              ? 'Some uploads failed. Tap to retry.'
              : stats.pending > 0
                ? 'Ready to upload'
                : 'All uploads complete'}
      </p>
    </div>
  );
}
