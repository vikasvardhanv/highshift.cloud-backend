"""
Tool system for AI agent - allows AI to perform actions like scheduling posts, listing integrations, etc.
Inspired by Postiz's tool system but simplified for Social Raven's architecture.
"""
from typing import Any, Callable, Dict, List, Optional
from abc import ABC, abstractmethod
from app.utils.logger import logger
import json


class Tool(ABC):
    """Base class for AI tools."""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.description = ""
        self.parameters = {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema for AI understanding."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class SchedulePostTool(Tool):
    """Tool for scheduling social media posts."""
    
    def __init__(self):
        super().__init__()
        self.name = "schedule_post"
        self.description = "Schedule a social media post to be published at a specific time"
        self.parameters = {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content of the post"
                },
                "platform": {
                    "type": "string",
                    "description": "The social media platform (twitter, facebook, instagram, linkedin, etc.)",
                    "enum": ["twitter", "facebook", "instagram", "linkedin", "tiktok", "youtube"]
                },
                "scheduled_for": {
                    "type": "string",
                    "description": "ISO format datetime for when to schedule the post (e.g., 2024-06-10T15:30:00Z)"
                },
                "media_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of media URLs to attach to the post"
                }
            },
            "required": ["content", "platform", "scheduled_for"]
        }
    
    async def execute(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the schedule post tool."""
        try:
            from app.db.postgres import create_scheduled_post
            from datetime import datetime
            
            content = kwargs.get("content")
            platform = kwargs.get("platform")
            scheduled_for = kwargs.get("scheduled_for")
            media_urls = kwargs.get("media_urls", [])
            
            # Parse the scheduled time
            try:
                scheduled_dt = datetime.fromisoformat(scheduled_for.replace("Z", "+00:00"))
            except:
                return {
                    "success": False,
                    "error": "Invalid datetime format. Use ISO format like 2024-06-10T15:30:00Z"
                }
            
            # Get user's linked accounts for the platform
            from app.db.postgres import fetch_user_by_id
            user = await fetch_user_by_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            linked_accounts = user.get("linked_accounts", [])
            platform_accounts = [acc for acc in linked_accounts if acc.get("platform") == platform]
            
            if not platform_accounts:
                return {
                    "success": False,
                    "error": f"No linked account found for {platform}. Please connect your {platform} account first."
                }
            
            # Create the scheduled post
            account = platform_accounts[0]
            post = await create_scheduled_post(
                user_id=user_id,
                content=content,
                accounts=[{"platform": platform, "accountId": account.get("account_id")}],
                scheduled_for=scheduled_dt,
                media=media_urls
            )
            
            return {
                "success": True,
                "post_id": post.get("id"),
                "scheduled_for": scheduled_for,
                "platform": platform,
                "message": f"Post scheduled successfully for {scheduled_for}"
            }
            
        except Exception as e:
            logger.error(f"Schedule post tool failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class ListIntegrationsTool(Tool):
    """Tool for listing user's connected social media integrations."""
    
    def __init__(self):
        super().__init__()
        self.name = "list_integrations"
        self.description = "List all connected social media accounts for the user"
        self.parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the list integrations tool."""
        try:
            from app.db.postgres import fetch_user_by_id
            
            user = await fetch_user_by_id(user_id)
            if not user:
                return {"success": False, "error": "User not found"}
            
            linked_accounts = user.get("linked_accounts", [])
            
            integrations = []
            for acc in linked_accounts:
                integrations({
                    "platform": acc.get("platform"),
                    "account_id": acc.get("account_id"),
                    "username": acc.get("username", "Unknown")
                })
            
            return {
                "success": True,
                "integrations": integrations,
                "count": len(integrations)
            }
            
        except Exception as e:
            logger.error(f"List integrations tool failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class GenerateContentTool(Tool):
    """Tool for generating AI content for social media posts."""
    
    def __init__(self):
        super().__init__()
        self.name = "generate_content"
        self.description = "Generate AI-powered content for social media posts"
        self.parameters = {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic or idea for the post"
                },
                "platform": {
                    "type": "string",
                    "description": "The social media platform",
                    "enum": ["twitter", "facebook", "instagram", "linkedin", "tiktok", "youtube"]
                },
                "tone": {
                    "type": "string",
                    "description": "The tone of the content (professional, casual, humorous, etc.)"
                }
            },
            "required": ["topic", "platform"]
        }
    
    async def execute(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the generate content tool."""
        try:
            from app.services.ai_service import generate_post_content
            
            topic = kwargs.get("topic")
            platform = kwargs.get("platform")
            tone = kwargs.get("tone")
            
            result = await generate_post_content(user_id, topic, platform, tone)
            
            if result.get("type") == "error":
                return {
                    "success": False,
                    "error": result.get("content", "Generation failed")
                }
            
            return {
                "success": True,
                "content": result.get("content"),
                "model": result.get("model"),
                "platform": platform
            }
            
        except Exception as e:
            logger.error(f"Generate content tool failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class ToolService:
    """Service for managing and executing AI tools."""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register the default set of tools."""
        self.register_tool(SchedulePostTool())
        self.register_tool(ListIntegrationsTool())
        self.register_tool(GenerateContentTool())
    
    def register_tool(self, tool: Tool):
        """Register a new tool."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all tools."""
        return [tool.get_schema() for tool in self.tools.values()]
    
    async def execute_tool(self, name: str, user_id: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name."""
        tool = self.get_tool(name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{name}' not found"
            }
        
        return await tool.execute(user_id=user_id, **kwargs)


# Global tool service instance
tool_service = ToolService()
