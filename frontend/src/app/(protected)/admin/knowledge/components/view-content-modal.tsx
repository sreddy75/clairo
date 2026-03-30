'use client';

import { ChevronLeft, ChevronRight, ExternalLink, FileText, LayoutList, Loader2, ScrollText, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  getSourceContent,
  type SourceChunkContent,
  type SourceContentResponse,
} from '@/lib/api/knowledge';
import { cn } from '@/lib/utils';

type ViewMode = 'chunks' | 'full';

interface ViewContentModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceId: string;
  sourceName: string;
  token: string;
}

export function ViewContentModal({
  isOpen,
  onClose,
  sourceId,
  sourceName,
  token,
}: ViewContentModalProps) {
  const [content, setContent] = useState<SourceContentResponse | null>(null);
  const [allContent, setAllContent] = useState<SourceChunkContent[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingAll, setLoadingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('chunks');

  const PAGE_SIZE = 10;

  useEffect(() => {
    if (isOpen && sourceId) {
      setViewMode('chunks');
      setAllContent([]);
      loadContent(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadContent is defined after this hook, only re-run on open/sourceId change
  }, [isOpen, sourceId]);

  const loadContent = async (pageNum: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSourceContent(
        token,
        sourceId,
        PAGE_SIZE,
        pageNum * PAGE_SIZE
      );
      setContent(data);
      setPage(pageNum);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load content');
    } finally {
      setLoading(false);
    }
  };

  const loadAllContent = async () => {
    if (allContent.length > 0 || !content) return;

    setLoadingAll(true);
    try {
      const data = await getSourceContent(token, sourceId, 500, 0);
      setAllContent(data.chunks);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load full content');
    } finally {
      setLoadingAll(false);
    }
  };

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode);
    if (mode === 'full' && allContent.length === 0) {
      loadAllContent();
    }
  };

  const totalPages = content ? Math.ceil(content.total_chunks / PAGE_SIZE) : 0;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative bg-card rounded-2xl shadow-lg w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden border border-border">
        {/* Header */}
        <div className="px-6 py-4 bg-muted border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg">
                <FileText className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-foreground">
                  View Indexed Content
                </h2>
                <p className="text-sm text-muted-foreground truncate max-w-md">
                  {sourceName}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* View Mode Toggle */}
              <div className="flex items-center bg-card rounded-lg border border-border p-1">
                <button
                  onClick={() => handleViewModeChange('chunks')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                    viewMode === 'chunks'
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                  title="View as individual chunks"
                >
                  <LayoutList className="w-4 h-4" />
                  Chunks
                </button>
                <button
                  onClick={() => handleViewModeChange('full')}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors',
                    viewMode === 'full'
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                  title="View as continuous document"
                >
                  <ScrollText className="w-4 h-4" />
                  Full Content
                </button>
              </div>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
                <X className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <span className="ml-3 text-muted-foreground">Loading content...</span>
            </div>
          )}

          {error && (
            <div className="bg-destructive/10 text-destructive p-4 rounded-lg">
              {error}
            </div>
          )}

          {!loading && !error && content && (
            <>
              {/* Stats */}
              <div className="mb-4 flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{content.total_chunks}</span> chunks indexed in{' '}
                  <span className="font-medium text-primary">{content.collection}</span>
                </div>
                {viewMode === 'chunks' && totalPages > 1 && (
                  <div className="text-sm text-muted-foreground">
                    Page {page + 1} of {totalPages}
                  </div>
                )}
              </div>

              {content.chunks.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No content chunks found for this source.</p>
                  <p className="text-sm mt-1">Content may not have been ingested yet.</p>
                </div>
              ) : viewMode === 'chunks' ? (
                <div className="space-y-3">
                  {content.chunks.map((chunk) => (
                    <ChunkCard
                      key={chunk.chunk_id}
                      chunk={chunk}
                      isExpanded={expandedChunk === chunk.chunk_id}
                      onToggle={() =>
                        setExpandedChunk(
                          expandedChunk === chunk.chunk_id ? null : chunk.chunk_id
                        )
                      }
                    />
                  ))}
                </div>
              ) : (
                <div className="bg-card border border-border rounded-lg">
                  {loadingAll ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                      <span className="ml-3 text-muted-foreground">Loading full content...</span>
                    </div>
                  ) : (
                    <div className="prose prose-sm max-w-none p-6 dark:prose-invert">
                      <h1 className="text-xl font-bold text-foreground mb-4 pb-4 border-b border-border">
                        {sourceName}
                      </h1>
                      {allContent.map((chunk, index) => (
                        <div key={chunk.chunk_id} className="mb-6">
                          {chunk.title && chunk.title !== allContent[index - 1]?.title && (
                            <h2 className="text-lg font-semibold text-foreground mb-2 mt-6">
                              {chunk.title}
                            </h2>
                          )}
                          <div className="text-foreground/80 leading-relaxed whitespace-pre-wrap">
                            {chunk.text}
                          </div>
                          {index < allContent.length - 1 && (
                            <hr className="my-6 border-border" />
                          )}
                        </div>
                      ))}
                      {allContent.length === 0 && !loadingAll && (
                        <p className="text-muted-foreground italic">No content available.</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer with Pagination */}
        <div className="px-6 py-4 bg-muted border-t border-border flex items-center justify-between">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>

          {viewMode === 'chunks' && totalPages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => loadContent(page - 1)}
                disabled={page === 0 || loading}
              >
                <ChevronLeft className="w-5 h-5" />
              </Button>
              <span className="text-sm text-muted-foreground min-w-[80px] text-center">
                {page + 1} / {totalPages}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => loadContent(page + 1)}
                disabled={page >= totalPages - 1 || loading}
              >
                <ChevronRight className="w-5 h-5" />
              </Button>
            </div>
          )}

          {viewMode === 'full' && allContent.length > 0 && (
            <div className="text-sm text-muted-foreground">
              Showing all {allContent.length} chunks as continuous text
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ChunkCard({
  chunk,
  isExpanded,
  onToggle,
}: {
  chunk: SourceChunkContent;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const previewText = chunk.text.slice(0, 200);
  const hasMore = chunk.text.length > 200;

  return (
    <div className="border border-border rounded-lg overflow-hidden hover:border-primary/30 transition-colors">
      <div className="px-4 py-2 bg-muted border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3 text-sm">
          {chunk.chunk_index !== null && (
            <span className="px-2 py-0.5 bg-primary/10 text-primary rounded font-mono text-xs">
              #{chunk.chunk_index}
            </span>
          )}
          <span className="font-medium text-foreground truncate max-w-md">
            {chunk.title || 'Untitled Chunk'}
          </span>
        </div>
        {chunk.source_url && (
          <a
            href={chunk.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-primary transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>

      <div
        className="px-4 py-3 cursor-pointer"
        onClick={onToggle}
      >
        <div className={cn('text-sm text-foreground/80 whitespace-pre-wrap', !isExpanded && 'line-clamp-4')}>
          {isExpanded ? chunk.text : (hasMore ? `${previewText}...` : chunk.text)}
        </div>
        {hasMore && (
          <button
            className="mt-2 text-xs text-primary hover:text-primary/80 font-medium"
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>

      {chunk.source_type && (
        <div className="px-4 py-2 bg-muted border-t border-border text-xs text-muted-foreground">
          Type: <span className="font-medium">{chunk.source_type}</span>
        </div>
      )}
    </div>
  );
}
