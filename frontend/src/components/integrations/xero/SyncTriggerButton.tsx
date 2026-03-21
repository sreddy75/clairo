'use client';

import { useAuth } from '@clerk/nextjs';
import { ChevronDown, Loader2, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import type { XeroSyncType } from '@/lib/xero-sync';
import { getSyncTypeName, initiateSync } from '@/lib/xero-sync';

interface SyncTriggerButtonProps {
  connectionId: string;
  isSyncing: boolean;
  onSyncStarted?: (jobId: string) => void;
  organizationName?: string;
  compact?: boolean;
  className?: string;
}

const SYNC_OPTIONS: { type: XeroSyncType; description: string }[] = [
  { type: 'full', description: 'Sync all data types' },
  { type: 'contacts', description: 'Sync clients only' },
  { type: 'invoices', description: 'Sync invoices only' },
  { type: 'bank_transactions', description: 'Sync transactions only' },
  { type: 'accounts', description: 'Sync chart of accounts' },
];

/**
 * Button to trigger Xero data sync with dropdown for sync type selection.
 */
export function SyncTriggerButton({
  connectionId,
  isSyncing,
  onSyncStarted,
  organizationName,
  compact = false,
  className,
}: SyncTriggerButtonProps) {
  const { getToken } = useAuth();
  const [isLoading, setIsLoading] = useState(false);

  const handleSync = async (syncType: XeroSyncType = 'full', forceFull = false) => {
    setIsLoading(true);

    try {
      const token = await getToken();
      if (!token) {
        toast.error('Authentication required');
        return;
      }

      const job = await initiateSync(token, connectionId, {
        sync_type: syncType,
        force_full: forceFull,
      });

      const target = organizationName ? `for ${organizationName}` : '';
      if (forceFull) {
        toast.success(`Full re-sync started ${target}...`.trim(), { duration: 4_000 });
      } else if (syncType === 'full') {
        toast.success(`Syncing data ${target}...`.trim(), { duration: 4_000 });
      } else {
        toast.success(`Syncing ${getSyncTypeName(syncType).toLowerCase()} ${target}...`.trim(), {
          duration: 4_000,
        });
      }

      onSyncStarted?.(job.id);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start sync';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const isDisabled = isSyncing || isLoading;

  return (
    <div className={cn('inline-flex', className)}>
      <DropdownMenu>
        <div className="inline-flex rounded-lg">
          <Button
            onClick={() => handleSync('full')}
            disabled={isDisabled}
            size={compact ? 'sm' : 'default'}
            className="rounded-r-none"
          >
            {isLoading || isSyncing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            {compact ? 'Sync' : 'Sync Now'}
          </Button>
          <DropdownMenuTrigger asChild>
            <Button
              disabled={isDisabled}
              size={compact ? 'sm' : 'default'}
              className="rounded-l-none border-l border-primary-foreground/20 px-2"
              aria-label="Show sync options"
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </Button>
          </DropdownMenuTrigger>
        </div>
        <DropdownMenuContent align="end" className="w-56">
          {SYNC_OPTIONS.map((option) => (
            <DropdownMenuItem
              key={option.type}
              onClick={() => handleSync(option.type)}
            >
              <div>
                <div className="font-medium">{getSyncTypeName(option.type)}</div>
                <div className="text-xs text-muted-foreground">{option.description}</div>
              </div>
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => handleSync('full', true)}
            className="text-status-warning"
          >
            <div>
              <div className="font-medium">Force Full Re-sync</div>
              <div className="text-xs text-muted-foreground">Re-download all data from Xero</div>
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

export default SyncTriggerButton;
