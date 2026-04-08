#!/usr/bin/env bash
# Seed pending tax code suggestions to trigger the client review workflow on the BAS tab.
# Usage: ./scripts/seed_client_review.sh [connection_id]
# Default connection_id: 36705e9d-3de9-4174-b792-c7f6ffd29f17 (Demo Company AU)

set -euo pipefail

CONNECTION_ID="${1:-482c7e5a-e7cd-4bbb-896e-e36499c193d6}"
CONTAINER="clairo-postgres"
DB_USER="clairo"
DB_NAME="clairo"

psql() {
  docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" "$@"
}

echo "→ Looking up tenant and most recent BAS session for connection $CONNECTION_ID..."

read -r TENANT_ID ORG_NAME < <(psql -tAc "
  SELECT tenant_id, organization_name
  FROM xero_connections
  WHERE id = '$CONNECTION_ID';
" | tr '|' ' ')

if [[ -z "$TENANT_ID" ]]; then
  echo "✗ Connection not found: $CONNECTION_ID" >&2
  exit 1
fi

echo "  Tenant:  $TENANT_ID ($ORG_NAME)"

read -r SESSION_ID PERIOD < <(psql -tAc "
  SET app.current_tenant_id = '$TENANT_ID';
  SELECT bs.id, bp.fy_year || ' Q' || bp.quarter
  FROM bas_sessions bs
  JOIN bas_periods bp ON bp.id = bs.period_id
  WHERE bp.connection_id = '$CONNECTION_ID'
  ORDER BY bp.start_date DESC
  LIMIT 1;
" | grep -v '^SET$' | tr '|' ' ')

if [[ -z "$SESSION_ID" ]]; then
  echo "✗ No BAS session found for this connection." >&2
  exit 1
fi

echo "  Session: $SESSION_ID ($PERIOD)"

echo "→ Fetching 3 recent unreconciled AUTHORISED bank transactions..."

TRANSACTIONS=$(psql -tAc "
  SET app.current_tenant_id = '$TENANT_ID';
  SELECT id, total_amount, reference, transaction_date
  FROM xero_bank_transactions
  WHERE connection_id = '$CONNECTION_ID'
    AND status = 'AUTHORISED'
    AND (is_reconciled = false OR is_reconciled IS NULL)
  ORDER BY transaction_date DESC
  LIMIT 3;
" | grep -v '^SET$')

if [[ -z "$TRANSACTIONS" ]]; then
  echo "✗ No AUTHORISED transactions found for this connection." >&2
  exit 1
fi

echo "→ Cancelling any active classification requests for this session..."
psql -c "
  UPDATE classification_requests
  SET status = 'cancelled', updated_at = now()
  WHERE session_id = '$SESSION_ID'
    AND status NOT IN ('cancelled', 'expired', 'completed');
" > /dev/null

echo "→ Inserting (or resetting) pending tax code suggestions..."

DESCRIPTIONS=(
  "Vague transfer — capital expense or loan repayment unclear"
  "Generic payment — description too vague to confirm GST treatment"
  "Could be entertainment (no GST credit) or office supplies — needs clarification"
)
ACCOUNTS=("461|Other Expenses" "489|Sundry Expenses" "420|Entertainment")
BASES=(
  "Wire transfer with no vendor details"
  "No description provided on transaction"
  "Category ambiguous — entertainment vs operating expense"
)
# original_tax_type: what's actually in Xero (INPUT = standard GST on purchases)
# suggested_tax_type: what the AI proposes to change it TO (BASEXCLUDED = GST-free)
ORIGINAL_TAX_TYPE="INPUT"
SUGGESTED_TAX_TYPE="BASEXCLUDED"

i=0
while IFS='|' read -r TX_ID AMOUNT REF TX_DATE; do
  TX_ID="${TX_ID// /}"
  ACCOUNT_CODE="${ACCOUNTS[$i]%%|*}"
  ACCOUNT_NAME="${ACCOUNTS[$i]##*|}"
  BASIS="${BASES[$i]}"
  DESC="${DESCRIPTIONS[$i]}"
  DISPLAY_REF="${REF:-${DESC:0:30}}"

  psql -c "
    SET app.current_tenant_id = '$TENANT_ID';
    INSERT INTO tax_code_suggestions (
      id, tenant_id, session_id, source_type, source_id,
      line_item_index, original_tax_type, suggested_tax_type,
      confidence_score, confidence_tier, suggestion_basis,
      status, account_code, account_name, description,
      line_amount, tax_amount, transaction_date
    ) VALUES (
      gen_random_uuid(), '$TENANT_ID', '$SESSION_ID',
      'bank_transaction', '$TX_ID',
      0, '$ORIGINAL_TAX_TYPE', '$SUGGESTED_TAX_TYPE',
      $(echo "0.4 + $i * 0.05" | bc), 'low',
      '$BASIS',
      'pending', '$ACCOUNT_CODE', '$ACCOUNT_NAME', '$DISPLAY_REF',
      $AMOUNT, $(echo "scale=2; $AMOUNT / 11" | bc), '$TX_DATE'
    )
    ON CONFLICT (session_id, source_type, source_id, line_item_index)
    DO UPDATE SET status = 'pending', updated_at = now();
  " > /dev/null

  echo "  ✓ $TX_DATE  \$$AMOUNT  — $DISPLAY_REF"
  i=$(( i + 1 ))
done <<< "$TRANSACTIONS"

echo ""
echo "✓ Done. Open the BAS tab for this client — the TaxCodeResolutionPanel"
echo "  should now show a 'Send to Client' button."
echo ""
echo "  http://localhost:3000/clients/$CONNECTION_ID?tab=bas"
