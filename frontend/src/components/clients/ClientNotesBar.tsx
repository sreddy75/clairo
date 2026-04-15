'use client';

/**
 * ClientNotesBar — persistent notes bar shown on client detail page.
 * Displays standing instructions that carry across quarters.
 */

import { Check, Edit3, Loader2, StickyNote } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api-client';

interface ClientNotesBarProps {
  clientId: string;
  getToken: () => Promise<string | null>;
}

interface PracticeClientData {
  notes: string | null;
  notes_updated_at: string | null;
  notes_updated_by_name: string | null;
}

export function ClientNotesBar({ clientId, getToken }: ClientNotesBarProps) {
  const [notes, setNotes] = useState<string>('');
  const [savedNotes, setSavedNotes] = useState<string>('');
  const [updatedBy, setUpdatedBy] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const fetchNotes = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      // Fetch the practice client by xero connection ID
      const response = await apiClient.get(`/api/v1/clients/${clientId}/notes/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return;

      // Also try to get the client's current notes via the portfolio endpoint
      const clientResp = await apiClient.get(`/api/v1/dashboard/clients?search=&limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (clientResp.ok) {
        const data = await clientResp.json();
        const client = data.clients?.find((c: PracticeClientData & { id: string }) => c.id === clientId);
        if (client) {
          setNotes(client.notes || '');
          setSavedNotes(client.notes || '');
          setUpdatedBy(client.notes_updated_by_name);
          setUpdatedAt(client.notes_updated_at);
        }
      }
    } catch {
      // silent
    } finally {
      setLoaded(true);
    }
  }, [clientId, getToken]);

  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.patch(`/api/v1/clients/${clientId}/notes`, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes }),
      });
      if (response.ok) {
        setSavedNotes(notes);
        setEditing(false);
        await fetchNotes();
      }
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  if (!loaded) return null;

  // No notes and not editing — show subtle add prompt
  if (!savedNotes && !editing) {
    return (
      <div className="px-4 sm:px-6 lg:px-8 pt-3">
        <button
          onClick={() => setEditing(true)}
          className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <StickyNote className="h-3.5 w-3.5" />
          Add standing instructions for this client...
        </button>
      </div>
    );
  }

  return (
    <div className="px-4 sm:px-6 lg:px-8 pt-3">
      <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2 flex-1 min-w-0">
            <StickyNote className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-wider text-amber-700 mb-1">
                Standing Instructions
              </p>
              {editing ? (
                <div className="space-y-2">
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full rounded border border-amber-300 bg-white px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-amber-400"
                    rows={3}
                    maxLength={5000}
                    placeholder="E.g., Client does the bookkeeping, usually sends on the last day..."
                  />
                  <div className="flex items-center gap-2">
                    <Button size="sm" className="h-7" onClick={handleSave} disabled={saving}>
                      {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Check className="h-3.5 w-3.5 mr-1" />}
                      Save
                    </Button>
                    <Button size="sm" variant="ghost" className="h-7" onClick={() => { setNotes(savedNotes); setEditing(false); }}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-foreground whitespace-pre-wrap">{savedNotes}</p>
              )}
              {!editing && updatedBy && (
                <p className="text-[10px] text-muted-foreground mt-1">
                  Last updated by {updatedBy}{updatedAt ? ` on ${new Date(updatedAt).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
                </p>
              )}
            </div>
          </div>
          {!editing && (
            <button onClick={() => setEditing(true)} className="text-amber-600 hover:text-amber-800">
              <Edit3 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
