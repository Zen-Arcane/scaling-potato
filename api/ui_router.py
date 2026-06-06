from  fastapi import APIRouter
from fastapi import FastAPI, UploadFile, File
import os
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
import shutil
from utils.pdfExtractor import extract_text

from utils.pdfExtractor import extract_text

load_dotenv()

app = FastAPI()

pdf_directory = os.getenv("UPLOAD_DIR")

os.makedirs(pdf_directory, exist_ok=True)

router = APIRouter()


@router.post("/input-handler")
def handle_ui_inputs():
    pass


@router.post("/upload")
def upload_pdfs(file : UploadFile = File(...)):
    file_path = os.path.join(pdf_directory, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "File uploaded successfully",
        "path": file_path
    }

@router.get("/extract")
def extract_text_from_pdf():
   return extract_text()

