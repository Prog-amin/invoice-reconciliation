"""Configuration settings for the invoice reconciliation system."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT.parent  # Where invoice PDFs and PO database are located
OUTPUT_DIR = PROJECT_ROOT / "output" / "results"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Best model for complex reasoning

# Tesseract OCR Configuration
TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD", 
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Poppler path for pdf2image (Windows)
POPPLER_PATH = os.getenv("POPPLER_PATH", None)

# Reconciliation Thresholds (from rules)
class ReconciliationThresholds:
    # Price tolerances
    PRICE_AUTO_APPROVE_TOLERANCE = 0.02  # ±2%
    PRICE_FLAG_REVIEW_THRESHOLD = 0.05   # >5%
    PRICE_ESCALATE_THRESHOLD = 0.15      # >15%
    
    # Total variance
    TOTAL_VARIANCE_AMOUNT = 5.00  # £5
    TOTAL_VARIANCE_PERCENT = 0.01  # 1%
    
    # Confidence thresholds
    EXTRACTION_HIGH_CONFIDENCE = 0.90
    EXTRACTION_ACCEPTABLE_CONFIDENCE = 0.70
    MATCH_HIGH_CONFIDENCE = 0.85
    MATCH_ACCEPTABLE_CONFIDENCE = 0.50
    
    # Fuzzy matching thresholds
    FUZZY_SUPPLIER_THRESHOLD = 0.80
    FUZZY_PRODUCT_THRESHOLD = 0.70
    
    # Discrepancy escalation
    MAX_DISCREPANCIES_BEFORE_ESCALATE = 3

# Invoice file paths
INVOICE_FILES = {
    "invoice_1": DATA_DIR / "Invoice_1_Baseline.pdf",
    "invoice_2": DATA_DIR / "Invoice_2_Scanned.pdf",
    "invoice_3": DATA_DIR / "Invoice_3_Different_Format.pdf",
    "invoice_4": DATA_DIR / "Invoice_4_Price_Trap.pdf",
    "invoice_5": DATA_DIR / "Invoice_5_Missing_PO.pdf",
}

PO_DATABASE_PATH = DATA_DIR / "purchase_orders.json"
