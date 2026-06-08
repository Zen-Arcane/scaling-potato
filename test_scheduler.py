"""
Test script to verify the PDF embedding scheduler functionality.

Run this to test the scheduler before deploying to production.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.pdf_scheduler import pdf_scheduler, scan_and_embed_pdfs, get_processed_pdfs
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_scheduler():
    """Test the scheduler functionality."""
    print("\n" + "="*50)
    print("PDF Embedding Scheduler - Test Suite")
    print("="*50)
    
    # Test 1: Check processed PDFs tracking
    print("\n[Test 1] Checking processed PDFs tracking...")
    processed = get_processed_pdfs()
    print(f"  Currently tracked PDFs: {len(processed)}")
    for pdf_name, info in processed.items():
        print(f"    - {pdf_name}: {info.get('processed_at')}")
    
    # Test 2: Manual scan
    print("\n[Test 2] Running manual PDF scan...")
    result = scan_and_embed_pdfs()
    print(f"  New PDFs: {result['new_pdfs']}")
    print(f"  Updated PDFs: {result['updated_pdfs']}")
    print(f"  Skipped PDFs: {result['skipped_pdfs']}")
    print(f"  Failed PDFs: {result['failed_pdfs']}")
    print(f"  Total chunks indexed: {result['total_chunks_indexed']}")
    
    # Test 3: Scheduler status before starting
    print("\n[Test 3] Checking scheduler status (before starting)...")
    status = pdf_scheduler.get_status()
    print(f"  Running: {status['is_running']}")
    print(f"  Interval: {status['interval_minutes']} minutes")
    
    # Test 4: Start scheduler
    print("\n[Test 4] Starting scheduler...")
    pdf_scheduler.start()
    status = pdf_scheduler.get_status()
    print(f"  Running: {status['is_running']}")
    print(f"  Scheduled jobs: {len(status['jobs'])}")
    if status['jobs']:
        for job in status['jobs']:
            print(f"    - {job['name']} (next run: {job['next_run_time']})")
    
    # Test 5: Let it run for a bit
    print("\n[Test 5] Letting scheduler run for 10 seconds...")
    for i in range(10, 0, -1):
        print(f"  Waiting... {i}s", end="\r")
        time.sleep(1)
    print("  Done!")
    
    # Test 6: Stop scheduler
    print("\n[Test 6] Stopping scheduler...")
    pdf_scheduler.stop()
    status = pdf_scheduler.get_status()
    print(f"  Running: {status['is_running']}")
    
    print("\n" + "="*50)
    print("All tests completed!")
    print("="*50 + "\n")

if __name__ == "__main__":
    try:
        test_scheduler()
    except Exception as e:
        print(f"\nError during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
