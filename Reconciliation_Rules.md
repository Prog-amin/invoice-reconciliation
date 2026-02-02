# Invoice Reconciliation Rules

## Auto-Approve Criteria

An invoice can be automatically approved if ALL of the following conditions are met:

1. **Exact PO Match**: Invoice references a valid PO number that exists in the database
2. **Line Item Matching**: All invoice line items match corresponding PO line items:
   - Product descriptions match (allowing for minor variations in wording)
   - Quantities match exactly
   - Prices match within ±2% tolerance (to account for rounding)
3. **Total Variance**: Invoice total is within £5 OR 1% of PO total (whichever is smaller)
4. **Extraction Confidence**: OCR/extraction confidence score is ≥90% for all critical fields

**Output**: `"recommended_action": "auto_approve"`

---

## Flag for Review

An invoice should be flagged for human review if ANY of the following conditions are met:

1. **Price Variance**: Unit price differs by >5% but ≤15% on any line item
2. **Quantity Mismatch**: Quantity differs from PO but product matches
3. **Missing PO Reference**: Invoice has no PO number OR invalid PO number, but products can be matched to a PO in the database with >70% confidence
4. **Low Extraction Confidence**: OCR/extraction confidence score is between 70-89% for any critical field
5. **Partial Match**: Only some line items match the PO
6. **Supplier Mismatch**: Invoice supplier name differs from PO supplier (accounting for minor variations like "Ltd" vs "Limited")

**Output**: `"recommended_action": "flag_for_review"`, with detailed explanation in `discrepancies` array

---

## Escalate to Human (High Priority)

An invoice MUST be escalated immediately if ANY of the following conditions are met:

1. **Significant Price Variance**: Unit price differs by >15% on any line item
2. **No Matching PO**: Cannot match to any PO with >50% confidence
3. **Large Total Variance**: Invoice total differs from nearest matching PO by >10%
4. **Multiple Discrepancies**: 3 or more separate discrepancies detected on the same invoice
5. **Very Low Confidence**: OCR/extraction confidence score <70% for critical fields
6. **Duplicate Invoice**: Invoice number already exists in system (if tracking this)

**Output**: `"recommended_action": "escalate_to_human"`, with all issues clearly listed

---

## Matching Logic

When matching invoices to purchase orders, use this hierarchy:

### Primary Matching (Highest Priority)
1. **Exact PO Number Match**: If invoice contains valid PO number, match to that PO first
   - Confidence: 95-99% if PO exists
   - Consider it definitive unless other major discrepancies found

### Secondary Matching (Fallback)
2. **Supplier + Date Range + Product Match**: 
   - Match by supplier name (fuzzy matching acceptable, e.g., "Ltd" vs "Limited")
   - Invoice date within ±14 days of PO date
   - At least 70% of products match by description (fuzzy matching)
   - Confidence: 60-85% depending on match quality

3. **Product-Only Fuzzy Match**:
   - When no PO reference and supplier doesn't match
   - Match based solely on product descriptions
   - Requires >80% similarity across multiple items
   - Confidence: 40-70% depending on number of matching items

### Confidence Scoring Guidelines
- **>95%**: Exact PO match + all line items match + totals within tolerance
- **85-95%**: Exact PO match but minor discrepancies (small price variance, description variations)
- **70-84%**: Fuzzy match via supplier + products + dates with reasonable confidence
- **50-69%**: Product-only fuzzy match or significant uncertainties
- **<50%**: Cannot confidently match - escalate

---

## Field Extraction Requirements

The following fields MUST be extracted from each invoice:

### Critical Fields (Required)
- Invoice number
- Invoice date
- Supplier name
- Line items (description, quantity, unit price, total)
- Subtotal
- VAT amount (if applicable)
- Total amount due

### Important Fields (High Priority)
- PO reference number
- Customer/bill-to information
- Payment terms
- Currency

### Nice-to-Have Fields
- Supplier address
- Tax/VAT registration numbers
- Bank details
- Item codes/SKUs

---

## Handling Edge Cases

### Multiple Possible PO Matches
- If multiple POs could match (similar products, close dates):
  - Calculate match confidence for each
  - Present top 2-3 candidates
  - Recommend human review
  - Include reasoning for each candidate

### Partial Deliveries
- Invoice may only include subset of PO items
- Match what you can
- Flag as "partial_delivery" in metadata
- Still approve if matched items are correct

### Credit Notes
- Detect if invoice is actually a credit note (negative amounts)
- Flag separately - don't attempt normal matching
- Recommend: `"invoice_type": "credit_note", "recommended_action": "escalate_to_human"`

### Currency Mismatches
- PO in GBP, invoice in EUR/USD
- Flag immediately
- Do not attempt to auto-approve
- Recommend: `"escalate_to_human"` with currency mismatch reason

---

## Quality Thresholds

### OCR Quality Indicators
- **Good**: Clean text, proper table structure, no rotation, clear fonts
- **Acceptable**: Minor rotation (≤5°), some compression artifacts, mostly readable
- **Poor**: Heavy rotation (>5°), low resolution, significant artifacts, handwritten notes

### Confidence Scoring by Quality
| Document Quality | Base Confidence | Adjustments |
|------------------|-----------------|-------------|
| Good (clean PDF) | 90-95% | +5% if all fields present |
| Acceptable (scan) | 75-85% | -10% if critical fields unclear |
| Poor (damaged) | 50-70% | -20% if multiple fields unreadable |

---

## Expected Output Format

All agent systems must output results in this JSON structure:

```json
{
  "invoice_id": "extracted_invoice_number",
  "processing_timestamp": "2024-01-29T10:30:00Z",
  "processing_results": {
    "extraction_confidence": 0.95,
    "document_quality": "good",
    "extracted_data": {
      "invoice_number": "INV-2024-1001",
      "invoice_date": "2024-01-15",
      "supplier": "PharmaChem Supplies Ltd",
      "po_reference": "PO-2024-001",
      "currency": "GBP",
      "line_items": [
        {
          "description": "Paracetamol BP 500mg",
          "item_code": "API-001",
          "quantity": 50,
          "unit": "kg",
          "unit_price": 125.00,
          "line_total": 6250.00,
          "extraction_confidence": 0.98
        }
      ],
      "subtotal": 7977.50,
      "vat": 1595.50,
      "total": 9573.00
    },
    "matching_results": {
      "po_match_confidence": 0.98,
      "matched_po": "PO-2024-001",
      "match_method": "exact_po_reference",
      "alternative_matches": []
    },
    "discrepancies": [],
    "recommended_action": "auto_approve",
    "agent_reasoning": "Invoice extracted with high confidence (95%). Exact PO match found (PO-2024-001). All line items match exactly. Total variance: £0.00. No discrepancies detected. System recommends auto-approval."
  }
}
```

### Discrepancy Format (if any)

```json
{
  "discrepancies": [
    {
      "type": "price_mismatch",
      "severity": "high",
      "line_item_index": 0,
      "field": "unit_price",
      "invoice_value": 88.00,
      "po_value": 80.00,
      "variance_percentage": 10.0,
      "details": "Line item 1 (Ibuprofen BP 200mg): Invoice unit price £88.00 vs PO price £80.00 (10% increase)",
      "recommended_action": "flag_for_review",
      "confidence": 0.99
    },
    {
      "type": "missing_po_reference",
      "severity": "medium",
      "field": "po_reference",
      "details": "Invoice does not contain a PO reference. Fuzzy matching by supplier and products suggests PO-2024-005 (78% confidence).",
      "suggested_po": "PO-2024-005",
      "match_confidence": 0.78,
      "recommended_action": "flag_for_review"
    }
  ]
}
```

---

## Validation Checklist

Before outputting final results, agents should verify:

- [ ] All critical fields extracted or marked as missing
- [ ] Confidence scores calculated for each field
- [ ] PO matching attempted (primary and fallback methods)
- [ ] All discrepancies identified and categorized
- [ ] Severity levels assigned correctly
- [ ] Recommended action aligns with rules above
- [ ] Agent reasoning clearly explains the decision path
- [ ] JSON structure matches expected format
- [ ] No hardcoded rules - all decisions are agent-driven based on these guidelines

---

## Notes for Implementers

1. **These are guidelines, not hardcoded rules**: Your agents should reason through each case based on these principles, not implement them as rigid if/else logic.

2. **Confidence is key**: Every decision should have an associated confidence score. When in doubt, lower confidence and escalate.

3. **Explain your reasoning**: The `agent_reasoning` field should read like a human analyst's notes - clear, specific, and actionable.

4. **Handle the unexpected**: Real invoices have endless variations. Your agents should gracefully handle formats, layouts, and edge cases not explicitly covered here.

5. **Prioritize accuracy over speed**: It's better to flag something for review than to auto-approve incorrectly.

Good luck building your agent system!
