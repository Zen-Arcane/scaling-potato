"""
PDF Embedding Scheduler

Automatically monitors the data-source directory for new PDFs,
embeds them, and stores them in the vector database.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils.pdfExtractor import store_pdf_embeddings
from utils.decorators import log_execution

logger = logging.getLogger(__name__)

# File to track processed PDFs
PROCESSED_PDFS_FILE = "data-source/.processed_pdfs.json"
DATA_SOURCE_DIR = "data-source"


def get_processed_pdfs():
    """Load list of already processed PDFs from tracking file."""
    if os.path.exists(PROCESSED_PDFS_FILE):
        try:
            with open(PROCESSED_PDFS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_processed_pdfs(processed):
    """Save list of processed PDFs to tracking file."""
    os.makedirs(os.path.dirname(PROCESSED_PDFS_FILE) or ".", exist_ok=True)
    with open(PROCESSED_PDFS_FILE, "w") as f:
        json.dump(processed, f, indent=2)


def get_pdf_hash(pdf_path):
    """Generate a simple hash based on file size and modification time."""
    try:
        stat = os.stat(pdf_path)
        return f"{stat.st_size}_{stat.st_mtime}"
    except OSError:
        return None


@log_execution
def scan_and_embed_pdfs():
    """
    Scan data-source directory for new or modified PDFs and embed them.
    
    Returns:
        dict: Statistics about the operation including count of new/updated/failed PDFs
    """
    stats = {
        "new_pdfs": 0,
        "updated_pdfs": 0,
        "failed_pdfs": [],
        "skipped_pdfs": 0,
        "total_chunks_indexed": 0,
        "timestamp": datetime.now().isoformat()
    }
    
    # Ensure data source directory exists
    if not os.path.exists(DATA_SOURCE_DIR):
        logger.info(f"Creating data-source directory: {DATA_SOURCE_DIR}")
        os.makedirs(DATA_SOURCE_DIR, exist_ok=True)
        return stats
    
    processed_pdfs = get_processed_pdfs()
    pdf_files = list(Path(DATA_SOURCE_DIR).glob("*.pdf"))
    
    if not pdf_files:
        logger.info("No PDF files found in data-source directory")
        return stats
    
    logger.info(f"Found {len(pdf_files)} PDF files in data-source directory")
    
    for pdf_path in pdf_files:
        pdf_name = pdf_path.name
        pdf_str = str(pdf_path)
        current_hash = get_pdf_hash(pdf_str)
        
        if not current_hash:
            stats["failed_pdfs"].append(pdf_name)
            continue
        
        # Check if PDF was already processed
        if pdf_name in processed_pdfs:
            previous_hash = processed_pdfs[pdf_name].get("hash")
            if previous_hash == current_hash:
                logger.debug(f"Skipping already processed PDF: {pdf_name}")
                stats["skipped_pdfs"] += 1
                continue
            else:
                logger.info(f"PDF has been modified, re-processing: {pdf_name}")
                stats["updated_pdfs"] += 1
        else:
            logger.info(f"Processing new PDF: {pdf_name}")
            stats["new_pdfs"] += 1
        
        try:
            # Embed and store the PDF
            chunks_indexed = store_pdf_embeddings(pdf_str)
            stats["total_chunks_indexed"] += chunks_indexed
            
            # Mark as processed
            processed_pdfs[pdf_name] = {
                "hash": current_hash,
                "processed_at": datetime.now().isoformat(),
                "chunks_indexed": chunks_indexed
            }
            
            logger.info(f"Successfully indexed {chunks_indexed} chunks from {pdf_name}")
            
        except Exception as e:
            logger.error(f"Failed to process PDF {pdf_name}: {str(e)}")
            stats["failed_pdfs"].append(f"{pdf_name} ({str(e)})")
    
    # Save updated tracking file
    save_processed_pdfs(processed_pdfs)
    
    logger.info(f"Scheduler cycle completed: {stats}")
    return stats


class PDFEmbeddingScheduler:
    """Manages scheduled PDF embedding tasks."""
    
    def __init__(self, interval_minutes=5):
        """
        Initialize the PDF embedding scheduler.
        
        Args:
            interval_minutes: How often to scan for new PDFs (default: 5 minutes)
        """
        self.scheduler = BackgroundScheduler()
        self.interval_minutes = interval_minutes
        self.is_running = False
    
    def start(self):
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.scheduler.add_job(
            scan_and_embed_pdfs,
            IntervalTrigger(minutes=self.interval_minutes),
            id="pdf_embedding_job",
            name="PDF Embedding Scheduler",
            replace_existing=True,
            misfire_grace_time=60
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info(f"PDF Embedding Scheduler started (checking every {self.interval_minutes} minutes)")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("PDF Embedding Scheduler stopped")
    
    def trigger_now(self):
        """Manually trigger a PDF scan right now."""
        logger.info("Manually triggering PDF scan")
        return scan_and_embed_pdfs()
    
    def get_status(self):
        """Get current scheduler status."""
        return {
            "is_running": self.is_running,
            "interval_minutes": self.interval_minutes,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in self.scheduler.get_jobs()
            ]
        }


# Global scheduler instance
pdf_scheduler = PDFEmbeddingScheduler(interval_minutes=5)
