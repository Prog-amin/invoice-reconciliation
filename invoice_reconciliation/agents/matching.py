"""Matching Agent - Matches invoices to purchase orders."""

import time
import json
from pathlib import Path
from typing import List, Optional

from ..config import PO_DATABASE_PATH, ReconciliationThresholds
from ..utils.schemas import (
    InvoiceState, 
    PurchaseOrder, 
    LineItem, 
    MatchingResult
)
from ..utils.fuzzy_matching import FuzzyMatcher


class MatchingAgent:
    """Agent responsible for matching invoices to purchase orders."""
    
    def __init__(self):
        """Initialize the Matching Agent."""
        self.po_database: List[PurchaseOrder] = []
        self._load_po_database()
    
    def _load_po_database(self):
        """Load the purchase order database."""
        try:
            with open(PO_DATABASE_PATH, "r") as f:
                data = json.load(f)
            
            self.po_database = []
            for po_data in data.get("purchase_orders", []):
                line_items = [
                    LineItem(
                        item_code=item.get("item_id"),
                        description=item["description"],
                        quantity=float(item["quantity"]),
                        unit=item.get("unit", "units"),
                        unit_price=float(item["unit_price"]),
                        line_total=float(item["line_total"])
                    )
                    for item in po_data.get("line_items", [])
                ]
                
                po = PurchaseOrder(
                    po_number=po_data["po_number"],
                    supplier=po_data["supplier"],
                    date=po_data["date"],
                    total=float(po_data["total"]),
                    currency=po_data.get("currency", "GBP"),
                    line_items=line_items
                )
                self.po_database.append(po)
                
        except Exception as e:
            print(f"Error loading PO database: {e}")
            self.po_database = []
    
    def process(self, state: InvoiceState) -> InvoiceState:
        """
        Match an invoice to the PO database.
        
        Args:
            state: Current invoice processing state
            
        Returns:
            Updated state with matching results
        """
        start_time = time.time()
        
        try:
            # Check if we have extracted invoice data
            if not state.extracted_invoice:
                state.matching_result = MatchingResult(
                    po_match_confidence=0.0,
                    match_method="no_match"
                )
                state.matching_notes = "No invoice data to match"
                state.errors.append("Matching failed: No extracted invoice data")
                return self._finalize_trace(state, start_time, "error")
            
            invoice = state.extracted_invoice
            
            # Try to match the invoice
            matched_po, confidence, method = FuzzyMatcher.find_best_po_match(
                invoice_supplier=invoice.supplier_name,
                invoice_items=invoice.line_items,
                invoice_date=invoice.invoice_date,
                po_list=self.po_database,
                po_reference=invoice.po_reference
            )
            
            if matched_po:
                # Calculate detailed matching info
                item_matches = FuzzyMatcher.match_line_items(
                    invoice.line_items,
                    matched_po.line_items,
                    threshold=0.60
                )
                
                supplier_match = FuzzyMatcher.supplier_match_score(
                    invoice.supplier_name,
                    matched_po.supplier
                ) >= 0.80
                
                # Calculate date variance
                date_variance = self._calculate_date_variance(
                    invoice.invoice_date,
                    matched_po.date
                )
                
                # Find alternative matches
                alternatives = self._find_alternative_matches(
                    invoice, 
                    matched_po.po_number
                )
                
                state.matching_result = MatchingResult(
                    po_match_confidence=confidence,
                    matched_po=matched_po.po_number,
                    match_method=method,
                    supplier_match=supplier_match,
                    date_variance_days=date_variance,
                    line_items_matched=len(item_matches),
                    line_items_total=len(invoice.line_items),
                    match_rate=len(item_matches) / len(invoice.line_items) if invoice.line_items else 0,
                    alternative_matches=alternatives,
                    matched_po_data=matched_po
                )
                
                state.matching_notes = self._generate_matching_notes(
                    state.matching_result, invoice, matched_po
                )
                
                return self._finalize_trace(state, start_time, "success")
            else:
                # No match found
                state.matching_result = MatchingResult(
                    po_match_confidence=0.0,
                    match_method="no_match",
                    alternative_matches=self._find_potential_matches(invoice)
                )
                
                state.matching_notes = (
                    f"No PO match found for invoice from {invoice.supplier_name}. "
                    f"PO reference: {invoice.po_reference or 'None'}. "
                    "Fuzzy matching attempted but no suitable match found."
                )
                
                return self._finalize_trace(state, start_time, "warning")
                
        except Exception as e:
            state.errors.append(f"Matching Agent error: {str(e)}")
            state.matching_notes = f"Error during matching: {str(e)}"
            state.matching_result = MatchingResult(
                po_match_confidence=0.0,
                match_method="no_match"
            )
            return self._finalize_trace(state, start_time, "error")
    
    def _calculate_date_variance(
        self, 
        invoice_date: str, 
        po_date: str
    ) -> Optional[int]:
        """Calculate the number of days between invoice and PO dates."""
        from datetime import datetime
        
        try:
            inv_dt = datetime.fromisoformat(invoice_date)
            po_dt = datetime.fromisoformat(po_date)
            return abs((inv_dt - po_dt).days)
        except Exception:
            return None
    
    def _find_alternative_matches(
        self, 
        invoice, 
        matched_po_number: str
    ) -> List[dict]:
        """Find alternative PO matches for review."""
        alternatives = []
        
        for po in self.po_database:
            if po.po_number == matched_po_number:
                continue
            
            # Calculate match score
            supplier_score = FuzzyMatcher.supplier_match_score(
                invoice.supplier_name,
                po.supplier
            )
            
            item_matches = FuzzyMatcher.match_line_items(
                invoice.line_items,
                po.line_items,
                threshold=0.60
            )
            match_rate = len(item_matches) / len(invoice.line_items) if invoice.line_items else 0
            
            # Only include reasonable alternatives
            if supplier_score >= 0.50 or match_rate >= 0.50:
                alternatives.append({
                    "po_number": po.po_number,
                    "supplier": po.supplier,
                    "supplier_match_score": round(supplier_score, 2),
                    "item_match_rate": round(match_rate, 2)
                })
        
        # Sort by score and limit to top 3
        alternatives.sort(key=lambda x: x["supplier_match_score"], reverse=True)
        return alternatives[:3]
    
    def _find_potential_matches(self, invoice) -> List[dict]:
        """Find potential matches when no confident match is found."""
        potentials = []
        
        for po in self.po_database:
            supplier_score = FuzzyMatcher.supplier_match_score(
                invoice.supplier_name,
                po.supplier
            )
            
            item_matches = FuzzyMatcher.match_line_items(
                invoice.line_items,
                po.line_items,
                threshold=0.50
            )
            match_rate = len(item_matches) / len(invoice.line_items) if invoice.line_items else 0
            
            if supplier_score >= 0.30 or match_rate >= 0.30:
                potentials.append({
                    "po_number": po.po_number,
                    "supplier": po.supplier,
                    "supplier_match_score": round(supplier_score, 2),
                    "item_match_rate": round(match_rate, 2),
                    "combined_score": round((supplier_score + match_rate) / 2, 2)
                })
        
        potentials.sort(key=lambda x: x["combined_score"], reverse=True)
        return potentials[:5]
    
    def _generate_matching_notes(
        self, 
        result: MatchingResult, 
        invoice, 
        matched_po: PurchaseOrder
    ) -> str:
        """Generate human-readable notes about the matching."""
        notes = []
        
        if result.match_method == "exact_po_reference":
            notes.append(f"Exact PO reference match ({matched_po.po_number}).")
        elif result.match_method == "fuzzy_supplier_product_match":
            notes.append(
                f"Fuzzy match by supplier and products to {matched_po.po_number}."
            )
        elif result.match_method == "product_only_match":
            notes.append(
                f"Product-only fuzzy match to {matched_po.po_number} "
                f"(supplier: {matched_po.supplier})."
            )
        
        if result.supplier_match:
            notes.append("Supplier name verified.")
        else:
            notes.append(
                f"Supplier mismatch: Invoice '{invoice.supplier_name}' "
                f"vs PO '{matched_po.supplier}'."
            )
        
        notes.append(
            f"{result.line_items_matched}/{result.line_items_total} "
            f"line items matched ({result.match_rate:.0%})."
        )
        
        if result.date_variance_days is not None:
            notes.append(
                f"Invoice date is {result.date_variance_days} days after PO date."
            )
        
        notes.append(f"Match confidence: {result.po_match_confidence:.0%}")
        
        return " ".join(notes)
    
    def _finalize_trace(
        self, 
        state: InvoiceState, 
        start_time: float,
        status: str
    ) -> InvoiceState:
        """Add execution trace to state."""
        duration_ms = int((time.time() - start_time) * 1000)
        
        state.agent_traces["matching_agent"] = {
            "duration_ms": duration_ms,
            "confidence": state.matching_result.po_match_confidence if state.matching_result else 0.0,
            "status": status,
            "match_method": state.matching_result.match_method if state.matching_result else "no_match"
        }
        
        return state
