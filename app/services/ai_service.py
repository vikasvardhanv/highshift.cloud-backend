import os
from typing import Optional
from openai import AsyncOpenAI
from app.models.brand_kit import BrandKit
from app.utils.logger import logger

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_post_content(user_id: str, topic: str, platform: str, tone: Optional[str] = None):
    """
    Generate social media content using OpenAI, incorporating Brand Kit context.
    """
    try:
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
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )

        content = response.choices[0].message.content.strip()

        return {
            "content": content,
            "model": "gpt-4o",
            "usage": response.usage.total_tokens
        }

    except Exception as e:
        logger.error(f"AI Generation failed: {e}")
        # Fallback to a basic template if OpenAI fails
        return {
            "content": f"Excited to share about {topic}! 🚀 #{platform}",
            "error": str(e),
            "model": "fallback"
        }
