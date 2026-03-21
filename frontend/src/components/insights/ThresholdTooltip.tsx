'use client';

/**
 * ThresholdTooltip Component
 *
 * Wraps any child element with a tooltip showing the threshold rules
 * for a given metric. Fetches threshold data from the platform API
 * and caches it indefinitely (thresholds are static).
 */

import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { apiClient } from '@/lib/api-client';

interface ThresholdBand {
  label: string;
  color: string;
  condition: string;
}

interface ThresholdRule {
  metric_key: string;
  display_name: string;
  description: string;
  rules: ThresholdBand[];
}

interface ThresholdRegistryResponse {
  thresholds: ThresholdRule[];
}

interface ThresholdTooltipProps {
  metricKey: string;
  children: ReactNode;
}

const BAND_COLORS: Record<string, string> = {
  green: 'text-status-success',
  yellow: 'text-status-warning',
  red: 'text-status-danger',
  gray: 'text-muted-foreground',
};

function useThresholds() {
  return useQuery({
    queryKey: ['platform', 'thresholds'],
    queryFn: async () => {
      const response = await apiClient.get<Response>('/api/v1/platform/thresholds');
      return (response as unknown as Response).json() as Promise<ThresholdRegistryResponse>;
    },
    staleTime: Infinity,
    gcTime: Infinity,
  });
}

export function ThresholdTooltip({ metricKey, children }: ThresholdTooltipProps) {
  const { data } = useThresholds();

  const rule = data?.thresholds?.find((t) => t.metric_key === metricKey);

  // Graceful degradation — render children without tooltip if no data
  if (!rule) {
    return <>{children}</>;
  }

  return (
    <TooltipProvider>
      <Tooltip delayDuration={200}>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent
          side="top"
          className="max-w-xs bg-card text-foreground border border-border shadow-lg p-3"
        >
          <div className="space-y-2">
            <p className="font-semibold text-xs">{rule.display_name}</p>
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              {rule.description}
            </p>
            <div className="space-y-1 pt-1 border-t border-border">
              {rule.rules.map((band, idx) => (
                <div key={idx} className="flex items-start gap-2 text-[11px]">
                  <span
                    className={`font-semibold min-w-[60px] ${BAND_COLORS[band.color] || BAND_COLORS.gray}`}
                  >
                    {band.label}:
                  </span>
                  <span className="text-muted-foreground">{band.condition}</span>
                </div>
              ))}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export default ThresholdTooltip;
