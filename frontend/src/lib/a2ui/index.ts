/**
 * A2UI Module Public API
 * Agent-to-User Interface for Clairo
 */

// =============================================================================
// Types
// =============================================================================

export type {
  // Core Message Types
  A2UIMessage,
  SurfaceUpdate,
  DataModelUpdate,
  RenderControl,
  A2UIMeta,
  DeviceContext,
  LayoutHint,

  // Component Types
  A2UIComponentType,
  A2UIComponentBase,
  A2UIComponent,
  A2UIComponentProps,
  ComponentCondition,

  // Chart Props
  LineChartProps,
  BarChartProps,
  PieChartProps,
  ScatterChartProps,
  AxisConfig,
  SeriesConfig,

  // Data Display Props
  DataTableProps,
  TableColumn,
  StatCardProps,
  StatChange,
  ComparisonTableProps,
  ComparisonRow,

  // Alert Props
  AlertCardProps,
  UrgencyBannerProps,
  BadgeProps,

  // Action Props
  ActionButtonProps,
  ApprovalBarProps,
  ApprovalOption,
  ExportButtonProps,
  ActionConfig,

  // Form Props
  TextInputProps,
  SelectFieldProps,
  SelectOption,
  DateRangePickerProps,
  FilterBarProps,
  FilterConfig,
  ValidationRule,

  // Media Props
  CameraCaptureProps,
  FileUploadProps,
  AvatarProps,

  // Layout Props
  CardProps,
  AccordionProps,
  AccordionItem,
  ExpandableSectionProps,
  TabsProps,
  TabItem,
  TimelineProps,
  TimelineItem,

  // Feedback Props
  ProgressProps,
  SkeletonProps,
  TooltipProps,
  DialogProps,

  // Action Handler Types
  ActionHandler,
  A2UIActionHandlers,
} from './types';

// =============================================================================
// Catalog
// =============================================================================

export {
  componentCatalog,
  getComponent,
  hasComponent,
  getAvailableComponents,
  getComponentCategories,
  type A2UIReactComponent,
} from './catalog';

// =============================================================================
// Context
// =============================================================================

export {
  A2UIDataProvider,
  useA2UIContext,
  useA2UIData,
  useA2UIDataSetter,
  useA2UIAction,
} from './context';

// =============================================================================
// Renderer
// =============================================================================

export {
  A2UIRenderer,
  A2UIStreamingRenderer,
  type A2UIRendererProps,
  type A2UIStreamingRendererProps,
  type A2UIRenderMetrics,
  type A2UIActionMetrics,
  type OnRenderComplete,
  type OnActionTriggered,
} from './renderer';

// =============================================================================
// Fallback Components
// =============================================================================

export {
  A2UIFallback,
  A2UIUnknownComponent,
  A2UIErrorFallback,
  A2UILoadingFallback,
  A2UIEmptyFallback,
  A2UIErrorBoundaryFallback,
} from './fallback';

// =============================================================================
// Streaming
// =============================================================================

export {
  A2UIStreamParser,
  fetchA2UIStream,
  createA2UIEventSource,
  type StreamingState,
  type StreamingOptions,
} from './streaming';
