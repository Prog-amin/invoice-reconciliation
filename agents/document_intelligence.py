"""Document Intelligence Agent - Extracts structured data from invoice documents."""

import time
import json
import re
from pathlib import Path
from typing import Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from ..config import GROQ_API_KEY, GROQ_MODEL, ReconciliationThresholds
from ..utils.schemas import ExtractedInvoice, LineItem, InvoiceState
from ..utils.pdf_extractor import PDFExtractor


class DocumentIntelligenceAgent:
    """Agent responsible for extracting structured data from invoices."""
    
    EXTRACTION_SYSTEM_PROMPT = """You are a specialized invoice data extraction agent. Your task is to analyze the raw text from an invoice document and extract structured data.

IMPORTANT EXTRACTION RULES:
1. Extract ALL line items with their descriptions, quantities, unit prices, and totals
2. Identify the PO reference number if present (may be labeled as "PO Number", "Purchase Order", "PO#", "PO Ref", etc.)
3. Extract the supplier/vendor name and address
4. Extract invoice number, date, and payment terms
5. Calculate totals if not explicitly stated
6. Be careful with currency symbols (£, $, €) and number formats

OUTPUT FORMAT:
Return a valid JSON object with this exact structure:
{
    "invoice_number": "string",
    "invoice_date": "YYYY-MM-DD",
    "supplier_name": "string",
    "supplier_address": "string or null",
    "supplier_vat": "string or null",
    "po_reference": "string or null (CRITICAL: look for PO-XXXX-XXX patterns)",
    "payment_terms": "string or null",
    "currency": "GBP/USD/EUR",
    "line_items": [
        {
            "item_code": "string or null",
            "description": "string",
            "quantity": number,
            "unit": "string (kg, L, units, etc.)",
            "unit_price": number,
            "line_total": number
        }
    ],
    "subtotal": number,
    "vat_rate": number or null (as decimal, e.g., 0.20 for 20%),
    "vat_amount": number or null,
    "total": number
}

CRITICAL: 
- Return ONLY valid JSON, no markdown or explanation
- Use null for missing fields, not empty strings
- All numbers should be plain numbers without currency symbols
- Dates must be in YYYY-MM-DD format"""

    def __init__(self):
        """Initialize the Document Intelligence Agent."""
        self.pdf_extractor = PDFExtractor()
        self.llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name=GROQ_MODEL,
            temperature=0.0,  # Deterministic for extraction
            max_tokens=4096
        )
    
    def process(self, state: InvoiceState) -> InvoiceState:
        """
        Process an invoice file and extract structured data.
        
        Args:
            state: Current invoice processing state
            
        Returns:
            Updated state with extracted invoice data
        """
        start_time = time.time()
        
        try:
            # Step 1: Extract raw text from document
            raw_text, ocr_confidence, doc_quality = self.pdf_extractor.extract_text(
                state.file_path
            )
            
            state.raw_text = raw_text
            state.document_quality = doc_quality
            
            if not raw_text or len(raw_text.strip()) < 50:
                state.extraction_confidence = 0.0
                state.extraction_notes = "Failed to extract text from document"
                state.errors.append("Document text extraction failed")
                return self._finalize_trace(state, start_time, "error")
            
            # Step 2: Use LLM to extract structured data
            extracted_data, llm_confidence = self._extract_with_llm(raw_text)
            
            if extracted_data:
                state.extracted_invoice = extracted_data
                # Combine OCR confidence with LLM extraction confidence
                state.extraction_confidence = min(ocr_confidence, llm_confidence)
                state.extraction_notes = self._generate_extraction_notes(
                    extracted_data, doc_quality, state.extraction_confidence
                )
            else:
                state.extraction_confidence = ocr_confidence * 0.5
                state.extraction_notes = "LLM extraction failed, data may be incomplete"
                state.errors.append("LLM structured extraction failed")
            
            return self._finalize_trace(state, start_time, "success")
            
        except Exception as e:
            state.errors.append(f"Document Intelligence Agent error: {str(e)}")
            state.extraction_notes = f"Error during extraction: {str(e)}"
            return self._finalize_trace(state, start_time, "error")
    
    def _extract_with_llm(
        self, 
        raw_text: str
    ) -> Tuple[ExtractedInvoice | None, float]:
        """Use LLM to extract structured invoice data."""
        try:
            messages = [
                SystemMessage(content=self.EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(content=f"Extract structured data from this invoice:\n\n{raw_text}")
            ]
            
            response = self.llm.invoke(messages)
            content = response.content.strip()
            
            # Clean up the response (remove markdown code blocks if present)
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            # Parse JSON
            data = json.loads(content)
            
            # Convert to Pydantic model
            line_items = [
                LineItem(
                    item_code=item.get("item_code"),
                    description=item["description"],
                    quantity=float(item["quantity"]),
                    unit=item.get("unit", "units"),
                    unit_price=float(item["unit_price"]),
                    line_total=float(item["line_total"]),
                    extraction_confidence=0.95
                )
                for item in data.get("line_items", [])
            ]
            
            extracted = ExtractedInvoice(
                invoice_number=data["invoice_number"],
                invoice_date=data["invoice_date"],
                supplier_name=data["supplier_name"],
                supplier_address=data.get("supplier_address"),
                supplier_vat=data.get("supplier_vat"),
                po_reference=data.get("po_reference"),
                payment_terms=data.get("payment_terms"),
                currency=data.get("currency", "GBP"),
                line_items=line_items,
                subtotal=float(data["subtotal"]),
                vat_rate=float(data["vat_rate"]) if data.get("vat_rate") else None,
                vat_amount=float(data["vat_amount"]) if data.get("vat_amount") else None,
                total=float(data["total"])
            )
            
            # Calculate confidence based on completeness
            confidence = self._calculate_extraction_confidence(extracted)
            
            return extracted, confidence
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return None, 0.0
        except Exception as e:
            print(f"LLM extraction error: {e}")
            return None, 0.0
    
    def _calculate_extraction_confidence(self, invoice: ExtractedInvoice) -> float:
        """Calculate confidence score based on extraction completeness."""
        score = 0.0
        max_score = 0.0
        
        # Critical fields
        critical_fields = [
            ("invoice_number", invoice.invoice_number, 0.15),
            ("invoice_date", invoice.invoice_date, 0.10),
            ("supplier_name", invoice.supplier_name, 0.15),
            ("line_items", len(invoice.line_items) > 0, 0.25),
            ("total", invoice.total > 0, 0.15),
        ]
        
        for name, value, weight in critical_fields:
            max_score += weight
            if value:
                score += weight
        
        # Important fields
        important_fields = [
            ("po_reference", invoice.po_reference, 0.10),
            ("subtotal", invoice.subtotal > 0, 0.05),
            ("vat_amount", invoice.vat_amount is not None, 0.05),
        ]
        
        for name, value, weight in important_fields:
            max_score += weight
            if value:
                score += weight
        
        return score / max_score if max_score > 0 else 0.0
    
    def _generate_extraction_notes(
        self, 
        invoice: ExtractedInvoice, 
        doc_quality: str,
        confidence: float
    ) -> str:
        """Generate human-readable notes about the extraction."""
        notes = []
        
        # Document quality assessment
        quality_map = {
            "excellent": "Clean PDF with excellent text quality.",
            "good": "Good quality document, minor OCR corrections may be needed.",
            "acceptable": "Acceptable document quality, some fields may be unclear.",
            "poor": "Poor document quality, extraction may be incomplete.",
        }
        notes.append(quality_map.get(doc_quality, "Unknown document quality."))
        
        # Field extraction status
        if invoice.po_reference:
            notes.append(f"PO reference found: {invoice.po_reference}")
        else:
            notes.append("No PO reference found in document.")
        
        notes.append(f"Extracted {len(invoice.line_items)} line items.")
        notes.append(f"Overall extraction confidence: {confidence:.0%}")
        
        return " ".join(notes)
    
    def _finalize_trace(
        self, 
        state: InvoiceState, 
        start_time: float,
        status: str
    ) -> InvoiceState:
        """Add execution trace to state."""
        duration_ms = int((time.time() - start_time) * 1000)
        
        state.agent_traces["document_intelligence_agent"] = {
            "duration_ms": duration_ms,
            "confidence": state.extraction_confidence,
            "status": status,
            "document_quality": state.document_quality
        }
        
        return state
