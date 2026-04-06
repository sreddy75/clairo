# Feature Specification: Tax Planning Intelligence Improvements

**Feature Branch**: `046-tax-planning-intelligence`
**Created**: 2026-04-06
**Status**: Draft
**Input**: Beta tester feedback on the tax planning module — 6 improvements needed

## Assumptions

- Australian financial year: July 1 to June 30
- Revenue forecasting uses simple linear projection (monthly average × 12) — no seasonal adjustment for beta
- Prior year data depends on client having sufficient Xero history; gracefully handles missing data
- Strategy sizing is advisory only — the AI suggests ranges, not exact amounts
- Payroll data availability depends on the Xero connection having payroll scope access
- All new data stored in existing data structures — no database schema changes

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Bank Balance Visibility (Priority: P1)

As an accountant reviewing a client's tax position, I see the client's actual bank balance so I can assess their capacity to implement tax strategies (pre-payments, asset purchases, super contributions) based on real cash availability.

**Why this priority**: Bank balance is the most basic financial data point. If it shows $0 or is hidden, the accountant loses trust in the platform's data accuracy. Quick fix with high impact.

**Independent Test**: Pull financials for a client with bank accounts in Xero. Verify the bank balance displays correctly. For a client with no bank data, verify "Bank data not available" appears instead of $0.

**Acceptance Scenarios**:

1. **Given** a client with bank accounts in Xero, **When** the accountant pulls financials, **Then** the bank balance section shows the correct closing balance for each account and the total
2. **Given** a client where Xero returns no bank summary data, **When** the accountant pulls financials, **Then** the bank balance section shows "Bank data not available" instead of $0
3. **Given** a client with multiple bank accounts, **When** the accountant views the tax plan, **Then** each account is listed with its closing balance and the total is the sum of all accounts
4. **Given** the bank balance is displayed, **When** the AI generates tax strategies, **Then** the AI references the available cash when sizing strategy recommendations

---

### User Story 2 — Revenue and Expense Forecasting (Priority: P1)

As an accountant preparing a tax plan mid-year (e.g., March), I see projected full-year revenue and expenses based on year-to-date performance so I can estimate the full-year tax position and plan strategies accordingly.

**Why this priority**: Without forecasting, the tax position shown is only for the period to date, which underestimates the full-year liability. Accountants need the projected figure to plan strategies effectively.

**Independent Test**: Pull financials for a client with 9 months of data (Jul-Mar). Verify the system shows both YTD actuals and projected full-year figures. Verify the projected tax position reflects the full-year estimate.

**Acceptance Scenarios**:

1. **Given** a client with 9 months of YTD data (Jul-Mar), **When** the accountant pulls financials, **Then** the system calculates monthly averages and projects to 12 months, showing both "YTD Actual" and "Projected Full Year" figures
2. **Given** projected full-year figures, **When** the tax position is calculated, **Then** it uses the projected full-year income to estimate the annual tax liability
3. **Given** 12 months of data (complete financial year), **When** financials are pulled, **Then** no projection is shown — the actuals are the full-year figures
4. **Given** fewer than 3 months of data, **When** financials are pulled, **Then** the system shows YTD only with a note "Insufficient data for full-year projection" (too few months for reliable projection)
5. **Given** projected figures, **When** the accountant views the financials panel, **Then** projected amounts are clearly labelled as estimates (e.g., "Projected" badge) to distinguish from actuals

---

### User Story 3 — Prior Year Comparison (Priority: P2)

As an accountant, I see a comparison of the current year's performance against the same period last year so I can identify trends, anomalies, and growth patterns that inform tax planning decisions.

**Why this priority**: Year-on-year comparison is a fundamental analytical tool. It helps accountants spot unusual changes (revenue spike, expense drop) that may need investigation or present planning opportunities.

**Independent Test**: Pull financials for a client with 2+ years of Xero data. Verify the system shows current YTD alongside same-period-last-year, with growth/decline percentages.

**Acceptance Scenarios**:

1. **Given** a client with prior year data in Xero, **When** the accountant pulls financials, **Then** the system also pulls the same period from the prior financial year and displays a side-by-side comparison
2. **Given** current YTD is Jul 2025 - Mar 2026, **When** prior year data is shown, **Then** it covers Jul 2024 - Mar 2025 (same 9-month window)
3. **Given** prior year data is available, **When** the comparison is displayed, **Then** revenue, expenses, and net profit show both absolute values and percentage change (e.g., "+12%" or "-5%")
4. **Given** a client with no prior year data in Xero (new connection), **When** financials are pulled, **Then** the comparison section is hidden with no error — current year data displays normally
5. **Given** prior year data, **When** the AI generates the tax plan, **Then** the AI references year-on-year trends in its analysis (e.g., "Revenue grew 15% vs same period last year")

---

### User Story 4 — Multi-Year Trend Analysis (Priority: P2)

As an accountant, I see full financial year results for the previous two years alongside the current year so I can analyse long-term trends in revenue, expenses, and profitability that inform strategic tax planning.

**Why this priority**: Two-year trends reveal whether growth is accelerating, plateauing, or declining — critical for advising on entity structure changes, capital investments, or dividend strategies.

**Independent Test**: Pull financials for a client with 3 years of Xero data. Verify FY-1 and FY-2 full-year P&L summaries appear alongside current year data.

**Acceptance Scenarios**:

1. **Given** a client with 3+ years of Xero data, **When** the accountant pulls financials, **Then** the system shows full-year P&L summaries for FY-1 and FY-2 alongside current year
2. **Given** the current plan is for FY2026, **When** multi-year data is displayed, **Then** FY2025 and FY2024 full-year revenue, expenses, and net profit are shown
3. **Given** only 1 year of prior data exists, **When** financials are pulled, **Then** only FY-1 is shown; FY-2 section is omitted
4. **Given** multi-year data, **When** the AI generates analysis, **Then** it references multi-year trends (e.g., "Revenue has grown consistently at ~10% pa over the past 3 years")

---

### User Story 5 — Data-Informed Strategy Sizing (Priority: P2)

As an accountant, when the AI suggests tax strategies (pre-payments, asset purchases, super contributions), the suggested amounts are grounded in the client's actual financial position — their available cash, spending patterns, and capacity — rather than generic placeholder amounts.

**Why this priority**: Generic suggestions like "consider a $50,000 prepayment" are useless if the client has $10,000 in the bank. Strategies must be realistic and actionable.

**Independent Test**: Generate a tax plan analysis for a client. Verify that strategy dollar amounts reference the client's bank balance and spending patterns, not generic figures.

**Acceptance Scenarios**:

1. **Given** a client with $50,000 in the bank, **When** the AI suggests a prepayment strategy, **Then** the suggested amount does not exceed the available cash and references the bank balance as a constraint
2. **Given** a client's P&L shows $30,000 in equipment purchases YTD, **When** the AI suggests asset purchase timing, **Then** it references the existing spend pattern and suggests incremental purchases within capacity
3. **Given** a client with limited cash, **When** the AI generates strategies, **Then** it prioritises low-cost or no-cost strategies (e.g., timing of income recognition, bad debt write-offs) over cash-intensive ones
4. **Given** the AI's strategy recommendations, **When** the accountant reviews them, **Then** each strategy shows a recommended range (min-max) with a note explaining why that range was chosen (e.g., "Based on $50K cash available and $10K monthly operating expenses")

---

### User Story 6 — Employee and Payroll Intelligence (Priority: P3)

As an accountant, when the tax planning system analyses a client's position, it checks whether the business has employees (including owner-directors) and factors wages, superannuation, and payroll obligations into the tax strategy recommendations.

**Why this priority**: Superannuation contributions and owner salary structures are among the most impactful tax planning levers. Without payroll data, the AI misses these opportunities entirely.

**Independent Test**: Pull financials for a client with payroll data in Xero. Verify the system includes employee count, total wages, and super in the financial context. Verify the AI mentions super contribution strategies.

**Acceptance Scenarios**:

1. **Given** a client with payroll data in Xero, **When** the accountant pulls financials, **Then** the system includes a payroll summary: employee count, total wages YTD, total super YTD, and total PAYG withheld
2. **Given** payroll data is available, **When** the AI generates strategies, **Then** it evaluates superannuation contribution strategies (e.g., maximising concessional contributions, catch-up contributions)
3. **Given** an owner-operator entity (company or trust), **When** payroll data shows a director/owner, **Then** the AI considers whether the owner's salary/dividend split is tax-efficient
4. **Given** a client without payroll access in Xero, **When** financials are pulled, **Then** the payroll section is omitted and the AI notes "Payroll data not available — consider reviewing employee remuneration separately"
5. **Given** a sole trader with no employees, **When** the AI generates strategies, **Then** it does not suggest wage/salary strategies but may suggest personal super contribution strategies

---

### Edge Cases

- What happens if the Xero connection has insufficient API scopes for bank or payroll data? The system proceeds with available data and indicates which sections are unavailable.
- What if prior year data exists but is incomplete (e.g., only 6 months)? The system shows whatever data is available with a note about the period coverage.
- What if the projected figures are wildly different from prior year actuals (e.g., seasonal business)? The projection is clearly labelled as a simple average-based estimate. No seasonal adjustment for beta.
- What if bank balance data is stale (reconciled weeks ago)? The system shows the last reconciliation date alongside the balance so the accountant can judge relevance.
- What if the client has payroll but the Xero connection lacks payroll scope? The system checks `has_payroll_access` before querying and shows "Payroll access not connected" rather than empty data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display the actual bank balance from Xero, or "Bank data not available" when no bank data exists — never show $0 as a default
- **FR-002**: System MUST calculate projected full-year revenue and expenses by extrapolating YTD monthly averages to 12 months, when 3 or more months of data are available
- **FR-003**: System MUST clearly label projected figures as estimates, distinct from actual YTD figures
- **FR-004**: System MUST pull the same YTD period from the prior financial year for side-by-side comparison
- **FR-005**: System MUST show percentage change (growth/decline) between current and prior year figures
- **FR-006**: System MUST pull full-year P&L summaries for up to two prior financial years (FY-1 and FY-2)
- **FR-007**: System MUST include bank balance, spending patterns, and cash position in the context provided to the AI when generating strategy recommendations
- **FR-008**: System MUST ensure AI-suggested strategy amounts do not exceed available cash without explicit justification
- **FR-009**: System MUST query payroll data (employee count, wages, super) when Xero payroll access is available and include it in the financial context
- **FR-010**: System MUST gracefully handle missing data for any section (bank, prior year, payroll) without breaking the tax plan or showing errors
- **FR-011**: System MUST include prior year comparisons and payroll data in the AI prompt context so the AI can reference them in analysis
- **FR-012**: All new financial data MUST be stored within existing data structures without requiring database schema changes

### Key Entities

- **Financial Data (enriched)**: Extended with projected figures (projected_revenue, projected_expenses, projected_net_profit, months_data_available, is_annualised), prior year data (prior_year_ytd with same fields), multi-year summaries (prior_years array), payroll summary (employee_count, total_wages_ytd, total_super_ytd, has_owners)
- **Strategy Context**: New data structure combining bank balance, spending patterns from P&L line items, and payroll data — provided to the AI for realistic strategy sizing

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Data Access Events**: Pulling additional financial data (prior year P&L, payroll) from Xero
- [x] **Integration Events**: Additional Xero API calls for prior year reports and payroll queries

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| tax_planning.financials.prior_year_pulled | Prior year P&L fetched from Xero | period, connection_id, data_available | 7 years | None |
| tax_planning.financials.payroll_queried | Payroll data queried for tax plan | connection_id, employee_count, has_payroll_access | 7 years | Wages amounts (non-PII) |
| tax_planning.financials.projection_calculated | Full-year projection computed | months_available, projection_method | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Projected figures must be clearly marked as estimates, not actual lodgeable amounts. Tax plans using projections should note the projection basis.
- **Data Retention**: Financial data in tax plans retained per standard 7-year policy
- **Access Logging**: All additional Xero data pulls logged via existing integration audit trail

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Bank balance displays correctly for 100% of clients with bank accounts in Xero — no false $0 values
- **SC-002**: Revenue projections are within 20% of actual full-year figures when validated against completed financial years
- **SC-003**: Prior year comparison data loads within 5 seconds alongside current year data
- **SC-004**: 100% of AI-generated strategy recommendations reference the client's actual financial position (bank balance, cash flow) when available
- **SC-005**: Accountants report the tax plan provides "more useful" or "more actionable" recommendations compared to before (qualitative feedback from beta testers)
- **SC-006**: Payroll data is included in the tax plan for 100% of clients with Xero payroll access enabled
- **SC-007**: The system handles missing data gracefully — zero errors when prior year, bank, or payroll data is unavailable
