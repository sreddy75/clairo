/**
 * A2UI Type Definitions
 * Agent-to-User Interface protocol types for Clairo
 */

// =============================================================================
// Core Message Types
// =============================================================================

export interface A2UIMessage {
  /** UI component tree to render */
  surfaceUpdate: SurfaceUpdate;
  /** Data bindings for components */
  dataModelUpdate?: DataModelUpdate;
  /** Rendering control */
  renderControl?: RenderControl;
  /** Message metadata */
  meta: A2UIMeta;
}

export interface SurfaceUpdate {
  /** List of components to render */
  components: A2UIComponent[];
  /** Optional layout hints */
  layout?: LayoutHint;
}

export type LayoutHint = 'stack' | 'grid' | 'flow' | 'sidebar';

export type DataModelUpdate = Record<string, unknown>;

export interface RenderControl {
  /** Whether this is a streaming message */
  streaming?: boolean;
  /** Component IDs to replace (for updates) */
  replace?: string[];
  /** Component IDs to append to */
  appendTo?: string;
  /** Signal that streaming is complete */
  complete?: boolean;
}

export interface A2UIMeta {
  /** Unique message ID */
  messageId: string;
  /** Timestamp of generation */
  generatedAt: string;
  /** Device context used for generation */
  deviceContext: DeviceContext;
  /** Source agent ID */
  agentId?: string;
  /** Fallback text if rendering fails */
  fallbackText?: string;
}

export interface DeviceContext {
  isMobile: boolean;
  isTablet: boolean;
  platform?: 'ios' | 'android' | 'windows' | 'macos' | 'linux';
  browser?: string;
}

// =============================================================================
// Component Types
// =============================================================================

export type A2UIComponentType =
  // Charts
  | 'lineChart'
  | 'barChart'
  | 'pieChart'
  | 'scatterChart'
  // Data Display
  | 'dataTable'
  | 'comparisonTable'
  | 'statCard'
  | 'queryResult'
  // Layout
  | 'card'
  | 'accordion'
  | 'expandableSection'
  | 'tabs'
  | 'timeline'
  // Actions
  | 'actionButton'
  | 'approvalBar'
  | 'exportButton'
  // Alerts
  | 'alertCard'
  | 'urgencyBanner'
  | 'badge'
  // Forms
  | 'textInput'
  | 'selectField'
  | 'checkbox'
  | 'dateRangePicker'
  | 'filterBar'
  // Media
  | 'cameraCapture'
  | 'fileUpload'
  | 'avatar'
  // Feedback
  | 'progressIndicator'
  | 'skeleton'
  | 'tooltip'
  | 'dialog';

export interface A2UIComponentBase {
  /** Unique identifier for this component instance */
  id: string;
  /** Component type from catalog */
  type: A2UIComponentType;
  /** Optional data binding key */
  dataBinding?: string;
  /** Nested components (for containers) */
  children?: A2UIComponent[];
  /** Component-specific props */
  props?: Record<string, unknown>;
  /** Conditional rendering */
  condition?: ComponentCondition;
}

export interface ComponentCondition {
  /** Data binding key to check */
  field: string;
  /** Comparison operator */
  operator: 'eq' | 'neq' | 'gt' | 'lt' | 'gte' | 'lte' | 'exists' | 'empty';
  /** Value to compare against */
  value?: unknown;
}

// =============================================================================
// Component Props Types
// =============================================================================

// Charts
export interface LineChartProps {
  title?: string;
  xAxis?: AxisConfig;
  yAxis?: AxisConfig;
  series?: SeriesConfig[];
  interactive?: boolean;
}

export interface BarChartProps {
  title?: string;
  orientation?: 'horizontal' | 'vertical';
  stacked?: boolean;
}

export interface PieChartProps {
  title?: string;
  donut?: boolean;
  showLegend?: boolean;
}

export interface ScatterChartProps {
  title?: string;
  xAxis?: AxisConfig;
  yAxis?: AxisConfig;
}

export interface AxisConfig {
  label?: string;
  dataKey?: string;
  format?: 'number' | 'currency' | 'percent' | 'date';
}

export interface SeriesConfig {
  dataKey: string;
  name?: string;
  color?: string;
}

// Data Display
export interface DataTableProps {
  columns: TableColumn[];
  sortable?: boolean;
  pagination?: boolean;
  pageSize?: number;
}

export interface TableColumn {
  key: string;
  header: string;
  format?: 'text' | 'number' | 'currency' | 'date' | 'badge';
  sortable?: boolean;
  width?: string;
}

export interface StatCardProps {
  label: string;
  value: string | number;
  change?: StatChange;
  icon?: string;
}

export interface StatChange {
  value: number;
  direction: 'up' | 'down' | 'neutral';
  label?: string;
}

export interface ComparisonTableProps {
  leftLabel: string;
  rightLabel: string;
  rows: ComparisonRow[];
}

export interface ComparisonRow {
  label: string;
  leftValue: string | number;
  rightValue: string | number;
  highlight?: 'left' | 'right' | 'none';
}

// Alerts
export interface AlertCardProps {
  severity: 'info' | 'warning' | 'error' | 'success';
  title: string;
  description?: string;
  actions?: ActionConfig[];
}

export interface UrgencyBannerProps {
  deadline: string;
  message: string;
  variant?: 'warning' | 'critical';
}

export interface BadgeProps {
  label: string;
  variant?: 'default' | 'secondary' | 'destructive' | 'outline';
}

// Actions
export interface ActionButtonProps {
  label: string;
  action: ActionConfig;
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  icon?: string;
  disabled?: boolean;
}

export interface ApprovalBarProps {
  options: ApprovalOption[];
  resourceId: string;
}

export interface ApprovalOption {
  label: string;
  action: 'approve' | 'reject' | 'query';
  variant?: 'primary' | 'secondary' | 'danger';
}

export interface ExportButtonProps {
  formats: ('csv' | 'pdf' | 'xlsx')[];
  dataBinding: string;
}

export interface ActionConfig {
  type: 'navigate' | 'createTask' | 'approve' | 'export' | 'custom';
  target?: string;
  payload?: Record<string, unknown>;
}

// Forms
export interface TextInputProps {
  label: string;
  placeholder?: string;
  dataBinding: string;
  required?: boolean;
  validation?: ValidationRule[];
}

export interface SelectFieldProps {
  label: string;
  options: SelectOption[];
  dataBinding: string;
  multiple?: boolean;
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface DateRangePickerProps {
  label: string;
  dataBinding: string;
  defaultStart?: string;
  defaultEnd?: string;
}

export interface FilterBarProps {
  filters: FilterConfig[];
}

export interface FilterConfig {
  field: string;
  label: string;
  type: 'select' | 'text' | 'date' | 'range';
  options?: SelectOption[];
}

export interface ValidationRule {
  type: 'required' | 'minLength' | 'maxLength' | 'pattern' | 'custom';
  value?: string | number;
  message: string;
}

// Media
export interface CameraCaptureProps {
  mode: 'photo' | 'document';
  multiPage?: boolean;
  hint?: string;
  onCapture: ActionConfig;
}

export interface FileUploadProps {
  accept?: string[];
  maxSize?: number;
  multiple?: boolean;
  onUpload: ActionConfig;
}

export interface AvatarProps {
  src?: string;
  fallback: string;
  size?: 'sm' | 'md' | 'lg';
}

// Layout
export interface CardProps {
  title?: string;
  description?: string;
  footer?: A2UIComponent[];
}

export interface AccordionProps {
  items: AccordionItem[];
  defaultOpen?: string[];
}

export interface AccordionItem {
  id: string;
  title: string;
  content: A2UIComponent[];
}

export interface TabsProps {
  items: TabItem[];
  defaultTab?: string;
}

export interface TabItem {
  id: string;
  label: string;
  content: A2UIComponent[];
}

export interface TimelineProps {
  items: TimelineItem[];
}

export interface TimelineItem {
  id: string;
  title: string;
  description?: string;
  timestamp: string;
  status?: 'completed' | 'current' | 'upcoming';
}

export interface ExpandableSectionProps {
  title: string;
  description?: string;
  defaultExpanded?: boolean;
  icon?: string;
}

// Feedback
export interface ProgressProps {
  value: number;
  max?: number;
  label?: string;
  showPercent?: boolean;
}

export interface SkeletonProps {
  variant: 'text' | 'card' | 'chart' | 'table';
  rows?: number;
}

export interface TooltipProps {
  content: string;
  trigger: A2UIComponent;
}

export interface DialogProps {
  title: string;
  description?: string;
  trigger: A2UIComponent;
  content: A2UIComponent[];
  actions?: ActionButtonProps[];
}

// Union type for all component props
export type A2UIComponentProps =
  | LineChartProps
  | BarChartProps
  | PieChartProps
  | ScatterChartProps
  | DataTableProps
  | StatCardProps
  | ComparisonTableProps
  | AlertCardProps
  | UrgencyBannerProps
  | BadgeProps
  | ActionButtonProps
  | ApprovalBarProps
  | ExportButtonProps
  | TextInputProps
  | SelectFieldProps
  | DateRangePickerProps
  | FilterBarProps
  | CameraCaptureProps
  | FileUploadProps
  | AvatarProps
  | CardProps
  | AccordionProps
  | ExpandableSectionProps
  | TabsProps
  | TimelineProps
  | ProgressProps
  | SkeletonProps
  | TooltipProps
  | DialogProps;

// Full component type
export type A2UIComponent = A2UIComponentBase & {
  props?: A2UIComponentProps;
};

// =============================================================================
// Action Handler Types
// =============================================================================

export type ActionHandler = (action: ActionConfig) => void | Promise<void>;

export interface A2UIActionHandlers {
  navigate?: (target: string) => void;
  createTask?: (payload: Record<string, unknown>) => Promise<void>;
  approve?: (resourceId: string) => Promise<void>;
  export?: (format: string, dataBinding: string) => Promise<void>;
  custom?: (payload: Record<string, unknown>) => Promise<void>;
}
