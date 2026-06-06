
from langchain_core.tools import tool
from utils.decorators import log_execution


@tool
@log_execution
def handle_fetch():
    """Tool to fetch data from the vector database."""
    return "Fetched data from vector database"


tools = [handle_fetch]