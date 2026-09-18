import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.media import Media

async def main():
    mongo_uri = os.environ.get("MONGO_URI", "mongodb+srv://admin:V6eS3U4QW1X3@socialraven-cluster.a8j0s.mongodb.net/?retryWrites=true&w=majority&appName=socialraven-cluster")
    client = AsyncIOMotorClient(mongo_uri)
    await init_beanie(database=client.socialraven, document_models=[Media])
    
    docs = await Media.find_all().to_list()
    print(f"Total media docs: {len(docs)}")
    for doc in docs[-3:]:
        print(f"ID: {doc.media_id}, Type: {doc.file_type}, URL: {doc.get_public_url()}")

asyncio.run(main())
