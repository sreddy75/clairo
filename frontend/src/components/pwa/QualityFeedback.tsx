/**
 * Quality Feedback Component
 *
 * Shows image quality analysis results with option to proceed anyway.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Camera,
  Sun,
  Eye,
  Loader2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import type { QualityResult } from '@/lib/pwa/quality-check';
import { cn } from '@/lib/utils';

interface QualityFeedbackProps {
  /** Quality analysis result */
  result: QualityResult | null;
  /** Whether analysis is in progress */
  isAnalyzing?: boolean;
  /** Callback when user wants to retake */
  onRetake: () => void;
  /** Callback when user accepts despite issues */
  onProceed: () => void;
  /** Custom class name */
  className?: string;
}

export function QualityFeedback({
  result,
  isAnalyzing = false,
  onRetake,
  onProceed,
  className,
}: QualityFeedbackProps) {
  // Analyzing state
  if (isAnalyzing) {
    return (
      <div className={cn('text-center space-y-3', className)}>
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
        <p className="text-sm text-muted-foreground">Analyzing image quality...</p>
      </div>
    );
  }

  // No result yet
  if (!result) {
    return null;
  }

  // Good quality
  if (result.isAcceptable) {
    return (
      <div className={cn('text-center space-y-3', className)}>
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-status-success/10">
          <CheckCircle2 className="h-6 w-6 text-status-success" />
        </div>
        <div>
          <p className="font-medium text-status-success">Good Quality</p>
          <p className="text-sm text-muted-foreground">
            Image is clear and ready to upload
          </p>
        </div>
      </div>
    );
  }

  // Quality issues found
  return (
    <div className={cn('space-y-4', className)}>
      {/* Score indicator */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-status-warning" />
          <span className="font-medium text-status-warning">Quality Issues Detected</span>
        </div>
        <span
          className={cn(
            'text-sm font-medium',
            result.score >= 70
              ? 'text-status-warning'
              : result.score >= 40
                ? 'text-status-warning'
                : 'text-status-danger'
          )}
        >
          Score: {result.score}/100
        </span>
      </div>

      {/* Quality score bar */}
      <Progress
        value={result.score}
        className={cn(
          'h-2',
          result.score >= 70
            ? '[&>div]:bg-status-warning'
            : result.score >= 40
              ? '[&>div]:bg-status-warning'
              : '[&>div]:bg-status-danger'
        )}
      />

      {/* Individual checks */}
      <div className="space-y-2">
        {/* Blur check */}
        <QualityCheckItem
          icon={Eye}
          label="Sharpness"
          passed={result.checks.blur.passed}
          message={result.checks.blur.message}
        />

        {/* Brightness check */}
        <QualityCheckItem
          icon={Sun}
          label="Brightness"
          passed={result.checks.brightness.passed}
          message={result.checks.brightness.message}
        />

        {/* Contrast check */}
        <QualityCheckItem
          icon={Camera}
          label="Contrast"
          passed={result.checks.contrast.passed}
          message={result.checks.contrast.message}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <Button variant="outline" className="flex-1" onClick={onRetake}>
          <Camera className="h-4 w-4 mr-2" />
          Retake
        </Button>
        <Button
          variant="secondary"
          className="flex-1"
          onClick={onProceed}
        >
          Use Anyway
        </Button>
      </div>
    </div>
  );
}

interface QualityCheckItemProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  passed: boolean;
  message: string;
}

function QualityCheckItem({
  icon: Icon,
  label,
  passed,
  message,
}: QualityCheckItemProps) {
  return (
    <div className="flex items-center gap-3 p-2 rounded-lg bg-muted/50">
      <div
        className={cn(
          'flex items-center justify-center w-8 h-8 rounded-full',
          passed ? 'bg-status-success/10' : 'bg-status-danger/10'
        )}
      >
        {passed ? (
          <CheckCircle2 className="h-4 w-4 text-status-success" />
        ) : (
          <XCircle className="h-4 w-4 text-status-danger" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm">{label}</p>
        <p className="text-xs text-muted-foreground truncate">{message}</p>
      </div>
      <Icon
        className={cn(
          'h-4 w-4 flex-shrink-0',
          passed ? 'text-muted-foreground' : 'text-status-danger'
        )}
      />
    </div>
  );
}

/**
 * Inline quality indicator for camera preview.
 */
export function QualityIndicator({
  isBlurry,
  className,
}: {
  isBlurry: boolean;
  className?: string;
}) {
  if (!isBlurry) return null;

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-full',
        'bg-status-warning/90 text-white text-sm font-medium',
        className
      )}
    >
      <AlertTriangle className="h-4 w-4" />
      <span>Image appears blurry</span>
    </div>
  );
}
