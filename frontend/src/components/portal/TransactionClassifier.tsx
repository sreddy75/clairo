"use client";

import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Receipt,
  User,
} from "lucide-react";
import { useCallback, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  EXPENSE_CATEGORIES,
  INCOME_CATEGORIES,
  getCategoryLabel,
} from "@/lib/constants/classification-categories";
import { formatCurrency } from "@/lib/formatters";
import { cn } from "@/lib/utils";

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

interface TransactionClassifierProps {
  transaction: Transaction;
  onSave: (
    classificationId: string,
    data: {
      category?: string;
      description?: string;
      is_personal?: boolean;
      needs_help?: boolean;
    }
  ) => Promise<void>;
}

export function TransactionClassifier({
  transaction,
  onSave,
}: TransactionClassifierProps) {
  const [expanded, setExpanded] = useState(!transaction.is_classified);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    transaction.current_category
  );
  const [freeText, setFreeText] = useState(transaction.current_description || "");
  const [saving, setSaving] = useState(false);

  const handleCategorySelect = useCallback(
    async (categoryId: string) => {
      setSelectedCategory(categoryId);
      setSaving(true);
      try {
        if (categoryId === "personal") {
          await onSave(transaction.id, { is_personal: true });
        } else if (categoryId === "dont_know") {
          await onSave(transaction.id, { needs_help: true });
        } else {
          await onSave(transaction.id, { category: categoryId });
        }
      } finally {
        setSaving(false);
      }
    },
    [onSave, transaction.id]
  );

  const handleFreeTextSave = useCallback(async () => {
    if (!freeText.trim()) return;
    setSaving(true);
    try {
      await onSave(transaction.id, {
        category: "other",
        description: freeText.trim(),
      });
      setSelectedCategory("other");
    } finally {
      setSaving(false);
    }
  }, [onSave, transaction.id, freeText]);

  const isClassified = transaction.is_classified || selectedCategory !== null;
  const isExpense = (transaction.amount ?? 0) < 0;

  return (
    <Card
      className={cn(
        "transition-colors",
        isClassified && "border-emerald-200 bg-emerald-50/30"
      )}
    >
      <CardContent className="p-4">
        {/* Header row — always visible */}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center justify-between text-left"
        >
          <div className="flex items-center gap-3 min-w-0">
            {isClassified ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
            ) : (
              <div className="h-5 w-5 rounded-full border-2 border-stone-300 shrink-0" />
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium tabular-nums">
                  {formatCurrency(Math.abs(transaction.amount))}
                </span>
                {transaction.transaction_date && (
                  <span className="text-xs text-muted-foreground">
                    {transaction.transaction_date}
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground truncate">
                {transaction.description || "No description"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {transaction.receipt_required && !transaction.receipt_attached && (
              <Badge variant="outline" className="text-amber-600 border-amber-300">
                <Receipt className="h-3 w-3 mr-1" />
                Receipt needed
              </Badge>
            )}
            {selectedCategory && (
              <Badge variant="secondary" className="text-xs">
                {getCategoryLabel(selectedCategory)}
              </Badge>
            )}
            {expanded ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </div>
        </button>

        {/* Expanded content — category selection */}
        {expanded && (
          <div className="mt-4 space-y-4">
            {/* Receipt flag callout */}
            {transaction.receipt_required && (
              <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <Receipt className="inline h-4 w-4 mr-1" />
                {transaction.receipt_reason || "Please attach a receipt or invoice"}
              </div>
            )}

            {/* What was this for? */}
            <p className="text-sm font-medium">What was this for?</p>

            {/* Expense categories */}
            {isExpense && (
              <div>
                <p className="text-xs text-muted-foreground mb-2">Business expenses</p>
                <div className="flex flex-wrap gap-2">
                  {EXPENSE_CATEGORIES.map((cat) => (
                    <Button
                      key={cat.id}
                      variant={selectedCategory === cat.id ? "default" : "outline"}
                      size="sm"
                      className="text-xs"
                      disabled={saving}
                      onClick={() => handleCategorySelect(cat.id)}
                    >
                      {cat.label}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Income categories */}
            {!isExpense && (
              <div>
                <p className="text-xs text-muted-foreground mb-2">Income</p>
                <div className="flex flex-wrap gap-2">
                  {INCOME_CATEGORIES.map((cat) => (
                    <Button
                      key={cat.id}
                      variant={selectedCategory === cat.id ? "default" : "outline"}
                      size="sm"
                      className="text-xs"
                      disabled={saving}
                      onClick={() => handleCategorySelect(cat.id)}
                    >
                      {cat.label}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Special actions */}
            <div className="flex gap-2 pt-2 border-t">
              <Button
                variant={selectedCategory === "personal" ? "destructive" : "outline"}
                size="sm"
                className="text-xs"
                disabled={saving}
                onClick={() => handleCategorySelect("personal")}
              >
                <User className="h-3 w-3 mr-1" />
                Personal — not business
              </Button>
              <Button
                variant={selectedCategory === "dont_know" ? "secondary" : "outline"}
                size="sm"
                className="text-xs"
                disabled={saving}
                onClick={() => handleCategorySelect("dont_know")}
              >
                <HelpCircle className="h-3 w-3 mr-1" />
                I don&apos;t know
              </Button>
            </div>

            {/* Free text for "Other" */}
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Or describe what this was for:
              </p>
              <div className="flex gap-2">
                <Textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  placeholder="e.g. Bought printer ink for the office"
                  className="text-sm min-h-[60px]"
                  maxLength={500}
                />
                <Button
                  size="sm"
                  variant="outline"
                  disabled={saving || !freeText.trim()}
                  onClick={handleFreeTextSave}
                >
                  Save
                </Button>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
