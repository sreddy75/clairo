'use client';

import { HelpCircle, Send } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { type SendBackResponse } from '@/lib/bas';
import { formatCurrency } from '@/lib/formatters';

import { SendBackModal } from './SendBackModal';

interface IdkItem {
  id: string;
  description: string | null;
  amount: number;
  client_description: string | null;
}

interface IdkItemsSectionProps {
  connectionId: string;
  sessionId: string;
  requestId: string;
  idkItems: IdkItem[];
  getToken: () => Promise<string | null>;
  onSentBack?: (response: SendBackResponse) => void;
}

export function IdkItemsSection({
  connectionId,
  sessionId,
  requestId,
  idkItems,
  getToken,
  onSentBack,
}: IdkItemsSectionProps) {
  const [modalOpen, setModalOpen] = useState(false);

  if (idkItems.length === 0) return null;

  return (
    <>
      <Card className="border-amber-200">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-amber-500" />
              <span className="text-sm font-medium">
                {idkItems.length} &ldquo;I don&apos;t know&rdquo; {idkItems.length === 1 ? 'item' : 'items'}
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="gap-2 border-amber-300 text-amber-700 hover:bg-amber-50"
              onClick={() => setModalOpen(true)}
            >
              <Send className="h-3.5 w-3.5" />
              Send Back to Client
            </Button>
          </div>

          <div className="space-y-2">
            {idkItems.map((item) => (
              <div key={item.id} className="flex items-start justify-between text-sm py-2 border-t border-amber-100">
                <div className="space-y-0.5 min-w-0">
                  <p className="text-muted-foreground truncate">
                    {item.description || 'No description'}
                  </p>
                  {item.client_description && (
                    <p className="text-xs italic text-muted-foreground">
                      &ldquo;{item.client_description}&rdquo;
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-3">
                  <span className="tabular-nums font-medium">
                    {formatCurrency(Math.abs(item.amount))}
                  </span>
                  <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                    I don&apos;t know
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <SendBackModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        connectionId={connectionId}
        sessionId={sessionId}
        requestId={requestId}
        idkItems={idkItems}
        getToken={getToken}
        onSuccess={(response) => {
          setModalOpen(false);
          onSentBack?.(response);
        }}
      />
    </>
  );
}
