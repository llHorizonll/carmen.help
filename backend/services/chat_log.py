"""
Chat Log Service

Stores and retrieves chat conversation history.
Uses SQLite for simplicity and portability.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Represents a single chat message."""
    id: str
    session_id: str
    role: str  # 'user' or 'assistant'
    content: str
    sources: Optional[List[Dict]] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class ChatSession:
    """Represents a chat session."""
    id: str
    user_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    metadata: Optional[Dict] = None

    def __post_init__(self):
        now = datetime.utcnow().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


class ChatLogService:
    """Service for storing and retrieving chat logs."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the chat log service.

        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "chat_logs.db")

        self.db_path = db_path
        self._ensure_db_exists()
        self._init_tables()

    def _ensure_db_exists(self):
        """Ensure the database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """Initialize database tables."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON chat_messages(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user
                ON chat_sessions(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON chat_messages(timestamp)
            """)

            conn.commit()
            logger.info("Chat log database initialized")
        finally:
            conn.close()

    def create_session(
        self,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            user_id: Optional user identifier
            metadata: Optional session metadata

        Returns:
            Created ChatSession
        """
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            metadata=metadata,
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_sessions (id, user_id, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session.id,
                session.user_id,
                session.created_at,
                session.updated_at,
                json.dumps(session.metadata) if session.metadata else None,
            ))
            conn.commit()
            logger.debug(f"Created session: {session.id}")
        finally:
            conn.close()

        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get a chat session by ID.

        Args:
            session_id: Session ID

        Returns:
            ChatSession or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM chat_sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            if row:
                return ChatSession(
                    id=row["id"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                )
            return None
        finally:
            conn.close()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[Dict]] = None,
    ) -> ChatMessage:
        """
        Add a message to a session.

        Args:
            session_id: Session ID
            role: Message role ('user' or 'assistant')
            content: Message content
            sources: Optional list of source documents

        Returns:
            Created ChatMessage
        """
        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Insert message
            cursor.execute("""
                INSERT INTO chat_messages (id, session_id, role, content, sources, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                message.id,
                message.session_id,
                message.role,
                message.content,
                json.dumps(message.sources) if message.sources else None,
                message.timestamp,
            ))

            # Update session timestamp
            cursor.execute("""
                UPDATE chat_sessions SET updated_at = ? WHERE id = ?
            """, (message.timestamp, session_id))

            conn.commit()
            logger.debug(f"Added message to session {session_id}")
        finally:
            conn.close()

        return message

    def get_session_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[ChatMessage]:
        """
        Get all messages for a session.

        Args:
            session_id: Session ID
            limit: Optional limit on number of messages

        Returns:
            List of ChatMessage objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            query = """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """
            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, (session_id,))
            rows = cursor.fetchall()

            messages = []
            for row in rows:
                messages.append(ChatMessage(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    sources=json.loads(row["sources"]) if row["sources"] else None,
                    timestamp=row["timestamp"],
                ))

            return messages
        finally:
            conn.close()

    def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[ChatSession]:
        """
        Get all sessions for a user.

        Args:
            user_id: User ID
            limit: Maximum number of sessions to return

        Returns:
            List of ChatSession objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM chat_sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()

            sessions = []
            for row in rows:
                sessions.append(ChatSession(
                    id=row["id"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                ))

            return sessions
        finally:
            conn.close()

    def get_recent_sessions(self, limit: int = 100) -> List[ChatSession]:
        """
        Get recent chat sessions.

        Args:
            limit: Maximum number of sessions

        Returns:
            List of ChatSession objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM chat_sessions
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()

            sessions = []
            for row in rows:
                sessions.append(ChatSession(
                    id=row["id"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                ))

            return sessions
        finally:
            conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Delete messages first
            cursor.execute(
                "DELETE FROM chat_messages WHERE session_id = ?",
                (session_id,)
            )

            # Delete session
            cursor.execute(
                "DELETE FROM chat_sessions WHERE id = ?",
                (session_id,)
            )

            deleted = cursor.rowcount > 0
            conn.commit()

            if deleted:
                logger.info(f"Deleted session: {session_id}")

            return deleted
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get chat log statistics.

        Returns:
            Dictionary with stats
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total sessions
            cursor.execute("SELECT COUNT(*) FROM chat_sessions")
            total_sessions = cursor.fetchone()[0]

            # Total messages
            cursor.execute("SELECT COUNT(*) FROM chat_messages")
            total_messages = cursor.fetchone()[0]

            # Messages by role
            cursor.execute("""
                SELECT role, COUNT(*) as count
                FROM chat_messages
                GROUP BY role
            """)
            messages_by_role = {row["role"]: row["count"] for row in cursor.fetchall()}

            # Sessions today
            today = datetime.utcnow().date().isoformat()
            cursor.execute("""
                SELECT COUNT(*) FROM chat_sessions
                WHERE created_at LIKE ?
            """, (f"{today}%",))
            sessions_today = cursor.fetchone()[0]

            return {
                "total_sessions": total_sessions,
                "total_messages": total_messages,
                "messages_by_role": messages_by_role,
                "sessions_today": sessions_today,
                "db_path": self.db_path,
            }
        finally:
            conn.close()


# Singleton instance
_chat_log_service: Optional[ChatLogService] = None


def get_chat_log_service() -> ChatLogService:
    """Get or create the chat log service singleton."""
    global _chat_log_service
    if _chat_log_service is None:
        _chat_log_service = ChatLogService()
    return _chat_log_service
