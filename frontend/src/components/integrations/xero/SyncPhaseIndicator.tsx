'use client';

import { Loader2 } from 'lucide-react';

interface SyncPhaseIndicatorProps {
  /** The sync phase this section's data depends on (2 or 3) */
  requiredPhase: 2 | 3;
  /** Current active sync's phase (null if no sync active) */
  activeSyncPhase: number | null;
  /** Human-readable name for the data type being synced */
  dataLabel?: string;
}

/**
 * Subtle inline banner that indicates historical data is still being synced.
 *
 * Displayed within client dashboard tab sections whose data depends on
 * Phase 2 or Phase 3 of the progressive Xero sync. Renders nothing when
 * the required phase has already completed (activeSyncPhase > requiredPhase
 * or no sync is active).
 */
export function SyncPhaseIndicator({
  requiredPhase,
  activeSyncPhase,
  dataLabel = 'data',
}: SyncPhaseIndicatorProps) {
  // Render nothing when no sync is active or the required phase is already done
  if (activeSyncPhase === null || activeSyncPhase > requiredPhase) {
    return null;
  }

  // Determine the message based on current phase vs required phase
  let message: string;

  if (activeSyncPhase === requiredPhase) {
    // The sync is currently on the phase this section needs
    message = `Syncing ${dataLabel} data...`;
  } else if (requiredPhase === 2 && activeSyncPhase === 1) {
    // Section needs Phase 2 but sync is still on Phase 1
    message = `${capitalize(dataLabel)} data syncing next \u2014 essential data available now`;
  } else if (requiredPhase === 3 && (activeSyncPhase === 1 || activeSyncPhase === 2)) {
    // Section needs Phase 3 but sync is on Phase 1 or 2
    message = `${capitalize(dataLabel)} data syncing soon \u2014 earlier phases in progress`;
  } else {
    // Fallback (should not happen given the guard above)
    return null;
  }

  return (
    <div
      className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm
        bg-primary/10 border border-primary/20
        text-primary animate-pulse"
    >
      <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
      <span>{message}</span>
    </div>
  );
}

/** Capitalize the first letter of a string. */
function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default SyncPhaseIndicator;
