# Clairo — Launch Readiness: Business & Operations

> Items that need to be done outside the codebase — legal, accounts, vendor setup, people tasks.

---

## 1. Legal Documents (Draft & Review)

### Get These Written (Lawyer or Template + Legal Review)
- [ ] Terms of Service — SaaS subscription terms, acceptable use, liability limitations, termination, IP ownership, AI-generated output ownership
- [ ] Privacy Policy — Australian Privacy Act 1988 compliant, covering the 13 APPs
- [ ] Acceptable Use Policy — what users can and can't do on the platform
- [ ] Service Level Agreement — uptime commitment, support response times, remedies for breach
- [ ] Cookie Policy — what cookies/tracking are used and why
- [ ] Data Retention & Deletion Policy — how long data is kept, how users request deletion

### Specific Clauses to Nail Down
- [ ] AI disclaimer language — signed off by legal ("decision support for registered tax agents, not tax advice")
- [ ] Cross-border data transfer disclosure — Anthropic, Pinecone, Voyage AI, Clerk are US-based; privacy policy must disclose this
- [ ] Third-party sub-processor list — Xero, Clerk, Anthropic, Pinecone, Resend, Stripe, Voyage AI, MinIO/hosting provider
- [ ] Intellectual property — clarify who owns client data, who owns AI outputs, what Clairo retains
- [ ] Australian Consumer Law (ACL) — ensure ToS doesn't exclude mandatory consumer guarantees

### Regulatory
- [ ] **TPB review** — get legal confirmation that Clairo does NOT constitute a "tax agent service" under TASA 2009
- [ ] Confirm that registered tax agents using Clairo remain personally responsible for all lodgements and advice
- [ ] **Notifiable Data Breaches (NDB)** — document your internal process for identifying, assessing, and reporting eligible data breaches to the OAIC within 30 days

---

## 2. Business Registration & Finance

- [ ] ABN registered and active (needed for footer, invoices, Stripe)
- [ ] Business name registered with ASIC (if trading as "Clairo" and it differs from the entity name)
- [ ] Domain name(s) secured — clairo.com.au, clairo.au, etc.
- [ ] Business bank account set up
- [ ] Stripe account created, verified, and connected to bank account
- [ ] GST registration — if turnover will exceed $75k, register for GST (affects subscription pricing)
- [ ] Accounting/bookkeeping set up for Clairo itself (Xero for your own books?)
- [ ] ABN Lookup / business registry listing is accurate and public

---

## 3. Insurance

- [ ] Professional indemnity insurance — covers AI-generated advice/outputs used by accountants
- [ ] Public liability insurance
- [ ] Cyber liability insurance — covers data breach response costs, especially given you hold financial data

---

## 4. Vendor & Third-Party Accounts

### Confirm Active and Production-Ready
- [ ] **Stripe** — live mode enabled, webhook signing secret set, tax rates configured
- [ ] **Clerk** — production instance, custom domain, MFA settings, branding applied
- [ ] **Resend** — production domain verified, sending limits adequate for beta
- [ ] **Anthropic** — production API key, usage limits/billing reviewed, rate limits adequate
- [ ] **Voyage AI** — production API key, billing reviewed
- [ ] **Pinecone** — production index (`clairo-knowledge`), billing tier adequate
- [ ] **Xero** — app listing status (private app for now? partner app later?), OAuth credentials for production
- [ ] **Hosting provider** — production tier, region (Sydney preferred for latency + data residency), auto-scaling if needed
- [ ] **Domain & DNS** — production domain pointing to hosting, SSL cert auto-renewal

### Vendor Agreements
- [ ] Review Anthropic's usage policies — confirm your use case (B2B tax tool) is within their acceptable use
- [ ] Review Xero's partner program terms — confirm you can use their API commercially at this scale
- [ ] Data Processing Agreements (DPAs) with key sub-processors if required by your privacy policy

---

## 5. Support & Communication Setup

- [ ] Support email created (e.g., support@clairo.com.au) and monitored
- [ ] Support process documented internally — who responds, SLA targets, escalation path
- [ ] Status page set up (e.g., Instatus, BetterUptime) — even a basic one for beta
- [ ] Onboarding email sequence drafted — welcome, getting started guide, tips & tricks (to be sent via Resend)
- [ ] Knowledge base / FAQ content written (doesn't need to be fancy — can be a page on the landing site)

---

## 6. Pricing & Commercial

- [ ] Pricing model finalised — per practice/month? Per client? Tiered?
- [ ] Pricing communicated clearly (landing page or during onboarding)
- [ ] Alpha terms — confirm Unni & Vik are not charged during alpha
- [ ] Beta pricing — any discount for early adopters? How long does beta pricing last?
- [ ] Refund/cancellation policy written and included in ToS

---

## 7. Alpha Prep — Unni & Vik (Week of 6 April)

- [ ] Unni briefed on what to test, what's in scope, known limitations
- [ ] Vik briefed on what to test, what's in scope, known limitations
- [ ] Feedback collection method agreed — shared doc? Slack channel? WhatsApp group? In-app?
- [ ] Daily or regular check-in cadence agreed for alpha week
- [ ] Known issues / limitations documented in a simple one-pager to share with them
- [ ] Rollback plan discussed — what happens if something critical breaks during testing?
- [ ] Written consent from Unni & Vik to use their real client data during alpha (even informally)

---

## 8. Beta Launch Prep (Post Alpha)

- [ ] Beta customer list of 10 practices identified and contacted
- [ ] Beta onboarding approach decided — self-serve signup or white-glove onboarding calls?
- [ ] Beta terms documented — any feature limitations? "Beta" label in the app?
- [ ] Announcement prepared — email to beta list, landing page update
- [ ] Testimonial/case study agreement with Unni & Vik (for use on landing page post-alpha)
- [ ] Feedback loop for beta customers — how do they report issues, request features?

---

## 9. Team Readiness

- [ ] Team briefed on launch timeline and responsibilities
- [ ] On-call rotation or point-of-contact for production issues during alpha/beta
- [ ] Incident response process — who gets paged, how do you communicate with affected customers?
- [ ] Internal demo / dry run of the full BAS and tax planning flows before handing to Unni & Vik
