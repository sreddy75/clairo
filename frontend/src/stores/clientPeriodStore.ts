import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

/**
 * Shared quarter/FY selection store for a client session.
 * Used by BAS, Insights, and Dashboard tabs to keep the selected
 * period in sync without prop-drilling.
 *
 * Intentionally NOT persisted — resets on page refresh.
 */

interface ClientPeriodState {
  selectedQuarter: number | null;
  selectedFyYear: number | null;
}

interface ClientPeriodActions {
  setQuarter: (quarter: number, fyYear: number) => void;
  reset: () => void;
}

type ClientPeriodStore = ClientPeriodState & ClientPeriodActions;

const initialState: ClientPeriodState = {
  selectedQuarter: null,
  selectedFyYear: null,
};

export const useClientPeriodStore = create<ClientPeriodStore>()(
  devtools(
    (set) => ({
      ...initialState,

      setQuarter: (quarter, fyYear) => set({ selectedQuarter: quarter, selectedFyYear: fyYear }),

      reset: () => set(initialState),
    }),
    { name: 'ClientPeriod Store' }
  )
);
