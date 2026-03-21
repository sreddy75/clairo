'use client';

/**
 * ClientDetailCompact - Alternative "Ledger Cards" Design
 *
 * A compact, card-based layout that consolidates 15 tabs into:
 * 1. Always-visible metrics dashboard
 * 2. Grouped dropdown navigation for detailed views
 * 3. Expandable sections for drill-down
 *
 * Design Philosophy: Information density with elegant hierarchy
 */

import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  BookOpen,
  Briefcase,
  Calculator,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  CreditCard,
  DollarSign,
  ExternalLink,
  FileText,
  Lightbulb,
  Package,
  RefreshCw,
  Sparkles,
  TrendingUp,
  Users,
  Wallet,
  ArrowLeftRight,
  Receipt,
} from 'lucide-react';
import Link from 'next/link';
import React, { useState } from 'react';

// =============================================================================
// Types & Data (same as before for consistency)
// =============================================================================

interface DropdownItem {
  id: string;
  label: string;
  count?: number;
  icon: React.ElementType;
}

interface DropdownGroup {
  id: string;
  label: string;
  icon: React.ElementType;
  items: DropdownItem[];
}

const dropdownGroups: DropdownGroup[] = [
  {
    id: 'financials',
    label: 'Financial Data',
    icon: DollarSign,
    items: [
      { id: 'invoices', label: 'Invoices', count: 189, icon: FileText },
      { id: 'transactions', label: 'Bank Transactions', count: 58, icon: ArrowLeftRight },
      { id: 'credit-notes', label: 'Credit Notes', count: 4, icon: Receipt },
      { id: 'payments', label: 'Payments', count: 156, icon: CreditCard },
      { id: 'journals', label: 'Journals', count: 23, icon: BookOpen },
    ],
  },
  {
    id: 'payroll',
    label: 'Payroll',
    icon: Briefcase,
    items: [
      { id: 'employees', label: 'Employees', count: 4, icon: Users },
      { id: 'pay-runs', label: 'Pay Runs', count: 3, icon: Wallet },
    ],
  },
  {
    id: 'assets',
    label: 'Assets',
    icon: Package,
    items: [
      { id: 'fixed-assets', label: 'Fixed Assets', count: 12, icon: Package },
      { id: 'purchase-orders', label: 'Purchase Orders', count: 3, icon: FileText },
    ],
  },
];

// =============================================================================
// Subcomponents
// =============================================================================

function NavigationDropdown({
  group,
  isOpen,
  onToggle,
  onSelect,
}: {
  group: DropdownGroup;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
}) {
  const Icon = group.icon;
  const totalCount = group.items.reduce((sum, item) => sum + (item.count || 0), 0);

  return (
    <div className="relative">
      <button
        onClick={onToggle}
        className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
          isOpen
            ? 'bg-foreground text-background'
            : 'bg-card text-foreground border border-border hover:border-border hover:bg-muted'
        }`}
      >
        <Icon className="w-4 h-4" />
        {group.label}
        {totalCount > 0 && (
          <span className={`text-xs tabular-nums px-1.5 py-0.5 rounded-full ${
            isOpen ? 'bg-white/20 text-white' : 'bg-muted text-muted-foreground'
          }`}>
            {totalCount}
          </span>
        )}
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full left-0 mt-2 w-56 bg-card rounded-xl border border-border shadow-xl overflow-hidden z-20"
          >
            <div className="p-1">
              {group.items.map((item) => {
                const ItemIcon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelect(item.id)}
                    className="w-full flex items-center justify-between px-3 py-2 text-sm text-foreground hover:bg-muted rounded-lg transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <ItemIcon className="w-4 h-4 text-muted-foreground" />
                      {item.label}
                    </span>
                    {item.count !== undefined && (
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {item.count}
                      </span>
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

function MetricPill({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: 'green' | 'red' | 'blue' | 'amber' | 'slate';
}) {
  const colorStyles = {
    green: 'bg-status-success/10 border-status-success/20 text-status-success',
    red: 'bg-status-danger/10 border-status-danger/20 text-status-danger',
    blue: 'bg-primary/10 border-primary/20 text-primary',
    amber: 'bg-status-warning/10 border-status-warning/20 text-status-warning',
    slate: 'bg-muted border-border text-foreground',
  };

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${colorStyles[color]}`}>
      <span className="text-xs font-medium opacity-70">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}

function StatCard({
  title,
  items,
  icon: Icon,
}: {
  title: string;
  items: { label: string; value: string; subtext?: string; color: 'green' | 'red' | 'blue' | 'amber' | 'slate' }[];
  icon: React.ElementType;
}) {
  const colorStyles = {
    green: 'text-status-success',
    red: 'text-status-danger',
    blue: 'text-primary',
    amber: 'text-status-warning',
    slate: 'text-foreground',
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
              <p className={`text-xl font-semibold tabular-nums ${colorStyles[item.color]}`}>
                {item.value}
              </p>
              {item.subtext && (
                <p className="text-xs text-muted-foreground/70 mt-0.5">{item.subtext}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function QualityMeter({ score, issues }: { score: number; issues: number }) {
  const getColor = (s: number) => {
    if (s >= 80) return { bar: 'bg-status-success', text: 'text-status-success', label: 'Ready' };
    if (s >= 60) return { bar: 'bg-status-warning', text: 'text-status-warning', label: 'Needs Review' };
    return { bar: 'bg-status-danger', text: 'text-status-danger', label: 'Issues Found' };
  };

  const colors = getColor(score);

  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden">
      <div className="px-4 py-3 bg-muted border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Data Quality
        </h3>
      </div>
      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className={`text-3xl font-bold tabular-nums ${colors.text}`}>{score}</span>
          <span className={`text-xs font-medium px-2 py-1 rounded-full ${
            colors.bar.replace('bg-', 'bg-') + '/10'
          } ${colors.text}`}>
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
            <span className="text-sm font-medium">{issues} critical issues</span>
            <ChevronRight className="w-4 h-4 ml-auto" />
          </div>
        )}
      </div>
    </div>
  );
}

function InsightRow({ type, title, description }: { type: 'warning' | 'info' | 'success'; title: string; description: string }) {
  const styles = {
    warning: { icon: AlertTriangle, color: 'text-status-warning bg-status-warning/10' },
    info: { icon: Lightbulb, color: 'text-primary bg-primary/10' },
    success: { icon: CheckCircle2, color: 'text-status-success bg-status-success/10' },
  };

  const style = styles[type];
  const Icon = style.icon;

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${style.color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </div>
      <ChevronRight className="w-4 h-4 text-muted-foreground/50 flex-shrink-0 mt-2" />
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export default function ClientDetailCompact() {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<string | null>(null);

  const handleDropdownToggle = (groupId: string) => {
    setOpenDropdown(openDropdown === groupId ? null : groupId);
  };

  const handleViewSelect = (viewId: string) => {
    setActiveView(viewId);
    setOpenDropdown(null);
    // Navigate to view
  };

  // Close dropdown when clicking outside
  const handleBackdropClick = () => {
    setOpenDropdown(null);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Click backdrop for closing dropdowns */}
      {openDropdown && (
        <div
          className="fixed inset-0 z-10"
          onClick={handleBackdropClick}
        />
      )}

      {/* Header */}
      <header className="bg-card border-b border-border sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Top row */}
          <div className="py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/clients"
                className="p-2 -ml-2 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </Link>

              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                  <span className="text-white font-bold text-sm">KR</span>
                </div>
                <div>
                  <h1 className="text-lg font-semibold text-foreground">KR8 IT</h1>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-700">
                      Active
                    </span>
                    <span className="text-xs text-muted-foreground/70 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Synced 1 Jan, 06:57 pm
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Quarter Selector */}
              <button className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-colors">
                <Clock className="w-4 h-4 text-muted-foreground" />
                Q3 FY26
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              </button>

              <div className="h-6 w-px bg-border mx-2" />

              <button className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-colors">
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
              <button className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/90 transition-colors">
                <Sparkles className="w-4 h-4" />
                Analyze
              </button>
              <button className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-colors">
                <ExternalLink className="w-4 h-4" />
                Xero
              </button>
            </div>
          </div>

          {/* Navigation row */}
          <div className="pb-3 flex items-center gap-2 overflow-x-auto">
            {/* Primary tabs */}
            <div className="flex items-center gap-1 mr-4">
              {[
                { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
                { id: 'bas', label: 'BAS Prep', icon: Calculator, badge: 2 },
                { id: 'quality', label: 'Quality', icon: TrendingUp },
                { id: 'insights', label: 'Insights', icon: Sparkles },
                { id: 'contacts', label: 'Contacts', icon: Users, count: 112 },
              ].map((tab) => {
                const Icon = tab.icon;
                const isActive = activeView === tab.id || (!activeView && tab.id === 'dashboard');
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveView(tab.id)}
                    className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                      isActive
                        ? 'bg-foreground text-background'
                        : 'text-muted-foreground hover:bg-muted'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                    {tab.badge && (
                      <span className={`w-5 h-5 rounded-full text-xs flex items-center justify-center ${
                        isActive ? 'bg-status-danger text-white' : 'bg-status-danger/10 text-status-danger'
                      }`}>
                        {tab.badge}
                      </span>
                    )}
                    {tab.count !== undefined && (
                      <span className={`text-xs tabular-nums ${isActive ? 'text-muted-foreground' : 'text-muted-foreground'}`}>
                        {tab.count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <div className="h-6 w-px bg-border" />

            {/* Dropdown groups */}
            <div className="flex items-center gap-2 ml-4">
              {dropdownGroups.map((group) => (
                <NavigationDropdown
                  key={group.id}
                  group={group}
                  isOpen={openDropdown === group.id}
                  onToggle={() => handleDropdownToggle(group.id)}
                  onSelect={handleViewSelect}
                />
              ))}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Quick Stats Bar */}
        <div className="flex flex-wrap gap-2 mb-6">
          <MetricPill label="Net GST" value="$4,857" color="blue" />
          <MetricPill label="Sales" value="$142,850" color="green" />
          <MetricPill label="Purchases" value="$89,420" color="red" />
          <MetricPill label="PAYG Tax" value="$52,420" color="amber" />
          <MetricPill label="Quality" value="85/100" color="slate" />
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Main Stats */}
          <div className="lg:col-span-2 space-y-6">
            <StatCard
              title="GST Summary"
              icon={DollarSign}
              items={[
                { label: 'Total Sales', value: '$142,850', subtext: 'GST Collected: $12,986', color: 'green' },
                { label: 'Total Purchases', value: '$89,420', subtext: 'GST Paid: $8,129', color: 'red' },
                { label: 'Net GST', value: '$4,857', subtext: 'Payable to ATO', color: 'blue' },
                { label: 'Activity', value: '247', subtext: '189 invoices, 58 transactions', color: 'slate' },
              ]}
            />

            <StatCard
              title="PAYG Withholding"
              icon={Briefcase}
              items={[
                { label: 'Total Wages (W1)', value: '$186,500', subtext: 'Gross wages for quarter', color: 'green' },
                { label: 'Tax Withheld (W2)', value: '$52,420', subtext: 'PAYG withheld', color: 'amber' },
                { label: 'Superannuation', value: '$19,383', subtext: 'Super contributions', color: 'blue' },
                { label: 'Payroll Activity', value: '12', subtext: '3 pay runs, 4 employees', color: 'slate' },
              ]}
            />
          </div>

          {/* Right Column - Quality & Insights */}
          <div className="space-y-6">
            <QualityMeter score={85} issues={2} />

            {/* AI Insights */}
            <div className="bg-card rounded-xl border border-border overflow-hidden">
              <div className="px-4 py-3 bg-primary/5 border-b border-border">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-primary flex items-center gap-2">
                  <Sparkles className="w-4 h-4" />
                  AI Insights
                </h3>
              </div>
              <div className="p-4">
                <InsightRow
                  type="warning"
                  title="3 transactions missing GST"
                  description="Bank transactions Dec 15-18"
                />
                <InsightRow
                  type="success"
                  title="PAYG reconciliation complete"
                  description="All records match ATO"
                />
                <InsightRow
                  type="info"
                  title="Instant write-off opportunity"
                  description="2 assets qualify ($20K)"
                />
              </div>
              <div className="px-4 py-3 bg-muted border-t border-border">
                <button className="text-sm text-primary hover:text-primary/80 font-medium flex items-center gap-1">
                  View all insights
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
