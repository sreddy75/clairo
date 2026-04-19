'use client';

/**
 * Side-sheet detail view for a single tax strategy (Spec 060 T039).
 *
 * Opened by clicking a `StrategyChip`. Hydrates the full strategy payload
 * (implementation, explanation, ATO sources, case refs) via
 * `useStrategyHydration`. Graceful-degrades to an explanatory empty state
 * when the strategy id can't be resolved — a hallucinated CLR-XXX, a
 * superseded version, or an unpublished draft the user shouldn't see.
 */

import { AlertTriangle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

import { useStrategyHydration } from './useStrategyHydration';

interface StrategyDetailSheetProps {
  strategyId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StrategyDetailSheet({
  strategyId,
  open,
  onOpenChange,
}: StrategyDetailSheetProps) {
  const idsForHydration = strategyId ? [strategyId] : [];
  const query = useStrategyHydration(idsForHydration, { enabled: open });
  const strategy = strategyId ? query.data?.get(strategyId) : undefined;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>{strategy?.name ?? strategyId ?? 'Strategy'}</SheetTitle>
          <SheetDescription>
            {strategyId && `${strategyId}`}
            {strategy && ` · v${strategy.version}`}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {query.isPending && (
            <p className="text-sm text-muted-foreground">Loading strategy…</p>
          )}

          {query.isError && (
            <UnavailableState
              title="Couldn't load this strategy"
              description="There was a problem hydrating the strategy. Try again in a moment."
            />
          )}

          {!query.isPending && !query.isError && !strategy && (
            <UnavailableState
              title="Strategy not found"
              description={
                strategyId
                  ? `We couldn't find a published strategy matching ${strategyId}. The assistant may have cited it in error, or it may have been superseded.`
                  : 'No strategy selected.'
              }
            />
          )}

          {strategy && (
            <>
              {strategy.categories.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {strategy.categories.map((c) => (
                    <Badge key={c} variant="secondary" className="text-xs">
                      {c.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                </div>
              )}

              <Section title="Implementation">
                <ProseBlock>{strategy.implementation_text}</ProseBlock>
              </Section>

              <Section title="Explanation">
                <ProseBlock>{strategy.explanation_text}</ProseBlock>
              </Section>

              {strategy.ato_sources.length > 0 && (
                <Section title="ATO sources">
                  <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
                    {strategy.ato_sources.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </Section>
              )}

              {strategy.case_refs.length > 0 && (
                <Section title="Cases">
                  <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
                    {strategy.case_refs.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </Section>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      <Separator />
      {children}
    </div>
  );
}

function ProseBlock({ children }: { children: string }) {
  if (!children || children.trim().length === 0) {
    return <p className="text-sm italic text-muted-foreground">(empty)</p>;
  }
  return (
    <div className="whitespace-pre-wrap text-sm leading-6 text-foreground">
      {children}
    </div>
  );
}

function UnavailableState({
  title,
  description,
  className,
}: {
  title: string;
  description: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm dark:border-amber-900/40 dark:bg-amber-950/30',
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
      <div className="space-y-1">
        <p className="font-medium text-foreground">{title}</p>
        <p className="text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
