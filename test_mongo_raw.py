import os
from pymongo import MongoClient

mongo_uri = os.environ.get("MONGO_URI", "mongodb+srv://admin:V6eS3U4QW1X3@socialraven-cluster.a8j0s.mongodb.net/?retryWrites=true&w=majority&appName=socialraven-cluster")
client = MongoClient(mongo_uri)
db = client.socialraven

media_docs = list(db.media.find().sort("createdAt", -1).limit(5))
for doc in media_docs:
    print(f"ID: {doc.get('media_id')}, file_type: {doc.get('fileType')}, content_type: {doc.get('contentType')}, filename: {doc.get('filename')}, cloud: {doc.get('cloudUrl')}")

