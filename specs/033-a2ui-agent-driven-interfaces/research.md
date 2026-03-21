# Research: A2UI Agent-Driven Interfaces

**Feature**: 033-a2ui-agent-driven-interfaces
**Date**: 2026-01-02
**Status**: Complete

---

## Research Questions

### 1. A2UI Protocol Version and Stability

**Decision**: Use A2UI v0.8 (Public Preview) concepts, but implement our own simplified schema

**Rationale**:
- A2UI v0.8 is still evolving; tight coupling to their spec risks breaking changes
- Clairo needs only ~30 component types, not the full A2UI spec
- By defining our own TypeScript/Pydantic types inspired by A2UI, we maintain control
- Can align more closely with official spec as it stabilizes

**Alternatives Considered**:
- Wait for v1.0: Delays feature, no clear timeline
- Use A2UI Web Components library: Not React-native, adds bundle size
- Fork A2UI spec: Maintenance burden

### 2. Frontend Rendering Approach

**Decision**: Custom React renderer with component catalog

**Rationale**:
- A2UI's official library is Flutter/Angular/Web Components - no React
- React's component model maps naturally to A2UI's declarative structure
- shadcn/ui components are already in our stack
- Custom renderer gives us full control over styling/theming

**Alternatives Considered**:
- Web Components wrapper: Poor React integration, additional abstraction layer
- Contribute React impl to A2UI: Timeline too long for our needs
- Use existing rendering library: None mature enough for React

### 3. Streaming/Progressive Rendering

**Decision**: Use Server-Sent Events (SSE) for streaming A2UI

**Rationale**:
- SSE is simpler than WebSocket for unidirectional streaming
- Works with existing FastAPI streaming response pattern
- AI agent can emit components as it generates them
- Frontend accumulates and renders incrementally

**Implementation**:
```typescript
// Frontend: useA2UIStream hook
const { components, isStreaming } = useA2UIStream('/api/v1/insights/123/ui/stream');

// Backend: SSE endpoint
@router.get("/insights/{id}/ui/stream")
async def stream_insight_ui(id: UUID):
    async def generate():
        async for component in agent.stream_ui(id):
            yield f"data: {component.json()}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 4. Device Context Detection

**Decision**: Use User-Agent parsing + CSS media queries

**Rationale**:
- Server-side detection via User-Agent enables different component selection
- CSS media queries handle responsive styling
- Combination provides both layout AND component-level adaptation

**Implementation**:
```python
# Backend: Device detection from request headers
def get_device_context(request: Request) -> DeviceContext:
    ua = parse_user_agent(request.headers.get("user-agent", ""))
    return DeviceContext(
        is_mobile=ua.is_mobile,
        is_tablet=ua.is_tablet,
        platform=ua.platform,
        browser=ua.browser
    )
```

### 5. Component Catalog Organization

**Decision**: Categorized folder structure with single registry

**Rationale**:
- 30+ components need logical grouping
- Single catalog.ts registry for type-safe mapping
- Categories: charts, data, layout, actions, alerts, forms, media, feedback

**Implementation**:
```typescript
// frontend/src/lib/a2ui/catalog.ts
export const componentCatalog: ComponentCatalog = {
  // Charts
  lineChart: LineChart,
  barChart: BarChart,
  pieChart: PieChart,
  scatterChart: ScatterChart,

  // Data
  dataTable: DataTable,
  comparisonTable: ComparisonTable,
  statCard: StatCard,

  // Layout
  card: Card,
  accordion: Accordion,
  tabs: Tabs,
  timeline: Timeline,

  // ... etc
};
```

### 6. Data Model Binding

**Decision**: React Context with Zustand for reactive updates

**Rationale**:
- A2UI dataModelUpdate needs to flow to multiple components
- React Context provides scoped access
- Zustand handles reactivity for data changes during streaming
- Avoids prop drilling through component tree

**Implementation**:
```typescript
// Data model context
const A2UIDataContext = createContext<A2UIDataStore | null>(null);

export function A2UIDataProvider({ initialData, children }) {
  const store = useA2UIDataStore(initialData);
  return (
    <A2UIDataContext.Provider value={store}>
      {children}
    </A2UIDataContext.Provider>
  );
}

// Component accessing bound data
function LineChart({ dataBinding }) {
  const data = useA2UIData(dataBinding); // Reactively updates
  return <RechartsLineChart data={data} />;
}
```

### 7. Action Handling

**Decision**: Action registry with typed handlers

**Rationale**:
- A2UI actions need to trigger real application behavior
- Registry pattern allows extension without modifying renderer
- Type-safe action definitions prevent runtime errors

**Implementation**:
```typescript
// Action types
type A2UIAction =
  | { type: 'navigate'; target: string }
  | { type: 'createTask'; payload: TaskCreate }
  | { type: 'approve'; resourceId: string }
  | { type: 'export'; format: 'csv' | 'pdf' };

// Action handler registry
const actionHandlers: Record<A2UIAction['type'], ActionHandler> = {
  navigate: (action) => router.push(action.target),
  createTask: (action) => api.tasks.create(action.payload),
  approve: (action) => api.approvals.approve(action.resourceId),
  export: (action) => exportService.export(action.format),
};
```

### 8. Error Handling and Fallbacks

**Decision**: Graceful degradation with error boundaries

**Rationale**:
- A2UI must never crash the application
- Unknown components render as generic cards
- Failed renders show "text-only" fallback
- Error boundaries isolate failures

**Implementation**:
```typescript
// Fallback for unknown component types
function UnknownComponent({ type, props }) {
  return (
    <Card>
      <CardHeader>Unknown Component: {type}</CardHeader>
      <CardContent>
        <pre>{JSON.stringify(props, null, 2)}</pre>
      </CardContent>
    </Card>
  );
}

// Error boundary wrapper
function A2UIErrorBoundary({ children, fallbackText }) {
  return (
    <ErrorBoundary fallback={<TextOnlyFallback text={fallbackText} />}>
      {children}
    </ErrorBoundary>
  );
}
```

### 9. Performance Optimization

**Decision**: Component memoization + lazy loading

**Rationale**:
- 30+ components shouldn't be bundled upfront
- Dynamic imports for rarely-used components
- React.memo prevents unnecessary re-renders

**Implementation**:
```typescript
// Lazy load chart components (heavy dependencies)
const LazyLineChart = lazy(() => import('./charts/LineChart'));
const LazyBarChart = lazy(() => import('./charts/BarChart'));

// Memoized component wrapper
const MemoizedA2UIComponent = memo(function A2UIComponent({ type, props, dataContext }) {
  const Component = componentCatalog[type] ?? UnknownComponent;
  return <Component {...props} dataContext={dataContext} />;
});
```

### 10. Testing Strategy

**Decision**: Unit tests for components, integration tests for renderer

**Rationale**:
- Each catalog component needs isolated tests
- Renderer needs integration tests with various A2UI messages
- Snapshot tests for visual regression

**Test Coverage**:
| Test Type | Scope | Count |
|-----------|-------|-------|
| Component Unit | Each A2UI component | 30+ |
| Renderer Integration | Full message rendering | 10 |
| Streaming | SSE handling | 5 |
| Error Handling | Fallback scenarios | 5 |

---

## Dependencies Identified

### Frontend Dependencies (New)

| Package | Version | Purpose |
|---------|---------|---------|
| recharts | ^2.x | Chart components (already in use) |
| date-fns | ^3.x | Date formatting (already in use) |
| No new dependencies required | - | Leveraging existing stack |

### Backend Dependencies (New)

| Package | Version | Purpose |
|---------|---------|---------|
| user-agents | ^2.x | User-Agent parsing for device detection |
| No other new dependencies | - | Using existing FastAPI/Pydantic |

---

## Risks Mitigated

| Risk | Mitigation |
|------|------------|
| A2UI spec changes | Custom schema inspired by A2UI, not coupled to it |
| Performance with many components | Lazy loading, memoization |
| Unknown component types | Fallback to generic card |
| Streaming failures | Partial render with retry button |
| Mobile detection inaccuracy | Server + client detection combined |

---

## Research Artifacts

- **Reference**: `/planning/analysis/a2ui-agent-driven-interfaces.md` (comprehensive analysis)
- **Reference**: `/planning/analysis/a2ui-spec-definition.md` (ROADMAP entry)
- **A2UI Official**: https://a2ui.org/
