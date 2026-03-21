/**
 * A2UI Component Catalog
 * Registry mapping A2UI component types to React components
 */

import type { ComponentType } from 'react';
import { lazy } from 'react';

import type { A2UIComponentType, A2UIComponentProps } from './types';

// =============================================================================
// Component Type Definition
// =============================================================================

export type A2UIReactComponent<P = A2UIComponentProps> = ComponentType<
  P & {
    id: string;
    dataBinding?: string;
    children?: React.ReactNode;
    onAction?: (action: unknown) => void;
  }
>;

// =============================================================================
// Lazy-loaded Chart Components (heavy dependencies)
// =============================================================================

const LineChart = lazy(() =>
  import('@/components/a2ui/charts/LineChart').then((m) => ({ default: m.LineChart }))
);
const BarChart = lazy(() =>
  import('@/components/a2ui/charts/BarChart').then((m) => ({ default: m.BarChart }))
);
const PieChart = lazy(() =>
  import('@/components/a2ui/charts/PieChart').then((m) => ({ default: m.PieChart }))
);
const ScatterChart = lazy(() =>
  import('@/components/a2ui/charts/ScatterChart').then((m) => ({ default: m.ScatterChart }))
);

// =============================================================================
// Lazy-loaded Data Components
// =============================================================================

const DataTable = lazy(() =>
  import('@/components/a2ui/data/DataTable').then((m) => ({ default: m.DataTable }))
);
const ComparisonTable = lazy(() =>
  import('@/components/a2ui/data/ComparisonTable').then((m) => ({ default: m.ComparisonTable }))
);
const StatCard = lazy(() =>
  import('@/components/a2ui/data/StatCard').then((m) => ({ default: m.StatCard }))
);
const QueryResult = lazy(() =>
  import('@/components/a2ui/data/QueryResult').then((m) => ({ default: m.QueryResult }))
);

// =============================================================================
// Lazy-loaded Layout Components
// =============================================================================

const Card = lazy(() =>
  import('@/components/a2ui/layout/Card').then((m) => ({ default: m.A2UICard }))
);
const Accordion = lazy(() =>
  import('@/components/a2ui/layout/Accordion').then((m) => ({ default: m.A2UIAccordion }))
);
const ExpandableSection = lazy(() =>
  import('@/components/a2ui/layout/ExpandableSection').then((m) => ({
    default: m.A2UIExpandableSection,
  }))
);
const Tabs = lazy(() =>
  import('@/components/a2ui/layout/Tabs').then((m) => ({ default: m.A2UITabs }))
);
const Timeline = lazy(() =>
  import('@/components/a2ui/layout/Timeline').then((m) => ({ default: m.Timeline }))
);

// =============================================================================
// Lazy-loaded Action Components
// =============================================================================

const ActionButton = lazy(() =>
  import('@/components/a2ui/actions/ActionButton').then((m) => ({ default: m.ActionButton }))
);
const ApprovalBar = lazy(() =>
  import('@/components/a2ui/actions/ApprovalBar').then((m) => ({ default: m.ApprovalBar }))
);
const ExportButton = lazy(() =>
  import('@/components/a2ui/actions/ExportButton').then((m) => ({ default: m.ExportButton }))
);

// =============================================================================
// Lazy-loaded Alert Components
// =============================================================================

const AlertCard = lazy(() =>
  import('@/components/a2ui/alerts/AlertCard').then((m) => ({ default: m.AlertCard }))
);
const UrgencyBanner = lazy(() =>
  import('@/components/a2ui/alerts/UrgencyBanner').then((m) => ({ default: m.UrgencyBanner }))
);
const Badge = lazy(() =>
  import('@/components/a2ui/alerts/Badge').then((m) => ({ default: m.A2UIBadge }))
);

// =============================================================================
// Lazy-loaded Form Components
// =============================================================================

const TextInput = lazy(() =>
  import('@/components/a2ui/forms/TextInput').then((m) => ({ default: m.TextInput }))
);
const SelectField = lazy(() =>
  import('@/components/a2ui/forms/SelectField').then((m) => ({ default: m.SelectField }))
);
const Checkbox = lazy(() =>
  import('@/components/a2ui/forms/Checkbox').then((m) => ({ default: m.A2UICheckbox }))
);
const DateRangePicker = lazy(() =>
  import('@/components/a2ui/forms/DateRangePicker').then((m) => ({ default: m.DateRangePicker }))
);
const FilterBar = lazy(() =>
  import('@/components/a2ui/forms/FilterBar').then((m) => ({ default: m.FilterBar }))
);

// =============================================================================
// Lazy-loaded Media Components
// =============================================================================

const CameraCapture = lazy(() =>
  import('@/components/a2ui/media/CameraCapture').then((m) => ({ default: m.CameraCapture }))
);
const FileUpload = lazy(() =>
  import('@/components/a2ui/media/FileUpload').then((m) => ({ default: m.FileUpload }))
);
const Avatar = lazy(() =>
  import('@/components/a2ui/media/Avatar').then((m) => ({ default: m.A2UIAvatar }))
);

// =============================================================================
// Lazy-loaded Feedback Components
// =============================================================================

const ProgressIndicator = lazy(() =>
  import('@/components/a2ui/feedback/Progress').then((m) => ({ default: m.ProgressIndicator }))
);
const Skeleton = lazy(() =>
  import('@/components/a2ui/feedback/Skeleton').then((m) => ({ default: m.A2UISkeleton }))
);
const Tooltip = lazy(() =>
  import('@/components/a2ui/feedback/Tooltip').then((m) => ({ default: m.A2UITooltip }))
);
const Dialog = lazy(() =>
  import('@/components/a2ui/feedback/Dialog').then((m) => ({ default: m.A2UIDialog }))
);

// =============================================================================
// Component Catalog Registry
// =============================================================================

export const componentCatalog: Record<A2UIComponentType, A2UIReactComponent> = {
  // Charts
  lineChart: LineChart as A2UIReactComponent,
  barChart: BarChart as A2UIReactComponent,
  pieChart: PieChart as A2UIReactComponent,
  scatterChart: ScatterChart as A2UIReactComponent,

  // Data Display
  dataTable: DataTable as A2UIReactComponent,
  comparisonTable: ComparisonTable as A2UIReactComponent,
  statCard: StatCard as A2UIReactComponent,
  queryResult: QueryResult as A2UIReactComponent,

  // Layout
  card: Card as A2UIReactComponent,
  accordion: Accordion as A2UIReactComponent,
  expandableSection: ExpandableSection as A2UIReactComponent,
  tabs: Tabs as A2UIReactComponent,
  timeline: Timeline as A2UIReactComponent,

  // Actions
  actionButton: ActionButton as A2UIReactComponent,
  approvalBar: ApprovalBar as A2UIReactComponent,
  exportButton: ExportButton as A2UIReactComponent,

  // Alerts
  alertCard: AlertCard as A2UIReactComponent,
  urgencyBanner: UrgencyBanner as A2UIReactComponent,
  badge: Badge as A2UIReactComponent,

  // Forms
  textInput: TextInput as A2UIReactComponent,
  selectField: SelectField as A2UIReactComponent,
  checkbox: Checkbox as A2UIReactComponent,
  dateRangePicker: DateRangePicker as A2UIReactComponent,
  filterBar: FilterBar as A2UIReactComponent,

  // Media
  cameraCapture: CameraCapture as A2UIReactComponent,
  fileUpload: FileUpload as A2UIReactComponent,
  avatar: Avatar as A2UIReactComponent,

  // Feedback
  progressIndicator: ProgressIndicator as A2UIReactComponent,
  skeleton: Skeleton as A2UIReactComponent,
  tooltip: Tooltip as A2UIReactComponent,
  dialog: Dialog as A2UIReactComponent,
};

// =============================================================================
// Catalog Access Functions
// =============================================================================

/**
 * Get a component from the catalog by type
 */
export function getComponent(type: A2UIComponentType): A2UIReactComponent | null {
  return componentCatalog[type] ?? null;
}

/**
 * Check if a component type exists in the catalog
 */
export function hasComponent(type: string): type is A2UIComponentType {
  return type in componentCatalog;
}

/**
 * Get all available component types
 */
export function getAvailableComponents(): A2UIComponentType[] {
  return Object.keys(componentCatalog) as A2UIComponentType[];
}

/**
 * Get component categories
 */
export function getComponentCategories(): Record<string, A2UIComponentType[]> {
  return {
    charts: ['lineChart', 'barChart', 'pieChart', 'scatterChart'],
    data: ['dataTable', 'comparisonTable', 'statCard', 'queryResult'],
    layout: ['card', 'accordion', 'expandableSection', 'tabs', 'timeline'],
    actions: ['actionButton', 'approvalBar', 'exportButton'],
    alerts: ['alertCard', 'urgencyBanner', 'badge'],
    forms: ['textInput', 'selectField', 'checkbox', 'dateRangePicker', 'filterBar'],
    media: ['cameraCapture', 'fileUpload', 'avatar'],
    feedback: ['progressIndicator', 'skeleton', 'tooltip', 'dialog'],
  };
}
