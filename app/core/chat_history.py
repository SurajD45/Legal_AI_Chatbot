"""
Chat history management using in-memory storage.

For production, this should be replaced with Redis or a database.
Currently uses a simple in-memory dict for simplicity.
"""

import uuid
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from app.utils import get_logger, InvalidSessionError

logger = get_logger(__name__)


class ChatHistoryManager:
    """
    Manages conversation history for multi-turn dialogues.
    
    Note: This is an in-memory implementation.
    For production with multiple workers, use Redis.
    """
    
    def __init__(self, max_history_length: int = 10, session_ttl_hours: int = 24):
        """
        Initialize chat history manager.
        
        Args:
            max_history_length: Maximum messages to keep per session
            session_ttl_hours: Session expiry time in hours
        """
        self.sessions: Dict[str, Dict] = {}
        self.max_history_length = max_history_length
        self.session_ttl = timedelta(hours=session_ttl_hours)
        
        logger.info("chat_history_initialized",
                   max_length=max_history_length,
                   ttl_hours=session_ttl_hours)
    
    def create_session(self) -> str:
        """
        Create a new chat session.
        
        Returns:
            New session ID
        """
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "history": [],
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        
        logger.info("session_created", session_id=session_id)
        return session_id
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of message dicts with 'role' and 'content'
            
        Raises:
            InvalidSessionError: If session doesn't exist or expired
        """
        if session_id not in self.sessions:
            logger.warning("session_not_found", session_id=session_id)
            raise InvalidSessionError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        
        # Check if session expired
        if datetime.now() - session["last_activity"] > self.session_ttl:
            logger.info("session_expired", session_id=session_id)
            del self.sessions[session_id]
            raise InvalidSessionError(f"Session {session_id} expired")
        
        return session["history"]
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str
    ) -> None:
        """
        Add a message to session history.
        
        Args:
            session_id: Session identifier
            role: Message role ('user' or 'assistant')
            content: Message content
            
        Raises:
            InvalidSessionError: If session doesn't exist
        """
        if session_id not in self.sessions:
            raise InvalidSessionError(f"Session {session_id} not found")
        
        session = self.sessions[session_id]
        session["history"].append({
            "role": role,
            "content": content
        })
        
        # Trim history if too long
        if len(session["history"]) > self.max_history_length:
            session["history"] = session["history"][-self.max_history_length:]
            logger.info("history_trimmed", session_id=session_id)
        
        # Update last activity
        session["last_activity"] = datetime.now()
        
        logger.debug("message_added",
                    session_id=session_id,
                    role=role,
                    history_length=len(session["history"]))
    
    def clear_session(self, session_id: str) -> None:
        """
        Delete a session and its history.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info("session_cleared", session_id=session_id)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.
        
        Returns:
            Number of sessions removed
        """
        now = datetime.now()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session["last_activity"] > self.session_ttl
        ]
        
        for sid in expired:
            del self.sessions[sid]
        
        if expired:
            logger.info("expired_sessions_cleaned",
                       count=len(expired))
        
        return len(expired)


# Global history manager instance
_history_manager: Optional[ChatHistoryManager] = None


def get_history_manager() -> ChatHistoryManager:
    """
    Get or create the global ChatHistoryManager instance.
    
    Returns:
        ChatHistoryManager instance
    """
    global _history_manager
    if _history_manager is None:
        _history_manager = ChatHistoryManager()
    return _history_manager