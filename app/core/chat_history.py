"""
Chat history management using Redis for persistence.

Multi-user, ownership-enforced, auth-ready design.
"""

import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime

import redis
from redis.exceptions import RedisError

from app.config import settings
from app.utils import get_logger, InvalidSessionError

logger = get_logger(__name__)


class ChatHistoryManager:
    def __init__(
        self,
        max_history_length: int = 10,
        session_ttl_hours: int = 24,
    ):
        self.max_history_length = max_history_length
        self.session_ttl_seconds = session_ttl_hours * 3600

        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self.redis_client.ping()

            logger.info(
                "redis_connected",
                redis_url="****",
                ttl_hours=session_ttl_hours,
            )

        except RedisError as e:
            logger.error("redis_connection_failed", error=str(e))
            raise RuntimeError(f"Redis unavailable: {e}")

    # ------------------------
    # Helpers
    # ------------------------
    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        return f"user_sessions:{user_id}"

    # ------------------------
    # Session lifecycle
    # ------------------------
    def create_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())

        session_data = {
            "user_id": user_id,
            "history": [],
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
        }

        try:
            pipe = self.redis_client.pipeline()
            pipe.setex(
                self._session_key(session_id),
                self.session_ttl_seconds,
                json.dumps(session_data),
            )
            pipe.sadd(self._user_sessions_key(user_id), session_id)
            pipe.execute()

            logger.info(
                "session_created",
                user_id=user_id,
                session_id=session_id,
            )
            return session_id

        except RedisError as e:
            logger.error("session_creation_failed", error=str(e))
            raise InvalidSessionError("Failed to create session")

    def get_history(self, user_id: str, session_id: str) -> List[Dict[str, str]]:
        try:
            raw = self.redis_client.get(self._session_key(session_id))
            if raw is None:
                raise InvalidSessionError("Session not found or expired")

            session_data = json.loads(raw)

            if session_data["user_id"] != user_id:
                raise InvalidSessionError("Session does not belong to user")

            return session_data["history"]

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("get_history_failed", error=str(e))
            raise InvalidSessionError("Failed to retrieve session history")

    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        try:
            key = self._session_key(session_id)
            raw = self.redis_client.get(key)

            if raw is None:
                raise InvalidSessionError("Session not found or expired")

            session_data = json.loads(raw)

            if session_data["user_id"] != user_id:
                raise InvalidSessionError("Session does not belong to user")

            session_data["history"].append(
                {"role": role, "content": content}
            )

            if len(session_data["history"]) > self.max_history_length:
                session_data["history"] = session_data["history"][
                    -self.max_history_length :
                ]

            session_data["last_activity"] = datetime.now().isoformat()

            self.redis_client.setex(
                key,
                self.session_ttl_seconds,
                json.dumps(session_data),
            )

        except (RedisError, json.JSONDecodeError) as e:
            logger.error("add_message_failed", error=str(e))
            raise InvalidSessionError("Failed to update session")

    def list_user_sessions(self, user_id: str) -> List[str]:
        try:
            return list(
                self.redis_client.smembers(
                    self._user_sessions_key(user_id)
                )
            )
        except RedisError:
            return []

    # ------------------------
    # NEW: restore latest session
    # ------------------------
    def get_latest_session(self, user_id: str) -> Optional[Dict]:
        try:
            session_ids = self.list_user_sessions(user_id)
            if not session_ids:
                return None

            latest_session = None
            latest_time = None

            for session_id in session_ids:
                raw = self.redis_client.get(self._session_key(session_id))
                if not raw:
                    continue

                data = json.loads(raw)
                last_activity = data.get("last_activity")

                if last_activity and (
                    latest_time is None or last_activity > latest_time
                ):
                    latest_time = last_activity
                    latest_session = {
                        "session_id": session_id,
                        "history": data.get("history", []),
                    }

            return latest_session

        except Exception as e:
            logger.error("get_latest_session_failed", error=str(e))
            return None


# Singleton
_history_manager: Optional[ChatHistoryManager] = None


def get_history_manager() -> ChatHistoryManager:
    global _history_manager
    if _history_manager is None:
        _history_manager = ChatHistoryManager()
    return _history_manager
