# Data Model: A2UI Agent-Driven Interfaces

**Feature**: 033-a2ui-agent-driven-interfaces
**Date**: 2026-01-02

---

## Overview

A2UI is a **presentation-only** feature. There are no database tables or persistent entities. This document defines the A2UI message schema types used for communication between backend agents and frontend renderer.

## Core A2UI Message Schema

### A2UIMessage (Root)

The complete A2UI response from backend to frontend.

```typescript
interface A2UIMessage {
  /** UI component tree to render */
  surfaceUpdate: SurfaceUpdate;

  /** Data bindings for components */
  dataModelUpdate?: DataModelUpdate;

  /** Rendering control */
  renderControl?: RenderControl;

  /** Message metadata */
  meta: A2UIMeta;
}
```

### SurfaceUpdate

Describes the UI structure to render.

```typescript
interface SurfaceUpdate {
  /** List of components to render */
  components: A2UIComponent[];

  /** Optional layout hints */
  layout?: LayoutHint;
}

type LayoutHint = 'stack' | 'grid' | 'flow' | 'sidebar';
```

### A2UIComponent (Base)

Every component shares these base properties.

```typescript
interface A2UIComponentBase {
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

type A2UIComponent = A2UIComponentBase & ComponentProps;
```

### Component Types

```typescript
type A2UIComponentType =
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
```

---

## Component-Specific Props

### Charts

```typescript
interface LineChartProps {
  type: 'lineChart';
  title?: string;
  xAxis?: AxisConfig;
  yAxis?: AxisConfig;
  series?: SeriesConfig[];
  interactive?: boolean;
}

interface BarChartProps {
  type: 'barChart';
  title?: string;
  orientation?: 'horizontal' | 'vertical';
  stacked?: boolean;
}

interface PieChartProps {
  type: 'pieChart';
  title?: string;
  donut?: boolean;
  showLegend?: boolean;
}

interface AxisConfig {
  label?: string;
  dataKey?: string;
  format?: 'number' | 'currency' | 'percent' | 'date';
}

interface SeriesConfig {
  dataKey: string;
  name?: string;
  color?: string;
}
```

### Data Display

```typescript
interface DataTableProps {
  type: 'dataTable';
  columns: TableColumn[];
  sortable?: boolean;
  pagination?: boolean;
  pageSize?: number;
}

interface TableColumn {
  key: string;
  header: string;
  format?: 'text' | 'number' | 'currency' | 'date' | 'badge';
  sortable?: boolean;
  width?: string;
}

interface StatCardProps {
  type: 'statCard';
  label: string;
  value: string | number;
  change?: StatChange;
  icon?: string;
}

interface StatChange {
  value: number;
  direction: 'up' | 'down' | 'neutral';
  label?: string;
}

interface ComparisonTableProps {
  type: 'comparisonTable';
  leftLabel: string;
  rightLabel: string;
  rows: ComparisonRow[];
}

interface ComparisonRow {
  label: string;
  leftValue: string | number;
  rightValue: string | number;
  highlight?: 'left' | 'right' | 'none';
}
```

### Alerts

```typescript
interface AlertCardProps {
  type: 'alertCard';
  severity: 'info' | 'warning' | 'error' | 'success';
  title: string;
  description?: string;
  actions?: ActionConfig[];
}

interface UrgencyBannerProps {
  type: 'urgencyBanner';
  deadline: string; // ISO date
  message: string;
  variant?: 'warning' | 'critical';
}

interface BadgeProps {
  type: 'badge';
  label: string;
  variant?: 'default' | 'secondary' | 'destructive' | 'outline';
}
```

### Actions

```typescript
interface ActionButtonProps {
  type: 'actionButton';
  label: string;
  action: ActionConfig;
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  icon?: string;
  disabled?: boolean;
}

interface ApprovalBarProps {
  type: 'approvalBar';
  options: ApprovalOption[];
  resourceId: string;
}

interface ApprovalOption {
  label: string;
  action: 'approve' | 'reject' | 'query';
  variant?: 'primary' | 'secondary' | 'danger';
}

interface ExportButtonProps {
  type: 'exportButton';
  formats: ('csv' | 'pdf' | 'xlsx')[];
  dataBinding: string;
}

interface ActionConfig {
  type: 'navigate' | 'createTask' | 'approve' | 'export' | 'custom';
  target?: string;
  payload?: Record<string, unknown>;
}
```

### Forms

```typescript
interface TextInputProps {
  type: 'textInput';
  label: string;
  placeholder?: string;
  dataBinding: string;
  required?: boolean;
  validation?: ValidationRule[];
}

interface SelectFieldProps {
  type: 'selectField';
  label: string;
  options: SelectOption[];
  dataBinding: string;
  multiple?: boolean;
}

interface SelectOption {
  value: string;
  label: string;
}

interface DateRangePickerProps {
  type: 'dateRangePicker';
  label: string;
  dataBinding: string;
  defaultStart?: string;
  defaultEnd?: string;
}

interface FilterBarProps {
  type: 'filterBar';
  filters: FilterConfig[];
}

interface FilterConfig {
  field: string;
  label: string;
  type: 'select' | 'text' | 'date' | 'range';
  options?: SelectOption[];
}
```

### Media

```typescript
interface CameraCaptureProps {
  type: 'cameraCapture';
  mode: 'photo' | 'document';
  multiPage?: boolean;
  hint?: string;
  onCapture: ActionConfig;
}

interface FileUploadProps {
  type: 'fileUpload';
  accept?: string[];
  maxSize?: number;
  multiple?: boolean;
  onUpload: ActionConfig;
}

interface AvatarProps {
  type: 'avatar';
  src?: string;
  fallback: string;
  size?: 'sm' | 'md' | 'lg';
}
```

### Layout

```typescript
interface CardProps {
  type: 'card';
  title?: string;
  description?: string;
  footer?: A2UIComponent[];
}

interface AccordionProps {
  type: 'accordion';
  items: AccordionItem[];
  defaultOpen?: string[];
}

interface AccordionItem {
  id: string;
  title: string;
  content: A2UIComponent[];
}

interface TabsProps {
  type: 'tabs';
  items: TabItem[];
  defaultTab?: string;
}

interface TabItem {
  id: string;
  label: string;
  content: A2UIComponent[];
}

interface TimelineProps {
  type: 'timeline';
  items: TimelineItem[];
}

interface TimelineItem {
  id: string;
  title: string;
  description?: string;
  timestamp: string;
  status?: 'completed' | 'current' | 'upcoming';
}
```

### Feedback

```typescript
interface ProgressProps {
  type: 'progressIndicator';
  value: number;
  max?: number;
  label?: string;
  showPercent?: boolean;
}

interface SkeletonProps {
  type: 'skeleton';
  variant: 'text' | 'card' | 'chart' | 'table';
  rows?: number;
}

interface TooltipProps {
  type: 'tooltip';
  content: string;
  trigger: A2UIComponent;
}

interface DialogProps {
  type: 'dialog';
  title: string;
  description?: string;
  trigger: A2UIComponent;
  content: A2UIComponent[];
  actions?: ActionButtonProps[];
}
```

---

## Data Model Update

```typescript
interface DataModelUpdate {
  /** Key-value pairs of data for component bindings */
  [key: string]: unknown;
}

// Example:
const dataModelUpdate: DataModelUpdate = {
  cashFlowTrend: [
    { date: '2025-10', value: 45000 },
    { date: '2025-11', value: 42000 },
    { date: '2025-12', value: 38000 },
  ],
  clientList: [
    { id: '1', name: 'Smith Co', status: 'urgent' },
    { id: '2', name: 'Jones Ltd', status: 'on_track' },
  ],
};
```

---

## Render Control

```typescript
interface RenderControl {
  /** Whether this is a streaming message */
  streaming?: boolean;

  /** Component IDs to replace (for updates) */
  replace?: string[];

  /** Component IDs to append to */
  appendTo?: string;

  /** Signal that streaming is complete */
  complete?: boolean;
}
```

---

## Message Metadata

```typescript
interface A2UIMeta {
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

interface DeviceContext {
  isMobile: boolean;
  isTablet: boolean;
  platform?: 'ios' | 'android' | 'windows' | 'macos' | 'linux';
  browser?: string;
}
```

---

## Validation Rules

```typescript
interface ValidationRule {
  type: 'required' | 'minLength' | 'maxLength' | 'pattern' | 'custom';
  value?: string | number;
  message: string;
}
```

---

## Component Condition

```typescript
interface ComponentCondition {
  /** Data binding key to check */
  field: string;

  /** Comparison operator */
  operator: 'eq' | 'neq' | 'gt' | 'lt' | 'gte' | 'lte' | 'exists' | 'empty';

  /** Value to compare against */
  value?: unknown;
}
```

---

## Python/Pydantic Equivalents

The backend will define matching Pydantic models:

```python
# backend/app/core/a2ui/schemas.py

from pydantic import BaseModel
from typing import Literal, Any

class A2UIComponent(BaseModel):
    id: str
    type: str
    data_binding: str | None = None
    children: list["A2UIComponent"] | None = None
    props: dict[str, Any] | None = None

class SurfaceUpdate(BaseModel):
    components: list[A2UIComponent]
    layout: Literal["stack", "grid", "flow", "sidebar"] | None = None

class DataModelUpdate(BaseModel):
    __root__: dict[str, Any]

class DeviceContext(BaseModel):
    is_mobile: bool
    is_tablet: bool
    platform: str | None = None
    browser: str | None = None

class A2UIMeta(BaseModel):
    message_id: str
    generated_at: str
    device_context: DeviceContext
    agent_id: str | None = None
    fallback_text: str | None = None

class A2UIMessage(BaseModel):
    surface_update: SurfaceUpdate
    data_model_update: dict[str, Any] | None = None
    render_control: dict[str, Any] | None = None
    meta: A2UIMeta
```

---

## Notes

- **No database tables**: A2UI is entirely runtime/presentation
- **Schema versioning**: Include version in meta if needed for backwards compatibility
- **Type safety**: Both TypeScript and Pydantic enforce schema validation
- **Extensibility**: New component types can be added by extending the type union
