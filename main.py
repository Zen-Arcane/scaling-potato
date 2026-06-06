from fastapi import FastAPI, UploadFile, File
import os
from dotenv import load_dotenv
import shutil

load_dotenv()

app = FastAPI()

pdf_directory = os.getenv("UPLOAD_DIR")

os.makedirs(pdf_directory, exist_ok=True)

@app.get("/health")
def healthCheck():
    return "System is Healthy"

@app.post("/upload")
def upload_pdfs(file : UploadFile = File(...)):
    file_path = os.path.join(pdf_directory, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "File uploaded successfully",
        "path": file_path
    }