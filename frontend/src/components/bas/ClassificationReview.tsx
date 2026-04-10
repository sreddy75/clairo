"use client";

import { CheckCircle2, AlertTriangle, Loader2, User, HelpCircle, Download } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { formatCurrency } from "@/lib/formatters";
import { cn } from "@/lib/utils";

interface ReviewItem {
  id: string;
  source_type: string;
  transaction_date: string | null;
  line_amount: number;
  description: string | null;
  client_category: string | null;
  client_category_label: string | null;
  client_description: string | null;
  client_is_personal: boolean;
  client_needs_help: boolean;
  classified_at: string | null;
  ai_suggested_tax_type: string | null;
  ai_confidence: number | null;
  needs_attention: boolean;
  receipt_required: boolean;
  receipt_attached: boolean;
  accountant_action: string | null;
}

interface ReviewSummary {
  total: number;
  classified_by_client: number;
  marked_personal: number;
  needs_help: number;
  auto_mappable: number;
  needs_attention: number;
  already_reviewed: number;
  receipts_required: number;
  receipts_attached: number;
  receipts_missing: number;
}

interface ClassificationReviewProps {
  connectionId: string;
  sessionId: string;
  getToken: () => Promise<string | null>;
  onComplete?: () => void;
}

export function ClassificationReview({
  connectionId,
  sessionId,
  getToken,
  onComplete: _onComplete,
}: ClassificationReviewProps) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadReview = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const apiBase = "";
      const response = await fetch(
        `${apiBase}/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification/review`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error("Failed to load review");
      const data = await response.json();
      setItems(data.classifications);
      setSummary(data.summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [connectionId, sessionId, getToken]);

  useEffect(() => {
    loadReview();
  }, [loadReview]);

  const handleResolve = useCallback(
    async (classificationId: string, action: string, taxType?: string) => {
      setActionLoading(classificationId);
      try {
        const token = await getToken();
        if (!token) return;
        const response = await fetch(
          `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification/${classificationId}/resolve`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ action, tax_type: taxType }),
          }
        );
        if (!response.ok) throw new Error("Failed to resolve");
        // Update local state
        setItems((prev) =>
          prev.map((item) =>
            item.id === classificationId
              ? { ...item, accountant_action: action }
              : item
          )
        );
        if (summary) {
          setSummary({ ...summary, already_reviewed: summary.already_reviewed + 1 });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed");
      } finally {
        setActionLoading(null);
      }
    },
    [connectionId, sessionId, getToken, summary]
  );

  const handleBulkApprove = useCallback(async () => {
    setActionLoading("bulk");
    try {
      const token = await getToken();
      if (!token) return;
      const response = await fetch(
        `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification/bulk-approve`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            min_confidence: 0.7,
            exclude_personal: true,
            exclude_needs_help: true,
          }),
        }
      );
      if (!response.ok) throw new Error("Failed to bulk approve");
      await loadReview();
    } finally {
      setActionLoading(null);
    }
  }, [connectionId, sessionId, getToken, loadReview]);

  const handleExport = useCallback(async () => {
    const token = await getToken();
    if (!token) return;
    const response = await fetch(
      `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification/audit-export?format=csv`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) return;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `classification-audit-${sessionId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [connectionId, sessionId, getToken]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-red-600">
        <AlertTriangle className="inline h-4 w-4 mr-1" />
        {error}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No client classifications to review.
      </div>
    );
  }

  const unreviewedCount = items.filter((i) => !i.accountant_action).length;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex gap-4 text-sm">
              <span>
                <strong className="tabular-nums">{summary?.classified_by_client ?? 0}</strong> classified by client
              </span>
              {(summary?.marked_personal ?? 0) > 0 && (
                <span className="text-amber-600">
                  <strong className="tabular-nums">{summary?.marked_personal}</strong> personal
                </span>
              )}
              {(summary?.needs_help ?? 0) > 0 && (
                <span className="text-red-600">
                  <strong className="tabular-nums">{summary?.needs_help}</strong> need help
                </span>
              )}
              {(summary?.needs_attention ?? 0) > 0 && (
                <span className="text-amber-600">
                  <strong className="tabular-nums">{summary?.needs_attention}</strong> need attention
                </span>
              )}
              <span className="text-emerald-600">
                <strong className="tabular-nums">{summary?.already_reviewed ?? 0}</strong> reviewed
              </span>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleExport}
              >
                <Download className="h-3 w-3 mr-1" />
                Export Audit Trail
              </Button>
              {unreviewedCount > 0 && (
                <Button
                  size="sm"
                  onClick={handleBulkApprove}
                  disabled={actionLoading === "bulk"}
                >
                  {actionLoading === "bulk" ? (
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  ) : (
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                  )}
                  Approve All High Confidence
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Classification table — compact rows for fast review */}
      <div className="border border-border rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50 text-xs text-muted-foreground uppercase tracking-wider">
              <th className="hidden md:table-cell px-3 py-2 text-left font-medium">Date</th>
              <th className="px-3 py-2 text-right font-medium">Amount</th>
              <th className="px-3 py-2 text-left font-medium">Description</th>
              <th className="hidden lg:table-cell px-3 py-2 text-left font-medium">Client Said</th>
              <th className="px-3 py-2 text-left font-medium">AI Suggests</th>
              <th className="px-3 py-2 text-right font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((item) => {
              const clientSaid = item.client_is_personal
                ? "Personal"
                : item.client_needs_help
                  ? "Needs help"
                  : item.client_category_label || item.client_description || "—";

              return (
                <tr
                  key={item.id}
                  className={cn(
                    "hover:bg-muted/30 transition-colors",
                    item.accountant_action === "approved" && "bg-emerald-50/50",
                    item.accountant_action === "rejected" && "bg-red-50/50",
                    item.needs_attention && !item.accountant_action && "bg-amber-50/30"
                  )}
                >
                  <td className="hidden md:table-cell px-3 py-1.5 text-xs text-muted-foreground whitespace-nowrap tabular-nums">
                    {item.transaction_date || "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium tabular-nums whitespace-nowrap">
                    {formatCurrency(Math.abs(item.line_amount))}
                  </td>
                  <td className="px-3 py-1.5 max-w-[200px]">
                    <span className="truncate block text-xs">{item.description || "—"}</span>
                  </td>
                  <td className="hidden lg:table-cell px-3 py-1.5 max-w-[180px]">
                    <div className="flex items-center gap-1">
                      {item.client_is_personal && <User className="h-3 w-3 text-amber-500 shrink-0" />}
                      {item.client_needs_help && <HelpCircle className="h-3 w-3 text-red-500 shrink-0" />}
                      <span className="truncate text-xs font-medium">{clientSaid}</span>
                    </div>
                    {item.client_description && item.client_category && (
                      <span className="text-[10px] text-muted-foreground truncate block">&ldquo;{item.client_description}&rdquo;</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 whitespace-nowrap">
                    {item.ai_suggested_tax_type ? (
                      <span className="text-xs">
                        <span className="font-medium">{item.ai_suggested_tax_type}</span>
                        {item.ai_confidence && (
                          <span className={cn(
                            "ml-1",
                            Number(item.ai_confidence) >= 0.8 ? "text-emerald-600" : Number(item.ai_confidence) >= 0.6 ? "text-amber-600" : "text-red-600"
                          )}>
                            {Math.round(Number(item.ai_confidence) * 100)}%
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-right whitespace-nowrap">
                    {item.accountant_action ? (
                      <Badge
                        variant={item.accountant_action === "approved" ? "default" : "secondary"}
                        className={cn(
                          "text-[10px] px-1.5 py-0",
                          item.accountant_action === "approved" && "bg-emerald-600"
                        )}
                      >
                        {item.accountant_action}
                      </Badge>
                    ) : (
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-[10px] h-6 px-2 text-emerald-700 border-emerald-300 hover:bg-emerald-50"
                          disabled={actionLoading === item.id}
                          onClick={() => handleResolve(item.id, "approved", item.ai_suggested_tax_type || undefined)}
                        >
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-[10px] h-6 px-2"
                          disabled={actionLoading === item.id}
                          onClick={() => handleResolve(item.id, "rejected")}
                        >
                          Reject
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* All reviewed */}
      {unreviewedCount === 0 && (
        <div className="text-center p-4">
          <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
          <p className="text-sm font-medium">All classifications reviewed</p>
          <p className="text-xs text-muted-foreground mt-1">
            You can now recalculate the BAS with the approved tax codes.
          </p>
        </div>
      )}
    </div>
  );
}
