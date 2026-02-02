"""Pydantic data models for the invoice reconciliation system."""

from datetime import datetime
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """A line item from an invoice or PO."""
    item_code: Optional[str] = None
    description: str
    quantity: float
    unit: str = "units"
    unit_price: float
    line_total: float
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractedInvoice(BaseModel):
    """Extracted data from an invoice document."""
    invoice_number: str
    invoice_date: str
    supplier_name: str
    supplier_address: Optional[str] = None
    supplier_vat: Optional[str] = None
    po_reference: Optional[str] = None
    payment_terms: Optional[str] = None
    currency: str = "GBP"
    line_items: list[LineItem]
    subtotal: float
    vat_rate: Optional[float] = None
    vat_amount: Optional[float] = None
    total: float
    bill_to: Optional[dict] = None


class PurchaseOrder(BaseModel):
    """A purchase order from the database."""
    po_number: str
    supplier: str
    date: str
    total: float
    currency: str = "GBP"
    line_items: list[LineItem]


class MatchingResult(BaseModel):
    """Result of matching an invoice to a PO."""
    po_match_confidence: float = Field(ge=0.0, le=1.0)
    matched_po: Optional[str] = None
    match_method: Literal[
        "exact_po_reference",
        "fuzzy_supplier_product_match",
        "product_only_match",
        "no_match"
    ] = "no_match"
    supplier_match: bool = False
    date_variance_days: Optional[int] = None
    line_items_matched: int = 0
    line_items_total: int = 0
    match_rate: float = 0.0
    alternative_matches: list[dict] = Field(default_factory=list)
    matched_po_data: Optional[PurchaseOrder] = None


class Discrepancy(BaseModel):
    """A discrepancy found between invoice and PO."""
    type: Literal[
        "price_mismatch",
        "quantity_mismatch",
        "missing_po_reference",
        "supplier_mismatch",
        "total_variance",
        "missing_line_item",
        "extra_line_item",
        "description_mismatch"
    ]
    severity: Literal["low", "medium", "high", "critical"]
    line_item_index: Optional[int] = None
    field: Optional[str] = None
    invoice_value: Optional[Any] = None
    po_value: Optional[Any] = None
    variance_percentage: Optional[float] = None
    details: str
    recommended_action: Literal["auto_approve", "flag_for_review", "escalate_to_human"]
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class TotalVariance(BaseModel):
    """Total variance between invoice and PO."""
    amount: float
    percentage: float
    within_tolerance: bool


class AgentExecutionTrace(BaseModel):
    """Execution trace for an agent."""
    duration_ms: int
    confidence: float
    status: Literal["success", "warning", "error"]
    notes: Optional[str] = None


class ProcessingResult(BaseModel):
    """Final processing result for an invoice."""
    invoice_id: str
    processing_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    processing_duration_seconds: Optional[float] = None
    document_info: dict = Field(default_factory=dict)
    processing_results: dict = Field(default_factory=dict)
    agent_execution_trace: dict = Field(default_factory=dict)


class InvoiceState(BaseModel):
    """Shared state for the LangGraph invoice processing workflow."""
    # Input
    file_path: str
    file_name: str
    
    # Document Intelligence Agent output
    raw_text: str = ""
    extracted_invoice: Optional[ExtractedInvoice] = None
    extraction_confidence: float = 0.0
    document_quality: str = "unknown"
    extraction_notes: str = ""
    
    # Matching Agent output
    matching_result: Optional[MatchingResult] = None
    matching_notes: str = ""
    
    # Discrepancy Detection Agent output
    discrepancies: list[Discrepancy] = Field(default_factory=list)
    total_variance: Optional[TotalVariance] = None
    discrepancy_notes: str = ""
    
    # Resolution Recommendation Agent output
    recommended_action: Literal[
        "auto_approve", "flag_for_review", "escalate_to_human"
    ] = "escalate_to_human"
    confidence: float = 0.0
    risk_level: Literal["none", "low", "medium", "high", "critical"] = "high"
    agent_reasoning: str = ""
    
    # Processing metadata
    processing_start_time: Optional[float] = None
    agent_traces: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
