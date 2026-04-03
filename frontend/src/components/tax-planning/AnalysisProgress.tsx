'use client';

/**
 * AnalysisProgress — 5-step pipeline progress stepper.
 *
 * Shows real-time progress as the multi-agent pipeline runs:
 * 1. Profile → 2. Scan Strategies → 3. Model Scenarios → 4. Write Documents → 5. Review
 */

interface AnalysisProgressProps {
  taskId: string;
  planId: string;
  onComplete: (analysisId: string) => void;
  onError: (error: string, stage: string) => void;
}

export function AnalysisProgress({ taskId, planId, onComplete, onError }: AnalysisProgressProps) {
  // TODO: Implement SSE polling + progress stepper UI
  return (
    <div className="p-8 text-center text-muted-foreground">
      <p>Generating tax plan analysis...</p>
      <p className="text-xs mt-2">Task: {taskId}</p>
    </div>
  );
}
