'use client';

import { AlertTriangle, Loader2, Plus, RotateCcw, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import type { SplitCreateRequest, TaxCodeOverrideWithSplit, XeroAccountOption, XeroLineItemView } from '@/lib/bas';
import { VALID_TAX_TYPES, createSplit, deleteSplit, listXeroAccounts, updateSplit } from '@/lib/bas';
import { cn } from '@/lib/utils';

import { AccountCodeCombobox } from './AccountCodeCombobox';

interface SplitCreationFormProps {
  connectionId: string;
  sessionId: string;
  sourceId: string;
  /** Original line items from Xero */
  originalLineItems: XeroLineItemView[];
  /** Existing active overrides for this transaction */
  splits: TaxCodeOverrideWithSplit[];
  /** Total amount of the transaction (for balance indicator) */
  transactionTotal: number | null;
  getToken: () => Promise<string | null>;
  onChanged: () => void;
  disabled?: boolean;
}

type EditValues = {
  override_tax_type?: string;
  line_amount?: string;
  line_description?: string;
  line_account_code?: string;
};

const VALID_TAX_TYPE_SET = new Set(VALID_TAX_TYPES.map((t) => t.value));

/** A merged row for display — either an original line item (with optional override) or a new split. */
type MergedRow =
  | { kind: 'original'; lineItem: XeroLineItemView; override: TaxCodeOverrideWithSplit | undefined }
  | { kind: 'new_split'; override: TaxCodeOverrideWithSplit };

/**
 * Unified line item editor for bank transaction splits.
 *
 * Shows all original Xero line items alongside any overrides (edits, deletes, new splits)
 * in a single list. Each item can be edited or deleted; new line items can be added.
 */
export function SplitCreationForm({
  connectionId,
  sessionId,
  sourceId,
  originalLineItems,
  splits,
  transactionTotal,
  getToken,
  onChanged,
  disabled = false,
}: SplitCreationFormProps) {
  const [accounts, setAccounts] = useState<XeroAccountOption[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await getToken();
      if (!token || cancelled) return;
      try {
        const data = await listXeroAccounts(token, connectionId);
        if (!cancelled) setAccounts(data);
      } catch {
        // silent — display falls back to raw code
      }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionId]);

  function resolveAccount(code: string | null | undefined): string {
    if (!code) return '';
    const match = accounts.find((a) => a.account_code === code);
    return match ? `${match.account_code} · ${match.account_name}` : code;
  }

  const [newTaxType, setNewTaxType] = useState('');
  const [newAmount, setNewAmount] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const defaultAccountCode = originalLineItems[0]?.account_code ?? '';
  const [newAccountCode, setNewAccountCode] = useState(defaultAccountCode);
  const [isAdding, setIsAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  // 'new-original-{index}' for originals without an existing override
  const [editingOriginalIndex, setEditingOriginalIndex] = useState<number | null>(null);
  const [editValues, setEditValues] = useState<EditValues>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Merge original line items with their overrides, then append new splits
  const rows: MergedRow[] = [
    ...originalLineItems.map((li) => ({
      kind: 'original' as const,
      lineItem: li,
      override: splits.find((o) => !o.is_new_split && o.line_item_index === li.index),
    })),
    ...splits.filter((o) => o.is_new_split).map((o) => ({ kind: 'new_split' as const, override: o })),
  ];

  // Next index for new splits: above all original indices and existing new-split indices
  const allIndices = [
    ...originalLineItems.map((li) => li.index),
    ...splits.filter((o) => o.is_new_split).map((o) => o.line_item_index),
  ];
  const nextIndex = allIndices.length > 0 ? Math.max(...allIndices) + 1 : 0;

  // ─── Handlers ──────────────────────────────────────────────────────────────

  async function handleAdd() {
    if (!newTaxType || !newAmount) return;
    setIsAdding(true);
    setAddError(null);
    try {
      const token = await getToken();
      if (!token) return;
      const body: SplitCreateRequest = {
        line_item_index: nextIndex,
        override_tax_type: newTaxType,
        line_amount: newAmount,
        line_description: newDescription || undefined,
        line_account_code: newAccountCode || undefined,
        is_new_split: true,
      };
      await createSplit(token, connectionId, sessionId, sourceId, body);
      setNewTaxType('');
      setNewAmount('');
      setNewDescription('');
      setNewAccountCode('');
      onChanged();
    } catch (err: unknown) {
      const detail =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err !== null && 'detail' in err
            ? String((err as { detail: unknown }).detail)
            : 'Failed to add line item';
      setAddError(detail);
    } finally {
      setIsAdding(false);
    }
  }

  /** Delete a new split (deactivate the override record). */
  async function handleDeleteNewSplit(overrideId: string) {
    setDeletingId(overrideId);
    try {
      const token = await getToken();
      if (!token) return;
      await deleteSplit(token, connectionId, sessionId, sourceId, overrideId);
      onChanged();
    } finally {
      setDeletingId(null);
    }
  }

  /** Mark an original line item as deleted. Creates or updates an override with is_deleted=true. */
  async function handleDeleteOriginal(lineItem: XeroLineItemView, existingOverride: TaxCodeOverrideWithSplit | undefined) {
    const key = `del-orig-${lineItem.index}`;
    setDeletingId(key);
    try {
      const token = await getToken();
      if (!token) return;
      if (existingOverride) {
        await updateSplit(token, connectionId, sessionId, sourceId, existingOverride.id, {
          is_deleted: true,
        });
      } else {
        await createSplit(token, connectionId, sessionId, sourceId, {
          line_item_index: lineItem.index,
          override_tax_type: lineItem.tax_type ?? 'BASEXCLUDED',
          is_new_split: false,
          is_deleted: true,
        });
      }
      onChanged();
    } finally {
      setDeletingId(null);
    }
  }

  /** Restore a deleted original line item (flip is_deleted back to false). */
  async function handleRestoreOriginal(override: TaxCodeOverrideWithSplit) {
    setSavingId(`restore-${override.id}`);
    try {
      const token = await getToken();
      if (!token) return;
      await updateSplit(token, connectionId, sessionId, sourceId, override.id, {
        is_deleted: false,
      });
      onChanged();
    } finally {
      setSavingId(null);
    }
  }

  /** Open inline edit form for an existing override (new split or edited original). */
  function startEditOverride(override: TaxCodeOverrideWithSplit) {
    setEditingId(override.id);
    setEditingOriginalIndex(null);
    setEditValues({
      override_tax_type: override.override_tax_type,
      line_amount: override.line_amount !== null ? String(Number(override.line_amount)) : '',
      line_description: override.line_description ?? '',
      line_account_code: override.line_account_code ?? '',
    });
  }

  /** Open inline edit form for an original line item that has no override yet. */
  function startEditOriginal(lineItem: XeroLineItemView) {
    setEditingOriginalIndex(lineItem.index);
    setEditingId(null);
    setEditValues({
      override_tax_type: lineItem.tax_type ?? '',
      line_amount: lineItem.line_amount !== null ? String(Number(lineItem.line_amount)) : '',
      line_description: lineItem.description ?? '',
      line_account_code: lineItem.account_code ?? '',
    });
  }

  /** Save an edit to an existing override record. */
  async function handleSaveEditOverride(overrideId: string) {
    setSavingId(overrideId);
    try {
      const token = await getToken();
      if (!token) return;
      await updateSplit(token, connectionId, sessionId, sourceId, overrideId, editValues);
      setEditingId(null);
      setEditValues({});
      onChanged();
    } finally {
      setSavingId(null);
    }
  }

  /** Save an edit to an original line item that had no override — creates a new override. */
  async function handleSaveEditOriginal(lineItem: XeroLineItemView) {
    setSavingId(`new-orig-${lineItem.index}`);
    try {
      const token = await getToken();
      if (!token) return;
      await createSplit(token, connectionId, sessionId, sourceId, {
        line_item_index: lineItem.index,
        override_tax_type: editValues.override_tax_type ?? lineItem.tax_type ?? 'BASEXCLUDED',
        line_amount: editValues.line_amount || undefined,
        line_description: editValues.line_description || undefined,
        line_account_code: editValues.line_account_code || undefined,
        is_new_split: false,
        is_deleted: false,
      });
      setEditingOriginalIndex(null);
      setEditValues({});
      onChanged();
    } finally {
      setSavingId(null);
    }
  }

  function cancelEdit() {
    setEditingId(null);
    setEditingOriginalIndex(null);
    setEditValues({});
  }

  // ─── Shared grid template ─────────────────────────────────────────────────
  // Columns: # | Tax Code | Amount | Description | Account | Actions
  const GRID = 'grid grid-cols-[1rem_9rem_6rem_24rem_11rem_auto] gap-x-2 items-center [&>*]:min-w-0';

  // ─── Edit cells (5 cells: tax, amount, description, account, save/cancel) ──

  function renderEditCells(
    onSave: () => void,
    saveKey: string,
    originalTaxType?: string,
    originalAmount?: string,
  ) {
    return (
      <>
        <Select
          value={editValues.override_tax_type ?? originalTaxType ?? ''}
          onValueChange={(v) => setEditValues((prev) => ({ ...prev, override_tax_type: v }))}
        >
          <SelectTrigger className="h-6 text-xs w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {VALID_TAX_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value} className="text-xs">
                {t.value}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          className="h-6 text-xs w-full"
          value={editValues.line_amount ?? originalAmount ?? ''}
          onChange={(e) => setEditValues((prev) => ({ ...prev, line_amount: e.target.value }))}
          placeholder="Amount"
        />
        <Textarea
          className="text-xs w-full min-h-0 h-12 resize-none py-1 px-2"
          value={editValues.line_description ?? ''}
          onChange={(e) => setEditValues((prev) => ({ ...prev, line_description: e.target.value }))}
          placeholder="Description"
        />
        <AccountCodeCombobox
          connectionId={connectionId}
          getToken={getToken}
          value={editValues.line_account_code ?? ''}
          onChange={(v) => setEditValues((prev) => ({ ...prev, line_account_code: v }))}
          className="w-full"
        />
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            className="h-6 text-xs px-2"
            disabled={savingId === saveKey}
            onClick={onSave}
          >
            {savingId === saveKey ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Save'}
          </Button>
          <Button size="sm" variant="ghost" className="h-6 text-xs px-1.5" onClick={cancelEdit}>
            Cancel
          </Button>
        </div>
      </>
    );
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="mt-2 space-y-1">
      {/* Column header */}
      <div className={cn(GRID, 'text-[10px] font-medium text-muted-foreground uppercase tracking-wide mb-1 px-2')}>
        <span>#</span>
        <span>Tax Code</span>
        <span className="text-right">Amount</span>
        <span>Description</span>
        <span>Account <span className="text-destructive">*</span></span>
        <span />
      </div>

      {/* Merged line item rows */}
      {rows.map((row) => {
        if (row.kind === 'original') {
          const { lineItem, override } = row;
          const isDeleted = override?.is_deleted === true;
          const isEdited = override && !isDeleted;
          const isEditingThis = editingOriginalIndex === lineItem.index ||
            (override && editingId === override.id);

          // Display values: override wins over original
          const displayTaxType = isEdited ? override.override_tax_type : (lineItem.tax_type ?? '—');
          const displayAmount = isEdited
            ? (override.line_amount !== null ? Number(override.line_amount) : null)
            : (lineItem.line_amount !== null ? Number(lineItem.line_amount) : null);
          const displayDescription = isEdited
            ? (override.line_description ?? lineItem.description)
            : lineItem.description;
          const displayAccountCode = isEdited
            ? (override.line_account_code ?? lineItem.account_code)
            : lineItem.account_code;

          return (
            <div
              key={`orig-${lineItem.index}`}
              className={cn(
                GRID,
                'text-xs rounded px-2 py-1.5',
                isDeleted
                  ? 'bg-destructive/5 border border-destructive/20 opacity-60'
                  : isEdited
                    ? 'bg-amber-50 border border-amber-200'
                    : 'bg-muted/20',
              )}
            >
              <span className="font-mono text-[10px] text-muted-foreground">{lineItem.index}</span>
              {isEditingThis ? (
                renderEditCells(
                  override && editingId === override.id
                    ? () => handleSaveEditOverride(override.id)
                    : () => handleSaveEditOriginal(lineItem),
                  override && editingId === override.id
                    ? override.id
                    : `new-orig-${lineItem.index}`,
                  override && editingId === override.id
                    ? override.override_tax_type
                    : (lineItem.tax_type ?? ''),
                  override && editingId === override.id
                    ? (override.line_amount !== null ? String(Number(override.line_amount)) : '')
                    : (lineItem.line_amount !== null ? String(Number(lineItem.line_amount)) : ''),
                )
              ) : (
                <>
                  <span className={cn('font-semibold truncate flex items-center gap-1', isDeleted && 'line-through')}>
                    {displayTaxType}
                    {isEdited && <span className="text-[9px] text-amber-600 font-normal">✏</span>}
                    {!VALID_TAX_TYPE_SET.has(displayTaxType as never) && displayTaxType !== '—' && (
                      <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" aria-label="This tax code may be invalid in Xero" />
                    )}
                  </span>
                  <span className={cn('tabular-nums text-right', isDeleted && 'line-through')}>
                    {displayAmount !== null ? `$${displayAmount.toFixed(2)}` : ''}
                  </span>
                  <span className={cn('text-muted-foreground truncate', isDeleted && 'line-through')}>
                    {displayDescription}
                  </span>
                  <span className={cn('text-muted-foreground text-[10px] truncate', isDeleted && 'line-through')}>
                    {resolveAccount(displayAccountCode)}
                  </span>
                  <div className="flex items-center gap-1">
                    {isDeleted ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 text-xs px-1.5 text-muted-foreground"
                        disabled={disabled || savingId === `restore-${override!.id}`}
                        onClick={() => handleRestoreOriginal(override!)}
                      >
                        {savingId === `restore-${override!.id}` ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <RotateCcw className="w-3 h-3" />
                        )}
                      </Button>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 text-xs px-1.5 text-muted-foreground"
                          disabled={disabled}
                          onClick={() =>
                            override ? startEditOverride(override) : startEditOriginal(lineItem)
                          }
                        >
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-1.5 text-destructive hover:text-destructive"
                          disabled={disabled || deletingId === `del-orig-${lineItem.index}`}
                          onClick={() => handleDeleteOriginal(lineItem, override)}
                        >
                          {deletingId === `del-orig-${lineItem.index}` ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Trash2 className="w-3 h-3" />
                          )}
                        </Button>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          );
        }

        // New split row
        const { override } = row;
        const isEditingThis = editingId === override.id;

        return (
          <div
            key={`split-${override.id}`}
            className={cn(GRID, 'text-xs rounded px-2 py-1.5 bg-primary/5 border border-primary/20')}
          >
            <span className="font-mono text-[10px] text-primary">+</span>
            {isEditingThis ? (
              renderEditCells(
                () => handleSaveEditOverride(override.id),
                override.id,
                override.override_tax_type,
                override.line_amount !== null ? String(Number(override.line_amount)) : '',
              )
            ) : (
              <>
                <span className="font-semibold truncate text-primary flex items-center gap-1">
                  {override.override_tax_type}
                  {!VALID_TAX_TYPE_SET.has(override.override_tax_type as never) && (
                    <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" aria-label="This tax code may be invalid in Xero" />
                  )}
                </span>
                <span className="tabular-nums text-right">
                  {override.line_amount !== null ? `$${Number(override.line_amount).toFixed(2)}` : ''}
                </span>
                <span className="text-muted-foreground truncate">
                  {override.line_description}
                </span>
                <span className="text-muted-foreground text-[10px] truncate">
                  {resolveAccount(override.line_account_code)}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-xs px-1.5 text-muted-foreground"
                    disabled={disabled}
                    onClick={() => startEditOverride(override)}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-1.5 text-destructive hover:text-destructive"
                    disabled={disabled || deletingId === override.id}
                    onClick={() => handleDeleteNewSplit(override.id)}
                  >
                    {deletingId === override.id ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Trash2 className="w-3 h-3" />
                    )}
                  </Button>
                </div>
              </>
            )}
          </div>
        );
      })}

      {/* Add new line item row */}
      <div className={cn(GRID, 'pt-1')}>
        <span />
        <Select value={newTaxType} onValueChange={setNewTaxType} disabled={disabled}>
          <SelectTrigger className="h-6 text-xs w-full">
            <SelectValue placeholder="Tax code..." />
          </SelectTrigger>
          <SelectContent>
            {VALID_TAX_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value} className="text-xs">
                {t.value}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          className="h-6 text-xs w-full"
          value={newAmount}
          onChange={(e) => setNewAmount(e.target.value)}
          placeholder="Amount"
          disabled={disabled}
        />
        <Textarea
          className="text-xs w-full min-h-0 h-12 resize-none py-1 px-2"
          value={newDescription}
          onChange={(e) => setNewDescription(e.target.value)}
          placeholder="Description (opt)"
          disabled={disabled}
        />
        <AccountCodeCombobox
          connectionId={connectionId}
          getToken={getToken}
          value={newAccountCode}
          onChange={setNewAccountCode}
          disabled={disabled}
          className="w-full"
        />
        <Button
          size="sm"
          variant="outline"
          className="h-6 text-xs px-2 gap-1"
          disabled={disabled || !newTaxType || !newAmount || !newAccountCode || isAdding}
          onClick={handleAdd}
        >
          {isAdding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
          Add
        </Button>
      </div>

      {addError && <p className="text-xs text-destructive mt-1">{addError}</p>}

      {transactionTotal !== null && rows.length > 0 && (
        <div className="text-[10px] text-muted-foreground mt-1">
          Transaction total:{' '}
          <span className="font-mono">${Math.abs(Number(transactionTotal)).toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}
