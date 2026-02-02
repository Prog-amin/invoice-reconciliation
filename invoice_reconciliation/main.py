"""Main entry point for the invoice reconciliation system."""

import json
import time
import argparse
from pathlib import Path

from .config import INVOICE_FILES, OUTPUT_DIR, GROQ_API_KEY
from .orchestrator.graph import InvoiceReconciliationGraph


def process_single_invoice(file_path: str, output_dir: Path = OUTPUT_DIR) -> dict:
    """
    Process a single invoice and save the result.
    
    Args:
        file_path: Path to the invoice file
        output_dir: Directory to save output JSON
        
    Returns:
        Processing result dictionary
    """
    print(f"\n{'='*60}")
    print(f"Processing: {Path(file_path).name}")
    print(f"{'='*60}")
    
    # Create the workflow
    workflow = InvoiceReconciliationGraph()
    
    # Process the invoice
    start_time = time.time()
    final_state = workflow.process_invoice(file_path)
    duration = time.time() - start_time
    
    # Format output
    result = workflow.format_output(final_state)
    
    # Print summary
    print(f"\n📄 Invoice ID: {result['invoice_id']}")
    print(f"⏱️  Processing time: {duration:.2f}s")
    print(f"📊 Extraction confidence: {result['processing_results']['extraction_confidence']:.0%}")
    
    if result['processing_results']['matching_results']:
        mr = result['processing_results']['matching_results']
        print(f"🔗 PO Match: {mr['matched_po'] or 'None'} ({mr['match_method']})")
        print(f"📈 Match confidence: {mr['po_match_confidence']:.0%}")
    
    discrepancies = result['processing_results']['discrepancies']
    print(f"⚠️  Discrepancies: {len(discrepancies)}")
    
    for d in discrepancies:
        severity_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(d['severity'], "⚪")
        print(f"   {severity_icon} {d['type']}: {d['severity']}")
    
    action = result['processing_results']['recommended_action']
    action_icon = {
        "auto_approve": "✅", 
        "flag_for_review": "🔍", 
        "escalate_to_human": "🚨"
    }.get(action, "❓")
    
    print(f"\n{action_icon} Recommended Action: {action.replace('_', ' ').upper()}")
    print(f"🎯 Confidence: {result['processing_results']['confidence']:.0%}")
    
    print(f"\n💭 Reasoning:")
    print(f"   {result['processing_results']['agent_reasoning'][:500]}...")
    
    # Save result
    output_file = output_dir / f"{Path(file_path).stem}_result.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n💾 Saved to: {output_file}")
    
    return result


def process_all_invoices():
    """Process all test invoices."""
    if not GROQ_API_KEY:
        print("❌ Error: GROQ_API_KEY not found in environment variables.")
        print("Please create a .env file with your Groq API key.")
        print("See .env.example for the required format.")
        return
    
    print("\n" + "="*70)
    print("🔄 INVOICE RECONCILIATION MULTI-AGENT SYSTEM")
    print("="*70)
    print(f"\nProcessing {len(INVOICE_FILES)} invoices...")
    
    overall_start = time.time()
    results = []
    
    for name, file_path in INVOICE_FILES.items():
        if not file_path.exists():
            print(f"\n⚠️  File not found: {file_path}")
            continue
        
        try:
            result = process_single_invoice(str(file_path))
            results.append(result)
        except Exception as e:
            print(f"\n❌ Error processing {name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    total_time = time.time() - overall_start
    print("\n" + "="*70)
    print("📊 PROCESSING SUMMARY")
    print("="*70)
    print(f"\n✅ Processed: {len(results)} invoices")
    print(f"⏱️  Total time: {total_time:.2f}s")
    print(f"📈 Average time: {total_time/len(results):.2f}s per invoice" if results else "")
    
    # Action breakdown
    actions = {}
    for r in results:
        action = r['processing_results']['recommended_action']
        actions[action] = actions.get(action, 0) + 1
    
    print("\n📋 Actions Breakdown:")
    for action, count in actions.items():
        icon = {"auto_approve": "✅", "flag_for_review": "🔍", "escalate_to_human": "🚨"}.get(action, "❓")
        print(f"   {icon} {action.replace('_', ' ').title()}: {count}")
    
    # Check critical test cases
    print("\n🎯 Critical Test Cases:")
    for r in results:
        invoice_id = r['invoice_id']
        
        # Invoice 4 - Price discrepancy check
        if "4" in r['document_info']['filename'] or "Price" in str(r):
            price_disc = [
                d for d in r['processing_results']['discrepancies'] 
                if d['type'] == 'price_mismatch'
            ]
            if price_disc:
                print(f"   ✅ Invoice 4: Price discrepancy DETECTED")
                for pd in price_disc:
                    print(f"      - {pd['details'][:100]}...")
            else:
                print(f"   ❌ Invoice 4: Price discrepancy NOT detected")
        
        # Invoice 5 - Missing PO check
        if "5" in r['document_info']['filename'] or "Missing" in str(r):
            mr = r['processing_results']['matching_results']
            if mr.get('match_method') in ['fuzzy_supplier_product_match', 'product_only_match']:
                print(f"   ✅ Invoice 5: Fuzzy matching SUCCEEDED ({mr['matched_po']})")
            elif mr.get('matched_po'):
                print(f"   ✅ Invoice 5: Matched to {mr['matched_po']}")
            else:
                print(f"   ⚠️  Invoice 5: No match found")
    
    print("\n" + "="*70)
    print("🏁 Processing Complete!")
    print("="*70)
    
    # Save combined results
    combined_output = OUTPUT_DIR / "all_results.json"
    with open(combined_output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 All results saved to: {combined_output}")


def main():
    """Main entry point with CLI support."""
    parser = argparse.ArgumentParser(
        description="Invoice Reconciliation Multi-Agent System"
    )
    parser.add_argument(
        "--file", "-f",
        help="Process a single invoice file"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Process all test invoices"
    )
    parser.add_argument(
        "--invoice",
        choices=["1", "2", "3", "4", "5"],
        help="Process specific test invoice (1-5)"
    )
    
    args = parser.parse_args()
    
    if args.file:
        process_single_invoice(args.file)
    elif args.invoice:
        invoice_key = f"invoice_{args.invoice}"
        if invoice_key in INVOICE_FILES:
            process_single_invoice(str(INVOICE_FILES[invoice_key]))
        else:
            print(f"Invoice {args.invoice} not found")
    else:
        # Default: process all
        process_all_invoices()


if __name__ == "__main__":
    main()
