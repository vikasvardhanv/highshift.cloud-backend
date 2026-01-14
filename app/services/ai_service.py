import os
import json
from typing import Optional
from openai import AsyncOpenAI
from app.models.brand_kit import BrandKit
from app.utils.logger import logger

# Initialize xAI Client
client = AsyncOpenAI(
    api_key=os.getenv("GROK_API_KEY"),
    base_url="https://api.x.ai/v1",
)

async def detect_intent(prompt: str) -> str:
    """
    Analyze the user prompt to determine if they want text, an image, or a video.
    Returns: 'text', 'image', or 'video'
    """
    try:
        response = await client.chat.completions.create(
            model="grok-2-latest",
            messages=[
                {"role": "system", "content": "You are an intent classifier. Analyze the user's prompt and determine if they want 'text' (default), an 'image' (if they ask to generate, draw, create a picture/logo/photo), or a 'video' (if they ask for a video, clip, animation). Return ONLY a JSON object: {\"intent\": \"text\"| \"image\"| \"video\"}."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return data.get("intent", "text")
    except Exception as e:
        logger.error(f"Intent detection failed: {e}")
        return "text"

async def generate_image(prompt: str):
    """
    Generate an image using Grok-2 Image model.
    """
    try:
        response = await client.images.generate(
            model="grok-2-image-1212",
            prompt=prompt,
            n=1,
            size="1024x1024",
            response_format="url"
        )
        return response.data[0].url
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise e

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
            image_url = await generate_image(topic)
            return {
                "type": "image",
                "content": image_url,
                "model": "grok-2-image-1212"
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

        response = await client.chat.completions.create(
            model="grok-2-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )

        content = response.choices[0].message.content.strip()

        return {
            "type": "text",
            "content": content,
            "model": "grok-2-latest",
            "usage": response.usage.total_tokens
        }

    except Exception as e:
        logger.error(f"AI Generation failed: {e}")
        return {
            "type": "error",
            "content": f"Failed to generate content: {str(e)}",
            "error": str(e),
            "model": "fallback"
        }
