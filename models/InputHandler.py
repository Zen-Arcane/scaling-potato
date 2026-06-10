from pydantic import BaseModel
from typing import Optional
from uuid_utils import uuid4


class UIInput(BaseModel):
    query: str
    conversation_id: Optional[str] = None  # Session ID for multi-turn conversations
    user_id: Optional[str] = None  # User identifier
    session_name: Optional[str] = None  # Human-readable session name

    def get_or_create_conversation_id(self) -> str:
        """Get existing conversation_id or create new one."""
        if not self.conversation_id:
            self.conversation_id = uuid4().hex
        return self.conversation_id
