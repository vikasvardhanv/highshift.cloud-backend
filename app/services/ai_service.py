import os
import json
from typing import Optional
import google.generativeai as genai
from openai import AsyncOpenAI
from app.models.brand_kit import BrandKit
from app.utils.logger import logger

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")

PROVIDER = "gemini" if GEMINI_API_KEY else ("grok" if GROK_API_KEY else "none")

# Initialize Clients
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

grok_client = None
if GROK_API_KEY:
    grok_client = AsyncOpenAI(
        api_key=GROK_API_KEY,
        base_url="https://api.x.ai/v1",
    )

logger.info(f"AI Service initialized with provider: {PROVIDER}")

async def detect_intent(prompt: str) -> str:
    """
    Analyze the user prompt to determine if they want text, an image, or a video.
    Returns: 'text', 'image', or 'video'
    """
    system_instruction = "You are an intent classifier. Analyze the user's prompt and determine if they want 'text' (default), an 'image' (if they ask to generate, draw, create a picture/logo/photo), or a 'video' (if they ask for a video, clip, animation). Return ONLY a JSON object: {\"intent\": \"text\"| \"image\"| \"video\"}."
    
    try:
        if PROVIDER == "gemini":
            model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
            response = await model.generate_content_async(
                f"{system_instruction}\nUser Prompt: {prompt}"
            )
            data = json.loads(response.text)
            return data.get("intent", "text")
            
        elif PROVIDER == "grok" and grok_client:
            response = await grok_client.chat.completions.create(
                model="grok-2-latest",
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
    """
    try:
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
                     "model": "gemini-1.5-flash"
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
        # Fetch Brand Kit
        brand = await BrandKit.find_one({"userId": user_id})
        brand_voice = brand.voice_description if brand else "Professional and engaging"
        brand_name = brand.name if brand else "our brand"

        system_prompt = f"""
        You are an expert social media ghostwriter for {brand_name}.
        Your brand voice is: {brand_voice}
        
        Platform-specific instructions:
        - Twitter/X: Under 280 characters, punchy, use 1-2 hashtags.
        - LinkedIn: Professional, longer form, includes a call to action or question.
        - Instagram: Visual descriptions, emoji-friendly, hashtags at the bottom.
        - Facebook: Engaging, conversational.
        """

        user_prompt = f"Write a {platform} post about: {topic}"
        if tone:
            user_prompt += f"\nUse a {tone} tone."

        content = ""
        model_name = ""
        usage = 0

        if PROVIDER == "gemini":
            model_name = "gemini-1.5-flash"
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(
                f"{system_prompt}\n\nTask: {user_prompt}"
            )
            content = response.text.strip()
            # Usage tracking not always available in same structure, ignoring for now
            
        elif PROVIDER == "grok" and grok_client:
            model_name = "grok-2-latest"
            response = await grok_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7
            )
            content = response.choices[0].message.content.strip()
            usage = response.usage.total_tokens

        else:
            return {
                "type": "error",
                "content": "No AI Provider configured (Missing GEMINI_API_KEY or GROK_API_KEY).",
                "model": "none"
            }

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
            "content": f"Failed to generate content: {str(e)}",
            "error": str(e),
            "model": "fallback"
        }
