'use client';

import { Check, Pencil, Loader2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface BriefPreviewProps {
  briefMarkdown: string;
  briefData: Record<string, unknown>;
  onConfirm: (revisions?: string) => Promise<void>;
  isLoading?: boolean;
}

export function BriefPreview({
  briefMarkdown,
  onConfirm,
  isLoading = false,
}: BriefPreviewProps) {
  const [showRevisions, setShowRevisions] = useState(false);
  const [revisions, setRevisions] = useState('');

  async function handleConfirm() {
    await onConfirm();
  }

  async function handleSubmitRevisions() {
    if (!revisions.trim()) return;
    await onConfirm(revisions.trim());
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Check className="size-5 text-emerald-600" />
          Generated Brief
        </CardTitle>
      </CardHeader>

      <CardContent>
        <div
          className={cn(
            'rounded-lg border bg-muted/40 p-4',
            'text-sm leading-relaxed whitespace-pre-wrap',
            'font-mono'
          )}
        >
          {briefMarkdown}
        </div>

        {showRevisions && (
          <div className="mt-4 space-y-3">
            <Textarea
              placeholder="Describe the changes you'd like made to the brief..."
              value={revisions}
              onChange={(e) => setRevisions(e.target.value)}
              rows={4}
              disabled={isLoading}
            />
            <div className="flex items-center gap-2">
              <Button
                onClick={handleSubmitRevisions}
                disabled={isLoading || !revisions.trim()}
                size="sm"
              >
                {isLoading ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Check />
                )}
                Submit Revisions
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowRevisions(false);
                  setRevisions('');
                }}
                disabled={isLoading}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="gap-2">
        <Button onClick={handleConfirm} disabled={isLoading}>
          {isLoading ? <Loader2 className="animate-spin" /> : <Check />}
          Confirm Brief
        </Button>
        <Button
          variant="outline"
          onClick={() => setShowRevisions((prev) => !prev)}
          disabled={isLoading}
        >
          <Pencil />
          Request Changes
        </Button>
      </CardFooter>
    </Card>
  );
}
