# Invoice Reconciliation Multi-Agent System

A production-grade multi-agent system built with **LangGraph** that processes supplier invoices, extracts structured data, matches them against purchase orders, and provides intelligent discrepancy detection with resolution recommendations.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Invoice (PDF/Scanned)                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
         ┌────────────────────────────────────────────────────────┐
         │              Document Intelligence Agent               │
         │  • PDF/OCR text extraction                             │
         │  • LLM-based structured data parsing (Groq)            │
         │  • Confidence scoring based on extraction quality      │
         └──────────────────────────┬─────────────────────────────┘
                                    ▼
              ┌─────────────────────────────────────────────┐
              │  Extraction OK?                              │
              │  (confidence >= 70%)                         │
              └─────────┬───────────────────────┬───────────┘
                        │ Yes                   │ No
                        ▼                       ▼
         ┌──────────────────────────┐   ┌───────────────────┐
         │      Matching Agent      │   │  Early Escalation │
         │  • Exact PO reference    │   │  (Human Review)   │
         │  • Fuzzy supplier match  │   └───────────────────┘
         │  • Product-level match   │
         └────────────┬─────────────┘
                      ▼
         ┌────────────────────────────────────────────────────────┐
         │           Discrepancy Detection Agent                  │
         │  • Price variance detection (±2% tolerance)            │
         │  • Quantity mismatch detection                         │
         │  • Severity scoring (low/medium/high/critical)         │
         └──────────────────────────┬─────────────────────────────┘
                                    ▼
         ┌────────────────────────────────────────────────────────┐
         │         Resolution Recommendation Agent                │
         │  • Action: auto_approve / flag_for_review / escalate   │
         │  • LLM-generated reasoning                             │
         │  • Risk assessment                                     │
         └──────────────────────────┬─────────────────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │     JSON Output     │
                         └─────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

| Requirement | Installation |
|-------------|--------------|
| Python 3.11+ | [python.org](https://python.org) |
| Groq API Key | [console.groq.com](https://console.groq.com) (free tier available) |
| Tesseract OCR | `winget install UB-Mannheim.TesseractOCR` |
| Poppler (optional) | `winget install oschwartz10612.poppler` (for scanned PDFs) |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/invoice-reconciliation-agent.git
cd invoice-reconciliation-agent

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure environment variables
copy .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### Running the System

```bash
# Process all 5 test invoices
python -m invoice_reconciliation.main --all

# Process a specific test invoice (1-5)
python -m invoice_reconciliation.main --invoice 4

# Process a custom invoice file
python -m invoice_reconciliation.main --file path/to/invoice.pdf
```

## 📁 Project Structure

```
invoice_reconciliation/
├── main.py                    # CLI entry point
├── config.py                  # Configuration & thresholds
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── README.md                  # This file
├── ANALYSIS.md                # Written analysis (500 words)
├── DEMO_VIDEO_SCRIPT.md       # Demo video script
│
├── agents/
│   ├── __init__.py
│   ├── document_intelligence.py   # PDF/OCR extraction + LLM parsing
│   ├── matching.py                # PO database matching (exact + fuzzy)
│   ├── discrepancy_detection.py   # Variance detection + severity scoring
│   └── resolution_recommendation.py  # Action determination + reasoning
│
├── orchestrator/
│   ├── __init__.py
│   └── graph.py               # LangGraph workflow with conditional routing
│
├── utils/
│   ├── __init__.py
│   ├── schemas.py             # Pydantic data models (20+ schemas)
│   ├── pdf_extractor.py       # PDF/image processing utilities
│   └── fuzzy_matching.py      # RapidFuzz-based matching algorithms
│
└── output/
    └── results/               # JSON output files for each invoice
```

## 🎯 Test Results

| Invoice | Challenge | Result | Action |
|---------|-----------|--------|--------|
| 1 - Baseline | Clean PDF | ✅ Perfect extraction | Auto-approve |
| 2 - Scanned | OCR needed | ⚠️ Low confidence | Escalate |
| 3 - Different Format | Template variation | ✅ Matched correctly | Auto-approve |
| **4 - Price Trap** | **10% price increase** | ✅ **DETECTED** | Flag for review |
| **5 - Missing PO** | **No PO reference** | ✅ **Fuzzy matched** | Flag for review |

### Critical Test Case Details

**Invoice 4 - Price Discrepancy:**
- Invoice shows Ibuprofen BP 200mg @ **£88.00**
- PO-2024-004 has Ibuprofen BP 200mg @ **£80.00**
- **+10% variance correctly detected and flagged**

**Invoice 5 - Missing PO Reference:**
- Invoice has no PO reference (Customer Ref: N/A)
- System used fuzzy matching on supplier name + products
- **Matched to PO-2024-005 with 95% confidence**

## 📊 Output Format

```json
{
  "invoice_id": "GPS-8842",
  "processing_timestamp": "2024-01-29T10:30:00Z",
  "processing_duration_seconds": 1.45,
  "document_info": {
    "filename": "Invoice_4_Price_Trap.pdf",
    "document_quality": "excellent"
  },
  "processing_results": {
    "extraction_confidence": 0.95,
    "extracted_data": { ... },
    "matching_results": {
      "po_match_confidence": 0.98,
      "matched_po": "PO-2024-004",
      "match_method": "exact_po_reference"
    },
    "discrepancies": [
      {
        "type": "price_mismatch",
        "severity": "medium",
        "invoice_value": 88.0,
        "po_value": 80.0,
        "variance_percentage": 10.0,
        "recommended_action": "flag_for_review"
      }
    ],
    "recommended_action": "flag_for_review",
    "confidence": 0.95,
    "agent_reasoning": "The invoice GPS-8842..."
  },
  "agent_execution_trace": { ... }
}
```

## ⚙️ Configuration Thresholds

| Parameter | Value | Description |
|-----------|-------|-------------|
| `PRICE_AUTO_APPROVE_TOLERANCE` | ±2% | Maximum price variance for auto-approval |
| `PRICE_FLAG_REVIEW_THRESHOLD` | >5% | Flag for review if exceeded |
| `PRICE_ESCALATE_THRESHOLD` | >15% | Escalate to human if exceeded |
| `EXTRACTION_ACCEPTABLE_CONFIDENCE` | 70% | Minimum for processing |
| `MATCH_ACCEPTABLE_CONFIDENCE` | 50% | Minimum for PO matching |

## 🔧 How It Works

### Agent Communication Flow

1. **Document Intelligence Agent** extracts text using:
   - Direct text extraction for clean PDFs (pypdf)
   - OCR for scanned documents (Tesseract + Poppler)
   - LLM-based structured parsing (Groq/Llama)
   - Returns confidence scores and quality assessment

2. **Matching Agent** finds corresponding PO using:
   - Primary: Exact PO reference match (95%+ confidence)
   - Secondary: Fuzzy supplier + product matching (60-85%)
   - Tertiary: Product-only matching (40-70%)

3. **Discrepancy Detection Agent** compares invoice to PO:
   - Price variance with configurable tolerances
   - Quantity mismatch detection
   - Total variance calculation
   - Severity scoring (low/medium/high/critical)

4. **Resolution Recommendation Agent** determines action:
   - `auto_approve`: All criteria met, no discrepancies
   - `flag_for_review`: Minor issues need human review
   - `escalate_to_human`: Significant issues or uncertainty

### LangGraph Workflow

The orchestrator implements conditional routing:
- If extraction confidence < 70%, triggers early escalation
- If no PO match, discrepancy detection still runs for complete reasoning
- Errors are captured and included in output for transparency

## 📝 Known Limitations

1. **Scanned PDFs**: Require Poppler installation; OCR quality varies with scan quality
2. **Document Rotation**: >15° rotation reduces OCR accuracy significantly
3. **Handwritten Notes**: Text overlapping printed content confuses extraction
4. **New Suppliers**: Suppliers not in PO database require human intervention

## 🔑 Environment Variables

```env
# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional (auto-detected on Windows after installation)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## 📄 License

MIT License - Built for the NIYAMRAI Agent Development Internship Assessment

## 📧 Contact

For questions about this implementation: [Your Email]
