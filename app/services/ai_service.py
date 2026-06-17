import os
import json
from typing import Optional
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from app.db.postgres import fetch_user_by_id
from app.services.memory_service import memory_service
from app.utils.logger import logger

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
GEMINI_INTENT_MODEL = os.getenv("GEMINI_INTENT_MODEL", GEMINI_TEXT_MODEL)
GROK_TEXT_MODEL = os.getenv("GROK_TEXT_MODEL", "grok-2-latest")

PROVIDER = "gemini" if GEMINI_API_KEY else ("grok" if GROK_API_KEY else "none")
N8N_INSTANT_WEBHOOK_URL = os.getenv("N8N_INSTANT_WEBHOOK_URL", "https://wfig.app.n8n.cloud/form/1e3df4e4-a0fd-453e-9942-63ee710aeded")

# Initialize Clients
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

grok_client = None
if GROK_API_KEY:
    grok_client = AsyncOpenAI(
        api_key=GROK_API_KEY,
        base_url="https://api.x.ai/v1",
    )

logger.info(f"AI Service initialized with provider: {PROVIDER}")


def _provider_error_message(error: Exception) -> str:
    """Return a safe, actionable message without leaking provider internals."""
    raw = str(error)
    lowered = raw.lower()

    if "api_key_invalid" in lowered or "api key expired" in lowered or "api key not valid" in lowered:
        return "The AI provider API key is expired or invalid. Please update the AI API key and try again."
    if "permission" in lowered or "forbidden" in lowered or "unauthorized" in lowered:
        return "The AI provider rejected the request. Please check the configured AI API key permissions."
    if "quota" in lowered or "rate limit" in lowered or "resource_exhausted" in lowered:
        return "The AI provider quota or rate limit was reached. Please try again later or use another provider key."

    return "AI generation failed. Please try again in a moment."


async def get_brand_context(user_id: str) -> dict:
    """
    Brand settings live on the Postgres users.brand_kit JSON column.
    Generation should still work if the user has not configured Brand Kit yet.
    """
    defaults = {
        "company_name": "our brand",
        "industry": "",
        "tone": "Professional",
        "description": "Professional and engaging",
        "keywords": [],
    }

    try:
        user_row = await fetch_user_by_id(user_id)
        brand = (user_row or {}).get("brand_kit") or {}
        if not isinstance(brand, dict):
            return defaults

        keywords = brand.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [item.strip() for item in keywords.split(",") if item.strip()]

        return {
            "company_name": brand.get("company_name") or defaults["company_name"],
            "industry": brand.get("industry") or defaults["industry"],
            "tone": brand.get("tone") or defaults["tone"],
            "description": brand.get("description") or defaults["description"],
            "keywords": keywords if isinstance(keywords, list) else [],
        }
    except Exception as e:
        logger.warning(f"Brand context lookup failed for user {user_id}: {e}")
        return defaults

async def detect_intent(prompt: str) -> str:
    """
    Analyze the user prompt to determine if they want text, an image, or a video.
    Returns: 'text', 'image', or 'video'
    """
    system_instruction = "You are an intent classifier. Analyze the user's prompt and determine if they want 'text' (default), an 'image' (if they ask to generate, draw, create a picture/logo/photo), or a 'video' (if they ask for a video, clip, animation). Return ONLY a JSON object: {\"intent\": \"text\"| \"image\"| \"video\"}."
    
    try:
        if PROVIDER == "gemini" and gemini_client:
            response = await gemini_client.aio.models.generate_content(
                model=GEMINI_INTENT_MODEL,
                contents=f"{system_instruction}\nUser Prompt: {prompt}",
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            data = json.loads(response.text)
            return data.get("intent", "text")
            
        elif PROVIDER == "grok" and grok_client:
            response = await grok_client.chat.completions.create(
                model=GROK_TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return data.get("intent", "text")
            
        return "text"
        
    except Exception as e:
        logger.error(f"Intent detection failed ({PROVIDER}): {e}")
        return "text"

async def generate_image(prompt: str):
    """
    Generate an image. Currently mostly relies on Grok or Placeholder for Gemini (as standard Gemini API is text-focused).
    """
    if PROVIDER == "grok" and grok_client:
        try:
            response = await grok_client.images.generate(
                model="grok-2-image-1212",
                prompt=prompt,
                n=1,
                size="1024x1024",
                response_format="url"
            )
            return response.data[0].url
        except Exception as e:
            logger.error(f"Grok Image generation failed: {e}")
            raise e
    
    # Gemini Image Generation (Placeholder or Vertex AI logic would be needed)
    # For now, if using Gemini, we fallback to a placeholder text or error, 
    # unless we have a specific Imagen endpoint.
    # We'll return a specific placeholder URL or error.
    logger.warning("Image generation requested but Gemini standard API does not support widespread image generation in this SDK version without Vertex AI.")
    raise Exception("Image generation not supported with current AI configuration.")

async def generate_post_content(user_id: str, topic: str, platform: str, tone: Optional[str] = None):
    """
    Generate generic content based on detected intent.
    If intent is 'image', generates an image.
    If intent is 'text', generates text.
    Enhanced with memory system for context awareness.
    """
    try:
        # Get conversation memory for context
        memory = await memory_service.get_conversation_memory(user_id)
        working_memory = await memory_service.get_working_memory(user_id)
        
        # Store current topic in working memory
        await memory_service.update_working_memory(user_id, {
            **working_memory,
            "last_topic": topic,
            "last_platform": platform,
            "last_request": datetime.utcnow().isoformat()
        })
        
        # Add user message to memory
        await memory_service.add_message(
            user_id,
            "user",
            topic,
            metadata={"platform": platform, "tone": tone}
        )
        
        # 1. Detect Intent
        intent = await detect_intent(topic)
        
        if intent == "image":
            # If provider is Gemini, we might skip this unless we have a solution
            if PROVIDER == "gemini":
                # Special case: Gemini currently returns text describing the image if we ask it to generate?
                # Or we can return a text response saying "Image gen not available".
                return {
                     "type": "text",
                     "content": f"[Image Generation not supported with Gemini Free Tier yet] I cannot generate the image of '{topic}' directly, but here represents what it might look like...",
                     "model": GEMINI_TEXT_MODEL
                }

            try:
                image_url = await generate_image(topic)
                return {
                    "type": "image",
                    "content": image_url,
                    "model": "grok-2-image-1212"
                }
            except Exception as e:
                 return {
                    "type": "text",
                    "content": f"Sorry, I couldn't generate an image at this time. ({str(e)})",
                    "model": "system"
                }
        
        elif intent == "video":
            return {
                "type": "video",
                "content": "Video generation is currently not configured/supported.",
                "model": "placeholder"
            }

        # 2. Text Generation (Default)
        brand = await get_brand_context(user_id)
        brand_name = brand["company_name"]
        brand_voice = brand["description"]
        brand_tone = tone or brand["tone"]
        keyword_text = ", ".join(str(k) for k in brand["keywords"] if k)

        system_prompt = f"""
        You are an expert social media ghostwriter for {brand_name}.
        Your brand voice is: {brand_voice}
        Industry: {brand["industry"] or "general"}
        Important brand keywords: {keyword_text or "none provided"}
        
        Platform-specific instructions:
        - Twitter/X: Under 280 characters, punchy, use 1-2 hashtags.
        - LinkedIn: Professional, longer form, includes a call to action or question.
        - Instagram: Visual descriptions, emoji-friendly, hashtags at the bottom.
        - Facebook: Engaging, conversational.
        """

        user_prompt = f"Write a {platform} post about: {topic}"
        if brand_tone:
            user_prompt += f"\nUse a {brand_tone} tone."

        content = ""
        model_name = ""
        usage = 0

        if PROVIDER == "gemini":
            model_name = GEMINI_TEXT_MODEL
            try:
                response = await gemini_client.aio.models.generate_content(
                    model=model_name,
                    contents=f"{system_prompt}\n\nTask: {user_prompt}",
                )
                content = (response.text or "").strip()
                # Usage tracking not always available in same structure, ignoring for now
            except Exception as gemini_error:
                if not grok_client:
                    raise
                logger.warning(f"Gemini generation failed; falling back to Grok: {gemini_error}")
                model_name = GROK_TEXT_MODEL
                response = await grok_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7
                )
                content = response.choices[0].message.content.strip()
                usage = response.usage.total_tokens if response.usage else 0
            
        elif PROVIDER == "grok" and grok_client:
            model_name = GROK_TEXT_MODEL
            response = await grok_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            usage = response.usage.total_tokens if response.usage else 0

        else:
            return {
                "type": "error",
                "content": "No AI Provider configured (Missing GEMINI_API_KEY or GROK_API_KEY).",
                "model": "none"
            }

        # Add AI response to memory
        await memory_service.add_message(
            user_id,
            "assistant",
            content,
            metadata={"platform": platform, "model": model_name}
        )

        return {
            "type": "text",
            "content": content,
            "model": model_name,
            "usage": usage
        }

    except Exception as e:
        logger.error(f"AI Generation failed: {e}")
        return {
            "type": "error",
            "content": _provider_error_message(e),
            "error": _provider_error_message(e),
            "model": "fallback"
        }

async def trigger_instant_publish(
    email: str, topic: str, audience: str, date: str, 
    system: Optional[str] = "social_raven", api_key: Optional[str] = None,
    instagram: Optional[str] = None, facebook: Optional[str] = None,
    twitter: Optional[str] = None, linkedin: Optional[str] = None
):
    """
    Triggers the n8n Social Media Automation workflow.
    """
    import httpx
    payload = {
        "Email": email,
        "Post Topic": topic,
        "Target Audience": audience,
        "Date": date,
        "System": system,
        "ApiKey": api_key,
        "Instagram": instagram,
        "Facebook": facebook,
        "Twitter": twitter,
        "Linkedin": linkedin
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # For n8n formTrigger, sending as standard Form Data is often more reliable
            # than JSON, as the node mimics a browser form submission.
            response = await client.post(N8N_INSTANT_WEBHOOK_URL, data=payload)
            response.raise_for_status()
            
            # Since it's a form trigger/webhook, it might return a success message or JSON
            return {
                "status": "success",
                "message": "Instant publish workflow triggered successfully.",
                "n8n_response": response.text[:200]
            }
    except Exception as e:
        logger.error(f"N8N Trigger failed: {e}")
        return {
            "status": "error",
            "message": f"Failed to trigger automation: {str(e)}"
        }
