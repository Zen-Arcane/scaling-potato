# PDF Embedding Scheduler Documentation

## Overview

The PDF Embedding Scheduler automatically monitors the `data-source` directory for new or modified PDF files, extracts text, creates embeddings, and stores them in the vector database. This eliminates the need for manual embedding operations.

## Features

- **Automatic Monitoring**: Continuously scans for new PDFs without manual intervention
- **Change Detection**: Re-processes modified PDFs while skipping unchanged ones
- **Tracking**: Maintains a `.processed_pdfs.json` file to track processed files and their metadata
- **Error Handling**: Gracefully handles processing failures and logs them for debugging
- **Configurable Intervals**: Adjust how frequently the scheduler checks for new PDFs
- **Manual Control**: Start, stop, or trigger scans via API endpoints
- **Background Operation**: Runs in the background without blocking the main application

## Installation

1. Install APScheduler (automatically added to requirements.txt):
```bash
pip install -r requirements.txt
```

2. The scheduler is automatically started when the application starts.

## Configuration

### Interval Configuration

Edit the scheduler interval in [main.py](main.py) or [pdf_scheduler.py](core/pdf_scheduler.py):

```python
# Default is 5 minutes
pdf_scheduler = PDFEmbeddingScheduler(interval_minutes=5)
```

### Data Source Directory

By default, the scheduler monitors: `data-source/`

Change this by modifying `DATA_SOURCE_DIR` in [core/pdf_scheduler.py](core/pdf_scheduler.py):

```python
DATA_SOURCE_DIR = "data-source"  # Change this path as needed
```

## Usage

### Automatic Start

The scheduler automatically starts when the FastAPI application starts and stops on shutdown.

### API Endpoints

#### Get Scheduler Status
```bash
curl http://localhost:8000/scheduler/status
```

Response:
```json
{
  "is_running": true,
  "interval_minutes": 5,
  "jobs": [
    {
      "id": "pdf_embedding_job",
      "name": "PDF Embedding Scheduler",
      "next_run_time": "2026-06-08T12:30:00"
    }
  ]
}
```

#### Start Scheduler
```bash
curl -X POST http://localhost:8000/scheduler/start
```

#### Stop Scheduler
```bash
curl -X POST http://localhost:8000/scheduler/stop
```

#### Trigger Immediate Scan
```bash
curl -X POST http://localhost:8000/scheduler/trigger
```

Response:
```json
{
  "message": "PDF scan triggered",
  "result": {
    "new_pdfs": 1,
    "updated_pdfs": 0,
    "failed_pdfs": [],
    "skipped_pdfs": 2,
    "total_chunks_indexed": 45,
    "timestamp": "2026-06-08T12:25:00"
  }
}
```

## Processed PDFs Tracking

The scheduler maintains a `.processed_pdfs.json` file in the `data-source/` directory:

```json
{
  "document1.pdf": {
    "hash": "123456_1625000000.0",
    "processed_at": "2026-06-08T12:20:00.123456",
    "chunks_indexed": 45
  },
  "document2.pdf": {
    "hash": "789012_1625000100.0",
    "processed_at": "2026-06-08T12:15:00.654321",
    "chunks_indexed": 32
  }
}
```

The hash is based on file size and modification time. If either changes, the PDF is re-processed automatically.

## Testing

Run the test script to verify scheduler functionality:

```bash
python test_scheduler.py
```

This will:
1. Check tracked PDFs
2. Run a manual scan
3. Check scheduler status
4. Start the scheduler
5. Let it run for 10 seconds
6. Stop the scheduler

## Logging

The scheduler logs to the standard Python logging system. Configure logging in your application:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Log messages include:
- New PDFs found and processed
- Modified PDFs re-processed
- Skipped unchanged PDFs
- Processing errors and failures
- Scheduler start/stop events

## How It Works

1. **Startup**: When the FastAPI app starts, the scheduler begins monitoring
2. **First Run**: An immediate scan happens on startup to process any pending PDFs
3. **Periodic Checks**: Every 5 minutes (configurable), the scheduler:
   - Scans the `data-source/` directory for `.pdf` files
   - Checks each file against the tracking database
   - For new or modified PDFs:
     - Extracts text using `pdfExtractor.extract_text()`
     - Chunks text using `pdfExtractor.chunk_text()`
     - Embeds chunks using the configured embedding model
     - Stores in the vector database
   - Updates the tracking file with processed metadata
4. **Error Handling**: Failures are logged and recorded but don't stop the scheduler
5. **Shutdown**: When the app stops, the scheduler gracefully shuts down

## File Structure

```
scaling-potato/
├── main.py                    # Updated with scheduler lifecycle
├── requirements.txt           # Added apscheduler
├── core/
│   ├── orchestrator.py
│   └── pdf_scheduler.py       # NEW: Scheduler implementation
├── data-source/
│   ├── *.pdf                  # PDFs to process
│   └── .processed_pdfs.json   # Auto-generated tracking file
├── utils/
│   ├── pdfExtractor.py        # Used by scheduler
│   ├── embeddings.py
│   └── ...
└── test_scheduler.py          # NEW: Test suite
```

## Troubleshooting

### Scheduler Not Processing PDFs

1. **Check logs** for error messages
2. **Verify** PDFs are in the correct directory: `data-source/`
3. **Trigger manually** with: `curl -X POST http://localhost:8000/scheduler/trigger`
4. **Check permissions** on the data-source directory
5. **Verify vector store** connection with the health endpoint

### PDFs Being Re-processed Repeatedly

This means the file is being modified. Check:
1. File is not being locked by another process
2. Modification time is not changing unexpectedly
3. File permissions are not being reset

### High Memory Usage

If processing very large PDFs:
1. Reduce chunk size in `pdfExtractor.chunk_text()` - default is 1000 chars
2. Increase scheduler interval in `pdf_scheduler.py` - default is 5 minutes
3. Process PDFs in smaller batches manually

## Future Enhancements

Potential improvements to consider:
- Database-backed tracking instead of JSON file
- Webhook notifications on completion
- Batch processing queue with priority levels
- Support for other document formats (DOCX, TXT, etc.)
- Retry mechanism for failed PDFs
- Compression of old tracking data
- Performance metrics and statistics
