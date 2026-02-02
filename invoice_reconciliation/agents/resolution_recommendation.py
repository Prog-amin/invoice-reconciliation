"""Resolution Recommendation Agent - Decides on actions and generates reasoning."""

import time
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from ..config import GROQ_API_KEY, GROQ_MODEL, ReconciliationThresholds
from ..utils.schemas import InvoiceState, Discrepancy


class ResolutionRecommendationAgent:
    """Agent responsible for recommending resolution actions and generating reasoning."""
    
    REASONING_SYSTEM_PROMPT = """You are an expert invoice reconciliation analyst. Your task is to analyze the processing results and provide a clear, professional reasoning summary.

You will be given:
1. Invoice extraction details
2. PO matching results
3. Discrepancies found
4. Recommended action

Write a clear, concise reasoning paragraph that:
- Summarizes what was extracted and matched
- Explains any discrepancies found
- Justifies the recommended action
- Mentions confidence levels
- Is written in past tense, professional tone
- Is 3-5 sentences maximum

The reasoning should be suitable for a business audit trail."""

    def __init__(self):
        """Initialize the Resolution Recommendation Agent."""
        self.llm = ChatGroq(
            api_key=GROQ_API_KEY,
            model_name=GROQ_MODEL,
            temperature=0.3,  # Slightly creative for natural language
            max_tokens=500
        )
    
    def process(self, state: InvoiceState) -> InvoiceState:
        """
        Determine recommended action and generate reasoning.
        
        Args:
            state: Current invoice processing state
            
        Returns:
            Updated state with recommendation and reasoning
        """
        start_time = time.time()
        
        try:
            # Determine the recommended action
            action, confidence, risk_level = self._determine_action(state)
            
            state.recommended_action = action
            state.confidence = confidence
            state.risk_level = risk_level
            
            # Generate reasoning using LLM
            state.agent_reasoning = self._generate_reasoning(state)
            
            return self._finalize_trace(state, start_time, "success")
            
        except Exception as e:
            state.errors.append(f"Resolution Agent error: {str(e)}")
            state.recommended_action = "escalate_to_human"
            state.confidence = 0.5
            state.risk_level = "high"
            state.agent_reasoning = (
                f"Error during resolution analysis: {str(e)}. "
                "Defaulting to human escalation for safety."
            )
            return self._finalize_trace(state, start_time, "error")
    
    def _determine_action(self, state: InvoiceState) -> tuple:
        """
        Determine the recommended action based on all agent outputs.
        
        Returns:
            Tuple of (action, confidence, risk_level)
        """
        # Check for errors first
        if state.errors:
            return "escalate_to_human", 0.5, "high"
        
        # Check extraction confidence
        if state.extraction_confidence < ReconciliationThresholds.EXTRACTION_ACCEPTABLE_CONFIDENCE:
            return "escalate_to_human", state.extraction_confidence, "critical"
        
        # Check for PO match
        if not state.matching_result or state.matching_result.match_method == "no_match":
            return "escalate_to_human", 0.3, "high"
        
        match_confidence = state.matching_result.po_match_confidence
        
        # If low match confidence, escalate
        if match_confidence < ReconciliationThresholds.MATCH_ACCEPTABLE_CONFIDENCE:
            return "escalate_to_human", match_confidence, "high"
        
        # Analyze discrepancies
        discrepancies = state.discrepancies
        
        if not discrepancies:
            # No discrepancies and good match
            if (
                match_confidence >= ReconciliationThresholds.MATCH_HIGH_CONFIDENCE and
                state.extraction_confidence >= ReconciliationThresholds.EXTRACTION_HIGH_CONFIDENCE
            ):
                return "auto_approve", min(match_confidence, state.extraction_confidence), "none"
            else:
                return "auto_approve", min(match_confidence, state.extraction_confidence) * 0.95, "low"
        
        # Count discrepancies by severity
        severity_counts = self._count_by_severity(discrepancies)
        
        # Decision logic based on reconciliation rules
        critical_count = severity_counts.get("critical", 0)
        high_count = severity_counts.get("high", 0)
        medium_count = severity_counts.get("medium", 0)
        low_count = severity_counts.get("low", 0)
        
        # Escalate if any critical or high severity issues
        if critical_count > 0 or high_count > 0:
            return "escalate_to_human", 0.95, "critical" if critical_count > 0 else "high"
        
        # Escalate if too many discrepancies
        total_discrepancies = len(discrepancies)
        if total_discrepancies >= ReconciliationThresholds.MAX_DISCREPANCIES_BEFORE_ESCALATE:
            return "escalate_to_human", 0.90, "high"
        
        # Flag for review if medium severity issues
        if medium_count > 0:
            avg_confidence = self._average_discrepancy_confidence(discrepancies)
            return "flag_for_review", avg_confidence, "medium"
        
        # Only low severity issues - can still auto-approve in some cases
        if low_count <= 2 and match_confidence >= 0.90:
            return "auto_approve", match_confidence * 0.95, "low"
        
        # Default to flag for review
        avg_confidence = self._average_discrepancy_confidence(discrepancies)
        return "flag_for_review", avg_confidence, "low"
    
    def _count_by_severity(self, discrepancies: List[Discrepancy]) -> dict:
        """Count discrepancies by severity level."""
        counts = {}
        for d in discrepancies:
            counts[d.severity] = counts.get(d.severity, 0) + 1
        return counts
    
    def _average_discrepancy_confidence(self, discrepancies: List[Discrepancy]) -> float:
        """Calculate average confidence across discrepancies."""
        if not discrepancies:
            return 1.0
        return sum(d.confidence for d in discrepancies) / len(discrepancies)
    
    def _generate_reasoning(self, state: InvoiceState) -> str:
        """Generate human-readable reasoning for the decision."""
        try:
            # Build context for LLM
            context_parts = []
            
            # Invoice info
            if state.extracted_invoice:
                inv = state.extracted_invoice
                context_parts.append(
                    f"Invoice: {inv.invoice_number} from {inv.supplier_name}, "
                    f"dated {inv.invoice_date}, total £{inv.total:.2f}. "
                    f"Extraction confidence: {state.extraction_confidence:.0%}. "
                    f"Document quality: {state.document_quality}."
                )
            
            # Matching info
            if state.matching_result:
                mr = state.matching_result
                if mr.matched_po:
                    context_parts.append(
                        f"PO Match: {mr.matched_po} via {mr.match_method.replace('_', ' ')}. "
                        f"Match confidence: {mr.po_match_confidence:.0%}. "
                        f"Line items matched: {mr.line_items_matched}/{mr.line_items_total}."
                    )
                else:
                    context_parts.append("No PO match found.")
            
            # Discrepancies
            if state.discrepancies:
                disc_summary = []
                for d in state.discrepancies:
                    disc_summary.append(f"- {d.type}: {d.details}")
                context_parts.append(
                    f"Discrepancies ({len(state.discrepancies)}):\n" + 
                    "\n".join(disc_summary)
                )
            else:
                context_parts.append("No discrepancies found.")
            
            # Total variance
            if state.total_variance:
                tv = state.total_variance
                context_parts.append(
                    f"Total variance: £{tv.amount:.2f} ({tv.percentage:.1%}), "
                    f"{'within' if tv.within_tolerance else 'exceeds'} tolerance."
                )
            
            # Action
            context_parts.append(
                f"Recommended action: {state.recommended_action.replace('_', ' ')}. "
                f"Confidence: {state.confidence:.0%}. Risk level: {state.risk_level}."
            )
            
            context = "\n\n".join(context_parts)
            
            # Generate reasoning with LLM
            messages = [
                SystemMessage(content=self.REASONING_SYSTEM_PROMPT),
                HumanMessage(content=f"Generate a reasoning summary for this invoice processing:\n\n{context}")
            ]
            
            response = self.llm.invoke(messages)
            return response.content.strip()
            
        except Exception as e:
            # Fallback to rule-based reasoning
            return self._generate_fallback_reasoning(state)
    
    def _generate_fallback_reasoning(self, state: InvoiceState) -> str:
        """Generate reasoning without LLM as fallback."""
        parts = []
        
        if state.extracted_invoice:
            inv = state.extracted_invoice
            parts.append(
                f"Invoice {inv.invoice_number} from '{inv.supplier_name}' "
                f"processed with {state.extraction_confidence:.0%} confidence."
            )
        
        if state.matching_result and state.matching_result.matched_po:
            mr = state.matching_result
            match_desc = mr.match_method.replace("_", " ")
            parts.append(
                f"Matched to {mr.matched_po} via {match_desc} "
                f"({mr.po_match_confidence:.0%} confidence)."
            )
        elif state.matching_result:
            parts.append("No matching PO found in database.")
        
        if state.discrepancies:
            disc_types = list(set(d.type.replace("_", " ") for d in state.discrepancies))
            parts.append(
                f"{len(state.discrepancies)} discrepancy(ies) detected: "
                f"{', '.join(disc_types)}."
            )
        else:
            parts.append("No discrepancies detected.")
        
        parts.append(
            f"Recommended action: {state.recommended_action.replace('_', ' ')} "
            f"with {state.confidence:.0%} confidence."
        )
        
        return " ".join(parts)
    
    def _finalize_trace(
        self,
        state: InvoiceState,
        start_time: float,
        status: str
    ) -> InvoiceState:
        """Add execution trace to state."""
        duration_ms = int((time.time() - start_time) * 1000)
        
        state.agent_traces["resolution_recommendation_agent"] = {
            "duration_ms": duration_ms,
            "confidence": state.confidence,
            "status": status,
            "recommended_action": state.recommended_action
        }
        
        return state
