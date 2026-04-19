'use client';

/**
 * Walk rendered markdown children, replacing any `[CLR-XXX: Name]` bracketed
 * text with an inline `<StrategyChip/>` React node (Spec 060 T041).
 *
 * Approach: ReactMarkdown renders each text-containing element (`p`, `li`,
 * `td`, `em`, etc.) with `children` that may be a string, a React element,
 * or an array thereof. We recurse through the structure, splitting any
 * raw string by the CLR regex and looking up each match's verification
 * status from `strategy_citations`. Non-string children pass through
 * unchanged so nested markdown (bold, links, tables) keeps its rendering.
 *
 * Graceful degradation (spec §Edge Cases / T050): an unknown CLR match —
 * i.e. the LLM mentioned `[CLR-999: Fake]` but no such citation is in the
 * verification payload — still renders a red chip with a "not found"
 * title. The chat never crashes or silently swallows the content.
 */

import { Children, Fragment, isValidElement, type ReactNode } from 'react';

import type { StrategyCitationItem } from '@/types/tax-planning';

import { StrategyChip } from './StrategyChip';

// Mirrors backend CitationVerifier.CLR_PATTERN exactly. Shared ids like
// CLR-012 render the same whether they appear in prose or in a list cell.
const CLR_PATTERN = /\[CLR-(\d{3,5}):\s*([^\]]+)\]/g;

export interface StrategyChipTokenizerContext {
  byId: Map<string, StrategyCitationItem>;
  onOpen: (strategyId: string) => void;
}

export function buildStrategyChipContext(
  strategyCitations: readonly StrategyCitationItem[] | undefined,
  onOpen: (strategyId: string) => void,
): StrategyChipTokenizerContext {
  const byId = new Map<string, StrategyCitationItem>();
  for (const c of strategyCitations ?? []) {
    byId.set(c.strategy_id, c);
  }
  return { byId, onOpen };
}

/**
 * Replace CLR citations inside a ReactMarkdown `children` tree with
 * `<StrategyChip/>` nodes.
 */
export function tokenizeStrategyChips(
  children: ReactNode,
  ctx: StrategyChipTokenizerContext,
): ReactNode {
  if (children == null || typeof children === 'boolean') {
    return children;
  }
  if (typeof children === 'string') {
    return splitStringByChips(children, ctx);
  }
  if (typeof children === 'number') {
    return children;
  }
  if (Array.isArray(children)) {
    return Children.map(children, (c, i) => (
      <Fragment key={i}>{tokenizeStrategyChips(c, ctx)}</Fragment>
    ));
  }
  if (isValidElement(children)) {
    // Don't recurse into chips we've already produced — they're terminal.
    if ((children.type as { displayName?: string } | undefined) === StrategyChip) {
      return children;
    }
    const { children: innerChildren, ...rest } = (children.props ?? {}) as {
      children?: ReactNode;
    } & Record<string, unknown>;
    if (innerChildren === undefined) return children;
    return {
      ...children,
      props: {
        ...rest,
        children: tokenizeStrategyChips(innerChildren, ctx),
      },
    } as typeof children;
  }
  return children;
}

function splitStringByChips(
  text: string,
  ctx: StrategyChipTokenizerContext,
): ReactNode {
  // Fast path: no brackets at all → return the string as-is so React can
  // merge it with adjacent text nodes.
  if (!text.includes('[CLR-')) return text;

  const out: ReactNode[] = [];
  let lastIndex = 0;
  // Reset regex state since we use the same singleton across calls.
  CLR_PATTERN.lastIndex = 0;

  let match: RegExpExecArray | null;
  let keyCounter = 0;
  while ((match = CLR_PATTERN.exec(text)) !== null) {
    const [full, idDigits, rawName] = match;
    const strategyId = `CLR-${idDigits}`;
    const citedName = (rawName ?? '').trim();

    if (match.index > lastIndex) {
      out.push(text.slice(lastIndex, match.index));
    }
    const citation = ctx.byId.get(strategyId);
    out.push(
      <StrategyChip
        key={`clr-${keyCounter++}-${match.index}`}
        strategyId={strategyId}
        citedName={citation?.cited_name ?? citedName}
        status={citation?.status ?? 'unverified'}
        onClick={ctx.onOpen}
      />,
    );
    lastIndex = match.index + full.length;
  }
  if (lastIndex === 0) return text;
  if (lastIndex < text.length) {
    out.push(text.slice(lastIndex));
  }
  return out;
}
