'use client';

import { Upload } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { initiateWriteback, type WritebackJobResponse } from '@/lib/bas';

interface SyncToXeroButtonProps {
  connectionId: string;
  sessionId: string;
  approvedUnsyncedCount: number;
  isJobInProgress: boolean;
  getToken: () => Promise<string | null>;
  onJobCreated: (job: WritebackJobResponse) => void;
}

export function SyncToXeroButton({
  connectionId,
  sessionId,
  approvedUnsyncedCount,
  isJobInProgress,
  getToken,
  onJobCreated,
}: SyncToXeroButtonProps) {
  const [loading, setLoading] = useState(false);

  if (approvedUnsyncedCount === 0) return null;

  async function handleSync() {
    setLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      const job = await initiateWriteback(token, connectionId, sessionId);
      onJobCreated(job);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      onClick={handleSync}
      disabled={loading || isJobInProgress}
      size="sm"
      className="gap-2"
    >
      <Upload className="h-4 w-4" />
      {loading ? 'Syncing…' : `Sync ${approvedUnsyncedCount} to Xero`}
    </Button>
  );
}
