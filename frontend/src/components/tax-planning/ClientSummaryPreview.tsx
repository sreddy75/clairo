'use client';

/**
 * ClientSummaryPreview — Preview of what the client will see in the portal.
 *
 * Renders the client summary markdown in a portal-like frame.
 */

interface ClientSummaryPreviewProps {
  summary: string;
  clientName: string;
  financialYear: string;
  totalSaving?: number;
}

export function ClientSummaryPreview({ summary, clientName, financialYear, totalSaving }: ClientSummaryPreviewProps) {
  // TODO: Implement portal-style preview
  return (
    <div className="p-4">
      <p className="text-muted-foreground">Client summary preview will render here</p>
    </div>
  );
}
