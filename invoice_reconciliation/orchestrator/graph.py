"""LangGraph workflow orchestrator for invoice reconciliation."""

import time
from typing import Dict, Any

from langgraph.graph import StateGraph, END

from ..utils.schemas import InvoiceState
from ..agents.document_intelligence import DocumentIntelligenceAgent
from ..agents.matching import MatchingAgent
from ..agents.discrepancy_detection import DiscrepancyDetectionAgent
from ..agents.resolution_recommendation import ResolutionRecommendationAgent
from ..config import ReconciliationThresholds


class InvoiceReconciliationGraph:
    """LangGraph-based invoice reconciliation workflow."""
    
    def __init__(self):
        """Initialize the workflow with all agents."""
        self.doc_agent = DocumentIntelligenceAgent()
        self.matching_agent = MatchingAgent()
        self.discrepancy_agent = DiscrepancyDetectionAgent()
        self.resolution_agent = ResolutionRecommendationAgent()
        
        self.graph = self._build_graph()
        self.app = self.graph.compile()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create the state graph
        graph = StateGraph(InvoiceState)
        
        # Add nodes for each agent
        graph.add_node("document_intelligence", self._run_doc_agent)
        graph.add_node("matching", self._run_matching_agent)
        graph.add_node("discrepancy_detection", self._run_discrepancy_agent)
        graph.add_node("resolution", self._run_resolution_agent)
        graph.add_node("early_escalation", self._early_escalation)
        
        # Set entry point
        graph.set_entry_point("document_intelligence")
        
        # Add conditional edges from document intelligence
        graph.add_conditional_edges(
            "document_intelligence",
            self._route_after_extraction,
            {
                "continue": "matching",
                "escalate": "early_escalation"
            }
        )
        
        # Add conditional edges from matching
        graph.add_conditional_edges(
            "matching",
            self._route_after_matching,
            {
                "continue": "discrepancy_detection",
                "escalate": "early_escalation"
            }
        )
        
        # Linear flow for remaining nodes
        graph.add_edge("discrepancy_detection", "resolution")
        graph.add_edge("resolution", END)
        graph.add_edge("early_escalation", END)
        
        return graph
    
    def _run_doc_agent(self, state: InvoiceState) -> Dict[str, Any]:
        """Run the Document Intelligence Agent."""
        result = self.doc_agent.process(state)
        return result.model_dump()
    
    def _run_matching_agent(self, state: InvoiceState) -> Dict[str, Any]:
        """Run the Matching Agent."""
        result = self.matching_agent.process(state)
        return result.model_dump()
    
    def _run_discrepancy_agent(self, state: InvoiceState) -> Dict[str, Any]:
        """Run the Discrepancy Detection Agent."""
        result = self.discrepancy_agent.process(state)
        return result.model_dump()
    
    def _run_resolution_agent(self, state: InvoiceState) -> Dict[str, Any]:
        """Run the Resolution Recommendation Agent."""
        result = self.resolution_agent.process(state)
        return result.model_dump()
    
    def _early_escalation(self, state: InvoiceState) -> Dict[str, Any]:
        """Handle early escalation when critical issues are detected."""
        state.recommended_action = "escalate_to_human"
        state.risk_level = "critical"
        state.confidence = 0.95
        
        # Generate reasoning for early escalation
        if state.extraction_confidence < ReconciliationThresholds.EXTRACTION_ACCEPTABLE_CONFIDENCE:
            state.agent_reasoning = (
                f"Early escalation triggered due to low extraction confidence "
                f"({state.extraction_confidence:.0%}). Document quality: {state.document_quality}. "
                f"The system could not reliably extract invoice data. Human review required."
            )
        elif state.matching_result and state.matching_result.match_method == "no_match":
            state.agent_reasoning = (
                f"Early escalation triggered because no matching PO was found. "
                f"Invoice supplier: {state.extracted_invoice.supplier_name if state.extracted_invoice else 'Unknown'}. "
                f"PO reference on invoice: {state.extracted_invoice.po_reference if state.extracted_invoice else 'None'}. "
                f"Human review required to identify correct PO or create new one."
            )
        else:
            state.agent_reasoning = (
                "Early escalation triggered due to critical issues during processing. "
                "Human review required."
            )
        
        state.agent_traces["early_escalation"] = {
            "duration_ms": 0,
            "confidence": state.confidence,
            "status": "escalated",
            "reason": "Critical issue detected"
        }
        
        return state.model_dump()
    
    def _route_after_extraction(self, state: InvoiceState) -> str:
        """Decide whether to continue or escalate after extraction."""
        # Escalate if extraction confidence is too low
        if state.extraction_confidence < ReconciliationThresholds.EXTRACTION_ACCEPTABLE_CONFIDENCE:
            return "escalate"
        
        # Escalate if no invoice data was extracted
        if not state.extracted_invoice:
            return "escalate"
        
        return "continue"
    
    def _route_after_matching(self, state: InvoiceState) -> str:
        """Decide whether to continue or escalate after matching."""
        if not state.matching_result:
            return "escalate"
        
        # Don't escalate for no match - let discrepancy detection handle it
        # This allows for better reasoning about what went wrong
        return "continue"
    
    def process_invoice(self, file_path: str) -> InvoiceState:
        """
        Process a single invoice through the workflow.
        
        Args:
            file_path: Path to the invoice file
            
        Returns:
            Final processing state
        """
        from pathlib import Path
        
        file_path = Path(file_path)
        start_time = time.time()
        
        # Initialize state
        initial_state = InvoiceState(
            file_path=str(file_path),
            file_name=file_path.name,
            processing_start_time=start_time
        )
        
        # Run the workflow
        final_state_dict = self.app.invoke(initial_state.model_dump())
        
        # Convert back to InvoiceState
        final_state = InvoiceState(**final_state_dict)
        
        return final_state
    
    def format_output(self, state: InvoiceState) -> dict:
        """
        Format the final state into the required JSON output format.
        
        Args:
            state: Final processing state
            
        Returns:
            Formatted output dictionary matching schema requirements
        """
        from datetime import datetime
        import time
        
        # Calculate processing duration
        if state.processing_start_time:
            duration = time.time() - state.processing_start_time
        else:
            duration = sum(
                trace.get("duration_ms", 0) 
                for trace in state.agent_traces.values()
            ) / 1000.0
        
        # Build extracted data section
        extracted_data = {}
        if state.extracted_invoice:
            inv = state.extracted_invoice
            extracted_data = {
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date,
                "supplier": inv.supplier_name,
                "supplier_vat": inv.supplier_vat,
                "po_reference": inv.po_reference,
                "payment_terms": inv.payment_terms,
                "currency": inv.currency,
                "line_items": [
                    {
                        "item_code": item.item_code,
                        "description": item.description,
                        "quantity": item.quantity,
                        "unit": item.unit,
                        "unit_price": item.unit_price,
                        "line_total": item.line_total,
                        "extraction_confidence": item.extraction_confidence
                    }
                    for item in inv.line_items
                ],
                "subtotal": inv.subtotal,
                "vat_amount": inv.vat_amount,
                "vat_rate": inv.vat_rate,
                "total": inv.total
            }
        
        # Build matching results section
        matching_results = {}
        if state.matching_result:
            mr = state.matching_result
            matching_results = {
                "po_match_confidence": mr.po_match_confidence,
                "matched_po": mr.matched_po,
                "match_method": mr.match_method,
                "supplier_match": mr.supplier_match,
                "line_items_matched": mr.line_items_matched,
                "line_items_total": mr.line_items_total,
                "match_rate": mr.match_rate,
                "alternative_matches": mr.alternative_matches
            }
        
        # Build discrepancies section
        discrepancies = []
        for d in state.discrepancies:
            disc_dict = {
                "type": d.type,
                "severity": d.severity,
                "field": d.field,
                "details": d.details,
                "recommended_action": d.recommended_action,
                "confidence": d.confidence
            }
            if d.line_item_index is not None:
                disc_dict["line_item_index"] = d.line_item_index
            if d.invoice_value is not None:
                disc_dict["invoice_value"] = d.invoice_value
            if d.po_value is not None:
                disc_dict["po_value"] = d.po_value
            if d.variance_percentage is not None:
                disc_dict["variance_percentage"] = d.variance_percentage
            discrepancies.append(disc_dict)
        
        # Build total variance section
        total_variance = {}
        if state.total_variance:
            total_variance = {
                "amount": state.total_variance.amount,
                "percentage": state.total_variance.percentage,
                "within_tolerance": state.total_variance.within_tolerance
            }
        
        # Build agent execution trace
        agent_trace = {}
        for agent_name, trace in state.agent_traces.items():
            agent_trace[agent_name] = {
                "duration_ms": trace.get("duration_ms", 0),
                "confidence": trace.get("confidence", 0.0),
                "status": trace.get("status", "unknown")
            }
        
        # Final output structure
        output = {
            "invoice_id": (
                state.extracted_invoice.invoice_number 
                if state.extracted_invoice 
                else state.file_name
            ),
            "processing_timestamp": datetime.utcnow().isoformat() + "Z",
            "processing_duration_seconds": round(duration, 2),
            "document_info": {
                "filename": state.file_name,
                "document_quality": state.document_quality
            },
            "processing_results": {
                "extraction_confidence": state.extraction_confidence,
                "document_quality": state.document_quality,
                "extracted_data": extracted_data,
                "matching_results": matching_results,
                "discrepancies": discrepancies,
                "total_variance": total_variance,
                "recommended_action": state.recommended_action,
                "risk_level": state.risk_level,
                "confidence": state.confidence,
                "agent_reasoning": state.agent_reasoning
            },
            "agent_execution_trace": agent_trace
        }
        
        if state.errors:
            output["errors"] = state.errors
        
        return output
