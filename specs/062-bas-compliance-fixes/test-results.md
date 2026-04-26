Spec items still failing :x:
FR-006 — W1/W2 manual entry: hint text says "enter manually" but there is no input field to do so
FR-007 — PAYG Instalment T1/T2 fields render but won't save
FR-010 — Cent precision: amounts still rounding to whole dollars
FR-017 — "How was this calculated?" link exists in insight modal but doesn't expand
FR-020 — Unreconciled warning absent (critical): Awning Scape has 116 unreconciled Xero transactions (statement $9,919 vs Xero balance $19,020). Clairo loaded full BAS figures with zero warning. Blocking prompt not appearing at all.
FR-022 — Request Client Input modal says "36 unresolved" — should say "uncoded" or "need tax code"
FR-013/015/016 — Insights: GST registration insight still appearing for registered clients; 5 variations of voided invoice insight in one session; contradictory employee count (one card says 6 employees, another says zero) in same tab

New bugs not in current spec :bug:
1 — BAS Excluded transactions wrongly flagged as uncoded
OreScope wage payments (Zac Phillpott $7,506.67, Angela Phillpott $3,818) are coded in Xero to "Wages Payable - Payroll" with tax rate BAS Excluded — a valid Xero tax code. Clairo is treating BAS Excluded as if it means no tax code and flagging them in the uncoded list. They should not appear there.
2 — Xero Payroll STP data not read for W1/W2
OreScope has full monthly STP-filed payroll in Xero (Jan, Feb, Mar 2026 all filed). Q3 wages ~$125K, PAYG withheld ~$35K. Clairo shows "No payroll data found." The Xero Payroll API does not appear to be called.3 — Quarter defaults to current quarter, not lodgement-relevant quarter
Today is 26 Apr — Q3 BAS is due 28 Apr. Clairo defaults to Q4 (in progress). Should default to the most recently completed quarter during the lodgement window (~28 days after quarter end).4 — "Could not fetch BAS data from Xero" appearing on multiple clients while figures still load
Seen on Heart of Love Foundation and Awning Scape. If figures are loading the error is misleading; if they're not the figures are wrong. Needs clarification either way.5 — Insights data pipeline disconnected from BAS data
OreScope Insights flagged "No financial activity in past 90 days" as urgent. BAS tab shows $206K Q3 sales for the same client and period. Insights is not reading from the same data source as the BAS calculation.Sent using Claude