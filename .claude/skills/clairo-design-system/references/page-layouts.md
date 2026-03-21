# Page Layout Patterns

Every page in Clairo follows one of these layout patterns. Choose the right one based on page purpose.

---

## General Page Structure

All protected pages share this outer structure with a **collapsible sidebar**:

```
EXPANDED (w-64)                        COLLAPSED (w-16)
┌──────────┬─────────────────────┐     ┌────┬──────────────────────────┐
│ Logo  «  │  Header (h-14)     │     │ ⚡ │  Header (h-14)           │
│          ├─────────────────────┤     │    ├──────────────────────────┤
│ MAIN     │                     │     │ 🏠 │                          │
│ 🏠 Dashboard│  Content (p-5)   │     │ 👥 │  Content (p-5)           │
│ 👥 Clients │                    │     │ 📄 │                          │
│ 📄 BAS     │  Page Header      │     │ 💬 │  (more room for data!)   │
│ 💬 Assistant│                   │     │    │                          │
│          │  Page Body          │     │ ⚙️ │                          │
│ ADMIN    │                     │     │    │                          │
│ ⚙️ Settings│                    │     │ DK │                          │
│          │                     │     └────┴──────────────────────────┘
│ DK email │                     │
└──────────┴─────────────────────┘
```

- Sidebar collapses to icon-only (`w-16`) — tooltips show labels on hover
- Content area padding adapts: `pl-64` (expanded) or `pl-16` (collapsed)
- Collapsed state persisted in localStorage/Zustand
- See `component-patterns.md` > Collapsible Sidebar for full implementation

Content area uses `p-5` padding and `space-y-5` between page sections (Professional Density).

---

## 1. Dashboard Layout

For: Main dashboard, client overview, practice overview.

```
┌──────────────────────────────────────────────────────┐
│ Page Header: "Dashboard"        [Date range] [Export] │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Stat    │ │ Stat    │ │ Stat    │ │ Stat    │   │
│  │ Card    │ │ Card    │ │ Card    │ │ Card    │   │
│  │ $45,230 │ │ 24      │ │ 87%     │ │ 3       │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                                                       │
│  ┌────────────────────────┐ ┌────────────────────┐   │
│  │ Chart Card             │ │ Activity / Alerts  │   │
│  │ [Hero number]          │ │ List               │   │
│  │ [Line/bar chart]       │ │                    │   │
│  │ [Legend]                │ │                    │   │
│  └────────────────────────┘ └────────────────────┘   │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Data Table: Recent items / Action items          │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

```tsx
<div className="space-y-5">
  {/* Page header */}
  <PageHeader title="Dashboard" subtitle="Overview of your practice" />

  {/* Stat cards row */}
  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
    <StatCard label="Total Revenue" value={formatCurrency(45230)} trend={{ value: 12, isPositive: true }} />
    <StatCard label="Active Clients" value="24" />
    <StatCard label="BAS Completion" value="87%" />
    <StatCard label="Action Items" value="3" />
  </div>

  {/* Charts row */}
  <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
    <div className="lg:col-span-2">
      <ChartCard />
    </div>
    <ActivityList />
  </div>

  {/* Table */}
  <DataTableCard title="Recent Activity" data={recentItems} />
</div>
```

---

## 2. List Layout

For: Client list, knowledge collections, lodgements, queries.

```
┌──────────────────────────────────────────────────────┐
│ Page Header: "Clients"                   [Add Client] │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Filter Bar                                        │ │
│  │ [Tab: All 45] [In Progress 43] [Closed 2]        │ │
│  │                                        [Search]   │ │
│  ├──────────────────────────────────────────────────┤ │
│  │ Table                                             │ │
│  │ Name       │ Status    │ BAS Due   │ Revenue     │ │
│  │ ─────────────────────────────────────────────── │ │
│  │ Acme Ltd   │ ● On Track│ 15 Mar   │   $12,500  │ │
│  │ Beta Corp  │ ● Overdue │ 01 Mar   │    $8,200  │ │
│  │ ...        │           │          │            │ │
│  ├──────────────────────────────────────────────────┤ │
│  │ Pagination                                        │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

The entire filter bar + table + pagination lives inside ONE Card:

```tsx
<div className="space-y-5">
  <PageHeader title="Clients" subtitle="Manage your client portfolio">
    <Button size="sm">Add Client</Button>
  </PageHeader>

  <Card>
    <CardHeader className="pb-4">
      <FilterBar tabs={tabs} activeTab={activeTab} onSearch={setSearch} />
    </CardHeader>
    <CardContent className="p-0">
      <Table>{/* ... */}</Table>
    </CardContent>
    <CardFooter className="justify-between border-t px-4 py-3">
      <span className="text-sm text-muted-foreground">
        Showing {start}-{end} of {total}
      </span>
      <Pagination />
    </CardFooter>
  </Card>
</div>
```

---

## 3. Detail Layout

For: Client detail, BAS review, single knowledge document.

```
┌──────────────────────────────────────────────────────┐
│ Breadcrumb: Clients > Acme Pty Ltd                    │
│ Page Header: "Acme Pty Ltd"     [Edit] [Sync] [More] │
├──────────────────────────────────────────────────────┤
│                                                       │
│  [Overview] [BAS] [Transactions] [Documents] [Notes]  │
│  ─────────────────────────────────────────────────── │
│                                                       │
│  (Tab content varies — typically stat cards + table   │
│   or form content matching the relevant patterns)     │
│                                                       │
└──────────────────────────────────────────────────────┘
```

```tsx
<div className="space-y-5">
  {/* Breadcrumb */}
  <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
    <Link href="/clients" className="hover:text-foreground">Clients</Link>
    <ChevronRight className="h-4 w-4" />
    <span className="text-foreground">{client.name}</span>
  </nav>

  <PageHeader title={client.name} subtitle={client.abn}>
    <Button variant="outline" size="sm">Edit</Button>
    <Button size="sm">Sync with Xero</Button>
  </PageHeader>

  {/* Tabs */}
  <Tabs defaultValue="overview">
    <TabsList>
      <TabsTrigger value="overview">Overview</TabsTrigger>
      <TabsTrigger value="bas">BAS</TabsTrigger>
      <TabsTrigger value="transactions">Transactions</TabsTrigger>
    </TabsList>
    <TabsContent value="overview" className="mt-5 space-y-5">
      {/* Stat cards + content */}
    </TabsContent>
  </Tabs>
</div>
```

---

## 4. Settings Layout

For: Practice settings, account, integrations, billing.

```
┌──────────────────────────────────────────────────────┐
│ Page Header: "Settings"                               │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌────────────┐ ┌──────────────────────────────────┐ │
│  │ Nav        │ │ Form Section                     │ │
│  │ General    │ │                                   │ │
│  │ Billing    │ │ PRACTICE DETAILS                  │ │
│  │ Team       │ │ ┌──────────┐ ┌──────────┐       │ │
│  │ Integrations│ │  Name      │ │  ABN      │       │ │
│  │ Notifications│ └──────────┘ └──────────┘       │ │
│  │            │ │                                   │ │
│  └────────────┘ │             [Save Changes]        │ │
│                  └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

Left nav for settings sections, right panel for forms.

---

## 5. Chat / Assistant Layout

For: AI assistant, knowledge queries (Orbita reference).

```
┌──────────────────────────────────────────────────────┐
│ Page Header: "Assistant"                              │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────┐ ┌────────────────────────────────┐  │
│  │ Conversations│ │                                │  │
│  │             │ │  Message bubbles               │  │
│  │ + New Chat  │ │                                │  │
│  │             │ │                                │  │
│  │ Saved       │ │                                │  │
│  │  - ChatAI   │ │                                │  │
│  │             │ │                                │  │
│  │ Today       │ ├────────────────────────────────┤  │
│  │  - Query 1  │ │ Input area                     │  │
│  │  - Query 2  │ │ [Select Source] [Attach] [Send]│  │
│  └─────────────┘ └────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

- Conversation sidebar: grouped by time (Saved, Today, Yesterday)
- Message area: generous padding, clean bubbles
- Input area: fixed to bottom with source selector and send button
- Clean, minimal — no distracting UI elements

---

## Responsive Grid Patterns

| Breakpoint | Stat cards | Chart + sidebar | Table |
|------------|-----------|-----------------|-------|
| Mobile (`<640px`) | 1 col stack | 1 col stack | Horizontal scroll |
| Tablet (`sm-lg`) | 2 cols | 1 col stack | Full width |
| Desktop (`lg+`) | 4 cols | 2:1 ratio (`lg:grid-cols-3`, chart `lg:col-span-2`) | Full width |

Always use `grid-cols-1` as base, then expand:
```tsx
<div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
```
