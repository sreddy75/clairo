'use client';

/**
 * LedgerCardsHeader - Client Detail Header (Focused Header Design)
 *
 * Streamlined two-row layout:
 * - Row 1: Client identity + quarter selector + primary actions
 * - Row 2: Clean text tabs + dropdown groups for secondary views
 */

import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowLeftRight,
  BarChart3,
  BookOpen,
  ChevronDown,
  CreditCard,
  ExternalLink,
  FileText,
  Lightbulb,
  Package,
  Plus,
  Receipt,
  RefreshCw,
  Send,
  ShieldCheck,
  ShoppingCart,
  Loader2,
  Sparkles,
  TrendingUp,
  UserPlus,
  Users,
  Wallet,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useState, useRef, useEffect } from 'react';

// =============================================================================
// Types
// =============================================================================

export type Tab =
  | 'overview'
  | 'bas'
  | 'quality'
  | 'insights'
  | 'tax-planning'
  | 'contacts'
  | 'invoices'
  | 'transactions'
  | 'credit-notes'
  | 'payments'
  | 'journals'
  | 'employees'
  | 'pay-runs';

interface DropdownItem {
  id: Tab | string;
  label: string;
  count?: number;
  icon: React.ElementType;
  href?: string;
  action?: () => void;
  external?: boolean;
}

interface DropdownGroup {
  id: string;
  label: string;
  items: DropdownItem[];
}

interface ClientInfo {
  name: string;
  status: string;
  lastSynced: string | null;
  quarterLabel: string;
  hasPayroll: boolean;
}

interface Counts {
  criticalIssues?: number;
  insights?: number;
  contacts?: number;
  invoices?: number;
  transactions?: number;
  creditNotes?: number;
  payments?: number;
  journals?: number;
  employees?: number;
  payRuns?: number;
  assets?: number;
  purchaseOrders?: number;
  pendingRequests?: number;
}

interface QuarterOption {
  quarter: number;
  fy_year: number;
  label: string;
}

interface LedgerCardsHeaderProps {
  client: ClientInfo;
  counts: Counts;
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  onRefresh: () => void;
  onAnalyze: () => void;
  onInvite?: () => void;
  isRefreshing?: boolean;
  isAnalyzing?: boolean;
  quarterDropdownOpen: boolean;
  setQuarterDropdownOpen: (open: boolean) => void;
  quarterOptions?: QuarterOption[];
  onQuarterSelect?: (quarter: number, year: number) => void;
  clientId: string;
}

// =============================================================================
// Navigation Dropdown Component
// =============================================================================

function NavigationDropdown({
  group,
  isOpen,
  onToggle,
  onSelect,
  activeTab,
  clientId,
}: {
  group: DropdownGroup;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  activeTab: Tab;
  clientId: string;
}) {
  const router = useRouter();
  const activeItem = group.items.find((item) => item.id === activeTab);
  const isGroupActive = !!activeItem;

  const handleItemClick = (item: DropdownItem) => {
    if (item.action) {
      item.action();
    } else if (item.external) {
      window.open(item.href, '_blank');
    } else if (item.href) {
      router.push(`/clients/${clientId}${item.href}`);
    } else {
      onSelect(item.id);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
          isOpen || isGroupActive
            ? 'bg-foreground text-background'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
        }`}
      >
        {isGroupActive && activeItem ? activeItem.label : group.label}
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            transition={{ duration: 0.12 }}
            className="absolute top-full left-0 mt-1.5 w-52 bg-card rounded-lg border border-border shadow-xl overflow-hidden z-50"
          >
            <div className="py-1">
              {group.items.map((item) => {
                const ItemIcon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleItemClick(item)}
                    className={`w-full flex items-center justify-between px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? 'bg-muted text-foreground font-medium'
                        : 'text-foreground/80 hover:bg-muted'
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <ItemIcon className="w-4 h-4 text-muted-foreground/70" />
                      {item.label}
                      {item.external && <ExternalLink className="w-3 h-3 text-muted-foreground/50" />}
                    </span>
                    {item.count !== undefined && item.count > 0 && (
                      <span className="text-xs tabular-nums text-muted-foreground/70">{item.count}</span>
                    )}
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// =============================================================================
// Metric Pill Component
// =============================================================================

function MetricPill({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: 'green' | 'red' | 'blue' | 'amber' | 'gray';
}) {
  const colorStyles = {
    green: 'bg-status-success/10 border-status-success/20 text-status-success',
    red: 'bg-status-danger/10 border-status-danger/20 text-status-danger',
    blue: 'bg-primary/10 border-primary/20 text-primary',
    amber: 'bg-status-warning/10 border-status-warning/20 text-status-warning',
    gray: 'bg-muted border-border text-foreground',
  };

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${colorStyles[color]}`}>
      <span className="text-xs font-medium opacity-70">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}

// =============================================================================
// Main Header Component
// =============================================================================

export function LedgerCardsHeader({
  client,
  counts,
  activeTab,
  onTabChange,
  onRefresh,
  onAnalyze,
  onInvite,
  isRefreshing = false,
  isAnalyzing = false,
  quarterDropdownOpen,
  setQuarterDropdownOpen,
  quarterOptions = [],
  onQuarterSelect,
  clientId,
}: LedgerCardsHeaderProps) {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const quarterRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpenDropdown(null);
      }
      if (quarterRef.current && !quarterRef.current.contains(event.target as Node)) {
        setQuarterDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [setQuarterDropdownOpen]);

  // Primary tabs - clean text labels, no icons, no counts
  const primaryTabs: { id: Tab; label: string; badge?: number }[] = [
    { id: 'overview', label: 'Dashboard' },
    { id: 'bas', label: 'BAS', badge: counts.criticalIssues },
    { id: 'insights', label: 'Insights' },
    { id: 'tax-planning', label: 'Tax Planning' },
  ];

  // "Data" dropdown - merges Contacts + Financial Data
  const dataGroup: DropdownGroup = {
    id: 'data',
    label: 'Data',
    items: [
      { id: 'contacts', label: 'Contacts', count: counts.contacts, icon: Users },
      { id: 'invoices', label: 'Invoices', count: counts.invoices, icon: FileText },
      { id: 'transactions', label: 'Bank Transactions', count: counts.transactions, icon: ArrowLeftRight },
      { id: 'credit-notes', label: 'Credit Notes', count: counts.creditNotes, icon: Receipt },
      { id: 'payments', label: 'Payments', count: counts.payments, icon: CreditCard },
      { id: 'journals', label: 'Journals', count: counts.journals, icon: BookOpen },
    ],
  };

  // "More" dropdown - everything else
  const moreGroup: DropdownGroup = {
    id: 'more',
    label: 'More',
    items: [
      ...(client.hasPayroll
        ? [
            { id: 'employees' as Tab, label: 'Employees', count: counts.employees, icon: Users },
            { id: 'pay-runs' as Tab, label: 'Pay Runs', count: counts.payRuns, icon: Wallet },
          ]
        : []),
      { id: 'fixed-assets', label: 'Fixed Assets', count: counts.assets, icon: Package, href: '/assets' },
      { id: 'purchase-orders', label: 'Purchase Orders', count: counts.purchaseOrders, icon: ShoppingCart, href: '/purchase-orders' },
      { id: 'view-requests', label: 'Requests', count: counts.pendingRequests, icon: Send, href: '/requests' },
      { id: 'new-request', label: 'New Request', icon: Plus, href: '/requests/new' },
      { id: 'invite-portal', label: 'Invite to Portal', icon: UserPlus, action: onInvite },
      { id: 'quality' as Tab, label: 'Data Quality', icon: ShieldCheck },
      { id: 'reports', label: 'Reports', icon: BarChart3, href: '/reports' },
      { id: 'open-xero', label: 'Open in Xero', icon: ExternalLink, href: 'https://go.xero.com', external: true },
    ],
  };

  const dropdownGroups = [dataGroup, moreGroup];

  const handleDropdownToggle = (groupId: string) => {
    setOpenDropdown(openDropdown === groupId ? null : groupId);
  };

  const handleViewSelect = (viewId: string) => {
    onTabChange(viewId as Tab);
    setOpenDropdown(null);
  };

  // Format last synced time
  const formatLastSynced = (dateStr: string | null) => {
    if (!dateStr) return 'Never synced';
    try {
      const date = new Date(dateStr);
      return `Synced ${date.toLocaleString('en-AU', {
        day: 'numeric',
        month: 'short',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      })}`;
    } catch {
      return 'Unknown';
    }
  };

  // Get status indicator dot color
  const getStatusDotColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
        return 'bg-status-success';
      case 'disconnected':
        return 'bg-status-danger';
      default:
        return 'bg-muted-foreground';
    }
  };

  return (
    <header className="sticky top-16 z-40 border-b border-border" ref={dropdownRef}>
      {/* Row 1 - Client identity (white background) */}
      <div className="bg-card px-3 sm:px-6 lg:px-8">
        <div className="py-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <Link
              href="/clients"
              className="p-1.5 -ml-1 text-muted-foreground/70 hover:text-foreground rounded-lg hover:bg-muted transition-colors flex-shrink-0"
            >
              <ArrowLeft className="w-4 h-4 sm:w-5 sm:h-5" />
            </Link>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-semibold text-foreground truncate">{client.name}</h1>
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusDotColor(client.status)}`}
                  title={`${client.status} — ${formatLastSynced(client.lastSynced)}`}
                />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
            {/* Quarter Selector */}
            <div className="relative" ref={quarterRef}>
              <button
                onClick={() => setQuarterDropdownOpen(!quarterDropdownOpen)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-sm font-medium text-foreground/80 bg-muted border border-border rounded-md hover:bg-muted transition-colors"
              >
                {client.quarterLabel}
                <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground/70 transition-transform ${quarterDropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              <AnimatePresence>
                {quarterDropdownOpen && quarterOptions.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 4 }}
                    transition={{ duration: 0.12 }}
                    className="absolute top-full right-0 mt-1.5 w-36 bg-card rounded-lg border border-border shadow-lg overflow-hidden z-50"
                  >
                    <div className="py-1">
                      {quarterOptions.map((option) => {
                        const isActive = option.label === client.quarterLabel;
                        return (
                          <button
                            key={option.label}
                            onClick={() => {
                              if (onQuarterSelect) {
                                onQuarterSelect(option.quarter, option.fy_year);
                              }
                              setQuarterDropdownOpen(false);
                            }}
                            className={`w-full flex items-center justify-between px-3 py-1.5 text-sm transition-colors ${
                              isActive
                                ? 'bg-muted text-foreground font-medium'
                                : 'text-foreground/80 hover:bg-muted'
                            }`}
                          >
                            {option.label}
                          </button>
                        );
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              title={`Refresh data\n${formatLastSynced(client.lastSynced)}`}
              className="p-1.5 sm:p-2 text-muted-foreground/70 hover:text-foreground rounded-md hover:bg-muted transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onAnalyze}
              disabled={isAnalyzing}
              title="Analyze with AI"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-primary-foreground bg-primary rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {isAnalyzing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5" />
              )}
              <span className="hidden sm:inline">{isAnalyzing ? 'Analyzing...' : 'Analyze'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Row 2 - Navigation tabs (subtle gray tint) */}
      <div className="bg-muted/80 px-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide">
          {/* Primary text tabs */}
          {primaryTabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors flex-shrink-0 ${
                  isActive
                    ? 'border-foreground text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                }`}
              >
                {tab.label}
                {tab.badge != null && tab.badge > 0 && (
                  <span className="w-4.5 h-4.5 min-w-[18px] rounded-full bg-status-danger text-white text-[10px] flex items-center justify-center">
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}

          <div className="h-4 w-px bg-border mx-1" />

          {/* Dropdown groups */}
          {dropdownGroups.map((group) => (
            <NavigationDropdown
              key={group.id}
              group={group}
              isOpen={openDropdown === group.id}
              onToggle={() => handleDropdownToggle(group.id)}
              onSelect={handleViewSelect}
              activeTab={activeTab}
              clientId={clientId}
            />
          ))}
        </div>
      </div>
    </header>
  );
}

// =============================================================================
// Stat Card Component (for Dashboard)
// =============================================================================

export function StatCard({
  title,
  items,
  icon: Icon,
}: {
  title: string;
  items: { label: string; value: string; subtext?: string; color: 'green' | 'red' | 'blue' | 'amber' | 'gray' }[];
  icon: React.ElementType;
}) {
  const colorStyles = {
    green: 'text-status-success',
    red: 'text-status-danger',
    blue: 'text-primary',
    amber: 'text-status-warning',
    gray: 'text-foreground',
  };

  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-3 bg-muted border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <Icon className="w-4 h-4" />
          {title}
        </h3>
      </div>
      <div className="p-4">
        <div className="grid grid-cols-2 gap-4">
          {items.map((item, i) => (
            <div key={i}>
              <p className="text-xs text-muted-foreground mb-0.5">{item.label}</p>
              <p className={`text-xl font-semibold tabular-nums ${colorStyles[item.color]}`}>{item.value}</p>
              {item.subtext && <p className="text-xs text-muted-foreground/70 mt-0.5">{item.subtext}</p>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Quality Meter Component
// =============================================================================

export function QualityMeter({
  score,
  issues,
  onClick,
}: {
  score: number;
  issues: number;
  onClick?: () => void;
}) {
  const getColor = (s: number) => {
    if (s >= 80) return { bar: 'bg-status-success', text: 'text-status-success', label: 'Ready' };
    if (s >= 60) return { bar: 'bg-status-warning', text: 'text-status-warning', label: 'Needs Review' };
    return { bar: 'bg-status-danger', text: 'text-status-danger', label: 'Issues Found' };
  };

  const colors = getColor(score);

  return (
    <div
      className={`bg-card rounded-xl border border-border overflow-hidden ${onClick ? 'cursor-pointer hover:border-border/80' : ''}`}
      onClick={onClick}
    >
      <div className="px-4 py-3 bg-muted border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Data Quality
        </h3>
      </div>
      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-2xl font-bold tabular-nums ${colors.text}`}>{score}</span>
          <span
            className={`text-xs font-medium px-2 py-1 rounded-full ${colors.bar}/10 ${colors.text}`}
          >
            {colors.label}
          </span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${score}%` }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
            className={`h-full ${colors.bar} rounded-full`}
          />
        </div>
        {issues > 0 && (
          <div className="mt-3 flex items-center gap-2 text-status-danger">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-sm font-medium tabular-nums">{issues} critical issues</span>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Insight Row Component
// =============================================================================

export function InsightRow({
  type,
  title,
  description,
  onClick,
}: {
  type: 'warning' | 'info' | 'success';
  title: string;
  description: string;
  onClick?: () => void;
}) {
  const styles = {
    warning: { icon: AlertTriangle, color: 'text-status-warning bg-status-warning/10' },
    info: { icon: Lightbulb, color: 'text-primary bg-primary/10' },
    success: { icon: TrendingUp, color: 'text-status-success bg-status-success/10' },
  };

  const style = styles[type];
  const Icon = style.icon;

  return (
    <div
      className={`flex items-start gap-3 py-3 border-b border-border last:border-0 ${onClick ? 'cursor-pointer hover:bg-muted' : ''}`}
      onClick={onClick}
    >
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${style.color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </div>
    </div>
  );
}

// Re-export MetricPill for use in pages
export { MetricPill };
