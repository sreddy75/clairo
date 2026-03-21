'use client';

/**
 * ClientDetailRedesign - "Swiss Ledger" Design System
 *
 * A refined, utilitarian-elegant client detail page that replaces
 * 15+ tabs with a three-zone architecture:
 * 1. Persistent sidebar - Grouped navigation with collapsible categories
 * 2. Dashboard hero - Key metrics always visible
 * 3. Command palette - Quick jump for power users
 *
 * Design Philosophy: Swiss precision meets editorial clarity
 */

import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3,
  BookOpen,
  Building2,
  Calculator,
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
  Search,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Users,
  AlertTriangle,
  CheckCircle2,
  Command,
  Briefcase,
  Receipt,
  ArrowLeftRight,
  Layers,
} from 'lucide-react';
import React, { useState, useEffect, useCallback } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface MetricCardProps {
  label: string;
  value: string;
  subtext?: string;
  trend?: 'up' | 'down' | 'neutral';
  color?: 'green' | 'red' | 'blue' | 'amber' | 'slate';
}

interface NavCategory {
  id: string;
  label: string;
  icon: React.ElementType;
  items: NavItem[];
}

interface NavItem {
  id: string;
  label: string;
  count?: number;
  badge?: 'warning' | 'error' | 'success';
}

interface InsightItem {
  id: string;
  type: 'warning' | 'info' | 'success';
  title: string;
  description: string;
}

// =============================================================================
// Sample Data
// =============================================================================

const sampleClient = {
  name: 'KR8 IT',
  status: 'Active',
  lastSynced: '1 Jan, 06:57 pm',
  quarter: 'Q3 FY26',
  qualityScore: 85,
  criticalIssues: 2,
};

const gstMetrics: MetricCardProps[] = [
  { label: 'Total Sales', value: '$142,850', subtext: 'GST Collected: $12,986', color: 'green', trend: 'up' },
  { label: 'Total Purchases', value: '$89,420', subtext: 'GST Paid: $8,129', color: 'red', trend: 'neutral' },
  { label: 'Net GST', value: '$4,857', subtext: 'Payable to ATO', color: 'blue', trend: 'up' },
  { label: 'Activity', value: '247', subtext: '189 invoices, 58 transactions', color: 'slate' },
];

const paygMetrics: MetricCardProps[] = [
  { label: 'Total Wages (W1)', value: '$186,500', subtext: 'Gross wages for quarter', color: 'green' },
  { label: 'Tax Withheld (W2)', value: '$52,420', subtext: 'PAYG withheld from wages', color: 'amber' },
  { label: 'Superannuation', value: '$19,383', subtext: 'Super contributions', color: 'blue' },
  { label: 'Payroll Activity', value: '12', subtext: '3 pay runs, 4 employees', color: 'slate' },
];

const navCategories: NavCategory[] = [
  {
    id: 'bas',
    label: 'BAS Preparation',
    icon: Calculator,
    items: [
      { id: 'workflow', label: 'BAS Workflow', badge: 'warning' },
      { id: 'quality', label: 'Data Quality', count: 2, badge: 'error' },
      { id: 'checklist', label: 'Pre-Lodge Checklist' },
    ],
  },
  {
    id: 'financials',
    label: 'Financial Data',
    icon: DollarSign,
    items: [
      { id: 'invoices', label: 'Invoices', count: 189 },
      { id: 'transactions', label: 'Bank Transactions', count: 58 },
      { id: 'credit-notes', label: 'Credit Notes', count: 4 },
      { id: 'payments', label: 'Payments', count: 156 },
      { id: 'journals', label: 'Journals', count: 23 },
    ],
  },
  {
    id: 'payroll',
    label: 'Payroll & PAYG',
    icon: Briefcase,
    items: [
      { id: 'employees', label: 'Employees', count: 4 },
      { id: 'pay-runs', label: 'Pay Runs', count: 3 },
    ],
  },
  {
    id: 'assets',
    label: 'Assets & Orders',
    icon: Package,
    items: [
      { id: 'fixed-assets', label: 'Fixed Assets', count: 12 },
      { id: 'purchase-orders', label: 'Purchase Orders', count: 3 },
    ],
  },
  {
    id: 'contacts',
    label: 'Contacts & Reports',
    icon: Users,
    items: [
      { id: 'contacts', label: 'Contacts', count: 112 },
      { id: 'reports', label: 'Financial Reports' },
    ],
  },
];

const insights: InsightItem[] = [
  {
    id: '1',
    type: 'warning',
    title: 'Missing GST coding on 3 transactions',
    description: 'Bank transactions from Dec 15-18 need GST codes assigned',
  },
  {
    id: '2',
    type: 'success',
    title: 'PAYG reconciliation complete',
    description: 'All wages and tax withheld match ATO records',
  },
  {
    id: '3',
    type: 'info',
    title: 'Potential instant write-off opportunity',
    description: '2 assets qualify for $20K instant asset write-off',
  },
];

// =============================================================================
// Subcomponents
// =============================================================================

function MetricCard({ label, value, subtext, trend, color = 'slate' }: MetricCardProps) {
  const colorStyles = {
    green: 'text-status-success',
    red: 'text-destructive',
    blue: 'text-primary',
    amber: 'text-amber-600',
    slate: 'text-foreground',
  };

  const bgStyles = {
    green: 'bg-status-success/10 border-status-success/20',
    red: 'bg-destructive/10 border-destructive/20',
    blue: 'bg-primary/5 border-primary/20',
    amber: 'bg-amber-50 border-amber-100',
    slate: 'bg-muted border-border',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('rounded-lg border p-4 transition-all hover:shadow-sm', bgStyles[color])}
    >
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {trend && (
          <span className={cn(
            trend === 'up' ? 'text-status-success' : trend === 'down' ? 'text-status-danger' : 'text-muted-foreground'
          )}>
            {trend === 'up' ? <TrendingUp className="w-3.5 h-3.5" /> :
             trend === 'down' ? <TrendingDown className="w-3.5 h-3.5" /> : null}
          </span>
        )}
      </div>
      <p className={cn('text-2xl font-semibold tabular-nums mt-1', colorStyles[color])}>
        {value}
      </p>
      {subtext && (
        <p className="text-xs text-muted-foreground mt-1">{subtext}</p>
      )}
    </motion.div>
  );
}

function QualityGauge({ score, issues }: { score: number; issues: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;

  const getScoreColor = (s: number) => {
    if (s >= 80) return { stroke: 'hsl(var(--status-success))', bg: 'bg-status-success/10', text: 'text-status-success' };
    if (s >= 60) return { stroke: 'hsl(var(--status-warning))', bg: 'bg-amber-50', text: 'text-amber-600' };
    return { stroke: 'hsl(var(--status-danger))', bg: 'bg-destructive/10', text: 'text-destructive' };
  };

  const colors = getScoreColor(score);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn('rounded-lg border border-border p-4 flex items-center gap-4', colors.bg)}
    >
      <div className="relative">
        <svg width="96" height="96" className="-rotate-90">
          <circle
            cx="48"
            cy="48"
            r={radius}
            fill="none"
            stroke="hsl(var(--border))"
            strokeWidth="8"
          />
          <motion.circle
            cx="48"
            cy="48"
            r={radius}
            fill="none"
            stroke={colors.stroke}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference - progress }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={cn('text-2xl font-bold tabular-nums', colors.text)}>
            {score}
          </span>
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">Data Quality</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {score >= 80 ? 'Ready for lodgement' : 'Issues need attention'}
        </p>
        {issues > 0 && (
          <div className="flex items-center gap-1 mt-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-destructive/10 text-destructive">
              <AlertTriangle className="w-3 h-3" />
              {issues} critical
            </span>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function NavSection({
  category,
  isExpanded,
  onToggle,
  activeItem,
  onSelectItem
}: {
  category: NavCategory;
  isExpanded: boolean;
  onToggle: () => void;
  activeItem: string | null;
  onSelectItem: (id: string) => void;
}) {
  const Icon = category.icon;

  return (
    <div className="mb-1">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-white hover:bg-foreground/50 rounded-lg transition-colors"
      >
        <Icon className="w-4 h-4 text-muted-foreground" />
        <span className="flex-1 text-left">{category.label}</span>
        <ChevronRight
          className={cn('w-4 h-4 text-muted-foreground transition-transform', isExpanded && 'rotate-90')}
        />
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="ml-6 mt-1 space-y-0.5">
              {category.items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => onSelectItem(item.id)}
                  className={cn(
                    'w-full flex items-center justify-between px-3 py-1.5 text-sm rounded-md transition-colors',
                    activeItem === item.id
                      ? 'bg-primary text-white'
                      : 'text-muted-foreground hover:text-white hover:bg-foreground/50'
                  )}
                >
                  <span>{item.label}</span>
                  <span className="flex items-center gap-2">
                    {item.badge && (
                      <span className={cn(
                        'w-1.5 h-1.5 rounded-full',
                        item.badge === 'error' ? 'bg-status-danger' :
                        item.badge === 'warning' ? 'bg-amber-400' :
                        'bg-status-success'
                      )} />
                    )}
                    {item.count !== undefined && (
                      <span className={cn(
                        'text-xs tabular-nums',
                        activeItem === item.id ? 'text-primary-foreground' : 'text-muted-foreground'
                      )}>
                        {item.count}
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function InsightCard({ insight }: { insight: InsightItem }) {
  const styles = {
    warning: { icon: AlertTriangle, bg: 'bg-amber-50', border: 'border-amber-200', iconColor: 'text-amber-500' },
    info: { icon: Lightbulb, bg: 'bg-primary/5', border: 'border-primary/20', iconColor: 'text-primary' },
    success: { icon: CheckCircle2, bg: 'bg-status-success/10', border: 'border-status-success/20', iconColor: 'text-status-success' },
  };

  const style = styles[insight.type];
  const Icon = style.icon;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn('p-3 rounded-lg border', style.bg, style.border)}
    >
      <div className="flex gap-3">
        <Icon className={cn('w-4 h-4 mt-0.5 flex-shrink-0', style.iconColor)} />
        <div>
          <p className="text-sm font-medium text-foreground">{insight.title}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{insight.description}</p>
        </div>
      </div>
    </motion.div>
  );
}

function CommandPaletteOverlay({
  isOpen,
  onClose
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState('');

  const commands = [
    { id: 'bas', label: 'Go to BAS Workflow', icon: Calculator, category: 'Navigation' },
    { id: 'invoices', label: 'View Invoices', icon: FileText, category: 'Navigation' },
    { id: 'quality', label: 'Check Data Quality', icon: TrendingUp, category: 'Navigation' },
    { id: 'analyze', label: 'Run AI Analysis', icon: Sparkles, category: 'Actions' },
    { id: 'refresh', label: 'Sync with Xero', icon: RefreshCw, category: 'Actions' },
    { id: 'reports', label: 'Generate Reports', icon: BarChart3, category: 'Actions' },
  ];

  const filteredCommands = query
    ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : commands;

  useEffect(() => {
    if (isOpen) {
      setQuery('');
    }
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
          onClick={onClose}
        >
          <div className="absolute inset-0 bg-foreground/50 backdrop-blur-sm" />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-lg bg-white rounded-xl shadow-2xl overflow-hidden"
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
              <Search className="w-5 h-5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search commands..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1 text-sm text-foreground placeholder:text-muted-foreground outline-none"
                autoFocus
              />
              <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium text-muted-foreground bg-muted rounded">
                <span>esc</span>
              </kbd>
            </div>

            <div className="max-h-80 overflow-y-auto p-2">
              {['Navigation', 'Actions'].map((category) => {
                const categoryCommands = filteredCommands.filter(c => c.category === category);
                if (categoryCommands.length === 0) return null;

                return (
                  <div key={category} className="mb-2">
                    <p className="px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      {category}
                    </p>
                    {categoryCommands.map((command) => {
                      const CmdIcon = command.icon;
                      return (
                        <button
                          key={command.id}
                          onClick={() => {
                            onClose();
                            // Handle command
                          }}
                          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-foreground hover:bg-muted rounded-lg transition-colors"
                        >
                          <CmdIcon className="w-4 h-4 text-muted-foreground" />
                          <span>{command.label}</span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export default function ClientDetailRedesign() {
  const [expandedCategories, setExpandedCategories] = useState<string[]>(['bas']);
  const [activeNavItem, setActiveNavItem] = useState<string | null>('workflow');
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [selectedQuarter, _setSelectedQuarter] = useState('Q3 FY26');

  // Command palette keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(true);
      }
      if (e.key === 'Escape') {
        setIsCommandPaletteOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const toggleCategory = useCallback((categoryId: string) => {
    setExpandedCategories(prev =>
      prev.includes(categoryId)
        ? prev.filter(id => id !== categoryId)
        : [...prev, categoryId]
    );
  }, []);

  return (
    <div className="min-h-screen bg-muted flex">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-foreground flex flex-col flex-shrink-0">
        {/* Client Header */}
        <div className="p-4 border-b border-foreground/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/70 to-primary flex items-center justify-center">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-sm font-semibold text-white truncate">
                {sampleClient.name}
              </h2>
              <p className="text-xs text-muted-foreground">
                {sampleClient.lastSynced}
              </p>
            </div>
          </div>

          {/* Quarter Selector */}
          <div className="mt-3">
            <button className="w-full flex items-center justify-between px-3 py-2 text-sm text-muted-foreground bg-foreground rounded-lg hover:bg-foreground/80 transition-colors">
              <span className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-muted-foreground" />
                {selectedQuarter}
              </span>
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 overflow-y-auto">
          {navCategories.map((category) => (
            <NavSection
              key={category.id}
              category={category}
              isExpanded={expandedCategories.includes(category.id)}
              onToggle={() => toggleCategory(category.id)}
              activeItem={activeNavItem}
              onSelectItem={setActiveNavItem}
            />
          ))}
        </nav>

        {/* Quick Actions */}
        <div className="p-3 border-t border-foreground/80 space-y-2">
          <button
            onClick={() => setIsCommandPaletteOpen(true)}
            className="w-full flex items-center justify-between px-3 py-2 text-sm text-muted-foreground bg-foreground/50 rounded-lg hover:bg-foreground hover:text-muted-foreground transition-colors"
          >
            <span className="flex items-center gap-2">
              <Search className="w-4 h-4" />
              Quick Search
            </span>
            <kbd className="text-xs text-muted-foreground">
              <Command className="w-3 h-3 inline" />K
            </kbd>
          </button>

          <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-white hover:bg-foreground/50 rounded-lg transition-colors">
            <ExternalLink className="w-4 h-4" />
            View in Xero
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {/* Top Actions Bar */}
        <header className="bg-white border-b border-border px-6 py-3 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-status-success/10 text-status-success">
                <CheckCircle2 className="w-3 h-3 mr-1" />
                Active
              </span>
              <span className="text-sm text-muted-foreground">
                Last synced: {sampleClient.lastSynced}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm">
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
              <Button size="sm">
                <Sparkles className="w-4 h-4" />
                Analyze
              </Button>
              <Button variant="outline" size="sm">
                <BarChart3 className="w-4 h-4" />
                Reports
              </Button>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="p-6 space-y-6">
          {/* GST Summary */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <DollarSign className="w-4 h-4" />
                GST Summary
              </h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {gstMetrics.map((metric, i) => (
                <MetricCard key={i} {...metric} />
              ))}
            </div>
          </section>

          {/* PAYG + Quality Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* PAYG Summary */}
            <section className="lg:col-span-2">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <Briefcase className="w-4 h-4" />
                  PAYG Withholding
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {paygMetrics.map((metric, i) => (
                  <MetricCard key={i} {...metric} />
                ))}
              </div>
            </section>

            {/* Quality Score */}
            <section>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Quality
                </h3>
              </div>
              <QualityGauge
                score={sampleClient.qualityScore}
                issues={sampleClient.criticalIssues}
              />
            </section>
          </div>

          {/* AI Insights */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                AI Insights
              </h3>
              <Button variant="link" size="sm" className="text-xs">
                View all
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {insights.map((insight, i) => (
                <motion.div
                  key={insight.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                >
                  <InsightCard insight={insight} />
                </motion.div>
              ))}
            </div>
          </section>

          {/* Quick Access Data Cards */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <Layers className="w-4 h-4" />
                Quick Access
              </h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {[
                { icon: FileText, label: 'Invoices', count: 189, color: 'bg-blue-500' },
                { icon: ArrowLeftRight, label: 'Transactions', count: 58, color: 'bg-emerald-500' },
                { icon: Receipt, label: 'Credit Notes', count: 4, color: 'bg-amber-500' },
                { icon: CreditCard, label: 'Payments', count: 156, color: 'bg-purple-500' },
                { icon: BookOpen, label: 'Journals', count: 23, color: 'bg-status-danger' },
                { icon: Users, label: 'Contacts', count: 112, color: 'bg-muted-foreground' },
              ].map((item, i) => {
                const ItemIcon = item.icon;
                return (
                  <motion.button
                    key={item.label}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: i * 0.05 }}
                    className="flex flex-col items-center gap-2 p-4 bg-white rounded-lg border border-border hover:border-border hover:shadow-sm transition-all group"
                  >
                    <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', item.color)}>
                      <ItemIcon className="w-5 h-5 text-white" />
                    </div>
                    <div className="text-center">
                      <p className="text-xs font-medium text-foreground group-hover:text-foreground">
                        {item.label}
                      </p>
                      <p className="text-sm font-semibold text-foreground tabular-nums">
                        {item.count}
                      </p>
                    </div>
                  </motion.button>
                );
              })}
            </div>
          </section>
        </div>
      </main>

      {/* Command Palette */}
      <CommandPaletteOverlay
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
      />
    </div>
  );
}
