from fastapi import FastAPI
from api.ui_router import router as uiRouter

app = FastAPI()

app.include_router(uiRouter)

@app.get("/health")
def healthCheck():
    return "System is Healthy"
