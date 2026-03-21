'use client';

/**
 * A2UI Tabs Component
 * Tabbed content navigation
 */

import {
  Tabs as ShadcnTabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';

// =============================================================================
// Types
// =============================================================================

interface TabConfig {
  id: string;
  label: string;
  icon?: string;
  badge?: string | number;
  content?: React.ReactNode;
}

interface A2UITabsProps {
  id: string;
  tabs?: TabConfig[];
  defaultTab?: string;
  dataBinding?: string;
  children?: React.ReactNode;
}

// =============================================================================
// Component
// =============================================================================

export function A2UITabs({
  id,
  tabs,
  defaultTab,
  children,
}: A2UITabsProps) {
  // If no tabs but children provided, just render children
  if (!tabs || tabs.length === 0) {
    if (children) {
      return <div id={id}>{children}</div>;
    }
    return null;
  }

  const firstTab = tabs[0];
  const defaultValue = defaultTab || firstTab?.id || tabs[0]?.id || '';

  return (
    <ShadcnTabs id={id} defaultValue={defaultValue} className="w-full">
      <TabsList className="w-full justify-start">
        {tabs.map((tab) => (
          <TabsTrigger key={tab.id} value={tab.id} className="gap-2">
            {tab.icon && <span className="text-muted-foreground">{tab.icon}</span>}
            {tab.label}
            {tab.badge !== undefined && (
              <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                {tab.badge}
              </span>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((tab) => (
        <TabsContent key={tab.id} value={tab.id} className="mt-4">
          {/* Tab content would be rendered by parent A2UIRenderer */}
          {tab.content && (
            <div className="space-y-4">
              {/* Placeholder for nested A2UI components */}
            </div>
          )}
        </TabsContent>
      ))}
    </ShadcnTabs>
  );
}
