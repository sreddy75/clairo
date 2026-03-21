'use client';

/**
 * Hook for managing day summary modal state.
 *
 * Usage:
 * ```tsx
 * const { isOpen, openSummary, closeSummary, summaryDate, setSummaryDate } = useDaySummary();
 *
 * // In your component:
 * <Button onClick={openSummary}>View Day Summary</Button>
 * <DaySummaryModal isOpen={isOpen} onClose={closeSummary} summaryDate={summaryDate} />
 * ```
 */

import { useCallback, useState } from 'react';

interface UseDaySummaryReturn {
  isOpen: boolean;
  summaryDate: string | undefined;
  openSummary: (date?: string) => void;
  closeSummary: () => void;
  setSummaryDate: (date: string | undefined) => void;
}

export function useDaySummary(): UseDaySummaryReturn {
  const [isOpen, setIsOpen] = useState(false);
  const [summaryDate, setSummaryDate] = useState<string | undefined>();

  const openSummary = useCallback((date?: string) => {
    if (date) {
      setSummaryDate(date);
    }
    setIsOpen(true);
  }, []);

  const closeSummary = useCallback(() => {
    setIsOpen(false);
  }, []);

  return {
    isOpen,
    summaryDate,
    openSummary,
    closeSummary,
    setSummaryDate,
  };
}

export default useDaySummary;
