'use client';

import { Lock, Sparkles, TrendingUp } from 'lucide-react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { SubscriptionTier } from '@/types/billing';

interface UpgradePromptProps {
  feature: string;
  requiredTier: SubscriptionTier;
  currentTier: SubscriptionTier;
  variant?: 'inline' | 'card' | 'banner';
  message?: string;
  className?: string;
  onUpgrade?: () => void;
}

const FEATURE_NAMES: Record<string, string> = {
  custom_triggers: 'Custom Triggers',
  client_portal: 'Client Portal',
  api_access: 'API Access',
  knowledge_base: 'Knowledge Base',
  magic_zone: 'Magic Zone',
  ai_insights: 'AI Insights',
};

const TIER_DISPLAY_NAMES: Record<SubscriptionTier, string> = {
  starter: 'Starter',
  professional: 'Professional',
  growth: 'Growth',
  enterprise: 'Enterprise',
};

export function UpgradePrompt({
  feature,
  requiredTier,
  currentTier,
  variant = 'card',
  message,
  className,
  onUpgrade,
}: UpgradePromptProps) {
  const featureName = FEATURE_NAMES[feature] || feature;
  const requiredTierName = TIER_DISPLAY_NAMES[requiredTier];

  const defaultMessage =
    message ||
    `${featureName} is available on ${requiredTierName} plan and above.`;

  if (variant === 'inline') {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 text-sm text-status-warning',
          className
        )}
      >
        <Lock className="h-3.5 w-3.5" />
        <span>{defaultMessage}</span>
        <Link
          href="/pricing"
          onClick={onUpgrade}
          className="font-medium text-primary hover:underline"
        >
          Upgrade
        </Link>
      </span>
    );
  }

  if (variant === 'banner') {
    return (
      <div
        className={cn(
          'flex items-center justify-between gap-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-500/20 dark:bg-amber-500/10',
          className
        )}
      >
        <div className="flex items-center gap-3">
          <Lock className="h-5 w-5 text-status-warning" />
          <span className="text-sm text-amber-800 dark:text-amber-200">{defaultMessage}</span>
        </div>
        <Button asChild size="sm">
          <Link href="/pricing" onClick={onUpgrade}>
            <TrendingUp className="mr-1.5 h-4 w-4" />
            Upgrade
          </Link>
        </Button>
      </div>
    );
  }

  // Card variant (default)
  return (
    <Card className={cn(className)}>
      <CardContent className="p-6 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-500/10">
          <Lock className="h-7 w-7 text-status-warning" />
        </div>

        <h3 className="mt-4 text-lg font-semibold">
          {featureName} Locked
        </h3>

        <p className="mt-2 text-sm text-muted-foreground">{defaultMessage}</p>

        <div className="mt-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <span>Your plan:</span>
          <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 font-medium text-foreground">
            {TIER_DISPLAY_NAMES[currentTier]}
          </span>
        </div>

        <Button asChild className="mt-6">
          <Link href="/pricing" onClick={onUpgrade}>
            <Sparkles className="mr-2 h-4 w-4" />
            Upgrade to {requiredTierName}
          </Link>
        </Button>

        <p className="mt-4 text-xs text-muted-foreground">
          Upgrade anytime. Cancel anytime.
        </p>
      </CardContent>
    </Card>
  );
}

/**
 * Higher-order component for feature gating.
 */
export function withFeatureGate<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  config: {
    feature: string;
    requiredTier: SubscriptionTier;
  }
) {
  return function FeatureGatedComponent(props: P & { currentTier: SubscriptionTier }) {
    const { currentTier, ...rest } = props;

    const tierOrder: SubscriptionTier[] = [
      'starter',
      'professional',
      'growth',
      'enterprise',
    ];
    const currentIndex = tierOrder.indexOf(currentTier);
    const requiredIndex = tierOrder.indexOf(config.requiredTier);

    if (currentIndex < requiredIndex) {
      return (
        <div className="flex min-h-[400px] items-center justify-center p-8">
          <UpgradePrompt
            feature={config.feature}
            requiredTier={config.requiredTier}
            currentTier={currentTier}
            variant="card"
          />
        </div>
      );
    }

    return <WrappedComponent {...(rest as P)} />;
  };
}

export default UpgradePrompt;
