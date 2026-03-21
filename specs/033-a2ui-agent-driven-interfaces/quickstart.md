# Quickstart: A2UI Agent-Driven Interfaces

**Feature**: 033-a2ui-agent-driven-interfaces
**Time to First Test**: ~3 hours

---

## Prerequisites

- Spec 015+ (AI Agents) implemented
- Spec 032 (PWA/Mobile) implemented (for camera components)
- Docker Compose running (backend + frontend)
- Node.js 18+ and Python 3.12+

---

## Quick Start Steps

### 1. Install Dependencies

No new dependencies required - A2UI uses existing stack:
- React 18, shadcn/ui, Recharts (frontend)
- FastAPI, Pydantic (backend)

### 2. Create A2UI Core Module

```typescript
// frontend/src/lib/a2ui/types.ts
export interface A2UIMessage {
  surfaceUpdate: SurfaceUpdate;
  dataModelUpdate?: Record<string, unknown>;
  renderControl?: RenderControl;
  meta: A2UIMeta;
}

export interface SurfaceUpdate {
  components: A2UIComponent[];
  layout?: 'stack' | 'grid' | 'flow' | 'sidebar';
}

export interface A2UIComponent {
  id: string;
  type: string;
  dataBinding?: string;
  children?: A2UIComponent[];
  props?: Record<string, unknown>;
}

export interface A2UIMeta {
  messageId: string;
  generatedAt: string;
  deviceContext: DeviceContext;
  fallbackText?: string;
}

export interface DeviceContext {
  isMobile: boolean;
  isTablet: boolean;
  platform?: string;
  browser?: string;
}
```

### 3. Create Component Catalog

```typescript
// frontend/src/lib/a2ui/catalog.ts
import { lazy, ComponentType } from 'react';
import { Alert } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Accordion } from '@/components/ui/accordion';

// Lazy load heavy components
const LineChart = lazy(() => import('@/components/a2ui/charts/LineChart'));
const BarChart = lazy(() => import('@/components/a2ui/charts/BarChart'));
const DataTable = lazy(() => import('@/components/a2ui/data/DataTable'));

export const componentCatalog: Record<string, ComponentType<any>> = {
  // Charts (lazy loaded)
  lineChart: LineChart,
  barChart: BarChart,

  // Alerts (direct shadcn)
  alertCard: Alert,
  badge: Badge,

  // Layout (direct shadcn)
  card: Card,
  accordion: Accordion,

  // Actions
  actionButton: Button,
};

export function getComponent(type: string): ComponentType<any> | null {
  return componentCatalog[type] ?? null;
}
```

### 4. Create A2UI Renderer

```typescript
// frontend/src/lib/a2ui/renderer.tsx
'use client';

import { Suspense } from 'react';
import { A2UIComponent, A2UIMessage } from './types';
import { getComponent } from './catalog';
import { A2UIDataProvider } from './context';
import { Skeleton } from '@/components/ui/skeleton';

interface A2UIRendererProps {
  message: A2UIMessage;
  onAction?: (action: any) => void;
}

export function A2UIRenderer({ message, onAction }: A2UIRendererProps) {
  const { surfaceUpdate, dataModelUpdate, meta } = message;

  return (
    <A2UIDataProvider data={dataModelUpdate ?? {}}>
      <div className={getLayoutClass(surfaceUpdate.layout)}>
        {surfaceUpdate.components.map((component) => (
          <A2UIComponentRenderer
            key={component.id}
            component={component}
            onAction={onAction}
          />
        ))}
      </div>
    </A2UIDataProvider>
  );
}

function A2UIComponentRenderer({
  component,
  onAction,
}: {
  component: A2UIComponent;
  onAction?: (action: any) => void;
}) {
  const Component = getComponent(component.type);

  if (!Component) {
    return <UnknownComponent type={component.type} props={component.props} />;
  }

  return (
    <Suspense fallback={<Skeleton className="h-32 w-full" />}>
      <Component
        {...component.props}
        dataBinding={component.dataBinding}
        onAction={onAction}
      >
        {component.children?.map((child) => (
          <A2UIComponentRenderer
            key={child.id}
            component={child}
            onAction={onAction}
          />
        ))}
      </Component>
    </Suspense>
  );
}

function UnknownComponent({ type, props }: { type: string; props?: any }) {
  return (
    <div className="p-4 border border-yellow-500 rounded bg-yellow-50">
      <p className="font-mono text-sm">Unknown component: {type}</p>
      <pre className="text-xs mt-2">{JSON.stringify(props, null, 2)}</pre>
    </div>
  );
}

function getLayoutClass(layout?: string): string {
  switch (layout) {
    case 'grid':
      return 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4';
    case 'flow':
      return 'flex flex-wrap gap-4';
    case 'sidebar':
      return 'grid grid-cols-1 md:grid-cols-[300px_1fr] gap-4';
    default:
      return 'flex flex-col gap-4';
  }
}
```

### 5. Create Data Context

```typescript
// frontend/src/lib/a2ui/context.tsx
'use client';

import { createContext, useContext, ReactNode } from 'react';

const A2UIDataContext = createContext<Record<string, unknown>>({});

export function A2UIDataProvider({
  data,
  children,
}: {
  data: Record<string, unknown>;
  children: ReactNode;
}) {
  return (
    <A2UIDataContext.Provider value={data}>
      {children}
    </A2UIDataContext.Provider>
  );
}

export function useA2UIData<T>(binding: string | undefined): T | undefined {
  const data = useContext(A2UIDataContext);
  return binding ? (data[binding] as T) : undefined;
}
```

### 6. Create Backend A2UI Schemas

```python
# backend/app/core/a2ui/schemas.py
from pydantic import BaseModel, Field
from typing import Any
from uuid import UUID
from datetime import datetime

class DeviceContext(BaseModel):
    is_mobile: bool
    is_tablet: bool
    platform: str | None = None
    browser: str | None = None

class A2UIComponent(BaseModel):
    id: str
    type: str
    data_binding: str | None = None
    children: list["A2UIComponent"] | None = None
    props: dict[str, Any] | None = None

class SurfaceUpdate(BaseModel):
    components: list[A2UIComponent]
    layout: str | None = None

class A2UIMeta(BaseModel):
    message_id: str = Field(default_factory=lambda: str(UUID()))
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    device_context: DeviceContext
    agent_id: str | None = None
    fallback_text: str | None = None

class A2UIMessage(BaseModel):
    surface_update: SurfaceUpdate
    data_model_update: dict[str, Any] | None = None
    render_control: dict[str, Any] | None = None
    meta: A2UIMeta
```

### 7. Create A2UI Builder

```python
# backend/app/core/a2ui/builder.py
from uuid import uuid4
from .schemas import A2UIMessage, SurfaceUpdate, A2UIComponent, A2UIMeta, DeviceContext

class A2UIBuilder:
    def __init__(self, device_context: DeviceContext):
        self.device_context = device_context
        self.components: list[A2UIComponent] = []
        self.data: dict = {}

    def add_alert(
        self,
        title: str,
        description: str | None = None,
        severity: str = "info",
    ) -> "A2UIBuilder":
        self.components.append(A2UIComponent(
            id=str(uuid4()),
            type="alertCard",
            props={
                "title": title,
                "description": description,
                "severity": severity,
            }
        ))
        return self

    def add_line_chart(
        self,
        data_key: str,
        data: list[dict],
        title: str | None = None,
    ) -> "A2UIBuilder":
        self.components.append(A2UIComponent(
            id=str(uuid4()),
            type="lineChart",
            data_binding=data_key,
            props={"title": title},
        ))
        self.data[data_key] = data
        return self

    def add_data_table(
        self,
        data_key: str,
        data: list[dict],
        columns: list[dict],
    ) -> "A2UIBuilder":
        self.components.append(A2UIComponent(
            id=str(uuid4()),
            type="dataTable",
            data_binding=data_key,
            props={"columns": columns},
        ))
        self.data[data_key] = data
        return self

    def add_action_button(
        self,
        label: str,
        action_type: str,
        target: str | None = None,
    ) -> "A2UIBuilder":
        self.components.append(A2UIComponent(
            id=str(uuid4()),
            type="actionButton",
            props={
                "label": label,
                "action": {"type": action_type, "target": target},
            }
        ))
        return self

    def build(self, fallback_text: str | None = None) -> A2UIMessage:
        return A2UIMessage(
            surface_update=SurfaceUpdate(components=self.components),
            data_model_update=self.data if self.data else None,
            meta=A2UIMeta(
                device_context=self.device_context,
                fallback_text=fallback_text,
            )
        )
```

### 8. Create Example Endpoint

```python
# backend/app/modules/insights/router.py (add to existing)
from fastapi import APIRouter, Request
from app.core.a2ui.builder import A2UIBuilder
from app.core.a2ui.schemas import DeviceContext

@router.get("/{insight_id}/ui")
async def get_insight_ui(insight_id: UUID, request: Request):
    # Get insight data
    insight = await insight_service.get(insight_id)

    # Detect device
    user_agent = request.headers.get("user-agent", "")
    device = DeviceContext(
        is_mobile="Mobile" in user_agent,
        is_tablet="Tablet" in user_agent,
    )

    # Build A2UI response
    builder = A2UIBuilder(device)

    if insight.severity == "critical":
        builder.add_alert(
            title=insight.title,
            description=insight.summary,
            severity="error",
        )
        if insight.trend_data:
            builder.add_line_chart(
                data_key="trend",
                data=insight.trend_data,
                title="Trend Analysis",
            )
    else:
        builder.add_alert(
            title=insight.title,
            description=insight.summary,
            severity="info",
        )

    builder.add_action_button(
        label="View Details",
        action_type="navigate",
        target=f"/insights/{insight_id}",
    )

    return builder.build(fallback_text=insight.summary)
```

---

## Test Scenarios

### 1. Basic A2UI Rendering

```gherkin
Scenario: Render A2UI message with alert and chart
  Given I have an A2UI message with an alertCard and lineChart
  When I pass it to the A2UIRenderer
  Then I should see the alert component rendered
  And I should see the chart component rendered with bound data
```

### 2. Unknown Component Fallback

```gherkin
Scenario: Handle unknown component type
  Given I have an A2UI message with type "unknownWidget"
  When I render it
  Then I should see a fallback card showing "Unknown component: unknownWidget"
```

### 3. Mobile Device Detection

```gherkin
Scenario: Camera-first UI on mobile
  Given I am on a mobile device
  When I request the document upload UI
  Then I should see cameraCapture as the primary component
  And fileUpload should be secondary
```

### 4. Streaming A2UI

```gherkin
Scenario: Progressive rendering of streaming A2UI
  Given I connect to the streaming endpoint
  When the agent sends components incrementally
  Then each component should appear as it's received
  And the UI should show a loading indicator for pending sections
```

---

## Verification Checklist

### A2UI Core
- [ ] A2UIRenderer component works with basic message
- [ ] Component catalog resolves all 30 types
- [ ] Unknown components show fallback
- [ ] Data binding flows to components

### Backend Integration
- [ ] A2UIBuilder creates valid messages
- [ ] Device detection works from User-Agent
- [ ] `/ui` endpoints return A2UI format
- [ ] Streaming endpoint sends SSE correctly

### User Stories
- [ ] US1: Insights render with appropriate visualizations
- [ ] US2: Dashboard adapts to time of day
- [ ] US3: Mobile shows camera-first UI
- [ ] US4: Ad-hoc queries generate visual responses
- [ ] US5: BAS review shows only anomalies expanded
- [ ] US6: Day summary generates with timesheet data

---

## Common Issues

### 1. Component Not Rendering

```typescript
// Check if component is in catalog
console.log('Available components:', Object.keys(componentCatalog));

// Check if type matches exactly (case-sensitive)
// Wrong: "LineChart" → Right: "lineChart"
```

### 2. Data Binding Not Working

```typescript
// Ensure data is in dataModelUpdate
const message: A2UIMessage = {
  surfaceUpdate: {
    components: [{
      id: '1',
      type: 'lineChart',
      dataBinding: 'trend', // Must match key in dataModelUpdate
    }]
  },
  dataModelUpdate: {
    trend: [{ date: '2025-01', value: 100 }], // Key must match
  },
  // ...
};
```

### 3. Lazy Loading Suspense Error

```typescript
// Ensure A2UIRenderer is wrapped in Suspense or components handle loading
import { Suspense } from 'react';

function InsightView({ message }) {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <A2UIRenderer message={message} />
    </Suspense>
  );
}
```

---

## Related Files

| File | Purpose |
|------|---------|
| `frontend/src/lib/a2ui/types.ts` | TypeScript type definitions |
| `frontend/src/lib/a2ui/catalog.ts` | Component registry |
| `frontend/src/lib/a2ui/renderer.tsx` | Main renderer component |
| `frontend/src/lib/a2ui/context.tsx` | Data binding context |
| `backend/app/core/a2ui/schemas.py` | Pydantic schemas |
| `backend/app/core/a2ui/builder.py` | A2UI message builder |
| `specs/033-a2ui-agent-driven-interfaces/contracts/a2ui-api.yaml` | OpenAPI spec |
