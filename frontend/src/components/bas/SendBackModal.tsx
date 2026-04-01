'use client';

import { Send } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { sendItemsBack, type SendBackResponse } from '@/lib/bas';
import { formatCurrency } from '@/lib/formatters';

interface IdkItem {
  id: string; // classification_id
  description: string | null;
  amount: number;
  client_description: string | null;
}

interface SendBackModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectionId: string;
  sessionId: string;
  requestId: string;
  idkItems: IdkItem[];
  getToken: () => Promise<string | null>;
  onSuccess: (response: SendBackResponse) => void;
}

export function SendBackModal({
  open,
  onOpenChange,
  connectionId,
  sessionId,
  requestId,
  idkItems,
  getToken,
  onSuccess,
}: SendBackModalProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set(idkItems.map((i) => i.id)));
  const [comments, setComments] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SendBackResponse | null>(null);

  const toggleItem = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectedItems = idkItems.filter((i) => selected.has(i.id));
  const allCommentsProvided = selectedItems.every((i) => (comments[i.id] || '').trim().length > 0);
  const canSubmit = selectedItems.length > 0 && allCommentsProvided;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) return;
      const items = selectedItems.map((i) => ({
        classification_id: i.id,
        agent_comment: (comments[i.id] ?? '').trim(),
      }));
      const response = await sendItemsBack(token, connectionId, sessionId, requestId, items);
      setResult(response);
      onSuccess(response);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Send Back to Client</DialogTitle>
          <DialogDescription>
            Select items to send back and add a comment for each explaining what you need.
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-3 py-2">
            <div className="rounded-md bg-emerald-50 border border-emerald-200 p-4 space-y-1">
              <p className="text-sm font-medium text-emerald-800">Sent successfully</p>
              <p className="text-sm text-emerald-700">
                {result.items_sent_back} item{result.items_sent_back === 1 ? '' : 's'} sent to {result.client_email}
              </p>
              <p className="text-xs text-emerald-600">
                Link expires {new Date(result.expires_at).toLocaleDateString('en-AU')}
              </p>
            </div>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>Close</Button>
            </DialogFooter>
          </div>
        ) : (
          <>
            <div className="space-y-4 py-2">
              {idkItems.map((item) => {
                const isSelected = selected.has(item.id);
                const comment = comments[item.id] || '';
                return (
                  <div key={item.id} className="space-y-2">
                    <div className="flex items-start gap-3">
                      <Checkbox
                        id={`item-${item.id}`}
                        checked={isSelected}
                        onCheckedChange={() => toggleItem(item.id)}
                        className="mt-0.5"
                      />
                      <Label htmlFor={`item-${item.id}`} className="cursor-pointer space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium tabular-nums">
                            {formatCurrency(Math.abs(item.amount))}
                          </span>
                          <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                            I don&apos;t know
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {item.description || 'No description'}
                        </p>
                        {item.client_description && (
                          <p className="text-xs italic text-muted-foreground">
                            Client said: &ldquo;{item.client_description}&rdquo;
                          </p>
                        )}
                      </Label>
                    </div>
                    {isSelected && (
                      <div className="ml-7">
                        <Textarea
                          value={comment}
                          onChange={(e) =>
                            setComments((prev) => ({ ...prev, [item.id]: e.target.value }))
                          }
                          placeholder="Add a comment for your client…"
                          className="text-sm min-h-[60px]"
                          maxLength={1000}
                        />
                        {comment.trim().length === 0 && (
                          <p className="text-xs text-red-500 mt-1">A comment is required</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={!canSubmit || submitting}
                className="gap-2"
              >
                <Send className="h-4 w-4" />
                {submitting ? 'Sending…' : `Send ${selectedItems.length} item${selectedItems.length === 1 ? '' : 's'}`}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
