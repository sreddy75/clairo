'use client';

/**
 * Query Visualization Page
 *
 * Interface for ad-hoc natural language queries with visual answers.
 * Uses A2UI to render dynamic charts, tables, and insights based on queries.
 */

import {
  BarChart2,
  Clock,
  DollarSign,
  Lightbulb,
  Loader2,
  PieChart,
  Search,
  Send,
  Sparkles,
  TrendingUp,
  Users,
  AlertTriangle,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { A2UIRenderer } from '@/lib/a2ui/renderer';
import type { A2UIMessage, A2UIActionHandlers } from '@/lib/a2ui/types';

// =============================================================================
// Types
// =============================================================================

interface QueryResult {
  correlation_id: string;
  text_response: string;
  a2ui_message: A2UIMessage | null;
  query_type: string;
  confidence: number;
  time_period?: Record<string, unknown> | null;
  metric_focus: string[];
}

interface Suggestion {
  query: string;
  category: string;
  icon: string;
}

// =============================================================================
// Query Suggestions
// =============================================================================

const defaultSuggestions: Suggestion[] = [
  {
    query: "What's my GST position for this quarter?",
    category: 'GST',
    icon: 'dollar-sign',
  },
  {
    query: 'Show expense breakdown by category',
    category: 'Expenses',
    icon: 'pie-chart',
  },
  {
    query: 'Compare this quarter to last quarter',
    category: 'Comparison',
    icon: 'bar-chart-2',
  },
  {
    query: 'What are my revenue trends?',
    category: 'Trends',
    icon: 'trending-up',
  },
  {
    query: 'Who owes me money?',
    category: 'Receivables',
    icon: 'users',
  },
  {
    query: 'Any unusual patterns in my data?',
    category: 'Anomalies',
    icon: 'alert-triangle',
  },
];

function getIconComponent(iconName: string) {
  const icons: Record<string, React.ReactNode> = {
    'dollar-sign': <DollarSign className="h-4 w-4" />,
    'pie-chart': <PieChart className="h-4 w-4" />,
    'bar-chart-2': <BarChart2 className="h-4 w-4" />,
    'trending-up': <TrendingUp className="h-4 w-4" />,
    users: <Users className="h-4 w-4" />,
    'alert-triangle': <AlertTriangle className="h-4 w-4" />,
  };
  return icons[iconName] || <Search className="h-4 w-4" />;
}

// =============================================================================
// Suggestion Card
// =============================================================================

interface SuggestionCardProps {
  suggestion: Suggestion;
  onClick: () => void;
}

function SuggestionCard({ suggestion, onClick }: SuggestionCardProps) {
  return (
    <button
      onClick={onClick}
      className="group flex items-start gap-3 rounded-lg border border-border bg-card p-4 text-left transition-all hover:border-primary/30 hover:bg-primary/5 hover:shadow-sm"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
        {getIconComponent(suggestion.icon)}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground line-clamp-2">{suggestion.query}</p>
        <p className="mt-1 text-xs text-muted-foreground">{suggestion.category}</p>
      </div>
    </button>
  );
}

// =============================================================================
// Query Type Badge
// =============================================================================

interface QueryTypeBadgeProps {
  type: string;
  confidence: number;
}

function QueryTypeBadge({ type, confidence }: QueryTypeBadgeProps) {
  const typeLabels: Record<string, string> = {
    summary: 'Summary',
    comparison: 'Comparison',
    trend: 'Trend Analysis',
    breakdown: 'Breakdown',
    list: 'List View',
    anomaly: 'Anomaly Detection',
  };

  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
        <Sparkles className="h-3 w-3" />
        {typeLabels[type] || type}
      </span>
      <span className="text-xs text-muted-foreground">{Math.round(confidence * 100)}% confidence</span>
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function QueriesPage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queryHistory, setQueryHistory] = useState<string[]>([]);

  // Submit query to backend
  const handleSubmit = useCallback(
    async (queryText?: string) => {
      const queryToSubmit = queryText || query.trim();
      if (!queryToSubmit) return;

      setIsLoading(true);
      setError(null);

      // Add to history
      setQueryHistory((prev) => {
        const newHistory = [queryToSubmit, ...prev.filter((q) => q !== queryToSubmit)];
        return newHistory.slice(0, 10); // Keep last 10
      });

      try {
        const response = await fetch('/api/v1/queries/ui', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query: queryToSubmit,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to process query');
        }

        const data: QueryResult = await response.json();
        setResult(data);
        setQuery('');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setIsLoading(false);
      }
    },
    [query]
  );

  // Handle suggestion click
  const handleSuggestionClick = useCallback(
    (suggestionQuery: string) => {
      setQuery(suggestionQuery);
      handleSubmit(suggestionQuery);
    },
    [handleSubmit]
  );

  // A2UI action handlers
  const actionHandlers: A2UIActionHandlers = {
    navigate: (target) => router.push(target),
    createTask: async (payload) => {
      console.log('Create task:', payload);
    },
    export: async (format, dataBinding) => {
      console.log('Export:', format, dataBinding);
    },
    custom: async (payload) => {
      console.log('Custom action:', payload);
    },
  };

  // Handle new query button
  const handleNewQuery = () => {
    setResult(null);
    setQuery('');
    setError(null);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="shrink-0 border-b border-border bg-card px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Query Visualizer</h1>
            <p className="text-sm text-muted-foreground">
              Ask questions in natural language and get visual answers
            </p>
          </div>
          {result && (
            <Button variant="outline" onClick={handleNewQuery}>
              <Search className="mr-2 h-4 w-4" />
              New Query
            </Button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto bg-background">
        {!result ? (
          // Empty State - Show suggestions
          <div className="mx-auto max-w-4xl px-6 py-8">
            {/* Hero Section */}
            <div className="mb-8 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/80 shadow-lg">
                <Lightbulb className="h-8 w-8 text-primary-foreground" />
              </div>
              <h2 className="text-2xl font-semibold text-foreground">Ask anything about your data</h2>
              <p className="mt-2 text-muted-foreground">
                Type a question in plain English and get instant visual insights
              </p>
            </div>

            {/* Query Input */}
            <div className="mb-8">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="e.g., What's my GST liability for this quarter?"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  className="h-14 pl-12 pr-14 text-base shadow-sm"
                  autoFocus
                />
                <Button
                  size="icon"
                  className="absolute right-2 top-1/2 -translate-y-1/2"
                  onClick={() => handleSubmit()}
                  disabled={!query.trim() || isLoading}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="mb-6 rounded-lg border border-status-danger/20 bg-status-danger/10 p-4 text-sm text-status-danger">
                {error}
              </div>
            )}

            {/* Suggestions Grid */}
            <div>
              <h3 className="mb-4 text-sm font-medium text-foreground">Try these queries</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {defaultSuggestions.map((suggestion, index) => (
                  <SuggestionCard
                    key={index}
                    suggestion={suggestion}
                    onClick={() => handleSuggestionClick(suggestion.query)}
                  />
                ))}
              </div>
            </div>

            {/* Query History */}
            {queryHistory.length > 0 && (
              <div className="mt-8">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
                  <Clock className="h-4 w-4" />
                  Recent Queries
                </h3>
                <div className="flex flex-wrap gap-2">
                  {queryHistory.map((historyQuery, index) => (
                    <button
                      key={index}
                      onClick={() => handleSuggestionClick(historyQuery)}
                      className="rounded-full border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:border-primary/30 hover:bg-primary/5"
                    >
                      {historyQuery.length > 40 ? historyQuery.slice(0, 40) + '...' : historyQuery}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          // Result Display
          <div className="mx-auto max-w-5xl px-6 py-8">
            {/* Query Display */}
            <Card className="mb-6">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-medium text-muted-foreground">Your Query</CardTitle>
                  <QueryTypeBadge type={result.query_type} confidence={result.confidence} />
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-lg text-foreground">
                  {queryHistory[0] || query}
                </p>
              </CardContent>
            </Card>

            {/* Text Response */}
            <Card className="mb-6">
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-medium text-muted-foreground">Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-foreground leading-relaxed">{result.text_response}</p>
              </CardContent>
            </Card>

            {/* A2UI Visualization */}
            {result.a2ui_message && (
              <div className="space-y-4">
                <h3 className="text-base font-medium text-foreground">Visualization</h3>
                <A2UIRenderer
                  message={result.a2ui_message}
                  actionHandlers={actionHandlers}
                  className="rounded-lg"
                />
              </div>
            )}

            {/* Ask Follow-up */}
            <div className="mt-8 rounded-lg border border-border bg-card p-4">
              <p className="mb-3 text-sm text-muted-foreground">Ask a follow-up question:</p>
              <div className="flex gap-2">
                <Input
                  placeholder="Ask another question..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  className="flex-1"
                />
                <Button onClick={() => handleSubmit()} disabled={!query.trim() || isLoading}>
                  {isLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 h-4 w-4" />
                  )}
                  Ask
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isLoading && !result && (
          <div className="mx-auto max-w-5xl px-6 py-8">
            <Card>
              <CardContent className="py-8">
                <div className="flex flex-col items-center justify-center gap-4">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <p className="text-muted-foreground">Analyzing your query...</p>
                </div>
              </CardContent>
            </Card>
            <div className="mt-6 space-y-4">
              <Skeleton className="h-32 w-full" />
              <div className="grid grid-cols-3 gap-4">
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
              </div>
              <Skeleton className="h-48 w-full" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
