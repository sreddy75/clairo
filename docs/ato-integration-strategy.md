# ATO Integration Strategy — Research & Options

> **Last updated**: 2026-03-10
> **Status**: Research complete, action required
> **Author**: KR8IT / Clairo team

## Executive Summary

Direct ATO integration (lodgment, correspondence, account data) is a key differentiator for Clairo. The ATO channels all machine-to-machine integration through **SBR2** (Standard Business Reporting v2) — a complex protocol built on ebMS 3.0 AS4 + XBRL. There is no modern REST API for BAS lodgment.

Four paths exist to get ATO connectivity. This document evaluates each with costs, timelines, trade-offs, and provider contact details.

---

## The Problem

BAS/Activity Statement lodgment is **SBR2-only**. The ATO's newer REST API Portal (apiportal.ato.gov.au) currently offers only 5 simple lookup services — none for core lodgment. Every path to ATO integration requires building or renting SBR2 capability.

### What We Need from the ATO

| Capability | Priority | SBR2 Required? |
|-----------|----------|----------------|
| BAS/IAS lodgment | P0 | Yes |
| Lodgment status queries | P0 | Yes |
| ATO client communications | P1 | Yes |
| Income tax account data | P1 | Yes |
| Outstanding lodgment list | P1 | Yes |
| Tax return lodgment | P2 | Yes |
| STP lodgment | P2 | Yes |
| Pre-fill data retrieval | P2 | Yes |

---

## Path A: Intermediary DSP Partner API

Use an existing DSP's REST API to lodge through their certified SBR2 connection. Your software calls their API; they handle all SBR2/ebMS3/XBRL complexity.

**Timeline**: 1-3 months integration work
**DSP registration required**: No
**SBR2 knowledge required**: No

### Provider: GovReports (Primary Option)

GovReports is the **1st ATO Certified Cloud SBR App** (since 2010) and the only provider offering a white-label Partner API for third-party ATO lodgment. Used by PwC, EY, CumulusTax, TaxToday, TaxReturn.com.au.

| Detail | Info |
|--------|------|
| **Website** | [govreports.com.au](https://www.govreports.com.au) |
| **API page** | [govreports.com.au/api](https://www.govreports.com.au/api/index.html) |
| **Phone (general)** | 1300 652 590 |
| **Email (general)** | info@govreports.com.au |
| **ABN** | 84 145 978 418 |
| **API type** | RESTful, OAuth 2.0, JSON/XML |
| **Token expiry** | 20 minutes |
| **Sandbox docs** | [sandbox-devapi.govreports.com.au/swagger](https://sandbox-devapi.govreports.com.au/swagger/index.html) |

**Our contact**: Tiana Tran
| Detail | Info |
|--------|------|
| **Name** | Tiana Tran |
| **Email** | tiana@govreports.com.au |
| **Mobile** | 0403 333 880 |
| **Phone** | 02 8677 9669 |
| **Address** | PO Box 8413, Parramatta |

**Status of conversations** (as of Jan 2026): Initial call completed. Tiana confirmed Developer API is free, end-users need GovReports retail subscription. Partner API pricing not yet discussed — follow up needed.

#### API Tiers

| Feature | Developer API | Partner API |
|---------|---------------|-------------|
| Requires end-user GovReports subscription | Yes | **No** |
| Lodgments | Per subscription limit | **Unlimited** |
| White-label (GovReports hidden) | No | **Yes** |
| Activity Statements (BAS/IAS) | Yes | Yes |
| TFND, SMSFAR, PAYG | Yes | Yes |
| STP, Tax Returns, TPAR, FBT | No | **Yes** |
| ATO Online Services (read) | No | **Yes** |
| Sandbox | Yes | Yes |

#### ATO Online Services Endpoints (Partner API)

- Lodgement List (outstanding/completed)
- Activity Statement Summary Report
- Income Tax Account
- ATO Client Communication
- Client Update Services

#### Pricing

| Tier | Cost | Catch |
|------|------|-------|
| **Developer API** | **Free** (confirmed by Tiana, Jan 2026) | End-users must have a GovReports retail subscription |
| **Partner API** | ~$30K/yr (unconfirmed, industry estimate) | Custom negotiation — not yet discussed with Tiana |

#### GovReports Retail Subscription Pricing (monthly, billed annually, +GST)

**Tax Agents:**

| Plan | Price | Client Limit |
|------|-------|-------------|
| Starter (NEW) | $53/mo | 50 active clients |
| Growing | $117/mo | 200 active clients |
| Professional | $294/mo | Unlimited clients |
| On Demand | $29/mo | Per-lodgment fee basis |

**BAS Agents:**

| Plan | Price | Client Limit |
|------|-------|-------------|
| Starter (NEW) | $44/mo | 15 active clients |
| Professional | $78/mo | Unlimited clients |
| On Demand | $19/mo | Per-lodgment fee basis |
| Additional users | $7/mo each | |

**Businesses (self-lodging):**

| Plan | Price | Notes |
|------|-------|-------|
| Business On Demand | $12/mo | AS, CTR, FBT, STP, TFND, TPAR + per-lodgment fee |
| STP Reporting | $9/mo | STP only |
| Business Ledger | $12.50/mo | Micro/small business ledger |
| Additional users | $8.17/mo | |

All plans are annual licence period. Free trials available (7 or 30 days depending on tier).

#### Developer API + Pass-Through Viability Analysis

With the Developer API being **free** and retail subscriptions being low-cost, the pass-through model is highly viable:

| Practice Type | Likely GovReports Plan | Cost/yr | Per Client/mo | Assessment |
|---------------|----------------------|---------|---------------|------------|
| Small BAS agent (15 clients) | BAS Starter | $528/yr | ~$2.93 | Trivial vs BAS fees charged |
| Mid BAS agent (50+ clients) | BAS Professional | $936/yr | <$1.56 | Very cheap |
| Small tax agent (50 clients) | Tax Starter | $636/yr | ~$1.06 | Negligible |
| Growing tax agent (200 clients) | Tax Growing | $1,404/yr | ~$0.59 | Rounding error |
| Large practice (unlimited) | Tax Professional | $3,528/yr | Pennies | No-brainer |

**Key insight**: Practices charge $500-2,000+ per BAS return. A $44-294/mo GovReports subscription for direct ATO connectivity is noise. Accountants already pay for lodgment tools — this is table stakes, not a hard sell.

#### Packaging Options for Clairo

**Option 1: Transparent pass-through (RECOMMENDED for MVP)**
- "Connect your GovReports account to enable direct ATO lodgment"
- Accountant signs up for GovReports directly ($44-294/mo depending on practice size)
- Clairo integrates via free Developer API
- **Zero cost to Clairo**, zero negotiation needed, ship immediately

**Option 2: Bundled add-on with markup (future)**
- Clairo resells as "ATO Direct Connect" add-on at $49-149/mo
- Negotiate bulk/reseller rate with GovReports below retail
- Margin opportunity + cleaner UX (single bill)

**Option 3: Value-add tier gate (future)**
- Include ATO lodgment only in Clairo Professional/Enterprise tiers
- GovReports cost absorbed into tier pricing
- Justifies premium subscription price

#### Recommendation

**Start with Option 1** (transparent pass-through + free Developer API). Zero cost, zero risk, fast to market. Upgrade to Option 2/3 once volume justifies negotiating a reseller arrangement with GovReports.

**Developer API limitations to accept for MVP**: GovReports branding visible, limited to BAS/IAS + TFND + SMSFAR + PAYG forms (no tax returns or STP), no ATO Online Services read access. These are acceptable — BAS/IAS lodgment is the P0 use case.

### Provider: LodgeiT (Limited Option)

ATO Tier 1 DSP since 2011, ISO 27001 certified, strong Xero integration. However, **no public developer API** for third-party integration confirmed.

| Detail | Info |
|--------|------|
| **Website** | [lodgeit.net.au](https://lodgeit.net.au/) |
| **Phone** | 1300 365 818 |
| **Email** | support@lodgeit.net.au |
| **Pricing (their product)** | BAS free, tax returns from $40/lodgment |
| **API for third parties** | Not confirmed — partnership discussion required |

#### Assessment

Would require a custom partnership arrangement. No evidence of an existing partner program. Lower priority than GovReports unless they offer significantly better terms.

---

## Path B: DSP Registration + SBR2 Gateway

Register directly as a DSP with the ATO (free), then use a third-party gateway to handle the ebMS3/AS4 transport protocol. You build the business logic and XBRL message construction; the gateway handles the hard transport layer.

**Timeline**: 6-12 months (DSP registration + gateway integration + EVTE testing)
**DSP registration required**: Yes
**SBR2 knowledge required**: Partial (XBRL message construction, not transport)
**ATO fees**: None (registration and EVTE access are free)

### DSP Registration Process

1. Set up Digital ID (myID) + configure authorisation in RAM
2. Register on "Online Services for DSPs" — grants EVTE (test environment) access
3. Contact ATO Digital Partnership Office (DPO) — assigned onboarding contact
4. Complete DSP Operational Security Framework (OSF) questionnaire
5. Build and test in EVTE (can run parallel with OSF)
6. Pass conformance testing (Production Verification + Extended Conformance)
7. Apply for whitelisting
8. Go live — listed on ATO Product Register

**ATO DSP resources**:
- Software Developers Portal: [softwaredevelopers.ato.gov.au](https://softwaredevelopers.ato.gov.au/)
- Getting Started: [softwaredevelopers.ato.gov.au/getting_started](https://softwaredevelopers.ato.gov.au/getting_started)
- DSP Requirements: [softwaredevelopers.ato.gov.au/RequirementsforDSPs](https://softwaredevelopers.ato.gov.au/RequirementsforDSPs)
- DSP Service Desk: Raise ticket via Online Services for DSPs portal

### DSP Operational Security Framework (OSF)

Two compliance paths:

| Path | Requirement | Cost | Renewal |
|------|-------------|------|---------|
| Self-assessment | Questionnaire against Essential Eight or ISO 27001 | Internal effort only | Every 2 years |
| Independent certification | iRAP or ISO/IEC 27001 audit | $15K-$50K+/yr | Annual |

**Recommendation**: Self-assessment against Essential Eight for initial registration. Upgrade to ISO 27001 certification later if needed for enterprise credibility.

Key security requirements: MFA, audit logging, entity validation, TLS 1.3 (mandatory from Jan 2026), encryption in transit and at rest.

### SBR2 Gateway Providers

These providers handle the ebMS3/AS4 transport complexity so you don't have to build it from scratch. **You still need to be a registered DSP.**

#### MessageXchange

Managed SBR2 gateway service. ISO 27001 certified. Direct ATO connection.

| Detail | Info |
|--------|------|
| **Website** | [home.messagexchange.com](https://home.messagexchange.com/) |
| **SBR2 product page** | [home.messagexchange.com/products/standard-business-reporting-sbr2/](https://home.messagexchange.com/products/standard-business-reporting-sbr2/) |
| **Phone** | +61 2 8920 1640 |
| **Email** | info@messagexchange.com |
| **Address** | Level 10, 1 Margaret Street, Sydney NSW 2000 |
| **Type** | Managed cloud gateway |
| **Certifications** | ISO 27001 |
| **Pricing** | Not published — contact for quote |

**Capabilities**: Handles full ebMS3/AS4 protocol including message routing, security, acknowledgments, and retry logic. Supports all ATO SBR2 services.

#### Oban Solutions

SBR2 gateway with RESTful API library option.

| Detail | Info |
|--------|------|
| **Website** | [obansolutions.com.au](https://www.obansolutions.com.au/) |
| **SBR2 product page** | [obansolutions.com.au/sbr2_gateway](https://www.obansolutions.com.au/sbr2_gateway) |
| **Phone** | 1300 414 330 |
| **Email** | Contact via website |
| **Type** | Gateway with REST API wrapper |
| **Pricing** | Not published — contact for quote |

**Capabilities**: RESTful API library, command-line interface, or on-premises AS4 client. Supports FVS, SuperTICK, PAYEVNT, Activity Statements, and more. Good option if you want a REST-like interface over SBR2.

#### Layer Security (LS-ATO)

Embeddable ebMS3/AS4 client — lightweight binary you integrate directly.

| Detail | Info |
|--------|------|
| **Website** | [layersecurity.com](https://layersecurity.com/) |
| **Product page** | [layersecurity.com/products/ls-ato](https://layersecurity.com/products/ls-ato) |
| **Email** | Contact via website |
| **Type** | Embeddable C binary (6MB) |
| **Testing** | Free copy available for testing |
| **Pricing** | Not published — contact for quote |

**Capabilities**: All ATO services (IITR, FBT, Activity Statements, STP, TPAR, TFND, etc.). Command-line interface. Very lightweight — can be embedded in your backend infrastructure. Good option for maximum control with minimal dependency.

#### OZEDI (OZ-ATO)

Embeddable ebMS3/AS4 client — direct ATO connection with no third-party intermediary.

| Detail | Info |
|--------|------|
| **Website** | [ozedi.com.au](https://ozedi.com.au/) |
| **SBR product page** | [ozedi.com.au/standard-business-reporting/](https://ozedi.com.au/standard-business-reporting/) |
| **Phone** | 1300 769 943 |
| **Email** | Contact via website |
| **Address** | Brisbane, QLD |
| **Type** | Embeddable client |
| **Testing** | Free copy available for testing |
| **Pricing** | Not published — contact for quote |

**Capabilities**: Direct ATO connection (no third party involved in the data path). Supports SBR2 message construction and transport. Good option if data sovereignty / no-intermediary is important.

#### Fujitsu ebMS3 Client

Enterprise-grade AS4 messaging platform.

| Detail | Info |
|--------|------|
| **Website** | [fujitsu.com/au](https://www.fujitsu.com/au/) |
| **Product page** | [fujitsu.com/au/products/infrastructure-management/middleware/ebms3-messenger.html](https://www.fujitsu.com/au/products/infrastructure-management/middleware/ebms3-messenger.html) |
| **Phone** | 1800 386 487 (Fujitsu AU) |
| **Type** | Enterprise middleware |
| **Pricing** | Enterprise pricing — likely highest cost option |

**Assessment**: Overkill for a startup. Better suited for large enterprises. Include in evaluation only if other options fall through.

### Path B Cost Estimate

| Item | Estimate |
|------|----------|
| ATO DSP registration | Free |
| EVTE access | Free |
| DSP OSF self-assessment | Internal effort |
| SBR2 gateway license | Unknown (expect $5K-$20K/yr based on market) |
| XBRL message construction engineering | 2-4 months dev time |
| EVTE conformance testing | 1-2 months |
| **Total timeline** | **6-12 months** |

---

## Path C: Direct DSP with Full SBR2 Build

Build everything from scratch — ebMS3/AS4 transport, XBRL message construction, SAML authentication, the lot.

**Timeline**: 6+ months dedicated engineering
**DSP registration required**: Yes
**SBR2 knowledge required**: Deep expertise required

### Technical Requirements

| Component | Detail |
|-----------|--------|
| Protocol | ebMS 3.0 AS4 (OASIS standard + ATO extensions) |
| Authentication | SAML token + M2M machine credential (from RAM) |
| Transport | TLS 1.3 (mandatory from Jan 2026) |
| Message format | XBRL body wrapped in ebMS3/AS4 envelope |
| Message patterns | One-Way PUSH and One-Way Selective PULL |
| Cloud auth (CAA) | DSP holds machine credential, businesses authorise in RAM |

### Technical Resources

- SBR2 specifications: [sbr.gov.au](https://www.sbr.gov.au/)
- ebMS3 artefacts: [sbr.gov.au/sbr-ebms3-webservices-artefacts](https://www.sbr.gov.au/sbr-ebms3-webservices-artefacts)
- ATO ebMS3 Implementation Guide: [sbr.gov.au (docx)](https://www.sbr.gov.au/sites/default/files/2023-11/ATO_ebMS3_Implementation_Guide.docx)
- CAA documentation: [softwaredevelopers.ato.gov.au/Cloud_Software_Authentication_and_Authorisation](https://softwaredevelopers.ato.gov.au/Cloud_Software_Authentication_and_Authorisation)
- M2M authentication: [softwaredevelopers.ato.gov.au/M2M](https://softwaredevelopers.ato.gov.au/M2M)

### Assessment

Developer community consensus (Whirlpool forums, DSPANZ discussions): "The SBR stuff is a nightmare" and "there simply isn't the time to go developing your own client." Only viable at significant scale where gateway licensing costs exceed engineering investment. **Not recommended for Clairo at current stage.**

---

## Path D: Wait for ATO API Modernization

The ATO has a Digital Services Gateway (DSG) modernization initiative ($6.7M contract) moving toward REST/JSON APIs. However, BAS lodgment is **not yet available** on this platform.

### Current ATO API Portal Services (apiportal.ato.gov.au)

| API | Status | Relevant to Clairo? |
|-----|--------|---------------------|
| Health Check API | Active | No |
| SMSF Alias Lookup API | Active | No |
| Stapled Super Fund API | Active | No |
| OAuth Dynamic Client Registration | Active | Infrastructure only |
| Global and Domestic Minimum Tax | Proposed | No |

**No public timeline** exists for when BAS lodgment will move to REST/JSON. Could be years.

### Assessment

Monitor only. Not a viable near-term strategy. Check the [ATO API Portal](https://apiportal.ato.gov.au/api-products) and [DARG meeting notes](https://softwaredevelopers.ato.gov.au/DARG20231114) quarterly for updates.

---

## Comparison Matrix

| Criteria | Path A: GovReports | Path B: DSP + Gateway | Path C: Full DIY | Path D: Wait |
|----------|--------------------|-----------------------|-------------------|-------------|
| **Time to market** | 1-3 months | 6-12 months | 6-12+ months | Unknown (years?) |
| **Engineering effort** | Low (REST API) | Medium (XBRL + gateway) | Very high (full SBR2) | None |
| **Annual cost** | **$0 (Dev API)** / ~$30K (Partner API) | Gateway license + eng | Engineering only | $0 |
| **Vendor lock-in** | High (near-monopoly) | Low (swap gateways) | None | N/A |
| **Control** | Low | High | Full | N/A |
| **DSP registration** | Not required | Required | Required | N/A |
| **Form coverage** | Full (Partner API) | What you build | What you build | N/A |
| **Risk** | Pricing, dependency | Engineering complexity | Extreme complexity | May never happen |

---

## Recommended Strategy

### Phase 1: Ship with Developer API (Now → 3 months)

**Action**: Build ATO lodgment using free Developer API + pass-through model.

- Accountants connect their own GovReports account (retail subscription: $44-294/mo)
- Clairo uses free Developer API — **zero cost to us**
- Covers BAS/IAS lodgment (P0 use case), TFND, SMSFAR, PAYG
- Explore sandbox docs at sandbox-devapi.govreports.com.au/swagger
- Goal: Direct ATO lodgment working in Clairo, validated with real users

### Phase 2: Expand Coverage (3-6 months)

**Action**: Negotiate Partner API or reseller arrangement for fuller coverage.

- Once volume proves demand, approach Tiana about Partner API / reseller pricing
- Partner API adds: tax returns, STP, TPAR, FBT, ATO Online Services read access
- Explore bundling as Clairo add-on (Option 2) for cleaner UX and margin
- In parallel: register as DSP (free) and get SBR2 gateway quotes for leverage

### Phase 3: Reduce Dependency (6-18 months, if justified)

**Action**: Evaluate direct DSP path based on economics.

- Get quotes from MessageXchange, Oban, Layer Security, OZEDI
- If gateway + engineering is cheaper than Partner API, build direct path
- Run both paths in parallel during transition

### Phase 4: Long-term Independence (18+ months)

- Complete direct DSP path if economics justify it
- Monitor ATO API Portal for REST-based lodgment services
- Consider DSPANZ membership for industry advocacy and early access to roadmap

---

## Industry Body

### DSPANZ (Digital Service Providers Australia New Zealand)

| Detail | Info |
|--------|------|
| **Website** | [dspanz.org](https://www.dspanz.org/) |
| **Member directory** | [dspanz.org/member-directory](https://dspanz.org/member-directory) |
| **Membership** | 90+ members, optional but valuable for networking |
| **Value** | Industry advocacy, ATO roadmap visibility, peer networking |

---

## Action Items

### Phase 1: Developer API MVP (NOW)
- [x] Initial call with Tiana Tran — confirmed Developer API is free, sandbox link received
- [x] Check GovReports retail subscription pricing — captured (Tax Agent $53-294/mo, BAS Agent $44-78/mo)
- [ ] Explore sandbox API docs at sandbox-devapi.govreports.com.au/swagger
- [ ] Sign up for Developer API (as instructed by Tiana: "sign up for the API and select Developer API")
- [ ] Map GovReports API data model to Clairo BAS schema
- [ ] Build GovReports integration module (OAuth flow, lodge BAS, status sync)
- [ ] Test end-to-end BAS lodgment in sandbox

### Phase 2: Expand (after MVP validated)
- [ ] Follow up with Tiana on **Partner API pricing** — use gateway quotes as leverage
- [ ] Request Partner API sandbox access
- [ ] Evaluate bundled add-on pricing model (Option 2)

### Phase 3: Gateway Quotes (for leverage + independence)
- [ ] Contact MessageXchange (+61 2 8920 1640 / info@messagexchange.com) — request SBR2 gateway pricing
- [ ] Contact Oban Solutions (1300 414 330) — request SBR2 gateway pricing
- [ ] Contact Layer Security (via website) — request LS-ATO pricing and free test copy
- [ ] Contact OZEDI (1300 769 943) — request OZ-ATO pricing and free test copy

### Background
- [ ] Register on ATO Online Services for DSPs portal (free)
- [ ] Join DSPANZ for industry visibility

---

## References

### ATO Official Resources

- [ATO Software Developers Portal](https://softwaredevelopers.ato.gov.au/)
- [Getting Started as a DSP](https://softwaredevelopers.ato.gov.au/getting_started)
- [DSP Requirements](https://softwaredevelopers.ato.gov.au/RequirementsforDSPs)
- [DSP Operational Security Framework](https://softwaredevelopers.ato.gov.au/operational_framework)
- [ATO API Portal](https://apiportal.ato.gov.au/)
- [Practitioner Lodgment Service](https://www.ato.gov.au/tax-and-super-professionals/digital-services/practitioner-lodgment-service)
- [PLS Supported Forms](https://www.ato.gov.au/tax-and-super-professionals/digital-services/practitioner-lodgment-service/practitioner-lodgment-service-user-guide/lodging-forms-and-schedules/forms-supported-by-the-pls)
- [Cloud Authentication & Authorisation (CAA)](https://softwaredevelopers.ato.gov.au/Cloud_Software_Authentication_and_Authorisation)
- [M2M Authentication](https://softwaredevelopers.ato.gov.au/M2M)
- [Sending Service Providers](https://softwaredevelopers.ato.gov.au/SSPs)
- [ATO Online Services for Agents](https://www.ato.gov.au/tax-and-super-professionals/digital-services/online-services-for-agents)

### SBR Resources

- [SBR.gov.au](https://www.sbr.gov.au/)
- [SBR Activity Statements](https://www.sbr.gov.au/digital-service-providers/developer-tools/australian-taxation-office-ato/activity-statements)
- [SBR ebMS3 Artefacts](https://www.sbr.gov.au/sbr-ebms3-webservices-artefacts)
- [ATO ebMS3 Implementation Guide (docx)](https://www.sbr.gov.au/sites/default/files/2023-11/ATO_ebMS3_Implementation_Guide.docx)

### Provider Resources

- [GovReports API](https://www.govreports.com.au/api/index.html)
- [GovReports API Brochure (PDF)](https://www.govreports.com.au/brochure/API.pdf)
- [MessageXchange SBR2](https://home.messagexchange.com/products/standard-business-reporting-sbr2/)
- [Oban Solutions SBR2 Gateway](https://www.obansolutions.com.au/sbr2_gateway)
- [Layer Security LS-ATO](https://layersecurity.com/products/ls-ato)
- [OZEDI Standard Business Reporting](https://ozedi.com.au/standard-business-reporting/)
- [Fujitsu ebMS3 Messenger](https://www.fujitsu.com/au/products/infrastructure-management/middleware/ebms3-messenger.html)
- [LodgeiT](https://lodgeit.net.au/)

### Internal Documents

- [GovReports Integration Research](/.project/planning/integrations/govreports/gov_reports.md)
- [GovReports API Brochure](/.project/planning/integrations/govreports/API.pdf)
- [ATOtrack Business Case](docs/atoTrack/ato-intel-business-case.md)
- [Gap Resolution Strategy](docs/gap%20analysis/gap-resolution-strategy.md)
- [Feasibility Analysis](docs/feasibility-analysis.md)
- [Interim Lodgement Spec](specs/011-interim-lodgement/spec.md)
