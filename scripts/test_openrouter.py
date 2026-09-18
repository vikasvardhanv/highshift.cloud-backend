import asyncio
import os
import sys

sys.path.append(os.getcwd())
os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-999fbf6e15efb7016d-d50a2b7023e454ebfd-f05e73780a02d5b85716fadb955b"
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/socialraven"

from app.services.ai_service import detect_intent, openrouter_client, PROVIDER, OPENROUTER_TEXT_MODEL

async def main():
    print("Provider:", PROVIDER)
    
    # Test intent
    intent = await detect_intent("Write a post about AI")
    print("Detected intent:", intent)

    # Test direct completion
    response = await openrouter_client.chat.completions.create(
        model=OPENROUTER_TEXT_MODEL,
        messages=[
            {"role": "user", "content": "Write a short 1-sentence tweet about AI."}
        ]
    )
    print("Response:", response.choices[0].message.content)

asyncio.run(main())
