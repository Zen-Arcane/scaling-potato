from  fastapi import APIRouter
from fastapi import FastAPI, UploadFile, File
import os
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
import shutil
from config.wrapperConfig import LLMFactory
from utils.sysPrompt import systemPrompt
from uuid_utils import uuid4
from utils.pdfExtractor import extract_text
from models.InputHandler import UIInput
from core.orchestrator import tools as orchestrator_tools

load_dotenv()
memory = InMemorySaver()

app = FastAPI()

pdf_directory = os.getenv("UPLOAD_DIR")

os.makedirs(pdf_directory, exist_ok=True)

router = APIRouter()

async def handle_input(query: str):
    thread_id = uuid4().hex
   
    llm = LLMFactory.get_llm()
    agent = create_react_agent(
        tools=orchestrator_tools,
        prompt=systemPrompt,
        model=llm,
        checkpointer=memory,
    )

    try:
        res = await agent.ainvoke({"messages": [("user", query)]},config={"configurable": {"thread_id": thread_id}})   
        if res is not None:
            ai_msg = res["messages"][-1].content
        if ai_msg is not None:
            if not isinstance(ai_msg, str):
                ai_msg = str(ai_msg).strip('"')
        return {"response": ai_msg}
    except Exception as e:
        return {"error": str(e)}

@router.post("/input-handler")
async def handle_ui_inputs(input: UIInput):
   return await handle_input(input.query)


@router.post("/upload")
async def upload_pdfs(file : UploadFile = File(...)):
    file_path = os.path.join(pdf_directory, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "File uploaded successfully",
        "path": file_path
    }



