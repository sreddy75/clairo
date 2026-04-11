'use client';

import { MessageSquare } from 'lucide-react';
import { useCallback, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import type { TaxCodeSuggestion } from '@/lib/bas';
import { saveNote, deleteNote } from '@/lib/bas';
import { cn } from '@/lib/utils';

interface SuggestionNoteEditorProps {
  suggestion: TaxCodeSuggestion;
  getToken: () => Promise<string | null>;
  connectionId: string;
  sessionId: string;
  onNoteChanged: () => void;
}

export function SuggestionNoteEditor({
  suggestion,
  getToken,
  connectionId,
  sessionId,
  onNoteChanged,
}: SuggestionNoteEditorProps) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(suggestion.note_text ?? '');
  const [syncToXero, setSyncToXero] = useState(false);
  const [saving, setSaving] = useState(false);

  const hasNote = !!suggestion.note_text;
  const maxLength = 2000;
  const canSyncToXero = ['bank_transaction', 'invoice', 'credit_note'].includes(suggestion.source_type);

  const handleOpen = useCallback((isOpen: boolean) => {
    if (isOpen) {
      setText(suggestion.note_text ?? '');
    }
    setOpen(isOpen);
  }, [suggestion.note_text]);

  async function handleSave() {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) return;
      await saveNote(token, connectionId, sessionId, suggestion.id, trimmed, syncToXero && canSyncToXero);
      setOpen(false);
      onNoteChanged();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setSaving(true);
    try {
      const token = await getToken();
      if (!token) return;
      await deleteNote(token, connectionId, sessionId, suggestion.id);
      setText('');
      setOpen(false);
      onNoteChanged();
    } finally {
      setSaving(false);
    }
  }

  const trigger = (
    <PopoverTrigger asChild>
      <Button
        variant="ghost"
        size="sm"
        className={cn(
          'h-6 w-6 p-0',
          hasNote ? 'text-primary' : 'text-muted-foreground/50 hover:text-muted-foreground',
        )}
      >
        <MessageSquare className={cn('w-3.5 h-3.5', hasNote && 'fill-current')} />
      </Button>
    </PopoverTrigger>
  );

  return (
    <Popover open={open} onOpenChange={handleOpen}>
      {hasNote ? (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>{trigger}</TooltipTrigger>
            <TooltipContent side="top" className="max-w-[300px] text-xs">
              <p className="whitespace-pre-wrap">{suggestion.note_text}</p>
              {suggestion.note_updated_by_name && (
                <p className="text-muted-foreground mt-1 text-[10px]">
                  — {suggestion.note_updated_by_name}
                </p>
              )}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        trigger
      )}

      <PopoverContent className="w-80" align="end">
        <div className="space-y-2">
          <p className="text-xs font-medium">Note</p>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Add a note about this transaction..."
            className="text-xs min-h-[80px] resize-none"
            maxLength={maxLength}
            disabled={saving}
          />
          {canSyncToXero && (
            <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={syncToXero}
                onChange={(e) => setSyncToXero(e.target.checked)}
                disabled={saving}
                className="rounded border-stone-300 h-3 w-3"
              />
              Sync to Xero
            </label>
          )}
          <div className="flex items-center justify-between">
            <span className={cn(
              'text-[10px]',
              text.length > maxLength * 0.9 ? 'text-amber-600' : 'text-muted-foreground',
            )}>
              {text.length}/{maxLength}
            </span>
            <div className="flex gap-1">
              {hasNote && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-[10px] h-6 px-2 text-red-600"
                  onClick={handleDelete}
                  disabled={saving}
                >
                  Delete
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="text-[10px] h-6 px-2"
                onClick={() => setOpen(false)}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="text-[10px] h-6 px-3"
                onClick={handleSave}
                disabled={saving || !text.trim()}
              >
                {saving ? '...' : 'Save'}
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
