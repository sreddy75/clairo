'use client';

import {
  AlertCircle,
  Clock,
  ExternalLink,
  Loader2,
  Search,
  X,
} from 'lucide-react';
import { useState } from 'react';

import { COLLECTION_NAMES } from '@/types/knowledge';

import { useSearchTest } from '../hooks/use-search-test';

export function SearchTestTab() {
  const { results, isSearching, error, search, clear } = useSearchTest();

  const [query, setQuery] = useState('');
  const [selectedCollections, setSelectedCollections] = useState<string[]>([]);
  const [limit, setLimit] = useState(10);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    await search({
      query: query.trim(),
      collections: selectedCollections.length > 0 ? selectedCollections : undefined,
      limit,
    });
  };

  const toggleCollection = (name: string) => {
    setSelectedCollections((prev) =>
      prev.includes(name)
        ? prev.filter((c) => c !== name)
        : [...prev, name]
    );
  };

  const handleClear = () => {
    setQuery('');
    clear();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-foreground">Search Test</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Test vector search and verify retrieval quality
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="space-y-4">
        {/* Query Input */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-foreground mb-1.5">
            Search Query
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., GST registration threshold for small business"
              className="w-full pl-10 pr-10 py-3 border border-border bg-card text-foreground rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-shadow placeholder:text-muted-foreground"
            />
            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-muted rounded-full transition-colors"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            )}
          </div>
        </div>

        {/* Collection Filter */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-foreground mb-2">
            Collections{' '}
            <span className="font-normal text-muted-foreground">
              (leave empty to search all)
            </span>
          </label>
          <div className="flex flex-wrap gap-2">
            {COLLECTION_NAMES.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => toggleCollection(name)}
                className={`px-3 py-1.5 text-sm rounded-full border transition-colors ${
                  selectedCollections.includes(name)
                    ? 'bg-primary/10 border-primary/20 text-primary'
                    : 'bg-card border-border text-muted-foreground hover:bg-muted'
                }`}
              >
                {formatCollectionName(name)}
              </button>
            ))}
          </div>
        </div>

        {/* Limit */}
        <div className="flex items-center gap-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-foreground mb-1.5">
              Max Results
            </label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="px-3 py-2 border border-border bg-card text-foreground rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>
          <div className="flex-1" />
          <button
            type="submit"
            disabled={!query.trim() || isSearching}
            className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {isSearching ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            Search
          </button>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="bg-status-danger/10 border border-status-danger/20 rounded-lg p-4">
          <div className="flex items-center gap-2 text-status-danger">
            <AlertCircle className="w-5 h-5" />
            <span className="font-medium">Search failed</span>
          </div>
          <p className="text-status-danger text-sm mt-1">{error}</p>
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="space-y-4">
          {/* Results Header */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              Found <span className="font-semibold">{results.total_results}</span>{' '}
              results in{' '}
              <span className="font-semibold">{results.collections_searched.length}</span>{' '}
              collections
            </div>
            <div className="flex items-center gap-1 text-sm text-muted-foreground">
              <Clock className="w-4 h-4" />
              {results.latency_ms.toFixed(0)}ms
            </div>
          </div>

          {/* Results List */}
          {results.results.length > 0 ? (
            <div className="space-y-3">
              {results.results.map((result, index) => (
                <div
                  key={result.chunk_id}
                  className="bg-card border border-border rounded-xl p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 bg-primary/10 text-primary rounded-full text-sm font-semibold">
                        {index + 1}
                      </div>
                      <div>
                        <div className="font-medium text-foreground">
                          {result.title || 'Untitled'}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs px-2 py-0.5 bg-muted text-muted-foreground rounded">
                            {result.collection}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {result.source_type}
                          </span>
                          {result.ruling_number && (
                            <span className="text-xs font-mono text-primary">
                              {result.ruling_number}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-semibold text-foreground">
                        {(result.score * 100).toFixed(1)}%
                      </div>
                      <div className="text-xs text-muted-foreground">score</div>
                    </div>
                  </div>

                  {/* Text Preview */}
                  <div className="mt-3 text-sm text-muted-foreground line-clamp-3">
                    {result.text}
                  </div>

                  {/* Metadata */}
                  <div className="mt-3 flex items-center flex-wrap gap-2">
                    {result.entity_types.length > 0 && (
                      <div className="flex items-center gap-1">
                        {result.entity_types.map((type) => (
                          <span
                            key={type}
                            className="text-xs px-2 py-0.5 bg-purple-500/10 text-purple-700 rounded"
                          >
                            {type}
                          </span>
                        ))}
                      </div>
                    )}
                    {result.effective_date && (
                      <span className="text-xs text-muted-foreground">
                        Effective: {result.effective_date}
                      </span>
                    )}
                  </div>

                  {/* Source Link */}
                  <div className="mt-3 pt-3 border-t border-border">
                    <a
                      href={result.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-primary hover:underline flex items-center gap-1"
                    >
                      {result.source_url}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 bg-muted rounded-lg border border-dashed border-border">
              <Search className="w-12 h-12 text-muted-foreground mx-auto" />
              <h3 className="mt-4 text-lg font-medium text-foreground">
                No results found
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Try adjusting your query or searching different collections.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!results && !isSearching && !error && (
        <div className="text-center py-12 bg-muted rounded-lg border border-dashed border-border">
          <Search className="w-12 h-12 text-muted-foreground mx-auto" />
          <h3 className="mt-4 text-lg font-medium text-foreground">
            Test your knowledge base
          </h3>
          <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
            Enter a query above to test vector search and verify that content is
            being retrieved correctly.
          </p>
        </div>
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
