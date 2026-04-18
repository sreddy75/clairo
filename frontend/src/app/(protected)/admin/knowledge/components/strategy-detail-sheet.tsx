'use client';

/**
 * Admin-side strategy detail Sheet (Spec 060 T044).
 *
 * Different from the chat-facing `StrategyDetailSheet` in
 * `components/tax-planning/` — this view reads from the admin detail
 * endpoint, exposes `source_ref` (admin-only), and surfaces the six-button
 * action bar that drives stage transitions.
 *
 * Button disabled logic mirrors the backend state machine
 * (`service._ALLOWED_TRANSITIONS` + `_validate_stage_precondition`). The
 * authoritative response comes back after each mutation and the query
 * invalidates, so the disabled state always reflects the current row.
 */

import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import type {
  StrategyStatus,
  TaxStrategyDetail,
} from '@/lib/api/tax-strategies';
import { cn } from '@/lib/utils';

import {
  useApproveAndPublish,
  useRejectToDraft,
  useStrategyDetail,
  useSubmitForReview,
  useTriggerStage,
} from '../hooks/use-tax-strategies';

interface Props {
  strategyId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Allowed current statuses for each admin action — mirrors
// `service._validate_stage_precondition` + the in_review/approved branches
// in `_ALLOWED_TRANSITIONS`. Keep in lockstep when the backend changes.
type StageAction = 'research' | 'draft' | 'enrich' | 'submit' | 'approve' | 'reject';

const STAGE_ALLOWED_STATUSES: Record<StageAction, StrategyStatus[]> = {
  research: ['stub', 'enriched', 'drafted'],
  draft: ['researching', 'enriched'],
  enrich: ['drafted'],
  submit: ['enriched'],
  approve: ['in_review'],
  reject: ['in_review'],
};

export function StrategyAdminDetailSheet({
  strategyId,
  open,
  onOpenChange,
}: Props) {
  const detailQuery = useStrategyDetail(strategyId, { enabled: open });
  const [rejectOpen, setRejectOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>
            {detailQuery.data?.name ?? strategyId ?? 'Strategy'}
          </SheetTitle>
          <SheetDescription>
            {strategyId}
            {detailQuery.data && ` · v${detailQuery.data.version} · status: ${detailQuery.data.status.replace('_', ' ')}`}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {detailQuery.isPending && <DetailSkeleton />}

          {detailQuery.isError && (
            <p className="text-sm text-destructive">
              Failed to load strategy: {detailQuery.error.message}
            </p>
          )}

          {detailQuery.data && (
            <>
              <ActionBar
                detail={detailQuery.data}
                onRejectRequested={() => setRejectOpen(true)}
              />

              {detailQuery.data.categories.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {detailQuery.data.categories.map((c) => (
                    <Badge key={c} variant="secondary" className="text-xs">
                      {c.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                </div>
              )}

              <Metadata detail={detailQuery.data} />

              <Section title="Implementation">
                <ProseBlock>{detailQuery.data.implementation_text}</ProseBlock>
              </Section>

              <Section title="Explanation">
                <ProseBlock>{detailQuery.data.explanation_text}</ProseBlock>
              </Section>

              {detailQuery.data.ato_sources.length > 0 && (
                <Section title="ATO sources">
                  <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
                    {detailQuery.data.ato_sources.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </Section>
              )}

              {detailQuery.data.case_refs.length > 0 && (
                <Section title="Cases">
                  <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
                    {detailQuery.data.case_refs.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </Section>
              )}
            </>
          )}
        </div>

        <RejectDialog
          open={rejectOpen}
          onOpenChange={setRejectOpen}
          strategyId={strategyId}
        />
      </SheetContent>
    </Sheet>
  );
}

function ActionBar({
  detail,
  onRejectRequested,
}: {
  detail: TaxStrategyDetail;
  onRejectRequested: () => void;
}) {
  const status = detail.status;
  const strategyId = detail.strategy_id;
  const trigger = useTriggerStage();
  const submit = useSubmitForReview();
  const approve = useApproveAndPublish();

  const busy =
    trigger.isPending || submit.isPending || approve.isPending;

  const can = (action: StageAction) =>
    STAGE_ALLOWED_STATUSES[action].includes(status);

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={!can('research') || busy}
        onClick={() =>
          trigger.mutate({ strategyId, stage: 'research' })
        }
      >
        Research
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={!can('draft') || busy}
        onClick={() => trigger.mutate({ strategyId, stage: 'draft' })}
      >
        Draft
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={!can('enrich') || busy}
        onClick={() => trigger.mutate({ strategyId, stage: 'enrich' })}
      >
        Enrich
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={!can('submit') || busy}
        onClick={() => submit.mutate(strategyId)}
      >
        Submit for review
      </Button>
      <Button
        size="sm"
        disabled={!can('approve') || busy}
        onClick={() => approve.mutate(strategyId)}
      >
        Approve &amp; publish
      </Button>
      <Button
        size="sm"
        variant="destructive"
        disabled={!can('reject') || busy}
        onClick={onRejectRequested}
      >
        Reject
      </Button>
    </div>
  );
}

function Metadata({ detail }: { detail: TaxStrategyDetail }) {
  const fields: Array<[string, React.ReactNode]> = [
    ['Tenant', detail.tenant_id],
    ['Version', String(detail.version)],
    ['Source ref', detail.source_ref ?? '—'],
    [
      'Last reviewed',
      detail.last_reviewed_at
        ? new Date(detail.last_reviewed_at).toLocaleString('en-AU')
        : '—',
    ],
    ['Reviewer', detail.reviewer_display_name ?? '—'],
    ['Keywords', detail.keywords.length > 0 ? detail.keywords.join(', ') : '—'],
  ];
  return (
    <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {fields.map(([label, value]) => (
        <div key={label} className="flex flex-col">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">
            {label}
          </dt>
          <dd className="text-sm text-foreground">{value}</dd>
        </div>
      ))}
    </dl>
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

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className={cn('h-8 w-24')} />
        ))}
      </div>
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

function RejectDialog({
  open,
  onOpenChange,
  strategyId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategyId: string | null;
}) {
  const [notes, setNotes] = useState('');
  const reject = useRejectToDraft({
    onSuccess: () => {
      setNotes('');
      onOpenChange(false);
    },
  });

  const submit = () => {
    if (!strategyId || notes.trim().length === 0) return;
    reject.mutate({ strategyId, reviewerNotes: notes.trim() });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject to drafted</DialogTitle>
          <DialogDescription>
            Send the strategy back to drafted with reviewer notes. The notes
            are included in the audit trail and shown to the next drafter.
          </DialogDescription>
        </DialogHeader>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Reviewer notes (required)…"
          className="min-h-[120px] w-full resize-y rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          maxLength={2000}
        />
        {reject.isError && (
          <p className="text-sm text-destructive">
            {reject.error.message}
          </p>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={reject.isPending}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={submit}
            disabled={notes.trim().length === 0 || reject.isPending}
          >
            {reject.isPending ? 'Rejecting…' : 'Reject'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
