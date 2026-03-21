'use client';

/**
 * A2UI Data Context
 * Provides data bindings to A2UI components
 */

import type {
  ReactNode} from 'react';
import {
  createContext,
  useContext,
  useCallback,
  useMemo,
  useState,
} from 'react';

import type { DataModelUpdate, ActionConfig, A2UIActionHandlers } from './types';

// =============================================================================
// Context Types
// =============================================================================

interface A2UIDataContextValue {
  /** Current data model */
  data: DataModelUpdate;
  /** Get value by binding key */
  getValue: <T>(binding: string | undefined) => T | undefined;
  /** Set value by binding key */
  setValue: (binding: string, value: unknown) => void;
  /** Execute an action */
  executeAction: (action: ActionConfig) => Promise<void>;
}

interface A2UIDataProviderProps {
  /** Initial data model */
  data: DataModelUpdate;
  /** Action handlers */
  actionHandlers?: A2UIActionHandlers;
  /** Children to render */
  children: ReactNode;
}

// =============================================================================
// Context Creation
// =============================================================================

const A2UIDataContext = createContext<A2UIDataContextValue | null>(null);

// =============================================================================
// Provider Component
// =============================================================================

export function A2UIDataProvider({
  data: initialData,
  actionHandlers,
  children,
}: A2UIDataProviderProps) {
  const [data, setData] = useState<DataModelUpdate>(initialData);

  // Get value from data model by dot-notation path
  const getValue = useCallback(
    <T,>(binding: string | undefined): T | undefined => {
      if (!binding) return undefined;

      // Support dot notation (e.g., "client.revenue.total")
      const keys = binding.split('.');
      let value: unknown = data;

      for (const key of keys) {
        if (value === null || value === undefined) return undefined;
        if (typeof value !== 'object') return undefined;
        value = (value as Record<string, unknown>)[key];
      }

      return value as T;
    },
    [data]
  );

  // Set value in data model by dot-notation path
  const setValue = useCallback((binding: string, newValue: unknown) => {
    setData((prev) => {
      const keys = binding.split('.');
      const lastKey = keys.pop()!;

      // Navigate to parent object
      let current: Record<string, unknown> = { ...prev };
      const result = current;

      for (const key of keys) {
        current[key] = { ...(current[key] as Record<string, unknown>) };
        current = current[key] as Record<string, unknown>;
      }

      // Set the value
      current[lastKey] = newValue;
      return result;
    });
  }, []);

  // Execute action based on type
  const executeAction = useCallback(
    async (action: ActionConfig): Promise<void> => {
      switch (action.type) {
        case 'navigate':
          if (actionHandlers?.navigate && action.target) {
            actionHandlers.navigate(action.target);
          } else if (typeof window !== 'undefined' && action.target) {
            window.location.href = action.target;
          }
          break;

        case 'createTask':
          if (actionHandlers?.createTask && action.payload) {
            await actionHandlers.createTask(action.payload);
          }
          break;

        case 'approve':
          if (actionHandlers?.approve && action.target) {
            await actionHandlers.approve(action.target);
          }
          break;

        case 'export':
          if (actionHandlers?.export && action.target && action.payload?.format) {
            await actionHandlers.export(
              action.payload.format as string,
              action.target
            );
          }
          break;

        case 'custom':
          if (actionHandlers?.custom && action.payload) {
            await actionHandlers.custom(action.payload);
          }
          break;
      }
    },
    [actionHandlers]
  );

  const contextValue = useMemo(
    () => ({
      data,
      getValue,
      setValue,
      executeAction,
    }),
    [data, getValue, setValue, executeAction]
  );

  return (
    <A2UIDataContext.Provider value={contextValue}>
      {children}
    </A2UIDataContext.Provider>
  );
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Access the full A2UI data context
 */
export function useA2UIContext(): A2UIDataContextValue {
  const context = useContext(A2UIDataContext);
  if (!context) {
    throw new Error('useA2UIContext must be used within A2UIDataProvider');
  }
  return context;
}

/**
 * Get a bound value from the A2UI data model
 */
export function useA2UIData<T>(binding: string | undefined): T | undefined {
  const context = useContext(A2UIDataContext);
  if (!context) {
    // Return undefined if not in provider (for standalone component usage)
    return undefined;
  }
  return context.getValue<T>(binding);
}

/**
 * Get a setter for a bound value
 */
export function useA2UIDataSetter(
  binding: string | undefined
): ((value: unknown) => void) | undefined {
  const context = useContext(A2UIDataContext);
  if (!context || !binding) {
    return undefined;
  }
  return (value: unknown) => context.setValue(binding, value);
}

/**
 * Get the action executor
 */
export function useA2UIAction(): (action: ActionConfig) => Promise<void> {
  const context = useContext(A2UIDataContext);
  if (!context) {
    // Return no-op if not in provider
    return async () => {};
  }
  return context.executeAction;
}
