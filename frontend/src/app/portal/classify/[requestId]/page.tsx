"use client";

import { AlertTriangle, CheckCircle2, Clock, Send } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { TransactionClassifier } from "@/components/portal/TransactionClassifier";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import portalApi from "@/lib/api/portal";

interface Transaction {
  id: string;
  transaction_date: string | null;
  amount: number;
  description: string | null;
  hint: string | null;
  current_category: string | null;
  current_description: string | null;
  is_classified: boolean;
  receipt_required: boolean;
  receipt_reason: string | null;
  receipt_attached: boolean;
}

interface ClassifyPageData {
  request_id: string;
  practice_name: string;
  message: string | null;
  expires_at: string;
  transactions: Transaction[];
  categories: Array<{ id: string; label: string; group: string }>;
  progress: { total: number; classified: number; remaining: number };
}

export default function ClassifyPage() {
  const params = useParams();
  const requestId = params.requestId as string;

  const [data, setData] = useState<ClassifyPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Load classification request data
  useEffect(() => {
    async function loadData() {
      try {
        const result = await portalApi.classify.getRequest(requestId);
        setData(result);
        // Auto-expand first unclassified transaction
        const firstUnclassified = result.transactions.find((t: Transaction) => !t.is_classified);
        if (firstUnclassified) {
          setExpandedId(firstUnclassified.id);
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to load classification request";
        setError(message);
      } finally {
        setLoading(false);
      }
    }
    if (requestId) {
      loadData();
    }
  }, [requestId]);

  // Handle saving a classification (auto-save on category select)
  const handleSave = useCallback(
    async (
      classificationId: string,
      saveData: {
        category?: string;
        description?: string;
        is_personal?: boolean;
        needs_help?: boolean;
      }
    ) => {
      await portalApi.classify.saveClassification(requestId, classificationId, saveData);

      // Update local state optimistically
      setData((prev) => {
        if (!prev) return prev;
        const updated = prev.transactions.map((t) =>
          t.id === classificationId ? { ...t, is_classified: true, current_category: saveData.category || t.current_category } : t
        );
        const classified = updated.filter((t) => t.is_classified).length;

        // Auto-advance to next unclassified transaction
        const currentIndex = updated.findIndex((t) => t.id === classificationId);
        const nextUnclassified = updated.find(
          (t, i) => i > currentIndex && !t.is_classified
        ) || updated.find((t) => !t.is_classified);
        setExpandedId(nextUnclassified?.id ?? null);

        return {
          ...prev,
          transactions: updated,
          progress: {
            total: prev.progress.total,
            classified,
            remaining: prev.progress.total - classified,
          },
        };
      });
    },
    [requestId]
  );

  // Handle submit
  const handleSubmit = useCallback(async () => {
    setSubmitting(true);
    try {
      await portalApi.classify.submit(requestId);
      setSubmitted(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to submit";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }, [requestId]);

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto" />
          <p className="text-sm text-muted-foreground">Loading your transactions...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center space-y-3">
            <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto" />
            <h2 className="text-lg font-semibold">Unable to load</h2>
            <p className="text-sm text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Submitted state — thank you screen
  if (submitted && data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="max-w-md w-full">
          <CardContent className="p-6 text-center space-y-4">
            <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto" />
            <h2 className="text-xl font-semibold">Thank you!</h2>
            <p className="text-sm text-muted-foreground">
              You classified {data.progress.classified} of {data.progress.total} transactions.
              Your accountant will review them shortly.
            </p>
            <p className="text-xs text-muted-foreground">
              You can close this page now.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  const progressPercent =
    data.progress.total > 0
      ? Math.round((data.progress.classified / data.progress.total) * 100)
      : 0;

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-xl font-semibold">Classify Your Transactions</h1>
        <p className="text-sm text-muted-foreground">
          {data.practice_name} needs you to tell them what each transaction was for.
        </p>
      </div>

      {/* Accountant message */}
      {data.message && (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="p-4">
            <p className="text-sm text-blue-800">{data.message}</p>
          </CardContent>
        </Card>
      )}

      {/* Progress bar */}
      <Card>
        <CardContent className="p-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">
              {data.progress.classified} of {data.progress.total} classified
            </span>
            <span className="text-muted-foreground tabular-nums">{progressPercent}%</span>
          </div>
          <Progress value={progressPercent} className="h-2" />
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            Link expires {new Date(data.expires_at).toLocaleDateString()}
          </div>
        </CardContent>
      </Card>

      {/* Transaction list */}
      <div className="space-y-1">
        {data.transactions.map((transaction) => (
          <TransactionClassifier
            key={transaction.id}
            transaction={transaction}
            isExpanded={expandedId === transaction.id}
            onToggle={() =>
              setExpandedId(expandedId === transaction.id ? null : transaction.id)
            }
            onSave={handleSave}
          />
        ))}
      </div>

      {/* Submit button */}
      <div className="sticky bottom-4 flex justify-center">
        <Button
          size="lg"
          onClick={handleSubmit}
          disabled={submitting || data.progress.classified === 0}
          className="shadow-lg"
        >
          {submitting ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent mr-2" />
              Submitting...
            </>
          ) : (
            <>
              <Send className="h-4 w-4 mr-2" />
              Submit ({data.progress.classified} classified)
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
