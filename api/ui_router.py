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
from core.conversation_manager import conversation_manager
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


def _build_conversation_context(conversation_id: str) -> str:
    """Build context string from conversation history."""
    context_data = conversation_manager.get_full_context(conversation_id)
    history = context_data["history"]

    if not history:
        return ""

    # Build context from recent history (last 10 exchanges)
    recent_history = history[-20:] if len(history) > 20 else history

    context_lines = ["## Previous Conversation Context:"]
    for role, content in recent_history:
        context_lines.append(f"{role.upper()}: {content[:200]}...")  # Truncate long messages

    context_lines.append("")  # Add blank line
    return "\n".join(context_lines)


async def handle_input(input_data: UIInput):
    """
    Handle user input with conversation persistence and context awareness.
    
    Flow:
    1. Get or create conversation ID
    2. Add user message to conversation history
    3. Retrieve full conversation context
    4. Invoke agent with context and message history
    5. Store assistant response in conversation
    6. Return parsed response
    """
    conversation_id = input_data.get_or_create_conversation_id()
    
    try:
        # Initialize conversation if new
        if not conversation_manager.db.get_conversation_info(conversation_id):
            conversation_manager.start_conversation(
                conversation_id,
                user_id=input_data.user_id,
                session_name=input_data.session_name
            )
            logger.info(f"Started new conversation: {conversation_id}")

        # Store user message in conversation
        conversation_manager.add_message(
            conversation_id,
            role="user",
            content=input_data.query,
            metadata={"source": "ui", "session_name": input_data.session_name}
        )

        # Get conversation history for LLM context
        conversation_context = _build_conversation_context(conversation_id)
        augmented_query = f"{conversation_context}USER: {input_data.query}"

        # Build message history for the agent (all previous messages)
        history = conversation_manager.get_conversation_history(conversation_id)

        # Invoke agent with conversation history and thread ID for consistency
        res = await agent.ainvoke(
            {"messages": history},  # Pass full history
            config={"configurable": {"thread_id": conversation_id}}  # Use conversation_id as thread
        )

        # Extract response
        if res is not None:
            ai_msg = res["messages"][-1].content
        else:
            ai_msg = "No response generated"

        if ai_msg is not None:
            if not isinstance(ai_msg, str):
                ai_msg = str(ai_msg).strip('"')

        parsed_response = parse_agent_response(ai_msg)

        # Store assistant response in conversation
        conversation_manager.add_message(
            conversation_id,
            role="assistant",
            content=json.dumps(parsed_response),
            metadata={"parsed": True}
        )

        # Return response with conversation ID for client
        return {
            **parsed_response,
            "conversation_id": conversation_id,
            "context_message_count": len(history)
        }

    except Exception as e:
        logger.error(f"Error in handle_input: {str(e)}", exc_info=True)
        
        # Try to store error in conversation
        try:
            conversation_manager.add_message(
                conversation_id,
                role="system",
                content=f"Error: {str(e)}",
                metadata={"error": True}
            )
        except:
            pass

        return {"error": str(e), "conversation_id": conversation_id}
    

@router.post("/input-handler")
async def handle_ui_inputs(input: UIInput):
    """
    Main endpoint for user queries with conversation context.
    
    Request body:
    {
        "query": "Your question",
        "conversation_id": "optional-conversation-id",  # Reuse for multi-turn
        "user_id": "optional-user-id",
        "session_name": "optional-session-name"
    }
    
    Response includes conversation_id to maintain context across requests.
    """
    return await handle_input(input)


@router.get("/conversations")
async def list_conversations(user_id: str = None):
    """
    List all conversations for a user or globally.
    """
    try:
        conversations = conversation_manager.list_conversations(user_id)
        return {
            "conversations": conversations,
            "count": len(conversations)
        }
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        return {"error": str(e)}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Get full conversation details including history.
    """
    try:
        context = conversation_manager.get_full_context(conversation_id)
        if not context:
            return {"error": "Conversation not found"}
        return context
    except Exception as e:
        logger.error(f"Error retrieving conversation: {e}")
        return {"error": str(e)}


@router.post("/conversations/{conversation_id}/context")
async def set_context_variable(conversation_id: str, data: dict):
    """
    Set context variables for a conversation.
    Useful for maintaining shared state across messages.
    
    Request body:
    {
        "key": "variable_name",
        "value": "variable_value"
    }
    """
    try:
        key = data.get("key")
        value = data.get("value")
        
        if not key:
            return {"error": "key is required"}
        
        success = conversation_manager.set_context_variable(
            conversation_id,
            key,
            value
        )
        
        if success:
            return {"message": f"Set {key}={value}", "conversation_id": conversation_id}
        else:
            return {"error": "Failed to set context variable"}
    except Exception as e:
        logger.error(f"Error setting context variable: {e}")
        return {"error": str(e)}


@router.get("/conversations/{conversation_id}/context")
async def get_context_variables(conversation_id: str):
    """
    Get all context variables for a conversation.
    """
    try:
        variables = conversation_manager.get_context_variables(conversation_id)
        return {
            "conversation_id": conversation_id,
            "context_variables": variables
        }
    except Exception as e:
        logger.error(f"Error retrieving context variables: {e}")
        return {"error": str(e)}


@router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(conversation_id: str):
    """
    Archive a conversation to clean up active memory.
    """
    try:
        success = conversation_manager.archive_conversation(conversation_id)
        if success:
            return {"message": "Conversation archived"}
        else:
            return {"error": "Failed to archive conversation"}
    except Exception as e:
        logger.error(f"Error archiving conversation: {e}")
        return {"error": str(e)}


@router.post("/upload")
async def upload_pdfs(file : UploadFile = File(...)):
    file_path = os.path.join(pdf_directory, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "File uploaded successfully",
        "path": file_path
    }




