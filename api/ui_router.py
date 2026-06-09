from  fastapi import APIRouter
from fastapi import FastAPI, UploadFile, File
import os
import logging
from dotenv import load_dotenv
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
import shutil
from config.wrapperConfig import LLMFactory
from utils.sysPrompt import systemPrompt
from uuid_utils import uuid4
from models.InputHandler import UIInput
from core.orchestrator import tools as orchestrator_tools
import json
import re

logger = logging.getLogger(__name__)
load_dotenv()
memory = InMemorySaver()

app = FastAPI()

pdf_directory = os.getenv("UPLOAD_DIR")

os.makedirs(pdf_directory, exist_ok=True)

router = APIRouter()

# Create agent once at module level - reused across all requests
logger.info("Initializing agent at module startup...")
llm = LLMFactory.get_llm()
agent = create_react_agent(
    tools=orchestrator_tools,
    prompt=systemPrompt,
    model=llm,
    checkpointer=memory,
)
logger.info("Agent initialized")

# async def handle_input(query: str):
#     thread_id = uuid4().hex

#     try:
#         # Invoke agent with thread-specific memory checkpoint
#         # The same agent instance handles multiple concurrent conversations
#         # via separate thread_ids
#         res = await agent.ainvoke(
#             {"messages": [("user", query)]},
#             config={"configurable": {"thread_id": thread_id}}
#         )
#         if res is not None:
#             ai_msg = res["messages"][-1].content
#         if ai_msg is not None:
#             if not isinstance(ai_msg, str):
#                 ai_msg = str(ai_msg).strip('"')
#         return {"response": ai_msg}
#     except Exception as e:
#         logger.error(f"Error in handle_input: {str(e)}")
#         return {"error": str(e)}



def parse_agent_response(ai_msg):
    if not isinstance(ai_msg, str):
        return ai_msg

    ai_msg = ai_msg.strip()

    # Extract JSON block if present
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", ai_msg, re.DOTALL)

    if match:
        ai_msg = match.group(1)

    try:
        return json.loads(ai_msg)
    except Exception:
        return {
            "response": ai_msg,
            "references": []
        }

async def handle_input(query: str):
    thread_id = uuid4().hex

    try:
        res = await agent.ainvoke(
            {"messages": [("user", query)]},
            config={"configurable": {"thread_id": thread_id}}
        )

        return parse_agent_response(
                res["messages"][-1].content
            )

    except Exception as e:
        logger.error(f"Error in handle_input: {str(e)}")
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



