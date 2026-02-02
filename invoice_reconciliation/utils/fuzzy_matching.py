"""Fuzzy matching utilities for supplier and product matching."""

import re
from typing import List, Tuple, Optional
from rapidfuzz import fuzz, process

from .schemas import LineItem, PurchaseOrder


class FuzzyMatcher:
    """Fuzzy matching utilities for invoice reconciliation."""
    
    # Common variations to normalize
    COMPANY_SUFFIXES = [
        (r'\bltd\.?\b', 'limited'),
        (r'\blimited\b', 'limited'),
        (r'\binc\.?\b', 'incorporated'),
        (r'\bincorporated\b', 'incorporated'),
        (r'\bcorp\.?\b', 'corporation'),
        (r'\bcorporation\b', 'corporation'),
        (r'\bco\.?\b', 'company'),
        (r'\bcompany\b', 'company'),
        (r'\bgmbh\b', 'gmbh'),
        (r'\bab\b', 'ab'),
        (r'\bplc\b', 'plc'),
    ]
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation except essential ones
        text = re.sub(r'[^\w\s\-.]', '', text)
        
        return text
    
    @classmethod
    def normalize_company_name(cls, name: str) -> str:
        """Normalize company name for matching."""
        name = cls.normalize_text(name)
        
        # Standardize company suffixes
        for pattern, replacement in cls.COMPANY_SUFFIXES:
            name = re.sub(pattern, replacement, name, flags=re.IGNORECASE)
        
        return name.strip()
    
    @staticmethod
    def supplier_match_score(name1: str, name2: str) -> float:
        """Calculate similarity score between two supplier names."""
        norm1 = FuzzyMatcher.normalize_company_name(name1)
        norm2 = FuzzyMatcher.normalize_company_name(name2)
        
        # Use token sort ratio for companies (handles word order differences)
        score = fuzz.token_sort_ratio(norm1, norm2) / 100.0
        
        return score
    
    @staticmethod
    def product_match_score(desc1: str, desc2: str) -> float:
        """Calculate similarity score between two product descriptions."""
        norm1 = FuzzyMatcher.normalize_text(desc1)
        norm2 = FuzzyMatcher.normalize_text(desc2)
        
        # Use partial ratio for products (one might be substring of other)
        partial = fuzz.partial_ratio(norm1, norm2) / 100.0
        
        # Also use token set ratio for products with different word orders
        token_set = fuzz.token_set_ratio(norm1, norm2) / 100.0
        
        # Take the higher score
        return max(partial, token_set)
    
    @classmethod
    def match_line_items(
        cls, 
        invoice_items: List[LineItem], 
        po_items: List[LineItem],
        threshold: float = 0.70
    ) -> List[Tuple[int, int, float]]:
        """
        Match invoice line items to PO line items.
        
        Returns:
            List of tuples (invoice_idx, po_idx, match_score)
        """
        matches = []
        used_po_indices = set()
        
        for inv_idx, inv_item in enumerate(invoice_items):
            best_match = None
            best_score = 0.0
            
            for po_idx, po_item in enumerate(po_items):
                if po_idx in used_po_indices:
                    continue
                
                # Calculate match score
                desc_score = cls.product_match_score(
                    inv_item.description, 
                    po_item.description
                )
                
                # Boost score if item codes match
                code_boost = 0.0
                if inv_item.item_code and po_item.item_code:
                    if inv_item.item_code.upper() == po_item.item_code.upper():
                        code_boost = 0.20
                    elif fuzz.ratio(
                        inv_item.item_code.upper(), 
                        po_item.item_code.upper()
                    ) > 80:
                        code_boost = 0.10
                
                total_score = min(1.0, desc_score + code_boost)
                
                if total_score > best_score and total_score >= threshold:
                    best_score = total_score
                    best_match = po_idx
            
            if best_match is not None:
                matches.append((inv_idx, best_match, best_score))
                used_po_indices.add(best_match)
        
        return matches
    
    @classmethod
    def find_best_po_match(
        cls,
        invoice_supplier: str,
        invoice_items: List[LineItem],
        invoice_date: str,
        po_list: List[PurchaseOrder],
        po_reference: Optional[str] = None
    ) -> Tuple[Optional[PurchaseOrder], float, str]:
        """
        Find the best matching PO for an invoice.
        
        Returns:
            Tuple of (matched_po, confidence, match_method)
        """
        # If we have an exact PO reference, try that first
        if po_reference:
            for po in po_list:
                if po.po_number.upper() == po_reference.upper():
                    return po, 0.98, "exact_po_reference"
                # Allow fuzzy PO number matching (high threshold to avoid false matches)
                if fuzz.ratio(po.po_number.upper(), po_reference.upper()) > 96:
                    return po, 0.92, "exact_po_reference"
        
        # Calculate scores for all POs
        po_scores = []
        
        for po in po_list:
            # Supplier match score
            supplier_score = cls.supplier_match_score(
                invoice_supplier, 
                po.supplier
            )
            
            # Product match score
            item_matches = cls.match_line_items(
                invoice_items, 
                po.line_items,
                threshold=0.60
            )
            
            if len(invoice_items) > 0:
                match_rate = len(item_matches) / len(invoice_items)
                avg_match_score = (
                    sum(m[2] for m in item_matches) / len(item_matches)
                    if item_matches else 0.0
                )
            else:
                match_rate = 0.0
                avg_match_score = 0.0
            
            # Date proximity score (within 14 days = full score)
            date_score = cls._calculate_date_proximity(invoice_date, po.date)
            
            # Combined score with weights
            # Supplier: 25%, Products: 50%, Date: 25%
            combined_score = (
                supplier_score * 0.25 +
                avg_match_score * match_rate * 0.50 +
                date_score * 0.25
            )
            
            po_scores.append((po, combined_score, supplier_score, match_rate))
        
        # Sort by score
        po_scores.sort(key=lambda x: x[1], reverse=True)
        
        if not po_scores:
            return None, 0.0, "no_match"
        
        best_po, best_score, supplier_score, match_rate = po_scores[0]
        
        # Determine match method and confidence
        if best_score >= 0.70 and supplier_score >= 0.80:
            return best_po, best_score * 0.95, "fuzzy_supplier_product_match"
        elif best_score >= 0.50 and match_rate >= 0.70:
            return best_po, best_score * 0.80, "product_only_match"
        elif best_score >= 0.40:
            return best_po, best_score * 0.60, "product_only_match"
        
        return None, 0.0, "no_match"
    
    @staticmethod
    def _calculate_date_proximity(date1: str, date2: str) -> float:
        """Calculate a score based on date proximity."""
        from datetime import datetime
        
        try:
            d1 = datetime.fromisoformat(date1)
            d2 = datetime.fromisoformat(date2)
            diff = abs((d1 - d2).days)
            
            if diff <= 7:
                return 1.0
            elif diff <= 14:
                return 0.8
            elif diff <= 30:
                return 0.5
            elif diff <= 60:
                return 0.3
            else:
                return 0.1
        except Exception:
            return 0.5  # Default to middle score if dates can't be parsed
