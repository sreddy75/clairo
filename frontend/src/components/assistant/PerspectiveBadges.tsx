'use client';

import {
  AlertTriangle,
  LineChart,
  Shield,
  TrendingUp,
} from 'lucide-react';
import { useMemo } from 'react';

import {
  type Perspective,
  PERSPECTIVE_CONFIG,
  getConfidenceLevel,
} from '@/types/agents';

// =============================================================================
// Icon Mapping
// =============================================================================

const PERSPECTIVE_ICONS = {
  compliance: Shield,
  quality: AlertTriangle,
  strategy: TrendingUp,
  insight: LineChart,
} as const;

// =============================================================================
// PerspectiveBadge Component
// =============================================================================

interface PerspectiveBadgeProps {
  perspective: Perspective;
  isActive?: boolean;
  onClick?: () => void;
  size?: 'sm' | 'md';
}

export function PerspectiveBadge({
  perspective,
  isActive = false,
  onClick,
  size = 'sm',
}: PerspectiveBadgeProps) {
  const config = PERSPECTIVE_CONFIG[perspective];
  const Icon = PERSPECTIVE_ICONS[perspective];

  const sizeClasses = size === 'sm'
    ? 'px-2 py-0.5 text-xs gap-1'
    : 'px-3 py-1 text-sm gap-1.5';

  const iconSize = size === 'sm' ? 12 : 14;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        inline-flex items-center rounded-full font-medium transition-all
        ${sizeClasses}
        ${isActive
          ? `${config.bgColor} ${config.color} ring-2 ring-offset-1 ring-current`
          : `${config.bgColor} ${config.color} opacity-80 hover:opacity-100`
        }
        ${onClick ? 'cursor-pointer' : 'cursor-default'}
      `}
      title={config.description}
    >
      <Icon size={iconSize} />
      <span>{config.label}</span>
    </button>
  );
}

// =============================================================================
// PerspectiveBadgeList Component
// =============================================================================

interface PerspectiveBadgeListProps {
  perspectives: Perspective[];
  activePerspective?: Perspective | null;
  onPerspectiveClick?: (perspective: Perspective) => void;
  size?: 'sm' | 'md';
}

export function PerspectiveBadgeList({
  perspectives,
  activePerspective,
  onPerspectiveClick,
  size = 'sm',
}: PerspectiveBadgeListProps) {
  // Sort perspectives in canonical order
  const sortedPerspectives = useMemo(() => {
    const order: Perspective[] = ['compliance', 'quality', 'strategy', 'insight'];
    return [...perspectives].sort((a, b) => order.indexOf(a) - order.indexOf(b));
  }, [perspectives]);

  if (perspectives.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {sortedPerspectives.map((perspective) => (
        <PerspectiveBadge
          key={perspective}
          perspective={perspective}
          isActive={activePerspective === perspective}
          onClick={onPerspectiveClick ? () => onPerspectiveClick(perspective) : undefined}
          size={size}
        />
      ))}
    </div>
  );
}

// =============================================================================
// ConfidenceIndicator Component
// =============================================================================

interface ConfidenceIndicatorProps {
  confidence: number;
  showLabel?: boolean;
  size?: 'sm' | 'md';
}

export function ConfidenceIndicator({
  confidence,
  showLabel = true,
  size = 'sm',
}: ConfidenceIndicatorProps) {
  const { label, color, bgColor } = getConfidenceLevel(confidence);

  const sizeClasses = size === 'sm' ? 'text-xs' : 'text-sm';
  const barHeight = size === 'sm' ? 'h-1' : 'h-1.5';

  return (
    <div className={`flex items-center gap-2 ${sizeClasses}`}>
      {showLabel && (
        <span className={`font-medium ${color}`}>{label}</span>
      )}
      <div className={`w-16 ${barHeight} rounded-full bg-muted overflow-hidden`}>
        <div
          className={`${barHeight} rounded-full transition-all ${bgColor.replace('bg-', 'bg-')}`}
          style={{
            width: `${Math.round(confidence * 100)}%`,
            backgroundColor: color.replace('text-', '').replace('-700', '-500'),
          }}
        />
      </div>
      <span className="text-muted-foreground">{Math.round(confidence * 100)}%</span>
    </div>
  );
}

// =============================================================================
// EscalationBanner Component
// =============================================================================

interface EscalationBannerProps {
  reason: string | null;
  onReview?: () => void;
}

export function EscalationBanner({ reason, onReview }: EscalationBannerProps) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-status-warning/10 border border-status-warning/30">
      <AlertTriangle className="w-5 h-5 text-status-warning flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-status-warning">
          Review Recommended
        </p>
        <p className="text-sm text-status-warning/80 mt-0.5">
          {reason || 'This response may require professional review before sharing with clients.'}
        </p>
      </div>
      {onReview && (
        <button
          type="button"
          onClick={onReview}
          className="flex-shrink-0 px-3 py-1.5 text-sm font-medium text-status-warning bg-status-warning/10 rounded-md hover:bg-status-warning/20 transition-colors"
        >
          Review
        </button>
      )}
    </div>
  );
}

// =============================================================================
// ResponseMetadata Component
// =============================================================================

interface ResponseMetadataProps {
  perspectives: Perspective[];
  confidence: number;
  escalationRequired: boolean;
  escalationReason: string | null;
  processingTimeMs: number;
  activePerspective?: Perspective | null;
  onPerspectiveClick?: (perspective: Perspective) => void;
}

export function ResponseMetadata({
  perspectives,
  confidence,
  escalationRequired,
  escalationReason,
  processingTimeMs,
  activePerspective,
  onPerspectiveClick,
}: ResponseMetadataProps) {
  return (
    <div className="space-y-3">
      {/* Escalation Banner */}
      {escalationRequired && (
        <EscalationBanner reason={escalationReason} />
      )}

      {/* Metadata Row */}
      <div className="flex items-center justify-between flex-wrap gap-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-4">
          {/* Perspective Badges */}
          <PerspectiveBadgeList
            perspectives={perspectives}
            activePerspective={activePerspective}
            onPerspectiveClick={onPerspectiveClick}
          />

          {/* Confidence */}
          <ConfidenceIndicator confidence={confidence} showLabel={false} />
        </div>

        {/* Processing Time */}
        <span>{(processingTimeMs / 1000).toFixed(1)}s</span>
      </div>
    </div>
  );
}
