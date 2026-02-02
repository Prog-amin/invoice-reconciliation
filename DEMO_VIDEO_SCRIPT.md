# Demo Video Script (5 minutes)

## Opening (0:00 - 0:30)
**[Screen: Terminal/IDE]**

"Hi, I'm demonstrating my multi-agent invoice reconciliation system built with LangGraph. This system processes supplier invoices, extracts structured data, matches them against purchase orders, and provides intelligent recommendations."

## Architecture Overview (0:30 - 1:00)
**[Screen: Show architecture diagram or code structure]**

"The system uses four agents that communicate through a LangGraph workflow:
1. **Document Intelligence Agent** - extracts text from PDFs using OCR and LLM
2. **Matching Agent** - finds corresponding purchase orders using exact and fuzzy matching
3. **Discrepancy Detection Agent** - identifies price, quantity, and total variances
4. **Resolution Recommendation Agent** - decides whether to approve, flag, or escalate"

## Running All 5 Invoices (1:00 - 2:00)
**[Screen: Terminal - run command]**

```
python -m invoice_reconciliation.main --all
```

"Let's process all 5 test invoices. Watch the real-time output showing each agent's work..."

*[Wait for processing to complete, narrate as it runs]*

"We processed 5 invoices in under 20 seconds. Let's look at the results breakdown:
- 2 auto-approved
- 2 flagged for review  
- 1 escalated to human"

## Invoice 4 - Price Discrepancy (2:00 - 3:00)
**[Screen: Show Invoice 4 result JSON or terminal output]**

"Now let's examine the critical test case - Invoice 4, the price trap."

*[Show the invoice image or PDF]*

"This invoice from Global Pharma Supply shows Ibuprofen at £88.00 per kilogram..."

*[Show PO-2024-004 in purchase_orders.json]*

"...but PO-2024-004 has Ibuprofen priced at £80.00. That's a 10% increase."

*[Show the detection in the JSON output]*

"Our Discrepancy Detection Agent caught this:
- Type: price_mismatch
- Severity: medium
- Variance: +10%
- Recommended action: flag for review

The agent reasoning explains why this decision was made."

## Invoice 5 - Missing PO Reference (3:00 - 4:00)
**[Screen: Show Invoice 5 result JSON]**

"Invoice 5 tests our fuzzy matching capability. This invoice from EuroChem Trading has NO PO reference - the Customer Ref field shows 'N/A'."

*[Show the invoice image]*

"Without an exact PO number, our Matching Agent uses fuzzy logic:
1. It compares supplier names across all POs
2. It matches product descriptions to find similar items
3. It calculates a confidence score"

*[Show matching result]*

"The system successfully matched to PO-2024-005 with 95% confidence using 'fuzzy_supplier_product_match'. All 4 line items matched perfectly."

*[Show the discrepancy detected]*

"It correctly flagged the missing PO reference as a medium-severity discrepancy, recommending human review to confirm the match."

## Limitations - What Breaks (4:00 - 4:45)
**[Screen: Show Invoice 2 result]**

"Let me be honest about limitations. Invoice 2 - the scanned document - failed to extract properly. The OCR confidence was only 29%."

"The system correctly escalated to human review rather than making unreliable decisions. This is intentional - agents should know when they're unsure."

"Other failure modes:
- **Heavily rotated documents** (>15°) reduce OCR accuracy
- **Handwritten notes** overlapping text confuse extraction
- **New suppliers** not in the PO database require human intervention
- **Unusual invoice formats** may need template adaptation"

## Closing (4:45 - 5:00)
**[Screen: Summary of results]**

"In summary, this system demonstrates:
- Intelligent agent communication via LangGraph
- Confidence scoring that knows when to escalate
- Transparent reasoning for every decision
- Critical test cases passed: price discrepancy and missing PO

Thank you for watching."

---

## Recording Tips
1. Use screen recording with audio (Loom, OBS, or similar)
2. Keep terminal font size large (14-16pt)
3. Pause briefly when showing JSON results
4. Speak clearly and at moderate pace
5. Total target: 4-5 minutes
