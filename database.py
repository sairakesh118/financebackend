
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URI = os.getenv("MONGO_URI")

client = AsyncIOMotorClient(MONGO_URI)

db = client["finance"]
accounts_collection = db["accounts"]
transactions_collection = db["transactions"]