# Agent Development Internship - Assessment Package

Welcome to the NIYAMRAI Agent Development Internship technical assessment. This package contains everything you need to complete the task.

## 📦 Package Contents

### Documentation
- **Agent_Development_Internship_Task.docx** - Complete task brief with requirements, evaluation criteria, and submission instructions
- **Reconciliation_Rules.md** - Detailed rules for invoice reconciliation logic
- **Complete_Example_Invoice_1.md** - Fully worked example showing expected output quality

### Test Data
- **Invoice_1_Baseline.pdf** - Clean invoice, perfect PO match (Easy)
- **Invoice_2_Scanned.pdf** - Scanned invoice with rotation, OCR challenge (Medium)
- **Invoice_3_Different_Format.pdf** - Different template, items in different order (Medium-Hard)
- **Invoice_4_Price_Trap.pdf** - Professional invoice with 10% price discrepancy (Critical Test)
- **Invoice_5_Missing_PO.pdf** - No PO reference, requires fuzzy matching (Critical Test)
- **purchase_orders.json** - Database of 20 purchase orders to match against

## 🎯 Quick Start

1. **Read the task brief** (`Agent_Development_Internship_Task.docx`) completely
2. **Study the reconciliation rules** (`Reconciliation_Rules.md`) to understand matching logic
3. **Review the complete example** (`Complete_Example_Invoice_1.md`) to see expected quality
4. **Process all 5 test invoices** using your agent system
5. **Create your demo video** showing your system in action
6. **Write your analysis** (500 words max)
7. **Submit via email** to internships@niyamrai.com

## ⏰ Timeline

You have **72 hours** from receiving this package to submit your work.

## ✅ Success Criteria

Your submission will be evaluated on:
- **Agent orchestration** (35%) - Communication, handoffs, error handling
- **Extraction accuracy** (25%) - Handling messy documents, OCR quality
- **Matching logic** (20%) - Discrepancy detection, confidence scoring
- **Code quality** (20%) - Maintainability, documentation, best practices

## 🚨 Critical Tests

Pay special attention to:
- **Invoice 4**: Should detect the 10% price increase on Ibuprofen (£88 vs £80)
- **Invoice 5**: Should match to PO-2024-005 via fuzzy matching despite missing PO reference

## 📋 What to Submit

1. GitHub repository link (public or grant access)
2. Demo video (5 minutes max, Loom/YouTube/similar)
3. Written analysis (PDF or Markdown, 500 words max)

## ⚠️ Important Notes

- This is hard by design. Show us your best work.
- Be honest about limitations and failure modes.
- We value thoughtful architecture over perfect results.
- Explain your agent reasoning chains clearly.
- No technical support will be provided during assessment.

## 📧 Questions?

For clarifications about the task (NOT technical help): internships@niyamrai.com

---

## File Descriptions

### Invoice Details

**Invoice 1** - PharmaChem Supplies
- Total: £9,573.00
- PO: PO-2024-001
- Items: 4 pharmaceutical ingredients
- Challenge: None (baseline)

**Invoice 2** - BioActive Materials
- Total: £5,328.00
- PO: PO-2024-002
- Items: 3 ingredients
- Challenge: Scanned/rotated image

**Invoice 3** - MedChem Ingredients
- Total: £7,362.00
- PO: PO-2024-003
- Items: 4 ingredients (different order than PO)
- Challenge: Different template format

**Invoice 4** - Global Pharma Supply
- Total: £13,476.00
- PO: PO-2024-004
- Items: 3 ingredients
- Challenge: **Ibuprofen price is £88.00 instead of £80.00 (10% increase)**

**Invoice 5** - EuroChem Trading
- Total: £5,571.60
- PO: PO-2024-005 (BUT NOT STATED ON INVOICE)
- Items: 4 ingredients
- Challenge: **No PO reference - requires fuzzy matching**

### Purchase Order Database

20 purchase orders from various suppliers, dated January 2024, ranging from £2,980 to £13,176.

The first 5 POs correspond to the 5 test invoices. The remaining 15 are red herrings to test your matching logic.

## 🔧 Technical Requirements

- Must use an agentic framework (LangGraph, CrewAI, AutoGPT, or custom)
- Must output results as JSON following the schema in Reconciliation_Rules.md
- Must handle multiple invoice formats (PDF, scanned images)
- Must include confidence scoring and reasoning transparency
- Code must be runnable with clear setup instructions

## 📊 Expected Outputs

For each invoice, your system should produce:

```json
{
  "invoice_id": "...",
  "processing_results": {
    "extraction_confidence": 0.0-1.0,
    "extracted_data": { ... },
    "matching_results": { ... },
    "discrepancies": [ ... ],
    "recommended_action": "auto_approve|flag_for_review|escalate_to_human",
    "agent_reasoning": "Clear explanation of decision path"
  }
}
```

See `Complete_Example_Invoice_1.md` for a full example.

## 🏆 Bonus Points

- Implement feedback loop (Human Reviewer Agent)
- Handle edge cases gracefully
- Provide performance metrics (processing time, memory usage)
- Include unit tests for critical components
- Add logging/debugging capabilities

## ❌ Instant Rejection Criteria

- Hardcoded rules instead of agent reasoning
- No error handling
- Code doesn't run
- Missing both critical tests (Invoice 4 & 5)
- No documentation

---

**Remember**: We're not looking for perfection. We're looking for people who can build production-grade agentic systems that handle real-world complexity.

Good luck!

— The NIYAMRAI Team
