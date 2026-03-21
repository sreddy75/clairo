'use client';

import { Check } from 'lucide-react';

import { cn } from '@/lib/utils';

export interface TierCardProps {
  name: string;
  price: number;
  clientLimit: number;
  features: string[];
  recommended?: boolean;
  selected?: boolean;
  isLoading?: boolean;
  onSelect: () => void;
}

/**
 * TierCard displays a subscription tier option.
 *
 * Shows tier name, price, features, and client limit with visual
 * indicators for recommended and selected states.
 */
export function TierCard({
  name,
  price,
  clientLimit,
  features,
  recommended = false,
  selected = false,
  isLoading = false,
  onSelect,
}: TierCardProps) {
  return (
    <div
      className={cn(
        'relative rounded-2xl border-2 p-6 bg-card transition-all',
        recommended
          ? 'border-blue-600 ring-2 ring-blue-100'
          : 'border-border hover:border-border',
        selected && 'ring-2 ring-blue-400'
      )}
    >
      {/* Recommended badge */}
      {recommended && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-primary text-white">
            Recommended
          </span>
        </div>
      )}

      {/* Tier info */}
      <div className="text-center">
        <h3 className="text-xl font-semibold text-foreground">{name}</h3>
        <div className="mt-4">
          <span className="text-4xl font-bold text-foreground">${price}</span>
          <span className="text-muted-foreground">/month</span>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Up to {clientLimit} clients
        </p>
      </div>

      {/* Features */}
      <ul className="mt-6 space-y-3">
        {features.map((feature) => (
          <li key={feature} className="flex items-start">
            <Check className="w-5 h-5 text-green-500 mr-2 flex-shrink-0" />
            <span className="text-sm text-muted-foreground">{feature}</span>
          </li>
        ))}
      </ul>

      {/* Select button */}
      <button
        onClick={onSelect}
        disabled={isLoading}
        className={cn(
          'mt-6 w-full py-3 px-4 rounded-lg font-medium transition-colors',
          recommended
            ? 'bg-primary text-white hover:bg-primary/90'
            : 'bg-muted text-foreground hover:bg-muted',
          'disabled:opacity-50 disabled:cursor-not-allowed'
        )}
      >
        {isLoading && selected ? (
          <span className="flex items-center justify-center">
            <svg
              className="animate-spin -ml-1 mr-2 h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Processing...
          </span>
        ) : (
          'Start Free Trial'
        )}
      </button>
    </div>
  );
}
