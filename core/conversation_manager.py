"""
Conversation memory management with SQLite persistence.
Handles multi-turn conversations, context variables, and conversation history.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("CONVERSATION_DB_PATH", "data-source/conversations.db")
CONTEXT_CACHE_SIZE = 50  # Keep last 50 conversations in memory


@dataclass
class Message:
    """Represents a single message in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    metadata: Dict[str, Any] = None

    def to_dict(self):
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata or {}
        }


@dataclass
class ContextVariables:
    """Shared context variables for a conversation."""
    conversation_id: str
    user_id: Optional[str] = None
    session_name: Optional[str] = None
    custom_vars: Dict[str, Any] = None
    created_at: str = None
    updated_at: str = None

    def __post_init__(self):
        if self.custom_vars is None:
            self.custom_vars = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "session_name": self.session_name,
            "custom_vars": self.custom_vars,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def get_var(self, key: str, default=None):
        return self.custom_vars.get(key, default)

    def set_var(self, key: str, value: Any):
        self.custom_vars[key] = value
        self.updated_at = datetime.utcnow().isoformat()


class ConversationDatabase:
    """SQLite database layer for conversation storage."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.local = threading.local()
        self._ensure_db_exists()

    def _get_connection(self):
        """Get thread-local database connection."""
        if not hasattr(self.local, "connection"):
            self.local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=10
            )
            self.local.connection.row_factory = sqlite3.Row
        return self.local.connection

    def _ensure_db_exists(self):
        """Create necessary tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        
        conn = self._get_connection()
        cursor = conn.cursor()

        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                session_name TEXT,
                created_at TEXT,
                updated_at TEXT,
                archived INTEGER DEFAULT 0
            )
        """)

        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT,
                metadata TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)

        # Context variables table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS context_variables (
                conversation_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)

        # Index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_user 
            ON conversations(user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_conversation 
            ON messages(conversation_id)
        """)

        conn.commit()

    def create_conversation(
        self,
        conversation_id: str,
        user_id: Optional[str] = None,
        session_name: Optional[str] = None
    ) -> bool:
        """Create a new conversation."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            cursor.execute("""
                INSERT INTO conversations (id, user_id, session_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, user_id, session_name, now, now))

            # Initialize context variables
            cursor.execute("""
                INSERT INTO context_variables (conversation_id, data, updated_at)
                VALUES (?, ?, ?)
            """, (conversation_id, "{}", now))

            conn.commit()
            logger.info(f"Created conversation: {conversation_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Conversation {conversation_id} already exists")
            return False
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            return False

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Add a message to a conversation."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            cursor.execute("""
                INSERT INTO messages (conversation_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, role, content, now, json.dumps(metadata or {})))

            # Update conversation timestamp
            cursor.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id)
            )

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return False

    def get_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Message]:
        """Retrieve messages from a conversation."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT role, content, timestamp, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
            """, (conversation_id, limit, offset))

            messages = []
            for row in cursor.fetchall():
                msg = Message(
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"] or "{}")
                )
                messages.append(msg)

            return messages
        except Exception as e:
            logger.error(f"Error retrieving messages: {e}")
            return []

    def update_context_variables(
        self,
        conversation_id: str,
        variables: Dict[str, Any]
    ) -> bool:
        """Update context variables for a conversation."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            cursor.execute("""
                UPDATE context_variables
                SET data = ?, updated_at = ?
                WHERE conversation_id = ?
            """, (json.dumps(variables), now, conversation_id))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating context variables: {e}")
            return False

    def get_context_variables(self, conversation_id: str) -> Dict[str, Any]:
        """Retrieve context variables for a conversation."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT data FROM context_variables
                WHERE conversation_id = ?
            """, (conversation_id,))

            row = cursor.fetchone()
            if row:
                return json.loads(row["data"])
            return {}
        except Exception as e:
            logger.error(f"Error retrieving context variables: {e}")
            return {}

    def get_conversation_info(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation metadata."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, user_id, session_name, created_at, updated_at
                FROM conversations
                WHERE id = ? AND archived = 0
            """, (conversation_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Error retrieving conversation info: {e}")
            return None

    def list_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """List conversations for a user."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if user_id:
                cursor.execute("""
                    SELECT id, user_id, session_name, created_at, updated_at
                    FROM conversations
                    WHERE user_id = ? AND archived = 0
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT id, user_id, session_name, created_at, updated_at
                    FROM conversations
                    WHERE archived = 0
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []

    def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE conversations
                SET archived = 1
                WHERE id = ?
            """, (conversation_id,))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error archiving conversation: {e}")
            return False


class ConversationManager:
    """
    High-level conversation management with in-memory cache and persistence.
    Manages multi-turn conversations, context, and history.
    """

    def __init__(self):
        self.db = ConversationDatabase()
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = threading.RLock()

    def start_conversation(
        self,
        conversation_id: str,
        user_id: Optional[str] = None,
        session_name: Optional[str] = None
    ) -> bool:
        """Start a new conversation."""
        with self.cache_lock:
            success = self.db.create_conversation(
                conversation_id,
                user_id,
                session_name
            )

            if success:
                self.memory_cache[conversation_id] = {
                    "messages": [],
                    "context_vars": ContextVariables(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        session_name=session_name
                    ),
                    "last_accessed": datetime.utcnow()
                }
            return success

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Add message to conversation."""
        with self.cache_lock:
            # Ensure conversation exists
            if conversation_id not in self.memory_cache:
                info = self.db.get_conversation_info(conversation_id)
                if not info:
                    logger.warning(f"Conversation {conversation_id} not found")
                    return False
                self._load_conversation_to_cache(conversation_id)

            # Add to DB
            success = self.db.add_message(
                conversation_id,
                role,
                content,
                metadata
            )

            # Update cache
            if success and conversation_id in self.memory_cache:
                self.memory_cache[conversation_id]["messages"].append(
                    Message(role, content, datetime.utcnow().isoformat(), metadata)
                )
                self.memory_cache[conversation_id]["last_accessed"] = datetime.utcnow()

            return success

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get conversation history formatted for LLM input.
        Returns messages in format ready for langchain/langgraph.
        """
        with self.cache_lock:
            # Check cache first
            if conversation_id in self.memory_cache:
                messages = self.memory_cache[conversation_id]["messages"]
            else:
                # Load from DB
                messages = self.db.get_messages(conversation_id, limit)

            # Format for langchain
            return [(msg.role, msg.content) for msg in messages]

    def get_full_context(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get full conversation context including history and variables.
        Useful for the LLM to understand the complete context.
        """
        with self.cache_lock:
            history = self.get_conversation_history(conversation_id)
            context_vars = self.get_context_variables(conversation_id)

            return {
                "conversation_id": conversation_id,
                "history": history,
                "context_variables": context_vars,
                "message_count": len(history)
            }

    def get_context_variables(self, conversation_id: str) -> Dict[str, Any]:
        """Get context variables for a conversation."""
        with self.cache_lock:
            if conversation_id in self.memory_cache:
                return self.memory_cache[conversation_id]["context_vars"].custom_vars

            # Load from DB
            data = self.db.get_context_variables(conversation_id)
            if conversation_id in self.memory_cache:
                self.memory_cache[conversation_id]["context_vars"].custom_vars = data
            return data

    def set_context_variable(
        self,
        conversation_id: str,
        key: str,
        value: Any
    ) -> bool:
        """Set a context variable."""
        with self.cache_lock:
            if conversation_id not in self.memory_cache:
                info = self.db.get_conversation_info(conversation_id)
                if not info:
                    return False
                self._load_conversation_to_cache(conversation_id)

            # Update in-memory
            self.memory_cache[conversation_id]["context_vars"].set_var(key, value)

            # Persist to DB
            updated_vars = self.memory_cache[conversation_id]["context_vars"].custom_vars
            return self.db.update_context_variables(conversation_id, updated_vars)

    def get_context_variable(self, conversation_id: str, key: str, default=None):
        """Get a specific context variable."""
        variables = self.get_context_variables(conversation_id)
        return variables.get(key, default)

    def list_conversations(self, user_id: Optional[str] = None) -> List[Dict]:
        """List conversations."""
        return self.db.list_conversations(user_id)

    def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation."""
        with self.cache_lock:
            self.memory_cache.pop(conversation_id, None)
            return self.db.archive_conversation(conversation_id)

    def _load_conversation_to_cache(self, conversation_id: str):
        """Load a conversation from DB into memory cache."""
        info = self.db.get_conversation_info(conversation_id)
        if not info:
            return False

        messages = self.db.get_messages(conversation_id, limit=1000)
        context_vars_data = self.db.get_context_variables(conversation_id)

        context_vars = ContextVariables(
            conversation_id=conversation_id,
            user_id=info.get("user_id"),
            session_name=info.get("session_name")
        )
        context_vars.custom_vars = context_vars_data

        self.memory_cache[conversation_id] = {
            "messages": messages,
            "context_vars": context_vars,
            "last_accessed": datetime.utcnow()
        }

        # Clean old cache entries if needed
        if len(self.memory_cache) > CONTEXT_CACHE_SIZE:
            self._cleanup_cache()

        return True

    def _cleanup_cache(self):
        """Remove least recently accessed conversations from cache."""
        if len(self.memory_cache) <= CONTEXT_CACHE_SIZE:
            return

        # Sort by last_accessed and remove oldest
        sorted_convs = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1]["last_accessed"]
        )
        remove_count = len(sorted_convs) - CONTEXT_CACHE_SIZE
        for conv_id, _ in sorted_convs[:remove_count]:
            self.memory_cache.pop(conv_id, None)


# Global instance
conversation_manager = ConversationManager()
