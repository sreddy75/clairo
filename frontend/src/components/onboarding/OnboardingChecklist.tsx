/**
 * Onboarding checklist widget component.
 *
 * Shows onboarding progress with collapsible checklist items.
 *
 * Spec 021: Onboarding Flow - Onboarding Checklist Widget
 */

'use client';

import { CheckCircle2, ChevronDown, ChevronUp, X, Circle } from 'lucide-react';
import { useState } from 'react';

import type { OnboardingChecklist as ChecklistType } from '@/lib/api/onboarding';

interface OnboardingChecklistProps {
  checklist: ChecklistType;
  onDismiss: () => void;
  className?: string;
}

const ITEM_LABELS: Record<string, string> = {
  tier_selected: 'Select subscription tier',
  payment_setup: 'Set up payment method',
  xero_connected: 'Connect Xero',
  clients_imported: 'Import your first client',
  tour_completed: 'Complete product tour',
};

const ITEM_LINKS: Record<string, string> = {
  tier_selected: '/onboarding/tier-selection',
  payment_setup: '/settings/billing',
  xero_connected: '/settings/integrations',
  clients_imported: '/clients',
  tour_completed: '/dashboard',
};

export function OnboardingChecklist({
  checklist,
  onDismiss,
  className = '',
}: OnboardingChecklistProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const progressPercent = Math.round(
    (checklist.completed_count / checklist.total_count) * 100
  );
  const isComplete = checklist.completed_count === checklist.total_count;

  return (
    <div
      className={`bg-card border border-border rounded-xl shadow-sm ${className}`}
    >
      {/* Header - always visible */}
      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-foreground">
            {isComplete ? 'Setup Complete!' : 'Complete Your Setup'}
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={onDismiss}
              className="p-1 text-muted-foreground hover:text-foreground rounded"
              aria-label="Dismiss checklist"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                isComplete ? 'bg-status-success' : 'bg-primary'
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">
            {checklist.completed_count}/{checklist.total_count}
          </span>
        </div>

        {/* Expand/collapse button */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="mt-3 flex items-center gap-1 text-sm text-primary hover:text-primary/80"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="w-4 h-4" />
              Hide details
            </>
          ) : (
            <>
              <ChevronDown className="w-4 h-4" />
              {isComplete ? 'View completed steps' : 'View remaining steps'}
            </>
          )}
        </button>
      </div>

      {/* Expanded checklist items */}
      {isExpanded && (
        <div className="border-t border-border p-4 pt-2">
          <ul className="space-y-2">
            {checklist.items.map((item) => (
              <li key={item.id} className="flex items-center gap-3">
                {item.completed ? (
                  <CheckCircle2 className="w-5 h-5 text-status-success flex-shrink-0" />
                ) : (
                  <Circle className="w-5 h-5 text-muted-foreground/50 flex-shrink-0" />
                )}
                {item.completed ? (
                  <span className="text-sm text-muted-foreground line-through">
                    {ITEM_LABELS[item.id] || item.label}
                  </span>
                ) : (
                  <a
                    href={ITEM_LINKS[item.id] || '#'}
                    className="text-sm text-primary hover:text-primary/80 hover:underline"
                  >
                    {ITEM_LABELS[item.id] || item.label}
                  </a>
                )}
              </li>
            ))}
          </ul>

          {isComplete && (
            <div className="mt-4 pt-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                You&apos;re all set up and ready to use Clairo!
              </p>
              <button
                onClick={onDismiss}
                className="mt-2 text-sm text-primary hover:text-primary/80"
              >
                Dismiss this checklist
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
