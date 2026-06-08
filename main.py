from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.ui_router import router as uiRouter
from core.pdf_scheduler import pdf_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    pdf_scheduler.trigger_now()  # scan immediately
    pdf_scheduler.start()

    yield

    pdf_scheduler.stop()


app = FastAPI(lifespan=lifespan)

app.include_router(uiRouter)


@app.get("/health")
def healthCheck():
    return "System is Healthy"


@app.get("/scheduler/status")
def get_scheduler_status():
    """Get the current status of the PDF embedding scheduler."""
    return pdf_scheduler.get_status()


@app.post("/scheduler/start")
def start_scheduler():
    """Manually start the PDF embedding scheduler."""
    pdf_scheduler.start()
    return {"message": "PDF embedding scheduler started", "status": pdf_scheduler.get_status()}


@app.post("/scheduler/stop")
def stop_scheduler():
    """Manually stop the PDF embedding scheduler."""
    pdf_scheduler.stop()
    return {"message": "PDF embedding scheduler stopped"}


@app.post("/scheduler/trigger")
def trigger_scheduler():
    """Manually trigger an immediate PDF scan and embedding."""
    result = pdf_scheduler.trigger_now()
    return {"message": "PDF scan triggered", "result": result}

