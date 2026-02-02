"""Discrepancy Detection Agent - Identifies mismatches between invoices and POs."""

import time
from typing import List, Tuple

from ..config import ReconciliationThresholds
from ..utils.schemas import (
    InvoiceState,
    Discrepancy,
    TotalVariance,
    LineItem
)
from ..utils.fuzzy_matching import FuzzyMatcher


class DiscrepancyDetectionAgent:
    """Agent responsible for detecting discrepancies between invoices and POs."""
    
    def process(self, state: InvoiceState) -> InvoiceState:
        """
        Detect discrepancies between invoice and matched PO.
        
        Args:
            state: Current invoice processing state
            
        Returns:
            Updated state with detected discrepancies
        """
        start_time = time.time()
        
        try:
            # Check prerequisites
            if not state.extracted_invoice:
                state.discrepancy_notes = "No invoice data available"
                state.errors.append("Discrepancy detection failed: No invoice data")
                return self._finalize_trace(state, start_time, "error")
            
            if not state.matching_result or not state.matching_result.matched_po_data:
                # No PO match - this is itself a discrepancy
                state.discrepancies = [
                    Discrepancy(
                        type="missing_po_reference",
                        severity="high",
                        field="po_reference",
                        invoice_value=state.extracted_invoice.po_reference,
                        po_value=None,
                        details=(
                            f"Cannot match invoice to any PO. "
                            f"Invoice PO reference: {state.extracted_invoice.po_reference or 'None'}. "
                            f"Supplier: {state.extracted_invoice.supplier_name}."
                        ),
                        recommended_action="escalate_to_human",
                        confidence=0.95
                    )
                ]
                state.discrepancy_notes = "No PO match found - cannot perform detailed discrepancy check"
                return self._finalize_trace(state, start_time, "warning")
            
            invoice = state.extracted_invoice
            po = state.matching_result.matched_po_data
            discrepancies: List[Discrepancy] = []
            
            # 1. Check for missing PO reference on invoice
            if not invoice.po_reference:
                discrepancies.append(
                    Discrepancy(
                        type="missing_po_reference",
                        severity="medium",
                        field="po_reference",
                        invoice_value=None,
                        po_value=po.po_number,
                        details=(
                            f"Invoice does not contain a PO reference. "
                            f"Fuzzy matching suggests PO {po.po_number} "
                            f"({state.matching_result.po_match_confidence:.0%} confidence)."
                        ),
                        recommended_action="flag_for_review",
                        confidence=state.matching_result.po_match_confidence
                    )
                )
            
            # 2. Check supplier match
            supplier_score = FuzzyMatcher.supplier_match_score(
                invoice.supplier_name,
                po.supplier
            )
            if supplier_score < 0.90:
                severity = "low" if supplier_score >= 0.75 else "medium"
                discrepancies.append(
                    Discrepancy(
                        type="supplier_mismatch",
                        severity=severity,
                        field="supplier_name",
                        invoice_value=invoice.supplier_name,
                        po_value=po.supplier,
                        details=(
                            f"Supplier name variation detected. "
                            f"Invoice: '{invoice.supplier_name}' vs "
                            f"PO: '{po.supplier}' ({supplier_score:.0%} similarity)."
                        ),
                        recommended_action="flag_for_review" if severity == "medium" else "auto_approve",
                        confidence=supplier_score
                    )
                )
            
            # 3. Check line items
            line_item_discrepancies = self._check_line_items(
                invoice.line_items,
                po.line_items
            )
            discrepancies.extend(line_item_discrepancies)
            
            # 4. Calculate total variance
            total_variance = self._calculate_total_variance(
                invoice.total,
                po.total
            )
            state.total_variance = total_variance
            
            if not total_variance.within_tolerance:
                severity = self._get_total_variance_severity(
                    total_variance.percentage
                )
                discrepancies.append(
                    Discrepancy(
                        type="total_variance",
                        severity=severity,
                        field="total",
                        invoice_value=invoice.total,
                        po_value=po.total,
                        variance_percentage=total_variance.percentage * 100,
                        details=(
                            f"Total invoice amount £{invoice.total:.2f} differs from "
                            f"PO total £{po.total:.2f} by £{total_variance.amount:.2f} "
                            f"({total_variance.percentage:.1%})."
                        ),
                        recommended_action=self._get_action_for_severity(severity),
                        confidence=0.99
                    )
                )
            
            state.discrepancies = discrepancies
            state.discrepancy_notes = self._generate_discrepancy_notes(
                discrepancies, total_variance
            )
            
            status = "success" if not discrepancies else "warning"
            return self._finalize_trace(state, start_time, status)
            
        except Exception as e:
            state.errors.append(f"Discrepancy Detection Agent error: {str(e)}")
            state.discrepancy_notes = f"Error during discrepancy detection: {str(e)}"
            return self._finalize_trace(state, start_time, "error")
    
    def _check_line_items(
        self,
        invoice_items: List[LineItem],
        po_items: List[LineItem]
    ) -> List[Discrepancy]:
        """Check for discrepancies in line items."""
        discrepancies = []
        
        # Match invoice items to PO items
        item_matches = FuzzyMatcher.match_line_items(
            invoice_items,
            po_items,
            threshold=0.60
        )
        
        matched_invoice_indices = {m[0] for m in item_matches}
        matched_po_indices = {m[1] for m in item_matches}
        
        # Check matched items for price/quantity differences
        for inv_idx, po_idx, match_score in item_matches:
            inv_item = invoice_items[inv_idx]
            po_item = po_items[po_idx]
            
            # Check price variance
            if po_item.unit_price > 0:
                price_variance = (
                    (inv_item.unit_price - po_item.unit_price) / po_item.unit_price
                )
                
                if abs(price_variance) > ReconciliationThresholds.PRICE_AUTO_APPROVE_TOLERANCE:
                    severity = self._get_price_severity(abs(price_variance))
                    discrepancies.append(
                        Discrepancy(
                            type="price_mismatch",
                            severity=severity,
                            line_item_index=inv_idx,
                            field="unit_price",
                            invoice_value=inv_item.unit_price,
                            po_value=po_item.unit_price,
                            variance_percentage=price_variance * 100,
                            details=(
                                f"Line item {inv_idx + 1} ({inv_item.description}): "
                                f"Invoice unit price £{inv_item.unit_price:.2f} vs "
                                f"PO price £{po_item.unit_price:.2f} "
                                f"({price_variance:+.1%} {'increase' if price_variance > 0 else 'decrease'})."
                            ),
                            recommended_action=self._get_action_for_severity(severity),
                            confidence=match_score
                        )
                    )
            
            # Check quantity mismatch
            if inv_item.quantity != po_item.quantity:
                qty_diff = inv_item.quantity - po_item.quantity
                qty_pct = qty_diff / po_item.quantity if po_item.quantity > 0 else 0
                severity = "medium" if abs(qty_pct) <= 0.10 else "high"
                
                discrepancies.append(
                    Discrepancy(
                        type="quantity_mismatch",
                        severity=severity,
                        line_item_index=inv_idx,
                        field="quantity",
                        invoice_value=inv_item.quantity,
                        po_value=po_item.quantity,
                        variance_percentage=qty_pct * 100,
                        details=(
                            f"Line item {inv_idx + 1} ({inv_item.description}): "
                            f"Invoice quantity {inv_item.quantity} {inv_item.unit} vs "
                            f"PO quantity {po_item.quantity} {po_item.unit}."
                        ),
                        recommended_action="flag_for_review",
                        confidence=match_score
                    )
                )
        
        # Check for unmatched invoice items (extra items)
        for inv_idx, inv_item in enumerate(invoice_items):
            if inv_idx not in matched_invoice_indices:
                discrepancies.append(
                    Discrepancy(
                        type="extra_line_item",
                        severity="medium",
                        line_item_index=inv_idx,
                        field="line_item",
                        invoice_value=inv_item.description,
                        po_value=None,
                        details=(
                            f"Invoice contains item not found in PO: "
                            f"'{inv_item.description}' ({inv_item.quantity} {inv_item.unit} "
                            f"@ £{inv_item.unit_price:.2f})."
                        ),
                        recommended_action="flag_for_review",
                        confidence=0.85
                    )
                )
        
        # Check for missing PO items
        for po_idx, po_item in enumerate(po_items):
            if po_idx not in matched_po_indices:
                discrepancies.append(
                    Discrepancy(
                        type="missing_line_item",
                        severity="low",
                        line_item_index=po_idx,
                        field="line_item",
                        invoice_value=None,
                        po_value=po_item.description,
                        details=(
                            f"PO item not found in invoice: "
                            f"'{po_item.description}' ({po_item.quantity} {po_item.unit})."
                        ),
                        recommended_action="flag_for_review",
                        confidence=0.85
                    )
                )
        
        return discrepancies
    
    def _calculate_total_variance(
        self,
        invoice_total: float,
        po_total: float
    ) -> TotalVariance:
        """Calculate the variance between invoice and PO totals."""
        amount = abs(invoice_total - po_total)
        percentage = amount / po_total if po_total > 0 else 0
        
        # Within tolerance if variance is <= £5 OR <= 1% (whichever is smaller)
        amount_ok = amount <= ReconciliationThresholds.TOTAL_VARIANCE_AMOUNT
        pct_ok = percentage <= ReconciliationThresholds.TOTAL_VARIANCE_PERCENT
        within_tolerance = amount_ok or pct_ok
        
        return TotalVariance(
            amount=amount,
            percentage=percentage,
            within_tolerance=within_tolerance
        )
    
    def _get_price_severity(self, variance: float) -> str:
        """Determine severity based on price variance."""
        if variance <= ReconciliationThresholds.PRICE_FLAG_REVIEW_THRESHOLD:
            return "low"
        elif variance <= ReconciliationThresholds.PRICE_ESCALATE_THRESHOLD:
            return "medium"
        else:
            return "high"
    
    def _get_total_variance_severity(self, variance_pct: float) -> str:
        """Determine severity based on total variance."""
        if variance_pct <= 0.05:
            return "low"
        elif variance_pct <= 0.10:
            return "medium"
        else:
            return "high"
    
    def _get_action_for_severity(self, severity: str) -> str:
        """Get recommended action based on severity."""
        return {
            "low": "auto_approve",
            "medium": "flag_for_review",
            "high": "escalate_to_human",
            "critical": "escalate_to_human"
        }.get(severity, "flag_for_review")
    
    def _generate_discrepancy_notes(
        self,
        discrepancies: List[Discrepancy],
        total_variance: TotalVariance
    ) -> str:
        """Generate human-readable notes about discrepancies."""
        if not discrepancies:
            return (
                f"No discrepancies detected. "
                f"Total variance: £{total_variance.amount:.2f} "
                f"({total_variance.percentage:.1%}), within tolerance."
            )
        
        notes = [f"{len(discrepancies)} discrepancy(ies) detected."]
        
        # Count by type
        type_counts = {}
        for d in discrepancies:
            type_counts[d.type] = type_counts.get(d.type, 0) + 1
        
        for disc_type, count in type_counts.items():
            readable_type = disc_type.replace("_", " ").title()
            notes.append(f"{readable_type}: {count}")
        
        # Severity summary
        high_severity = sum(1 for d in discrepancies if d.severity in ["high", "critical"])
        if high_severity > 0:
            notes.append(f"High severity issues: {high_severity}")
        
        return " | ".join(notes)
    
    def _finalize_trace(
        self,
        state: InvoiceState,
        start_time: float,
        status: str
    ) -> InvoiceState:
        """Add execution trace to state."""
        duration_ms = int((time.time() - start_time) * 1000)
        
        state.agent_traces["discrepancy_detection_agent"] = {
            "duration_ms": duration_ms,
            "confidence": 0.99 if status == "success" else 0.85,
            "status": status,
            "discrepancies_found": len(state.discrepancies)
        }
        
        return state
