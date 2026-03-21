'use client';

/**
 * ClientNavigation - Grouped Tab Navigation
 *
 * Consolidates 15+ tabs into organized groups:
 * - Primary tabs: Dashboard, BAS Prep, Quality, Insights, Contacts
 * - Dropdown groups: Financial Data, Payroll, Assets
 */

import {
  BarChart3,
  BookOpen,
  Briefcase,
  ChevronDown,
  CreditCard,
  DollarSign,
  FileText,
  Lightbulb,
  Minus,
  TrendingUp,
  Users,
  Wallet,
  ArrowLeftRight,
} from 'lucide-react';
import React, { useState, useRef, useEffect } from 'react';

// =============================================================================
// Types
// =============================================================================

export type Tab =
  | 'overview'
  | 'bas'
  | 'quality'
  | 'insights'
  | 'contacts'
  | 'invoices'
  | 'transactions'
  | 'credit-notes'
  | 'payments'
  | 'journals'
  | 'employees'
  | 'pay-runs';

interface TabItem {
  id: Tab;
  label: string;
  icon: React.ElementType;
  count?: number | null;
  badge?: 'warning' | 'error';
}

interface DropdownGroup {
  id: string;
  label: string;
  icon: React.ElementType;
  items: TabItem[];
}

interface ClientNavigationProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  counts: {
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
  };
  hasPayroll?: boolean;
}

// =============================================================================
// Component
// =============================================================================

export function ClientNavigation({
  activeTab,
  onTabChange,
  counts,
  hasPayroll = false,
}: ClientNavigationProps) {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpenDropdown(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Primary tabs - always visible
  const primaryTabs: TabItem[] = [
    { id: 'overview', label: 'Dashboard', icon: BarChart3 },
    { id: 'bas', label: 'BAS Prep', icon: FileText },
    {
      id: 'quality',
      label: 'Quality',
      icon: TrendingUp,
      count: counts.criticalIssues,
      badge: counts.criticalIssues && counts.criticalIssues > 0 ? 'error' : undefined,
    },
    {
      id: 'insights',
      label: 'AI Insights',
      icon: Lightbulb,
      count: counts.insights,
    },
    { id: 'contacts', label: 'Contacts', icon: Users, count: counts.contacts },
  ];

  // Grouped tabs in dropdowns
  const dropdownGroups: DropdownGroup[] = [
    {
      id: 'financials',
      label: 'Financial Data',
      icon: DollarSign,
      items: [
        { id: 'invoices', label: 'Invoices', icon: FileText, count: counts.invoices },
        { id: 'transactions', label: 'Bank Transactions', icon: ArrowLeftRight, count: counts.transactions },
        { id: 'credit-notes', label: 'Credit Notes', icon: Minus, count: counts.creditNotes },
        { id: 'payments', label: 'Payments', icon: CreditCard, count: counts.payments },
        { id: 'journals', label: 'Journals', icon: BookOpen, count: counts.journals },
      ],
    },
    ...(hasPayroll
      ? [
          {
            id: 'payroll',
            label: 'Payroll',
            icon: Briefcase,
            items: [
              { id: 'employees' as Tab, label: 'Employees', icon: Users, count: counts.employees },
              { id: 'pay-runs' as Tab, label: 'Pay Runs', icon: Wallet, count: counts.payRuns },
            ],
          },
        ]
      : []),
  ];

  return (
    <div className="border-b border-border" ref={dropdownRef}>
      <nav className="flex items-center gap-1">
        {/* Primary Tabs */}
        {primaryTabs.map((tab) => (
          <TabButton
            key={tab.id}
            tab={tab}
            isActive={activeTab === tab.id}
            onClick={() => onTabChange(tab.id)}
          />
        ))}

        {/* Divider */}
        <div className="w-px h-6 bg-border mx-2" />

        {/* Dropdown Groups */}
        {dropdownGroups.map((group) => {
          const isGroupActive = group.items.some((item) => item.id === activeTab);
          const activeItem = group.items.find((item) => item.id === activeTab);
          const totalCount = group.items.reduce((sum, item) => sum + (item.count || 0), 0);

          return (
            <div key={group.id} className="relative">
              <button
                onClick={() => setOpenDropdown(openDropdown === group.id ? null : group.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-sm font-medium ${
                  isGroupActive
                    ? 'bg-primary/10 text-primary border border-primary/20'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <group.icon className="w-4 h-4" />
                <span>{isGroupActive && activeItem ? activeItem.label : group.label}</span>
                {totalCount > 0 && !isGroupActive && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
                    {totalCount}
                  </span>
                )}
                <ChevronDown
                  className={`w-3 h-3 transition-transform ${
                    openDropdown === group.id ? 'rotate-180' : ''
                  }`}
                />
              </button>

              {/* Dropdown Menu */}
              {openDropdown === group.id && (
                <div className="absolute top-full left-0 mt-1 w-56 bg-card rounded-lg shadow-lg border border-border py-1 z-50">
                  {group.items.map((item) => {
                    const ItemIcon = item.icon;
                    return (
                      <button
                        key={item.id}
                        onClick={() => {
                          onTabChange(item.id);
                          setOpenDropdown(null);
                        }}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                          activeTab === item.id
                            ? 'bg-primary/10 text-primary'
                            : 'text-foreground hover:bg-muted'
                        }`}
                      >
                        <ItemIcon className="w-4 h-4 flex-shrink-0" />
                        <span className="flex-1 text-left">{item.label}</span>
                        {item.count !== undefined && item.count !== null && item.count > 0 && (
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              activeTab === item.id
                                ? 'bg-primary/10 text-primary'
                                : 'bg-muted text-muted-foreground'
                            }`}
                          >
                            {item.count}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </div>
  );
}

// =============================================================================
// TabButton Component
// =============================================================================

function TabButton({
  tab,
  isActive,
  onClick,
}: {
  tab: TabItem;
  isActive: boolean;
  onClick: () => void;
}) {
  const Icon = tab.icon;

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-sm font-medium ${
        isActive
          ? 'bg-primary/10 text-primary border border-primary/20'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      }`}
    >
      <Icon className="w-4 h-4" />
      <span>{tab.label}</span>
      {tab.count !== undefined && tab.count !== null && tab.count > 0 && (
        <span
          className={`text-xs px-1.5 py-0.5 rounded-full ${
            tab.badge === 'error'
              ? 'bg-status-danger/10 text-status-danger'
              : tab.badge === 'warning'
              ? 'bg-status-warning/10 text-status-warning'
              : isActive
              ? 'bg-primary/10 text-primary'
              : 'bg-muted text-muted-foreground'
          }`}
        >
          {tab.count}
        </span>
      )}
    </button>
  );
}
