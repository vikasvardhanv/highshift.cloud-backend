"""
Memory service for AI chat bot - stores conversation context and user preferences.
Inspired by Postiz's memory system but simplified for Social Raven's architecture.
"""
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from app.db.postgres import get_pool
import logging

logger = logging.getLogger("memory_service")


class MemoryService:
    """Manages conversation memory for AI interactions."""
    
    async def get_conversation_memory(self, user_id: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve conversation memory for a user.
        Returns recent messages and context.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Check if conversation_memory table exists
            table_check = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'conversation_memory'
                )
            """)
            
            if not table_check:
                return {"messages": [], "context": {}}
            
            if conversation_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM conversation_memory
                    WHERE user_id = $1 AND conversation_id = $2
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    user_id,
                    conversation_id
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM conversation_memory
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    user_id
                )
            
            messages = [dict(row) for row in rows]
            return {
                "messages": messages,
                "context": self._extract_context(messages)
            }
    
    async def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a message to conversation memory.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Ensure table exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    conversation_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            
            await conn.execute(
                """
                INSERT INTO conversation_memory (user_id, conversation_id, role, content, metadata)
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_id,
                conversation_id,
                role,
                content,
                json.dumps(metadata or {})
            )
    
    async def clear_old_memory(self, days: int = 7) -> None:
        """Clear conversation memory older than specified days."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM conversation_memory
                WHERE created_at < now() - interval '1 day' * $1
                """,
                days
            )
    
    def _extract_context(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract context from recent messages."""
        context = {
            "recent_topics": [],
            "user_preferences": {},
            "platform_mentions": []
        }
        
        for msg in messages:
            content = msg.get("content", "").lower()
            
            # Extract platform mentions
            platforms = ["twitter", "facebook", "instagram", "linkedin", "tiktok", "youtube"]
            for platform in platforms:
                if platform in content:
                    if platform not in context["platform_mentions"]:
                        context["platform_mentions"].append(platform)
        
        return context
    
    async def get_working_memory(self, user_id: str) -> Dict[str, Any]:
        """
        Get working memory - short-term context for current session.
        Similar to Postiz's working memory with schema.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Check if working_memory table exists
            table_check = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'working_memory'
                )
            """)
            
            if not table_check:
                return {}
            
            row = await conn.fetchrow(
                """
                SELECT data FROM working_memory
                WHERE user_id = $1
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                user_id
            )
            
            if row:
                return row.get("data", {})
            return {}
    
    async def update_working_memory(self, user_id: str, data: Dict[str, Any]) -> None:
        """Update working memory for a user."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Ensure table exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS working_memory (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL UNIQUE,
                    data JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            
            await conn.execute(
                """
                INSERT INTO working_memory (user_id, data)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET
                    data = $2,
                    updated_at = now()
                """,
                user_id,
                json.dumps(data)
            )


memory_service = MemoryService()
