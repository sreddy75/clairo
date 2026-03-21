/**
 * Page Thumbnail Strip Component
 *
 * Displays captured pages with reordering and delete capabilities.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

'use client';

import { X, GripVertical } from 'lucide-react';
import Image from 'next/image';
import { useState, useCallback } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface PageThumbnail {
  id: string;
  imageUrl: string;
  order: number;
}

interface PageThumbnailStripProps {
  /** Array of page thumbnails */
  pages: PageThumbnail[];
  /** Currently selected page */
  selectedId?: string;
  /** Callback when page is selected */
  onSelect?: (id: string) => void;
  /** Callback when page is deleted */
  onDelete?: (id: string) => void;
  /** Callback when pages are reordered */
  onReorder?: (pages: PageThumbnail[]) => void;
  /** Custom class name */
  className?: string;
}

export function PageThumbnailStrip({
  pages,
  selectedId,
  onSelect,
  onDelete,
  onReorder,
  className,
}: PageThumbnailStripProps) {
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  const handleDragStart = useCallback(
    (e: React.DragEvent, id: string) => {
      setDraggedId(id);
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', id);
    },
    []
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent, id: string) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (id !== draggedId) {
        setDragOverId(id);
      }
    },
    [draggedId]
  );

  const handleDragLeave = useCallback(() => {
    setDragOverId(null);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, targetId: string) => {
      e.preventDefault();
      setDragOverId(null);
      setDraggedId(null);

      if (!draggedId || draggedId === targetId) return;

      const draggedIndex = pages.findIndex((p) => p.id === draggedId);
      const targetIndex = pages.findIndex((p) => p.id === targetId);

      if (draggedIndex === -1 || targetIndex === -1) return;

      // Reorder pages
      const newPages = [...pages];
      const [removed] = newPages.splice(draggedIndex, 1);
      if (!removed) return;
      newPages.splice(targetIndex, 0, removed);

      // Update order values
      const reorderedPages = newPages.map((p, i) => ({
        ...p,
        order: i,
      }));

      onReorder?.(reorderedPages);
    },
    [draggedId, pages, onReorder]
  );

  const handleDragEnd = useCallback(() => {
    setDraggedId(null);
    setDragOverId(null);
  }, []);

  if (pages.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'flex gap-2 overflow-x-auto py-2 px-1 scrollbar-thin',
        className
      )}
    >
      {pages.map((page) => (
        <div
          key={page.id}
          draggable
          onDragStart={(e) => handleDragStart(e, page.id)}
          onDragOver={(e) => handleDragOver(e, page.id)}
          onDragLeave={handleDragLeave}
          onDrop={(e) => handleDrop(e, page.id)}
          onDragEnd={handleDragEnd}
          className={cn(
            'relative flex-shrink-0 cursor-grab active:cursor-grabbing',
            'transition-all duration-150',
            draggedId === page.id && 'opacity-50 scale-95',
            dragOverId === page.id && 'scale-110',
            selectedId === page.id && 'ring-2 ring-primary ring-offset-2'
          )}
          onClick={() => onSelect?.(page.id)}
        >
          {/* Thumbnail */}
          <div className="relative w-16 h-20 rounded-md overflow-hidden bg-muted">
            <Image
              src={page.imageUrl}
              alt={`Page ${page.order + 1}`}
              fill
              className="object-cover"
            />

            {/* Page number badge */}
            <div className="absolute bottom-1 left-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
              {page.order + 1}
            </div>

            {/* Drag handle */}
            <div className="absolute top-1 left-1 text-white/80">
              <GripVertical className="h-3 w-3" />
            </div>
          </div>

          {/* Delete button */}
          {onDelete && (
            <Button
              variant="destructive"
              size="icon"
              className="absolute -top-2 -right-2 h-5 w-5 rounded-full"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(page.id);
              }}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}
