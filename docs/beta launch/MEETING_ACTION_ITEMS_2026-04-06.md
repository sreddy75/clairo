# Clairo Team — Action Items for the Week
## Meeting: 6 April 2026

---

## Asaf — BAS Workflow & Platform Fixes

### Critical (Before Alpha Testing)
- [ ] **Unify Reject/Dismiss** — Consolidate reject and dismiss into a single "Park it" action
- [ ] **Park It Notes** — Add notes field/popup when accountant clicks Park, capture internal context
- [ ] **Push Notes to Xero** — Push captured notes/metadata to Xero API when transaction syncs
- [ ] **Client Save & Resume** — Fix client portal so clients can save progress and return later (blocker — clients can't answer everything in one session)
- [ ] **Client Link Expiry** — Verify if expiring client link issue is resolved, implement regeneration if not
- [ ] **Fix GST Tax Code Error** — Investigate invalid GST tax code status error encountered during demo
- [ ] **Fix Page Refresh State** — Fix UX issue where page loses state after sync operation

### High Priority
- [ ] **Account Code Override** — Add ability to override/change account code during transaction allocation (not just GST code)
- [ ] **Client Due Dates & Reminders** — Add due date setting for client reviews + automated reminder emails (work back from BAS deadline)
- [ ] **Rebase Client Portal** — Rebase local dev branch to include recent client portal enhancements, new email templates, resend invite
- [ ] **Clarify Adjust/Approve/Lodge UI** — Post questions about Adjust, Approve, and Lodge button flows in Slack
- [ ] **Confirm Rollout Fixes** — Share list of necessary fixes in Slack to confirm rollout readiness

---

## Vik — BAS Testing & Requirements

- [ ] **Trial BAS for 10 Clients** — Run the BAS process flow for 10 Xero clients this week
- [ ] **Structured Feedback via Cowork** — Collect and document feature feedback using the Cowork tool
- [ ] **Document Allocation Overrides** *(with Unni)* — Write up required functionality for transaction allocation: account code changes, GST code changes, splitting total amounts
- [ ] **Compile Xero Sync Requirements** — Complete list of Xero sync requirements including account code overriding and splitting figures
- [ ] **Hero Message** *(with Suren)* — Propose a powerful, non-technical hero message for the website

---

## Unni — Tax Planning Testing & Feedback

- [ ] **Trial Tax Plans** — Run extensive tax plans for multiple clients across entity types
- [ ] **Trial BAS** — Complete a couple of BAS submissions end to end
- [ ] **Document Allocation Overrides** *(with Vik)* — Write up required functionality for transaction allocation overrides
- [ ] **Pricing & Website Feedback** — Prepare thoughts on pricing structure and website messaging
- [ ] **Create Temp CLO Account** — Create another temporary CLO account to test the client whose connection was lost

---

## Suren — Platform, Infra & Business

### Platform & Code
- [ ] **Fix Unni's Login & Client Issues** — Investigate login issues and missing clients/orgs (4 orgs not visible)
- [ ] **AI Disclaimers Everywhere** — Add disclaimers to all chat/AI output locations: "AI-generated, not financial advice"
- [ ] **Create Staging Environment** — Spin up new Railway staging environment, keep current setup as production
- [ ] **Stripe Integration** — Finalise Stripe setup, define price categories, configure discounted monthly pricing for first 10 customers
- [ ] **Review Tax Analysis Automation** — Review analysis automation for tax planning steps 2 and 3
- [ ] **Share Spec Template** — Share the spec template document for requirements gathering
- [ ] **Build Feedback/Ticket Feature** — Build a simple in-app backlog management / ticket submission feature

### Business Admin
- [ ] **Legal Pages** — Finalise Terms of Service, Privacy Policy, Acceptable Use Policy on the website
- [ ] **Trademark Registration** — Register Clairo trademark
- [ ] **Bank Accounts** — Set up business bank accounts for subscription payments
- [ ] **Hero Message** *(with Vik)* — Propose the hero message for the landing page

### Landing Page
- [ ] **Rewrite Technical Copy** — Turn technical descriptions into accountant-centric language
- [ ] **Live Usage Counters** — Surface live platform numbers (connected clients, BAS prepared, tax plans created)
- [ ] **Pricing Section** — Add pricing or "contact us for pricing" to the landing page

---

## Key Decisions Made

- **Pricing model for beta:** Simple discounted monthly pricing for first 10 customers. Outcome-based pricing to be explored later.
- **BAS lodgement status:** Manual "mark as lodged" field in CLO for now — no need to build ATO integration yet.
- **Deployment workflow:** Branch-based. Merge to main → deploys to production. Staging for Unni & Vik to test.
- **Non-Xero clients:** Parked for now — initial focus stays on Xero-connected clients only.
- **Teams/multi-user:** Not built yet — Vik can use shared login temporarily.
- **Infrastructure:** Stay on Railway until ~100 paying customers, then consider AWS.

---

## Feedback Highlights

> *"The base is really good... I can see the friction being taken out of the workflow. The elements and the value proposition are in place."* — Unni

> *Unni would tell other accountants they let go of $20,000 worth of subscriptions for this product because it offers unique capabilities beyond competitors.*
