# Australian Tax Compliance Glossary

Terminology, definitions, and how each concept maps to Clairo's data model. Includes ATO reporting obligations and deadlines relevant to the platform.

---

## Tax & Reporting Concepts

### GST (Goods and Services Tax)
- **Definition**: A 10% broad-based consumption tax on most goods, services, and other items sold or consumed in Australia.
- **Who Reports**: Businesses with GST turnover of $75,000+ (or $150,000+ for non-profits) MUST register for GST.
- **Reporting Period**: Quarterly (default) or monthly (if annual turnover > $20M or by election).
- **Clairo Mapping**: Calculated from XeroInvoice (sales/purchases), XeroBankTransaction, and XeroCreditNote entities. Results stored in BASCalculation G-fields.
- **Key Fields**:
  - G1: Total sales (including GST)
  - G2: Export sales (GST-free)
  - G3: Other GST-free sales
  - G10: Capital purchases
  - G11: Non-capital purchases
  - 1A: GST on sales (collected)
  - 1B: GST on purchases (paid)
  - Net GST = 1A - 1B (positive = payable, negative = refund)
- **Credit Note Impact**: GST Collected = Sum(Invoice GST) - Sum(Credit Note GST). Introduced in Spec 024.

### BAS (Business Activity Statement)
- **Definition**: A form submitted to the ATO that reports a business's tax obligations including GST, PAYG-W, PAYG-I, and FBT-I.
- **Filing Frequency**: Quarterly (most common), monthly (large businesses), or annually (small businesses).
- **Clairo Mapping**: The core workflow entity. BASPeriod defines the reporting window; BASSession tracks preparation state; BASCalculation holds computed fields.
- **Workflow**: DRAFT -> IN_PROGRESS -> READY_FOR_REVIEW -> APPROVED -> LODGED
- **Lodgement Methods**: ATO Business Portal, Xero Tax, or other (recorded in BASSession.lodgement_method)

### IAS (Instalment Activity Statement)
- **Definition**: A simplified activity statement for businesses that are not registered for GST but still have PAYG-W or PAYG-I obligations.
- **Difference from BAS**: IAS has no GST section. Only PAYG fields.
- **Clairo Mapping**: Same BASPeriod/BASSession structure, but GST G-fields are zero. The `period_type` field distinguishes quarterly vs monthly reporting.

### PAYG-W (Pay As You Go Withholding)
- **Definition**: Tax withheld from payments to employees, contractors, and other payees. Businesses act as collection agents for the ATO.
- **Who Reports**: All employers who withhold tax from payments.
- **Reporting**: Reported on BAS/IAS. Annual summary via Payment Summary (or STP Annual Report).
- **Clairo Mapping**: Calculated from XeroPayRun entities. BASCalculation fields W1 (total wages) and W2 (amount withheld).
- **Key Fields**:
  - W1: Total salary, wages, and other payments
  - W2: Amount withheld from payments in W1

### PAYG-I (Pay As You Go Instalments)
- **Definition**: Regular prepayments of income tax for businesses and individuals with business/investment income. Prevents a large year-end tax bill.
- **Calculation Methods**: Amount method (ATO specifies amount) or Instalment rate method (rate x income).
- **Clairo Mapping**: BAS field T1. Currently not auto-calculated (manual entry by accountant via BASAdjustment).
- **Key Field**: T1: PAYG income tax instalment

### FBT (Fringe Benefits Tax)
- **Definition**: Tax paid by employers on non-cash benefits provided to employees (e.g., car, parking, entertainment, loans).
- **FBT Year**: 1 April to 31 March (different from income tax FY).
- **Rate**: 47% (2024-25).
- **Reporting**: Annual FBT return (due 21 May) + quarterly BAS instalment.
- **Clairo Mapping**: BAS field F1 (FBT instalment). Not currently auto-calculated. Knowledge base contains FBT guides and rulings.

### STP (Single Touch Payroll)
- **Definition**: Real-time payroll reporting to the ATO. Each time an employer runs payroll, tax and super information is reported directly to the ATO through STP-enabled software.
- **Who Reports**: All employers (STP Phase 2 since 1 January 2022).
- **What's Reported**: Gross payments, PAYG-W, super, allowances, deductions, and other reportable items.
- **Clairo Mapping**: Xero handles STP reporting directly. Clairo reads the payroll data via XeroEmployee and XeroPayRun for BAS calculation purposes.

---

## Tax Identifiers

### ABN (Australian Business Number)
- **Definition**: An 11-digit identifier for businesses interacting with other businesses and government agencies.
- **Format**: XX XXX XXX XXX (2-digit check + 9-digit body)
- **Clairo Mapping**: Stored on XeroClient as `abn`. Used for client matching in ATO correspondence parsing (Spec 027).
- **Privacy**: Not considered sensitive. Publicly searchable on ABR.

### TFN (Tax File Number)
- **Definition**: A 9-digit number issued by the ATO to identify individuals and entities for tax purposes.
- **Format**: XXX XXX XXX
- **Clairo Mapping**: Stored as `tax_file_number_masked` on XeroEmployee (masked for security).
- **Privacy**: HIGHLY SENSITIVE. Must NEVER be logged, displayed in full, or stored unencrypted. Subject to TFN Rule (Privacy Act 1988). Penalty for misuse: up to 2 years imprisonment.

### ACN (Australian Company Number)
- **Definition**: A 9-digit identifier for companies registered under the Corporations Act 2001.
- **Clairo Mapping**: Not directly stored; available via Xero organization details.

---

## Regulatory Bodies & Systems

### ATO (Australian Taxation Office)
- **Role**: Federal tax authority responsible for administering tax law, collecting revenue, and managing superannuation.
- **Clairo Integration**: Knowledge base ingests ATO rulings, guides, and website content. ATOtrack (Spec 026-028) planned for correspondence parsing.
- **Key ATO Systems**: Business Portal, Online Services, myGov (individual), ATO app

### DSP (Digital Service Provider)
- **Definition**: Software providers certified by the ATO to submit tax returns and BAS electronically.
- **Tiers**: Tier 1 (direct SBR connection), Tier 2 (via gateway), Tier 3 (limited)
- **Clairo Status**: Not a DSP. Lodgement is currently recorded externally (ATO Portal, Xero Tax). Direct lodgement is a future Phase H goal.

### AustLII (Australasian Legal Information Institute)
- **Definition**: Free database of Australian legislation, case law, and treaties.
- **Clairo Integration**: Knowledge source for legislation content (ITAA 1997, ITAA 1936, GST Act, FBT Act). Scraped by `austlii` source type.

---

## BAS Reporting Deadlines

### Quarterly BAS Due Dates
| Quarter | Period | Standard Due Date | Tax Agent Extended |
|---------|--------|-------------------|--------------------|
| Q1 | Jul-Sep | 28 October | Varies (usually +4 weeks) |
| Q2 | Oct-Dec | 28 February | Varies |
| Q3 | Jan-Mar | 28 April | Varies |
| Q4 | Apr-Jun | 28 July | Varies |

- If due date falls on weekend/public holiday, lodgement is due the next business day.
- Tax agents receive extended lodgement dates from the ATO each year.
- Late lodgement penalty: $313 per 28-day period (2024-25, indexed annually). Compounds up to 5 periods ($1,565 max per BAS).
- Clairo stores `due_date` on BASPeriod and generates deadline notifications.

### Monthly BAS Due Dates
- Due on the 21st of the following month (e.g., July BAS due 21 August).
- Exception: December BAS due 21 February.

### FY Key Dates
| Date | Event |
|------|-------|
| 1 July | FY starts |
| 28 October | Q1 BAS due |
| 31 October | Income tax return due (individuals) |
| 28 February | Q2 BAS due |
| 31 March | FBT year ends |
| 28 April | Q3 BAS due |
| 21 May | FBT return due |
| 30 June | FY ends |
| 28 July | Q4 BAS due |

---

## Tax Classification in Xero

### GST Tax Types (as mapped to BAS fields)
| Xero Tax Type | Meaning | BAS Impact |
|---------------|---------|------------|
| `OUTPUT` | GST on sales (10%) | Adds to G1, 1A |
| `INPUT` | GST on purchases (10%) | Adds to G10/G11, 1B |
| `EXEMPTOUTPUT` | GST-free sales | Adds to G3 |
| `EXEMPTINPUT` | GST-free purchases | No GST impact |
| `GSTONIMPORTS` | GST on imported goods | Adds to 1A |
| `INPUTTAXED` | Input-taxed (no GST credit) | No GST impact |
| `CAPEXINPUT` | Capital purchases with GST | Adds to G10, 1B |
| `BASEXCLUDED` | BAS excluded | No impact |
| `NONE` | No tax | No impact |
| `EXPORTOUTPUT` | Export sales (GST-free) | Adds to G2 |

### Common GST Misclassification Issues
- GST-free items coded with tax amount (QualityIssue: INVALID_GST_CODE)
- Input-taxed items claiming GST credits (blocked by quality scoring)
- Capital vs non-capital purchase distinction (G10 vs G11)
- Export sales not coded as EXPORTOUTPUT (missing G2 credits)

---

## Legislation Referenced in Knowledge Base

### Primary Tax Acts
| Act | Short Name | Key Topics |
|-----|------------|------------|
| Income Tax Assessment Act 1997 | ITAA 1997 | Income tax, CGT, deductions, depreciation |
| Income Tax Assessment Act 1936 | ITAA 1936 | Division 7A (loans), trusts, international |
| A New Tax System (Goods and Services Tax) Act 1999 | GST Act | GST rules, taxable supplies, input tax credits |
| Fringe Benefits Tax Assessment Act 1986 | FBT Act | FBT categories, exemptions, reporting |
| Taxation Administration Act 1953 | TAA 1953 | Penalties, interest, rulings, objections |
| Superannuation Guarantee (Administration) Act 1992 | SG Act | Super guarantee rate, due dates, penalties |

### ATO Ruling Types
| Type | Prefix | Purpose |
|------|--------|---------|
| Taxation Ruling | TR | Binding interpretive guidance on tax law |
| GST Ruling | GSTR | GST-specific binding guidance |
| Taxation Determination | TD | Short-form binding ruling on specific issue |
| Practical Compliance Guideline | PCG | ATO compliance approach (not legally binding) |
| Law Companion Ruling | LCR | Guidance on new or amended legislation |

### Court Hierarchy (for Case Law)
| Code | Court | Authority Level |
|------|-------|-----------------|
| HCA | High Court of Australia | Highest - binding on all courts |
| FCAFC | Federal Court Full Court | Binding on Federal Court, persuasive otherwise |
| FCA | Federal Court of Australia | Persuasive |
| AATA | Administrative Appeals Tribunal | Not binding, indicates ATO practice |

---

## Superannuation (Super)

### Superannuation Guarantee
- **Rate**: 12% (from 1 July 2025; was 11.5% from 1 July 2024)
- **Due Dates**: 28 days after each quarter end (28 Oct, 28 Jan, 28 Apr, 28 Jul)
- **Penalty for Late Payment**: Super Guarantee Charge (SGC) = missed super + interest (10% pa) + admin fee ($20/employee). Not tax deductible.
- **Clairo Mapping**: XeroPayRun tracks `total_super`. Quality scoring flags MISSING_PAYROLL and INCOMPLETE_PAYROLL issues.

---

## Instant Asset Write-Off

- **Threshold**: $20,000 per asset for businesses with aggregated turnover < $10M (2024-25).
- **Eligibility**: Asset must be first used or installed ready for use in the relevant FY.
- **Clairo Mapping**: XeroAsset entities flagged by depreciation analysis agent. `purchase_price` compared to threshold. Assets with `tax_depreciation_method` = FullDepreciation indicate existing write-offs.

---

## Division 7A (Loans from Private Companies)

- **Definition**: Tax provisions preventing private company profits being distributed to shareholders/associates tax-free through loans, payments, or debt forgiveness.
- **Key Rules**: Loans must be repaid or placed on compliant loan agreement by the earlier of the lodgement day for the company's tax return or the actual lodgement date.
- **Clairo Mapping**: Knowledge base contains ATO guidance. AI agents can identify potential Division 7A issues from transaction patterns (loans to directors/shareholders visible in XeroJournal entries).

---

## Key Thresholds

| Threshold | Value | Impact |
|-----------|-------|--------|
| GST registration | $75,000 annual turnover | Must register for GST |
| GST registration (non-profit) | $150,000 annual turnover | Must register for GST |
| Monthly BAS reporting | $20M+ annual turnover | Must report monthly |
| Mandatory monthly reporting | Poor compliance history (from Apr 2025) | Forced to monthly |
| Instant asset write-off | $20,000 per asset | Full deduction in year of purchase |
| Small business entity | < $10M aggregated turnover | Access to small business concessions |
| STP Phase 2 | All employers | Required since 1 Jan 2022 |
| Super guarantee rate | 12% (from 1 Jul 2025) | Employer obligation |
| Late BAS penalty | $313 per 28-day period | Up to 5 periods ($1,565 max) |
