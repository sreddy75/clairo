'use client';

import { useAuth } from '@clerk/nextjs';
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  ExternalLink,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  getCollectionContent,
  type CollectionContentItem,
  type CollectionContentResponse,
} from '@/lib/api/knowledge';
import type { CollectionInfo } from '@/types/knowledge';

import { useCollections } from '../hooks/use-collections';

// =============================================================================
// Source type display config
// =============================================================================

const SOURCE_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  legislation: { label: 'Legislation', color: 'bg-purple-500/10 text-purple-700' },
  ato_ruling: { label: 'ATO Rulings', color: 'bg-blue-500/10 text-blue-700' },
  ato_guide: { label: 'ATO Guides', color: 'bg-sky-500/10 text-sky-700' },
  ato_api: { label: 'ATO API', color: 'bg-violet-500/10 text-violet-700' },
  case_law: { label: 'Case Law', color: 'bg-amber-500/10 text-amber-700' },
  tpb_guidance: { label: 'TPB Guidance', color: 'bg-green-500/10 text-green-700' },
  tpb: { label: 'TPB Guidance', color: 'bg-green-500/10 text-green-700' },
  treasury: { label: 'Treasury', color: 'bg-teal-500/10 text-teal-700' },
  manual: { label: 'Manual Upload', color: 'bg-muted text-muted-foreground' },
  static_content: { label: 'Static Content', color: 'bg-muted text-muted-foreground' },
  pdf_url: { label: 'PDF Documents', color: 'bg-rose-500/10 text-rose-700' },
  ato_web: { label: 'ATO Web', color: 'bg-indigo-500/10 text-indigo-700' },
  ato_rss: { label: 'ATO RSS', color: 'bg-cyan-500/10 text-cyan-700' },
};

function getSourceTypeDisplay(type: string) {
  return SOURCE_TYPE_CONFIG[type] || { label: type, color: 'bg-muted text-muted-foreground' };
}

// =============================================================================
// Content Browser Modal
// =============================================================================

function ContentBrowser({
  collectionName,
  displayName,
  onClose,
}: {
  collectionName: string;
  displayName: string;
  onClose: () => void;
}) {
  const { getToken } = useAuth();
  const [data, setData] = useState<CollectionContentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sourceTypeFilter, setSourceTypeFilter] = useState<string | undefined>();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');

  const fetchContent = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error('Not authenticated');
      const result = await getCollectionContent(token, collectionName, {
        page,
        pageSize: 20,
        sourceType: sourceTypeFilter,
        search: searchQuery || undefined,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load content');
    } finally {
      setIsLoading(false);
    }
  }, [getToken, collectionName, page, sourceTypeFilter, searchQuery]);

  useEffect(() => {
    fetchContent();
  }, [fetchContent]);

  const handleSearch = () => {
    setPage(1);
    setSearchQuery(searchInput);
  };

  const handleFilterChange = (type: string | undefined) => {
    setPage(1);
    setSourceTypeFilter(type);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-card rounded-xl border border-border w-full max-w-4xl max-h-[85vh] flex flex-col shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {displayName}
            </h3>
            <p className="text-sm text-muted-foreground">
              {data ? `${data.total.toLocaleString()} documents` : 'Loading...'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-muted rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Filters */}
        <div className="px-6 py-3 border-b border-border flex flex-wrap gap-3 items-center">
          {/* Search */}
          <div className="flex items-center gap-2 flex-1 min-w-[200px]">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by title..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="w-full pl-9 pr-3 py-2 text-sm border border-border rounded-lg bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <button
              onClick={handleSearch}
              className="px-3 py-2 text-sm bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
            >
              Search
            </button>
          </div>

          {/* Source type filter pills */}
          {data?.source_type_counts && Object.keys(data.source_type_counts).length > 1 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <button
                onClick={() => handleFilterChange(undefined)}
                className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
                  !sourceTypeFilter
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:bg-muted'
                }`}
              >
                All
              </button>
              {Object.entries(data.source_type_counts).map(([type, count]) => {
                const display = getSourceTypeDisplay(type);
                return (
                  <button
                    key={type}
                    onClick={() => handleFilterChange(sourceTypeFilter === type ? undefined : type)}
                    className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
                      sourceTypeFilter === type
                        ? 'bg-primary text-primary-foreground'
                        : `${display.color} hover:opacity-80`
                    }`}
                  >
                    {display.label} ({count})
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-status-danger">
              <AlertCircle className="w-8 h-8 mx-auto mb-2" />
              <p>{error}</p>
            </div>
          ) : data && data.items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Database className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No content found</p>
            </div>
          ) : (
            <div className="space-y-2">
              {data?.items.map((item) => (
                <ContentRow key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="px-6 py-3 border-t border-border flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Page {data.page} of {data.total_pages}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-2 rounded-lg border border-border hover:bg-muted disabled:opacity-30 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page >= data.total_pages}
                className="p-2 rounded-lg border border-border hover:bg-muted disabled:opacity-30 transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ContentRow({ item }: { item: CollectionContentItem }) {
  const display = getSourceTypeDisplay(item.source_type);
  const date = new Date(item.created_at);

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${display.color}`}>
            {display.label}
          </span>
          {item.section_ref && (
            <span className="text-xs text-muted-foreground font-mono">
              {item.section_ref}
            </span>
          )}
        </div>
        <p className="text-sm font-medium text-foreground truncate">
          {item.title || item.natural_key || 'Untitled'}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5 truncate">
          {item.source_url}
        </p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="text-xs text-muted-foreground">
          {date.toLocaleDateString()}
        </span>
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 hover:bg-muted rounded transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5 text-muted-foreground" />
          </a>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Main Collections Tab
// =============================================================================

export function CollectionsTab() {
  const {
    collections,
    isLoading,
    error,
    refresh,
    initialize,
    isInitializing,
  } = useCollections();

  const [browsingCollection, setBrowsingCollection] = useState<{
    name: string;
    displayName: string;
  } | null>(null);

  const totalVectors = collections.reduce((sum, c) => sum + c.vectors_count, 0);
  const allExist = collections.every((c) => c.exists);

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
          <span className="font-medium">Error loading collections</span>
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
      {/* Summary Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Knowledge Base Collections
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            {collections.length} namespaces configured &middot;{' '}
            {totalVectors.toLocaleString()} total vectors
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
            onClick={() => initialize()}
            disabled={isInitializing || allExist}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {isInitializing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {allExist ? 'All Initialized' : 'Initialize All'}
          </button>
        </div>
      </div>

      {/* Collection Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {collections.map((collection) => (
          <CollectionCard
            key={collection.name}
            collection={collection}
            onBrowse={() =>
              setBrowsingCollection({
                name: collection.name,
                displayName: formatCollectionName(collection.name),
              })
            }
          />
        ))}
      </div>

      {/* Empty State */}
      {collections.length === 0 && (
        <div className="text-center py-12 bg-muted rounded-lg border border-dashed border-border">
          <Database className="w-12 h-12 text-muted-foreground mx-auto" />
          <h3 className="mt-4 text-lg font-medium text-foreground">
            No collections found
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Click &quot;Initialize All&quot; to create the knowledge base collections.
          </p>
        </div>
      )}

      {/* Content Browser Modal */}
      {browsingCollection && (
        <ContentBrowser
          collectionName={browsingCollection.name}
          displayName={browsingCollection.displayName}
          onClose={() => setBrowsingCollection(null)}
        />
      )}
    </div>
  );
}

// =============================================================================
// Collection Card with source type breakdown
// =============================================================================

function CollectionCard({
  collection,
  onBrowse,
}: {
  collection: CollectionInfo;
  onBrowse: () => void;
}) {
  return (
    <div
      className={`bg-card rounded-xl border p-5 ${
        collection.exists
          ? 'border-border'
          : 'border-status-warning/20 bg-status-warning/10'
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              collection.exists ? 'bg-primary/10' : 'bg-status-warning/10'
            }`}
          >
            <Database
              className={`w-5 h-5 ${
                collection.exists ? 'text-primary' : 'text-status-warning'
              }`}
            />
          </div>
          <div>
            <h4 className="font-semibold text-foreground">
              {formatCollectionName(collection.name)}
            </h4>
            <p className="text-xs text-muted-foreground font-mono">
              {collection.name}
            </p>
          </div>
        </div>
        {collection.exists ? (
          <CheckCircle2 className="w-5 h-5 text-status-success" />
        ) : (
          <AlertCircle className="w-5 h-5 text-status-warning" />
        )}
      </div>

      <p className="text-sm text-muted-foreground mt-3">{collection.description}</p>

      <div className="mt-4 pt-4 border-t border-border">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Vectors</span>
          <span className="font-semibold text-foreground">
            {collection.vectors_count.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm mt-1">
          <span className="text-muted-foreground">Status</span>
          <span
            className={`font-medium ${
              collection.exists ? 'text-status-success' : 'text-status-warning'
            }`}
          >
            {collection.exists ? 'Active' : 'Not Created'}
          </span>
        </div>

        {/* Source type breakdown */}
        {collection.source_type_counts && Object.keys(collection.source_type_counts).length > 0 && (
          <div className="mt-3 pt-3 border-t border-border space-y-1.5">
            {Object.entries(collection.source_type_counts)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => {
                const display = getSourceTypeDisplay(type);
                return (
                  <div key={type} className="flex items-center justify-between text-xs">
                    <span className={`px-2 py-0.5 rounded-full font-medium ${display.color}`}>
                      {display.label}
                    </span>
                    <span className="text-muted-foreground font-medium tabular-nums">
                      {count.toLocaleString()}
                    </span>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {/* Browse button */}
      {collection.exists && collection.vectors_count > 0 && (
        <button
          onClick={onBrowse}
          className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-primary bg-primary/10 border border-primary/20 rounded-lg hover:bg-primary/20 transition-colors"
        >
          <Search className="w-4 h-4" />
          Browse Content
        </button>
      )}
    </div>
  );
}

function formatCollectionName(name: string): string {
  return name
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
