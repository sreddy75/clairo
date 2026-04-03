'use client';

/**
 * AccountantBrief — Renders and edits the AI-generated accountant brief.
 *
 * View mode: Markdown rendering with react-markdown
 * Edit mode: Textarea for direct editing
 */

interface AccountantBriefProps {
  brief: string;
  reviewResult?: Record<string, unknown> | null;
  reviewPassed?: boolean;
  onSave: (updatedBrief: string) => void;
  readOnly?: boolean;
}

export function AccountantBrief({ brief, reviewResult, reviewPassed, onSave, readOnly }: AccountantBriefProps) {
  // TODO: Implement markdown renderer + edit mode
  return (
    <div className="p-4">
      <p className="text-muted-foreground">Accountant brief will render here</p>
    </div>
  );
}
