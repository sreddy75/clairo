'use client';

import {
  DndContext,
  type DragEndEvent,
  DragOverlay,
  type DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useCallback, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { FeedbackSubmission, SubmissionStatus } from '@/types/feedback';

import { FeedbackCard } from './FeedbackCard';

interface KanbanBoardProps {
  submissions: FeedbackSubmission[];
  onStatusChange: (submissionId: string, newStatus: SubmissionStatus) => void;
  onCardClick: (submission: FeedbackSubmission) => void;
}

interface ColumnDef {
  status: SubmissionStatus;
  label: string;
  accentClass: string;
}

const columns: ColumnDef[] = [
  { status: 'new', label: 'New', accentClass: 'border-t-primary' },
  { status: 'in_review', label: 'In Review', accentClass: 'border-t-amber-500' },
  { status: 'planned', label: 'Planned', accentClass: 'border-t-amber-500' },
  {
    status: 'in_progress',
    label: 'In Progress',
    accentClass: 'border-t-blue-500',
  },
  { status: 'done', label: 'Done', accentClass: 'border-t-emerald-500' },
];

/* ------------------------------------------------------------------ */
/*  SortableCard — wraps FeedbackCard with dnd-kit sortable behavior  */
/* ------------------------------------------------------------------ */

function SortableCard({
  submission,
  onCardClick,
}: {
  submission: FeedbackSubmission;
  onCardClick: (submission: FeedbackSubmission) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: submission.id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : undefined,
  };

  return (
    <div ref={setNodeRef}>
      <FeedbackCard
        submission={submission}
        onClick={onCardClick}
        dragAttributes={attributes as unknown as Record<string, unknown>}
        dragListeners={listeners as unknown as Record<string, unknown>}
        style={style}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  KanbanBoard                                                       */
/* ------------------------------------------------------------------ */

export function KanbanBoard({
  submissions,
  onStatusChange,
  onCardClick,
}: KanbanBoardProps) {
  const [activeSubmission, setActiveSubmission] =
    useState<FeedbackSubmission | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const submissionsByStatus = useCallback(
    (status: SubmissionStatus) =>
      submissions.filter((s) => s.status === status),
    [submissions]
  );

  function handleDragStart(event: DragStartEvent) {
    const found = submissions.find((s) => s.id === event.active.id);
    setActiveSubmission(found ?? null);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveSubmission(null);

    const { active, over } = event;
    if (!over) return;

    // Determine target column: the "over" could be a card or a droppable column
    const draggedId = active.id as string;
    const overId = over.id as string;

    // Check if dropped over a column droppable
    const targetColumn = columns.find((c) => c.status === overId);
    let targetStatus: SubmissionStatus | null = targetColumn
      ? targetColumn.status
      : null;

    // If dropped over another card, find that card's status
    if (!targetStatus) {
      const overSubmission = submissions.find((s) => s.id === overId);
      if (overSubmission) {
        targetStatus = overSubmission.status;
      }
    }

    if (!targetStatus) return;

    // Find current status of dragged item
    const draggedSubmission = submissions.find((s) => s.id === draggedId);
    if (!draggedSubmission) return;

    if (draggedSubmission.status !== targetStatus) {
      onStatusChange(draggedId, targetStatus);
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="grid grid-cols-5 gap-4 max-lg:grid-cols-1 max-lg:overflow-x-auto">
        {columns.map((col) => {
          const items = submissionsByStatus(col.status);
          return (
            <SortableContext
              key={col.status}
              id={col.status}
              items={items.map((s) => s.id)}
              strategy={verticalListSortingStrategy}
            >
              <div
                className={cn(
                  'bg-muted/30 rounded-lg p-3 min-h-[200px] border-t-2',
                  col.accentClass
                )}
              >
                {/* Column header */}
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium">{col.label}</h3>
                  <Badge variant="secondary" className="tabular-nums">
                    {items.length}
                  </Badge>
                </div>

                {/* Cards */}
                <div className="space-y-2">
                  {items.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-6">
                      No submissions
                    </p>
                  ) : (
                    items.map((submission) => (
                      <SortableCard
                        key={submission.id}
                        submission={submission}
                        onCardClick={onCardClick}
                      />
                    ))
                  )}
                </div>
              </div>
            </SortableContext>
          );
        })}
      </div>

      {/* Drag overlay — shows a floating copy of the card while dragging */}
      <DragOverlay>
        {activeSubmission ? (
          <FeedbackCard
            submission={activeSubmission}
            onClick={() => {}}
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
