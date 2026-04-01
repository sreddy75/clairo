"use client";

import {
  CheckCircle2,
  ChevronDown,
  HelpCircle,
  Receipt,
  User,
} from "lucide-react";
import { useCallback, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  agent_note?: string | null;
}

interface TransactionClassifierProps {
  transaction: Transaction;
  isExpanded: boolean;
  onToggle: () => void;
  onSave: (
    classificationId: string,
    data: {
      category?: string;
      description?: string;
      is_personal?: boolean;
      needs_help?: boolean;
    }
  ) => Promise<void>;
  /** Called when this item's answered state changes (for unanswered counter) */
  onAnsweredChange?: (classificationId: string, answered: boolean) => void;
}

export function TransactionClassifier({
  transaction,
  isExpanded,
  onToggle,
  onSave,
  onAnsweredChange,
}: TransactionClassifierProps) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    transaction.current_category
  );
  const [freeText, setFreeText] = useState(transaction.current_description || "");
  const [idkDescription, setIdkDescription] = useState("");
  const [idkDescriptionTouched, setIdkDescriptionTouched] = useState(false);
  const [saving, setSaving] = useState(false);

  const idkSelected = selectedCategory === "dont_know";
  const idkValid = idkDescription.trim().length > 0;

  // An item is "answered" when it has a non-IDK category, personal, or IDK+description
  const isAnswered =
    selectedCategory !== null &&
    (selectedCategory !== "dont_know" || idkValid);

  const handleCategorySelect = useCallback(
    async (categoryId: string) => {
      setSelectedCategory(categoryId);
      if (categoryId !== "dont_know") {
        setSaving(true);
        try {
          if (categoryId === "personal") {
            await onSave(transaction.id, { is_personal: true });
          } else {
            await onSave(transaction.id, { category: categoryId });
          }
          onAnsweredChange?.(transaction.id, true);
        } finally {
          setSaving(false);
        }
      }
      // For "dont_know", wait until description saved
    },
    [onSave, onAnsweredChange, transaction.id]
  );

  const handleIdkSave = useCallback(async () => {
    if (!idkValid) return;
    setSaving(true);
    try {
      await onSave(transaction.id, { needs_help: true, description: idkDescription.trim() });
      onAnsweredChange?.(transaction.id, true);
    } finally {
      setSaving(false);
    }
  }, [onSave, onAnsweredChange, transaction.id, idkDescription, idkValid]);

  const handleFreeTextSave = useCallback(async () => {
    if (!freeText.trim()) return;
    setSaving(true);
    try {
      await onSave(transaction.id, {
        category: "other",
        description: freeText.trim(),
      });
      setSelectedCategory("other");
      onAnsweredChange?.(transaction.id, true);
    } finally {
      setSaving(false);
    }
  }, [onSave, onAnsweredChange, transaction.id, freeText]);

  const isClassified = transaction.is_classified || isAnswered;
  const isExpense = (transaction.amount ?? 0) < 0;

  return (
    <div
      className={cn(
        "border rounded-lg transition-colors",
        isClassified && "border-emerald-200 bg-emerald-50/30",
        isExpanded && !isClassified && "border-primary/30 bg-primary/[0.02]",
        !isExpanded && !isClassified && "hover:bg-muted/30"
      )}
    >
      {/* Collapsed row — always visible */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left"
      >
        {/* Status icon */}
        {isClassified ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
        ) : (
          <div className="h-4 w-4 rounded-full border-2 border-stone-300 shrink-0" />
        )}

        {/* Amount */}
        <span className="text-sm font-medium tabular-nums w-20 shrink-0 text-right">
          {formatCurrency(Math.abs(transaction.amount))}
        </span>

        {/* Date */}
        <span className="text-xs text-muted-foreground w-20 shrink-0">
          {transaction.transaction_date || "—"}
        </span>

        {/* Description */}
        <span className="text-sm text-muted-foreground truncate flex-1 min-w-0">
          {transaction.description || "No description"}
        </span>

        {/* Right side badges */}
        <div className="flex items-center gap-1.5 shrink-0">
          {transaction.receipt_required && !transaction.receipt_attached && (
            <Badge variant="outline" className="text-amber-600 border-amber-300 text-[10px] px-1.5 py-0">
              <Receipt className="h-2.5 w-2.5 mr-0.5" />
              Receipt
            </Badge>
          )}
          {selectedCategory && !isExpanded && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
              {getCategoryLabel(selectedCategory)}
            </Badge>
          )}
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 text-muted-foreground transition-transform",
              isExpanded && "rotate-180"
            )}
          />
        </div>
      </button>

      {/* Expanded content — category selection */}
      {isExpanded && (
        <div className="px-3 pb-3 space-y-3">
          <div className="border-t pt-3" />

          {/* Agent note callout */}
          {transaction.agent_note && (
            <div className="rounded-md bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs text-amber-800">
              <p className="font-medium text-amber-600 mb-0.5">Your accountant says:</p>
              {transaction.agent_note}
            </div>
          )}

          {/* Receipt flag callout */}
          {transaction.receipt_required && (
            <div className="rounded-md bg-amber-50 px-3 py-1.5 text-xs text-amber-800">
              <Receipt className="inline h-3.5 w-3.5 mr-1" />
              {transaction.receipt_reason || "Please attach a receipt or invoice"}
            </div>
          )}

          {/* What was this for? */}
          <p className="text-xs font-medium text-muted-foreground">What was this for?</p>

          {/* Category buttons — compact grid */}
          <div className="flex flex-wrap gap-1.5">
            {(isExpense ? EXPENSE_CATEGORIES : INCOME_CATEGORIES).map((cat) => (
              <button
                key={cat.id}
                type="button"
                disabled={saving}
                onClick={() => handleCategorySelect(cat.id)}
                className={cn(
                  "px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
                  selectedCategory === cat.id
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-background text-foreground border-border hover:bg-muted"
                )}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Special actions — inline with categories */}
          <div className="flex gap-1.5">
            <button
              type="button"
              disabled={saving}
              onClick={() => handleCategorySelect("personal")}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
                selectedCategory === "personal"
                  ? "bg-red-500 text-white border-red-500"
                  : "bg-background text-muted-foreground border-border hover:bg-muted"
              )}
            >
              <User className="h-3 w-3" />
              Personal
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={() => handleCategorySelect("dont_know")}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors",
                selectedCategory === "dont_know"
                  ? "bg-stone-500 text-white border-stone-500"
                  : "bg-background text-muted-foreground border-border hover:bg-muted"
              )}
            >
              <HelpCircle className="h-3 w-3" />
              Not sure
            </button>
          </div>

          {/* IDK mandatory description */}
          {idkSelected && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium">
                Describe what you know about this transaction
                <span className="text-red-500 ml-1">*</span>
              </p>
              <div className="flex gap-2 items-start">
                <Textarea
                  value={idkDescription}
                  onChange={(e) => setIdkDescription(e.target.value)}
                  onBlur={() => setIdkDescriptionTouched(true)}
                  placeholder="e.g. I think it was for a supplier but I'm not sure which one"
                  className="text-xs min-h-[40px] h-10 resize-none"
                  maxLength={500}
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs shrink-0 h-10"
                  disabled={saving || !idkValid}
                  onClick={handleIdkSave}
                >
                  Save
                </Button>
              </div>
              {idkDescriptionTouched && !idkValid && (
                <p className="text-xs text-red-500">A description is required</p>
              )}
            </div>
          )}

          {/* Free text — collapsible, only show if no category selected */}
          {!selectedCategory && (
            <div className="flex gap-2 items-start">
              <Textarea
                value={freeText}
                onChange={(e) => setFreeText(e.target.value)}
                placeholder="Or describe what this was for..."
                className="text-xs min-h-[40px] h-10 resize-none"
                maxLength={500}
              />
              <Button
                size="sm"
                variant="outline"
                className="text-xs shrink-0 h-10"
                disabled={saving || !freeText.trim()}
                onClick={handleFreeTextSave}
              >
                Save
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
