'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  CheckCircle2,
  Edit2,
  ExternalLink,
  FileText,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';

import { SOURCE_TYPES, type KnowledgeSource, type KnowledgeSourceCreate } from '@/types/knowledge';

import { useSources } from '../hooks/use-sources';

import { SourceFormModal } from './source-form-modal';
import { UploadContentModal } from './upload-content-modal';
import { ViewContentModal } from './view-content-modal';

export function SourcesTab() {
  const { getToken } = useAuth();
  const {
    sources,
    isLoading,
    error,
    refresh,
    create,
    update,
    remove,
    ingest,
    isOperating,
  } = useSources();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<KnowledgeSource | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [ingestingId, setIngestingId] = useState<string | null>(null);
  const [viewingSource, setViewingSource] = useState<KnowledgeSource | null>(null);
  const [uploadingSource, setUploadingSource] = useState<KnowledgeSource | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const handleViewContent = async (source: KnowledgeSource) => {
    const t = await getToken();
    if (t) {
      setToken(t);
      setViewingSource(source);
    }
  };

  const handleCreate = () => {
    setEditingSource(null);
    setIsModalOpen(true);
  };

  const handleEdit = (source: KnowledgeSource) => {
    setEditingSource(source);
    setIsModalOpen(true);
  };

  const handleSubmit = async (data: KnowledgeSourceCreate) => {
    if (editingSource) {
      await update(editingSource.id, {
        name: data.name,
        scrape_config: data.scrape_config,
        is_active: data.is_active,
      });
    } else {
      await create(data);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this source? This cannot be undone.')) {
      return;
    }
    setDeletingId(id);
    try {
      await remove(id);
    } finally {
      setDeletingId(null);
    }
  };

  const handleIngest = async (id: string) => {
    setIngestingId(id);
    try {
      await ingest(id);
      alert('Ingestion job started! Check the Jobs tab to monitor progress.');
    } catch {
      // Error handled by hook
    } finally {
      setIngestingId(null);
    }
  };

  const getSourceTypeLabel = (type: string) => {
    return SOURCE_TYPES.find((t) => t.value === type)?.label || type;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4">
        <div className="flex items-center gap-2 text-status-danger">
          <AlertCircle className="w-5 h-5" />
          <span className="font-medium">Error loading sources</span>
        </div>
        <p className="text-status-danger text-sm mt-1">{error}</p>
        <button
          onClick={() => refresh()}
          className="mt-3 px-3 py-1.5 text-sm bg-status-danger/10 hover:bg-status-danger/20 text-status-danger rounded-md transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Knowledge Sources
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Configure content sources for the knowledge base
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refresh()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleCreate}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Source
          </button>
        </div>
      </div>

      {/* Sources Table */}
      {sources.length > 0 ? (
        <div className="bg-card rounded-xl border border-border overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted border-b border-border">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Source
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Collection
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Last Scraped
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sources.map((source) => (
                <tr key={source.id} className="hover:bg-muted">
                  <td className="px-4 py-3">
                    <div>
                      <div className="font-medium text-foreground">{source.name}</div>
                      <a
                        href={source.base_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary hover:underline flex items-center gap-1 mt-0.5"
                      >
                        {truncateUrl(source.base_url)}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-muted-foreground">
                      {getSourceTypeLabel(source.source_type)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm font-mono text-muted-foreground">
                      {source.collection_name}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {source.is_active ? (
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-status-success bg-status-success/10 rounded-full">
                        <CheckCircle2 className="w-3 h-3" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-muted-foreground bg-muted rounded-full">
                        <XCircle className="w-3 h-3" />
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm text-muted-foreground">
                      {source.last_scraped_at
                        ? formatDate(source.last_scraped_at)
                        : 'Never'}
                    </div>
                    {source.last_error && (
                      <div className="text-xs text-status-danger mt-0.5 truncate max-w-[150px]">
                        {source.last_error}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleViewContent(source)}
                        className="p-1.5 text-status-success hover:bg-status-success/10 rounded-md transition-colors"
                        title="View Content"
                      >
                        <FileText className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setUploadingSource(source)}
                        className="p-1.5 text-primary hover:bg-primary/10 rounded-md transition-colors"
                        title="Upload Content"
                      >
                        <Upload className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleIngest(source.id)}
                        disabled={ingestingId === source.id || !source.is_active}
                        title={source.is_active ? 'Run Ingestion' : 'Source is inactive'}
                        className="p-1.5 text-status-success hover:bg-status-success/10 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {ingestingId === source.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Play className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => handleEdit(source)}
                        className="p-1.5 text-muted-foreground hover:bg-muted rounded-md transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(source.id)}
                        disabled={deletingId === source.id}
                        className="p-1.5 text-status-danger hover:bg-status-danger/10 rounded-md disabled:opacity-50 transition-colors"
                        title="Delete"
                      >
                        {deletingId === source.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 bg-muted rounded-lg border border-dashed border-border">
          <ExternalLink className="w-12 h-12 text-muted-foreground mx-auto" />
          <h3 className="mt-4 text-lg font-medium text-foreground">
            No sources configured
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Add a knowledge source to start ingesting content.
          </p>
          <button
            onClick={handleCreate}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add First Source
          </button>
        </div>
      )}

      {/* Edit/Create Modal */}
      <SourceFormModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleSubmit}
        source={editingSource}
        isSubmitting={isOperating}
      />

      {/* View Content Modal */}
      {viewingSource && token && (
        <ViewContentModal
          isOpen={!!viewingSource}
          onClose={() => setViewingSource(null)}
          sourceId={viewingSource.id}
          sourceName={viewingSource.name}
          token={token}
        />
      )}

      {/* Upload Content Modal */}
      {uploadingSource && (
        <UploadContentModal
          isOpen={!!uploadingSource}
          onClose={() => setUploadingSource(null)}
          source={uploadingSource}
          onSuccess={() => refresh()}
        />
      )}
    </div>
  );
}

function truncateUrl(url: string, maxLength = 40): string {
  if (url.length <= maxLength) return url;
  return url.substring(0, maxLength - 3) + '...';
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
