import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * Example Zustand store demonstrating best practices.
 *
 * Features demonstrated:
 * - Type-safe state and actions
 * - Devtools integration for debugging
 * - Persistence to localStorage
 *
 * Usage:
 *   const { count, increment } = useExampleStore();
 */

interface ExampleState {
  count: number;
  name: string;
}

interface ExampleActions {
  increment: () => void;
  decrement: () => void;
  setName: (name: string) => void;
  reset: () => void;
}

type ExampleStore = ExampleState & ExampleActions;

const initialState: ExampleState = {
  count: 0,
  name: '',
};

export const useExampleStore = create<ExampleStore>()(
  devtools(
    persist(
      (set) => ({
        ...initialState,

        increment: () => set((state) => ({ count: state.count + 1 })),

        decrement: () => set((state) => ({ count: state.count - 1 })),

        setName: (name) => set({ name }),

        reset: () => set(initialState),
      }),
      {
        name: 'example-storage', // localStorage key
        partialize: (state) => ({ name: state.name }), // Only persist name
      }
    ),
    { name: 'Example Store' } // Devtools display name
  )
);
